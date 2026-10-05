# (Re)start the rehearsal server on 8832 over tmp/showcase/data, optionally from a fresh seed or a saved state first.
#   bash tools/showcase/server.sh seed      # new data: owner + the approved demo firm (tools/showcase/seed.py)
#   bash tools/showcase/server.sh p2        # back to the state saved after parts 1-2
#   bash tools/showcase/server.sh           # just restart over the current data
H="$(cd "$(dirname "$0")" && pwd)"; R="$(cd "$H/../.." && pwd)"; T="$R/tmp/showcase"
for pid in $(netstat -ano | grep ":8832 .*LISTEN" | awk '{print $5}' | sort -u); do taskkill //F //PID $pid >/dev/null; done
sleep 1
mkdir -p "$T"; cd "$R"
case $1 in
  seed) rm -rf "$T/data"; .venv/Scripts/python.exe "$H/seed.py" "$(cygpath -w "$T/data")" 2>&1 | tail -1;;
  p2) rm -rf "$T/data" && cp -r "$T/data-p2" "$T/data";;
esac
TV_DATA="$(cygpath -w "$T/data")" nohup .venv/Scripts/python.exe -m uvicorn app:app --host 127.0.0.1 --port 8832 > "$T/server.log" 2>&1 &
for i in $(seq 1 30); do curl -sf -o /dev/null http://127.0.0.1:8832/ && break; sleep 1; done
curl -s -o /dev/null -w "server %{http_code}\n" http://127.0.0.1:8832/
