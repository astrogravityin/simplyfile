#!/usr/bin/env bash
# SimplyFile update on the VPS: pull, install, self-check, restart, health.
# Run on the VPS: bash /opt/simplyfile/deploy.sh    From Windows: Deploy-To-VPS.cmd
# Stops BEFORE the restart if the pull, the install or the self-check fails, so the running site is never
# replaced by code that does not pass.
set -euo pipefail
cd "$(dirname "$0")"
[ -n "${DEPLOY_PULLED:-}" ] || echo "=== SimplyFile deploy on $(hostname) in $(pwd) ==="
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

.venv/bin/pip install -q -r requirements.txt
.venv/bin/python selfcheck.py

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
