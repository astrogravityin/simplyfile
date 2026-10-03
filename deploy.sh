#!/usr/bin/env bash
# SimplyFile update on the VPS: pull, install, self-check, restart, health.
# Run on the VPS: bash /opt/simplyfile/deploy.sh    From Windows: Deploy-To-VPS.cmd
# Stops BEFORE the restart if the pull, the install or the self-check fails, so the running site is never
# replaced by code that does not pass.
set -euo pipefail
cd "$(dirname "$0")"
SERVICE=${SF_SERVICE:-simplyfile}
PORT=${SF_PORT:-8830}

before=$(git rev-parse --short HEAD)
git pull --ff-only
after=$(git rev-parse --short HEAD)
echo "code: $before -> $after"

.venv/bin/pip install -q -r requirements.txt
.venv/bin/python selfcheck.py

systemctl restart "$SERVICE"
for i in $(seq 1 30); do
  if curl -sf -o /dev/null "http://127.0.0.1:$PORT/health"; then
    echo "DEPLOY OK - $after is live on port $PORT"
    exit 0
  fi
  sleep 1
done
echo "HEALTH CHECK FAILED - $SERVICE did not answer on port $PORT. Its log:"
journalctl -u "$SERVICE" -n 40 --no-pager
exit 1
