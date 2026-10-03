#!/usr/bin/env bash
# SimplyFile update on the VPS: pull, install, self-check, restart, health. Run: bash /opt/simplyfile/deploy.sh
set -euo pipefail
cd "$(dirname "$0")"
git pull --ff-only
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python selfcheck.py
systemctl restart simplyfile
sleep 3
curl -sf http://127.0.0.1:8830/health >/dev/null && echo "DEPLOY OK - $(git rev-parse --short HEAD)" || { echo "HEALTH CHECK FAILED - journalctl -u simplyfile -n 50"; exit 1; }
