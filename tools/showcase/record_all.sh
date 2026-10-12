# Re-record every showcase video, each from the state it was first recorded in, then build the demo site's data and snapshot:
# fresh seed -> parts 1-2 (recorded) -> save P2; from P2: 3 | @pre4 4 5 | @pre6 6 | 7 | @pre6 @pre8 8 (each recorded);
# 2026-10-07, from P2 again: the self-filer (pre_selfer.py) 9 @pre10 10 + the My return screen tour | 11 (the CA firm's HUF and consultant)
# | as the owner: @pre_taxwatch + the Tax rules screen tour, 12 (Apply moves the live year: never in the demo data);
# finally from P2 every CA-firm part in order (check mode), then the party master (pre_parties.py) and New filing's worked examples
# (pre_cases.py, 2026-10-11: each path left at Review) -> tmp/showcase/demo-final -> tmp/demo/demo-tax-snapshot.tgz. Their films: record_cases.sh.
#   bash tools/showcase/record_all.sh > tmp/showcase/record_all.log 2>&1      (about an hour and a half; run in the background)
#   FROM=more bash tools/showcase/record_all.sh ...   parts 9-12 and the demo data only (P2 saved by an earlier run)
#   FROM=demo bash tools/showcase/record_all.sh ...   the demo data and snapshot only
# Before: python tools/showcase/make_showcase_tour*.py and make_showcase_tours9_12.py (write tmp/tour_video/showcase*.json);
# demo files in tools/tour_video/showcase/ (make_myreturn_demo.py writes self/, self-again/, huf/, kavya/).
H="$(cd "$(dirname "$0")" && pwd)"; R="$(cd "$H/../.." && pwd)"; T="$R/tmp/showcase"
cd "$R"
log() { echo "[$(date +%H:%M:%S)] $*"; }
if [ -z "$FROM" ]; then
  bash "$H/server.sh" seed
  log "parts 1-2"; bash "$H/run_tours.sh" record showcase showcase2 | grep -E "done:|FAILED|STOP"
  rm -rf "$T/data-p2" && cp -r "$T/data" "$T/data-p2"
  for chain in "showcase3" "@pre4.py showcase4 showcase5" "@pre6.py showcase6" "showcase7" "@pre6.py @pre8.py showcase8"; do
    bash "$H/server.sh" p2 | tail -1
    log "chain: $chain"; bash "$H/run_tours.sh" record $chain | grep -E "done:|FAILED|STOP|pre"
  done
fi
if [ "$FROM" != demo ]; then
  bash "$H/server.sh" p2 | tail -1
  log "chain: self-filer 9 10 + screen tour sf-myreturn"; .venv/Scripts/python.exe "$H/pre_selfer.py" http://localhost:${SC_PORT:-8832} | tail -1
  TOUR_LOGIN=selfer bash "$H/run_tours.sh" record showcase9 @pre10.py showcase10 ../../tours/sf-myreturn | grep -E "done:|FAILED|STOP|pre"
  bash "$H/server.sh" p2 | tail -1
  log "chain: showcase11"; bash "$H/run_tours.sh" record showcase11 | grep -E "done:|FAILED|STOP"
  bash "$H/server.sh" p2 | tail -1
  log "chain: owner - tax rules"; TOUR_LOGIN=admin bash "$H/run_tours.sh" record @pre_taxwatch.py ../../tours/sf-taxwatch showcase12 | grep -E "done:|FAILED|STOP|pre"
fi
bash "$H/server.sh" p2 | tail -1
log "demo data: every part in order"; bash "$H/run_tours.sh" check showcase3 @pre4.py showcase4 showcase5 @pre6.py showcase6 showcase7 @pre8.py showcase8 showcase11 @pre_parties.py | grep -E "passed|FAILED|STOP|pre"
rm -rf "$T/demo-before-cases" && cp -r "$T/data" "$T/demo-before-cases"      # record_cases.sh films each worked example from here
.venv/Scripts/python.exe "$H/pre_companies.py" "$(cygpath -w "$T/data")" 2>&1 | tail -1   # 2026-10-11 ITR-6: the two demo companies
.venv/Scripts/python.exe "$H/pre_cases.py" "$(cygpath -w "$T/data")" 2>&1 | tail -1      # after the companies: their worked examples find them
rm -rf "$T/demo-final" && cp -r "$T/data" "$T/demo-final"
mkdir -p tmp/demo && .venv/Scripts/python.exe "$H/pack_demo.py" "$T/demo-final" tmp/demo/demo-tax-snapshot.tgz
log "ALL DONE"
