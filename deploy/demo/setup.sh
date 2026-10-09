#!/usr/bin/env bash
# One-time setup of a product's demo on the VPS (run as root). Safe to run again.
#   bash /opt/simplyfile/deploy/demo/setup.sh tax 8840 /root/demo-tax-snapshot.tgz            (SimplyFile)
#   bash /opt/justify/deploy/demo/setup.sh legal 8841 /root/demo-legal-snapshot.tgz justify    (another product: its app name 4th)
# Makes /opt/<app>-demo/<name>/{snapshot,data}, the service <app>-demo-<name> (same code as /opt/<app>, demo mode,
# its own data, port and cookie), copies prod's mail settings so codes can be sent, and the nightly reset (03:00 IST).
set -euo pipefail
NAME=${1:?demo name, e.g. tax}
PORT=${2:?port, e.g. 8840}
TGZ=${3:-}
APP=${4:-${PORTAL_APP:-$(basename "$(cd "$(dirname "$0")/../.." && pwd)")}}   # the product: its folder /opt/<app> and its prod service <app> - default: the folder this script ships in
ROOT=/opt/$APP-demo/$NAME
SERVICE=$APP-demo-$NAME
CODE=/opt/$APP
RUNAS=$(systemctl show -p User --value "$APP"); RUNAS=${RUNAS:-root}

mkdir -p "$ROOT"
if [ -n "$TGZ" ]; then
  rm -rf "$ROOT/snapshot" && mkdir -p "$ROOT/snapshot"
  tar -xzf "$TGZ" -C "$ROOT/snapshot"
  echo "snapshot: $(du -sh "$ROOT/snapshot" | cut -f1)"
fi
[ -d "$ROOT/data" ] || cp -a "$ROOT/snapshot" "$ROOT/data"
# the codes go out through the same mail account as prod
PROD_DATA=$(systemctl show -p Environment --value "$APP" | tr ' ' '\n' | sed -n 's/^\(PORTAL\|TV\)_DATA=//p' | head -1)
PROD_DATA=${PROD_DATA:-$CODE/data}
# prod has none yet (a new domain): borrow any sibling site's, so the demo can still send codes (2026-10-08)
MAIL="$PROD_DATA/smtp.json"; [ -f "$MAIL" ] || MAIL=$(ls /opt/*/data/smtp.json 2>/dev/null | head -1 || true)
[ -n "$MAIL" ] && [ -f "$MAIL" ] && cp -a "$MAIL" "$ROOT/data/smtp.json" && echo "mail settings copied from $MAIL"
[ -f "$ROOT/data/smtp.json" ] || echo "WARNING: no mail settings anywhere - the demo cannot send sign-in codes"
chown -R "$RUNAS":"$RUNAS" "$ROOT"
# who owns every demo: set once with  PORTAL_DEMO_OWNER=<email> in /etc/valuestream/demo.env (setup keeps it)
mkdir -p /etc/valuestream && touch /etc/valuestream/demo.env && chmod 600 /etc/valuestream/demo.env

cat > "/etc/systemd/system/$SERVICE.service" <<UNIT
[Unit]
Description=$APP demo ($NAME) - demo.valuestream.in/$NAME
After=network.target

[Service]
User=$RUNAS
WorkingDirectory=$CODE
Environment=PORTAL_DEMO=1
Environment=PORTAL_BASE=/$NAME
Environment=PORTAL_DATA=$ROOT/data
Environment=PORTAL_COOKIE=${APP}demo_$NAME
Environment=PORTAL_HTTPS=1
Environment=PORTAL_TRUSTED_PROXY=nginx
# the demo's owner (PORTAL_DEMO_OWNER=<email>) lives in one file for every demo - never in a snapshot
EnvironmentFile=-/etc/valuestream/demo.env
ExecStart=$CODE/.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port $PORT
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now "$SERVICE"

echo "30 21 * * * root PORTAL_APP=$APP bash $CODE/deploy/demo/reset.sh $NAME >> /var/log/$APP-demo-$NAME.log 2>&1" > "/etc/cron.d/$APP-demo-$NAME"
for i in $(seq 1 30); do
  curl -sf -o /dev/null "http://127.0.0.1:$PORT/$NAME/health" && { echo "SETUP OK - $SERVICE answers on port $PORT"; exit 0; }
  sleep 1
done
echo "$SERVICE did not answer on port $PORT. Its log:"; journalctl -u "$SERVICE" -n 40 --no-pager; exit 1
