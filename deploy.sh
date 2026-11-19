#!/usr/bin/env bash
# SimplyFy update on the VPS: pull, install, self-check, restart, health.
# Run on the VPS: bash /opt/simplyfile/deploy.sh    From Windows: Deploy-To-VPS.cmd
# Stops BEFORE the restart if the pull, the install or the self-check fails, so the running site is never
# replaced by code that does not pass.
set -euo pipefail
cd "$(dirname "$0")"
[ -n "${DEPLOY_PULLED:-}" ] || echo "=== SimplyFy deploy on $(hostname) in $(pwd) ==="
SERVICE=${SF_SERVICE:-simplyfile}
# The port the service really listens on (VPS Console's New site writes Environment=PORT= into the unit), else 8830.
PORT=${SF_PORT:-$(grep -oP '^Environment=PORT=\K[0-9]+' "/etc/systemd/system/$SERVICE.service" 2>/dev/null || echo 8830)}

before=$(git rev-parse --short HEAD)
if [ -z "${DEPLOY_PULLED:-}" ]; then
  git pull --ff-only
  # This script may have just changed: bash is still reading the old copy, so run the new one from the top
  # (2026-10-05: a pulled fix to this file failed its own first run).
  DEPLOY_PULLED=$before exec bash "$0" "$@"
fi
before=$DEPLOY_PULLED
after=$(git rev-parse --short HEAD)
echo "code: $before -> $after"

# 2026-11-18 gap audit C1-18: packages, the self-check and the recorder run as the service's own user (the unit's User=), never
# root - a package's install script or a test then cannot touch the server. Root keeps only the pull above, the one sign-in
# drop-in and the restart below. A unit still running as root says so loudly (switch over: DEPLOY.md "Switch-over").
APP_USER=$(grep -oP '^User=\K\S+' "/etc/systemd/system/$SERVICE.service" 2>/dev/null || true)
as_app() { if [ "$(id -u)" = 0 ] && [ -n "$APP_USER" ] && [ "$APP_USER" != root ]; then runuser -u "$APP_USER" -- "$@"; else "$@"; fi; }
if [ -z "$APP_USER" ] || [ "$APP_USER" = root ]; then
  echo "WARNING: $SERVICE runs as root - packages and the self-check run as root too. Switch over: DEPLOY.md \"Switch-over\"."
fi
# 2026-11-12 (VS standards): the lock is installed exactly - every file checked by its hash (chip deps.lock). No lock, no deploy:
# an unhashed requirements.txt is never installed on a server (2026-11-18 C1-18).
[ -f requirements.lock ] || { echo "DEPLOY STOPPED - no requirements.lock (python tools/lock_deps.py, commit it)"; exit 1; }
as_app .venv/bin/pip install -q --require-hashes --no-deps -r requirements.lock
as_app .venv/bin/python selfcheck.py
# 2026-11-14 owner: Tour Video records on the server - its own Python (.venv/tour: Playwright + edge-tts), chip tourvideo.settings
as_app .venv/bin/python -c "import store, tourvideo; print(tourvideo.ensure_recorder())" || echo "tour recorder: not installed (Tour Video cannot record here)"

systemctl restart "$SERVICE"
for i in $(seq 1 30); do
  if curl -sf -o /dev/null "http://127.0.0.1:$PORT/health"; then
    echo "DEPLOY OK - $after is live on port $PORT"
    # the product demos (deploy/demo/setup.sh) run the same code: restart them onto it too
    for d in $(systemctl list-units --type=service --all --no-legend 'simplyfile-demo-*' | awk '{print $1}'); do
      systemctl restart "$d" && echo "restarted demo $d"
    done
    exit 0
  fi
  sleep 1
done
echo "HEALTH CHECK FAILED - $SERVICE did not answer on port $PORT. Its log:"
journalctl -u "$SERVICE" -n 40 --no-pager
exit 1
