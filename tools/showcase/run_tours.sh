# Play showcase tours against the rehearsal server on 8832 (already running): sign in, then each tour / @step.py in order.
#   bash tools/showcase/run_tours.sh record|check showcase3 @pre4.py showcase4 ...   (tour:check plays one tour in check mode)
H="$(cd "$(dirname "$0")" && pwd)"; R="$(cd "$H/../.." && pwd)"; DATA="$R/tmp/showcase/data"
MODE=$1; shift
cd "$R"
WHO=${TOUR_LOGIN:-uncle}     # the TEST-LOGIN.txt login the tours play as (Justify: TOUR_LOGIN=principal)
TOUR_USER=$(grep "^$WHO=" "$H/TEST-LOGIN.txt" | cut -d= -f2) TOUR_PASSWORD=$(grep "^${WHO}_pw=" "$H/TEST-LOGIN.txt" | cut -d= -f2) \
  python tools/tour_video/make_tour.py --login --base http://localhost:8832 2>&1 | tail -1
for t in "$@"; do
  case $t in @*) .venv/Scripts/python.exe "$H/${t#@}" "$(cygpath -w "$DATA")" 2>&1 | tail -1; continue;; esac
  M=$MODE; case $t in *:*) M=${t#*:}; t=${t%%:*};; esac
  if [ "$M" = check ]; then X=--check; else X=; fi
  PYTHONIOENCODING=utf-8 python tools/tour_video/make_tour.py tmp/tour_video/$t.json $X --base http://localhost:8832 2>&1 | grep -v "^  ok step" | grep -v "skipped optional" | tail -6
  [ ${PIPESTATUS[0]} -ne 0 ] && echo "STOP at $t" && break
done
