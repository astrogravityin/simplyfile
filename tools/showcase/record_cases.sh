# New filing's films - one per worked example (chip wizard.cases, tours/sf-case-*.json from tools/make_case_tours.py) and the
# screen's own walk (tours/sf-wizard.json). Each is recorded from a fresh copy of the demo data before the cases were played
# (tmp/showcase/demo-before-cases - record_all.sh keeps it - so every client is made on camera; Lakshmi Narayana Textiles is the register's own), on its own
# rehearsal server (127.0.0.1:$CASE_PORT, default 8900) with its own sign-in file (tmp/wizard/auth.json - never the shared one).
#   bash tools/showcase/record_cases.sh [record|check] [sf-case-salaried sf-wizard ...]     (no names = all)
# Then: python tools/showcase/case_films.py (encodes them small into static/showcase and lists them on the landing page).
MODE=${1:-record}; shift
H="$(cd "$(dirname "$0")" && pwd)"; R="$(cd "$H/../.." && pwd)"; cd "$R"
P=${CASE_PORT:-8900}; W="$R/tmp/wizard"; BASE_DATA=${CASE_BASE:-$R/tmp/showcase/demo-before-cases}
mkdir -p "$W"
export TOUR_AUTH="$W/auth.json"
WHO=${TOUR_LOGIN:-uncle}
U=$(grep "^$WHO=" "$H/TEST-LOGIN.txt" | cut -d= -f2); PW=$(grep "^${WHO}_pw=" "$H/TEST-LOGIN.txt" | cut -d= -f2)
TOURS="$*"; [ -z "$TOURS" ] && TOURS="sf-wizard $(ls tours/sf-case-*.json | xargs -n1 basename | sed 's/\.json$//' | tr '\n' ' ')"
stop() { for pid in $(netstat -ano | grep ":$P .*LISTEN" | awk '{print $5}' | sort -u); do taskkill //F //PID $pid >/dev/null 2>&1; done; }
for t in $TOURS; do
  stop; sleep 1
  rm -rf "$W/rec-data" && cp -r "$BASE_DATA" "$W/rec-data"
  TV_DATA="$(cygpath -w "$W/rec-data")" PORTAL_COOKIE=sf_caserec_session nohup .venv/Scripts/python.exe -m uvicorn app:app --host 127.0.0.1 --port $P > "$W/rec-server.log" 2>&1 &
  for i in $(seq 1 40); do curl -sf -o /dev/null http://127.0.0.1:$P/ && break; sleep 1; done
  TOUR_USER="$U" TOUR_PASSWORD="$PW" PYTHONIOENCODING=utf-8 python tools/tour_video/make_tour.py --login --base http://127.0.0.1:$P 2>&1 | tail -1
  if [ "$MODE" = check ]; then X=--check; else X=; fi
  echo "[$(date +%H:%M:%S)] $t"
  PYTHONIOENCODING=utf-8 python tools/tour_video/make_tour.py tours/$t.json $X --base http://127.0.0.1:$P > "$W/rec-$t.log" 2>&1; grep -v "^  ok step" "$W/rec-$t.log" | grep -v "skipped optional" | tail -3; grep -c "skipped optional" "$W/rec-$t.log" | sed "s/^/  optional steps skipped: /"
done
stop
echo "[$(date +%H:%M:%S)] cases done"
