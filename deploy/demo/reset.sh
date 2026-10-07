#!/usr/bin/env bash
# Put one product's demo back to its clean snapshot (cron runs it every night; run by hand any time).
#   bash /opt/simplyfile/deploy/demo/reset.sh tax          PORTAL_APP=justify bash /opt/justify/deploy/demo/reset.sh legal
# Kept across a reset: the accounts (your admin passwords and every visitor's seat), the activity ledger (who came, what they
# opened), mail settings and portal settings. Everything else - clients, files, returns, audit work, History - is the snapshot again,
# its dates moved up to today where the product asks (chip demo.host move_dates: Justify's diary yes, SimplyFile's tax year no).
set -euo pipefail
NAME=${1:?which demo - e.g. tax}
APP=${PORTAL_APP:-$(basename "$(cd "$(dirname "$0")/../.." && pwd)")}   # the product - default: the folder this script ships in (/opt/justify -> justify)
ROOT=/opt/$APP-demo/$NAME
SERVICE=$APP-demo-$NAME
KEEP=(users.json ledger.sqlite3 smtp.json settings.json)

[ -d "$ROOT/snapshot" ] || { echo "no snapshot at $ROOT/snapshot"; exit 1; }
systemctl stop "$SERVICE"
tmp=$(mktemp -d)
for f in "${KEEP[@]}"; do [ -e "$ROOT/data/$f" ] && cp -a "$ROOT/data/$f" "$tmp/"; done
rm -rf "$ROOT/data" "$ROOT/jobs"   # jobs/: DummyFy's upload folders (beside data/, never in a snapshot) - gone with the day's visitors
cp -a "$ROOT/snapshot" "$ROOT/data"
# the demo's dates move forward by the days since the snapshot was packed (where chip demo.host move_dates is on)
(cd "/opt/$APP" && PORTAL_DATA="$ROOT/data" .venv/bin/python -m core.demo freshen "$ROOT/data" "$ROOT/snapshot") || echo "dates not moved"
for f in "${KEEP[@]}"; do [ -e "$tmp/$f" ] && cp -a "$tmp/$f" "$ROOT/data/"; done
rm -rf "$tmp"
chown -R "$(stat -c %U "$ROOT")":"$(stat -c %G "$ROOT")" "$ROOT/data"
systemctl start "$SERVICE"
echo "$(date -Is) $NAME demo reset to its snapshot"
