#!/usr/bin/env bash
# One-time setup of a product's demo on the VPS (run as root). Safe to run again.
#   bash /opt/simplyfile/deploy/demo/setup.sh tax 8840 /root/demo-tax-snapshot.tgz
# Makes /opt/simplyfile-demo/<name>/{snapshot,data}, the service simplyfile-demo-<name> (same code as /opt/simplyfile, demo mode,
# its own data, port and cookie), copies prod's mail settings so codes can be sent, and the nightly reset (03:00 IST).
set -euo pipefail
NAME=${1:?demo name, e.g. tax}
PORT=${2:?port, e.g. 8840}
TGZ=${3:-}
ROOT=/opt/simplyfile-demo/$NAME
SERVICE=simplyfile-demo-$NAME
CODE=/opt/simplyfile
RUNAS=$(systemctl show -p User --value simplyfile); RUNAS=${RUNAS:-root}

mkdir -p "$ROOT"
if [ -n "$TGZ" ]; then
  rm -rf "$ROOT/snapshot" && mkdir -p "$ROOT/snapshot"
  tar -xzf "$TGZ" -C "$ROOT/snapshot"
  echo "snapshot: $(du -sh "$ROOT/snapshot" | cut -f1)"
fi
[ -d "$ROOT/data" ] || cp -a "$ROOT/snapshot" "$ROOT/data"
# the codes go out through the same mail account as prod
PROD_DATA=$(systemctl show -p Environment --value simplyfile | tr ' ' '\n' | sed -n 's/^\(PORTAL\|TV\)_DATA=//p' | head -1)
PROD_DATA=${PROD_DATA:-$CODE/data}
[ -f "$PROD_DATA/smtp.json" ] && cp -a "$PROD_DATA/smtp.json" "$ROOT/data/smtp.json" && echo "mail settings copied from prod"
chown -R "$RUNAS":"$RUNAS" "$ROOT"

cat > "/etc/systemd/system/$SERVICE.service" <<UNIT
[Unit]
Description=SimplyFile demo ($NAME) - demo.valuestream.in/$NAME
After=network.target

[Service]
User=$RUNAS
WorkingDirectory=$CODE
Environment=PORTAL_DEMO=1
Environment=PORTAL_BASE=/$NAME
Environment=PORTAL_DATA=$ROOT/data
Environment=PORTAL_COOKIE=sfdemo_$NAME
Environment=PORTAL_HTTPS=1
Environment=PORTAL_TRUSTED_PROXY=nginx
ExecStart=$CODE/.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port $PORT
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now "$SERVICE"

echo "30 21 * * * root bash $CODE/deploy/demo/reset.sh $NAME >> /var/log/simplyfile-demo-$NAME.log 2>&1" > "/etc/cron.d/simplyfile-demo-$NAME"
for i in $(seq 1 30); do
  curl -sf -o /dev/null "http://127.0.0.1:$PORT/$NAME/health" && { echo "SETUP OK - $SERVICE answers on port $PORT"; exit 0; }
  sleep 1
done
echo "$SERVICE did not answer on port $PORT. Its log:"; journalctl -u "$SERVICE" -n 40 --no-pager; exit 1
