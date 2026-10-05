# Re-record every showcase video, each from the state it was first recorded in, then build the demo site's data and snapshot:
# fresh seed -> parts 1-2 (recorded) -> save P2; from P2: 3 | @pre4 4 5 | @pre6 6 | 7 | @pre6 @pre8 8 (each recorded);
# finally from P2 every later part in order (check mode) -> tmp/showcase/demo-final -> tmp/demo/demo-tax-snapshot.tgz.
#   bash tools/showcase/record_all.sh > tmp/showcase/record_all.log 2>&1      (about an hour; run in the background)
# Before: python tools/showcase/make_showcase_tour*.py (writes tmp/tour_video/showcase*.json); demo files in tools/tour_video/showcase/.
H="$(cd "$(dirname "$0")" && pwd)"; R="$(cd "$H/../.." && pwd)"; T="$R/tmp/showcase"
cd "$R"
log() { echo "[$(date +%H:%M:%S)] $*"; }
bash "$H/server.sh" seed
log "parts 1-2"; bash "$H/run_tours.sh" record showcase showcase2 | grep -E "done:|FAILED|STOP"
rm -rf "$T/data-p2" && cp -r "$T/data" "$T/data-p2"
for chain in "showcase3" "@pre4.py showcase4 showcase5" "@pre6.py showcase6" "showcase7" "@pre6.py @pre8.py showcase8"; do
  bash "$H/server.sh" p2 | tail -1
  log "chain: $chain"; bash "$H/run_tours.sh" record $chain | grep -E "done:|FAILED|STOP|pre"
done
bash "$H/server.sh" p2 | tail -1
log "demo data: every part in order"; bash "$H/run_tours.sh" check showcase3 @pre4.py showcase4 showcase5 @pre6.py showcase6 showcase7 @pre8.py showcase8 | grep -E "passed|FAILED|STOP|pre"
rm -rf "$T/demo-final" && cp -r "$T/data" "$T/demo-final"
mkdir -p tmp/demo && .venv/Scripts/python.exe "$H/pack_demo.py" "$T/demo-final" tmp/demo/demo-tax-snapshot.tgz
log "ALL DONE"
