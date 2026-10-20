#!/bin/bash
# Hourly from /etc/cron.d/simplyfile-backup. The data folder is the portal's whole memory.
# Local, in /var/backups/sf: 24 hourly + 7 daily + 5 weekly copies (each slot is overwritten, so disk use is bounded).
# Off-site: at 02:xx the day's copy also goes to $SF_OFFSITE (an rclone remote, ideally a `crypt` one) - 7 daily + 5 weekly there too.
# data/geo is left out: it is the downloaded place database, fetched again by itself.
set -euo pipefail
APP=${SF_APP:-/opt/simplyfile}
D=${SF_BACKUPS:-/var/backups/sf}
umask 077
mkdir -p "$D"
H=$(date +%H)
f="$D/hour-$H.tar.gz"
rm -f "$D"/*.tmp                 # a copy cut short earlier never lingers
# 2026-10-20 restore drill: tar says 1 ("file changed as we read it") when the portal writes during the copy; the copy is
# still whole (every store write is a rename), but set -e stopped before the mv and that hour was lost. 1 is fine, 2+ is not.
tar czf "$f.tmp" --warning=no-file-changed --exclude=data/geo -C "$APP" data || [ $? -eq 1 ]
mv "$f.tmp" "$f"
[ "$H" = 02 ] || exit 0
day="$D/day-$(date +%a).tar.gz"
cp "$f" "$day"
week=""
if [ "$(date +%u)" = 7 ]; then week="$D/week-$(( ($(date +%-d) - 1) / 7 )).tar.gz"; cp "$f" "$week"; fi
if [ -n "${SF_OFFSITE:-}" ]; then
  rclone copyto "$day" "$SF_OFFSITE/$(basename "$day")"
  [ -z "$week" ] || rclone copyto "$week" "$SF_OFFSITE/$(basename "$week")"
fi
