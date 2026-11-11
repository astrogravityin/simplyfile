#!/usr/bin/env bash
# Dry run of deploy/deploy.sh on THIS machine (Git Bash on Windows, or Linux) - never touches a server.
#
#   bash deploy/harness/dryrun.sh            -> a temp folder with an origin repo, a prod and a staging target
#
# A stub portal (app.py with /health and /version, selfcheck.py) gets five commits:
#   v1 good, v2 good, v3 selfcheck fails, v4 selfcheck passes but /health is 500, v5 healthy on an empty data
#   folder (the probe) but 500 on the live data (a data-shaped bug).
# It then deploys v1 -> v2 -> v3 -> v4 -> v5, checks after each that the right version still serves, rolls back,
# rolls forward, deploys staging on its own port, and prints how long each step took. The deploy files used are the
# ones in this checkout (deploy/deploy.sh, deploy/settings.py, chips/deploy.settings.json); the harness only overrides
# folders, ports and the restart command through DEPLOY_* env - the same doors an owner has.
set -uo pipefail
SRC=$(cd "$(dirname "$0")/../.." && pwd)
ROOT=${DRYRUN_DIR:-$( [ -d /d/Temp ] && echo /d/Temp || echo "${TMPDIR:-/tmp}")}/deploy-dryrun-$(date +%Y%m%d-%H%M%S)
mkdir -p "$ROOT"
PY=$(command -v python3 >/dev/null 2>&1 && python3 -c 'import uvicorn' 2>/dev/null && echo python3 || echo python)
PROD_PORT=${DRYRUN_PROD_PORT:-18830}; STAGE_PORT=${DRYRUN_STAGE_PORT:-18836}
windows() { case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) return 0;; esac; return 1; }
ms() { date +%s%3N; }
PASS=0; FAIL=0; ROWS=()
row() { ROWS+=("$(printf '%-3s %-58s %8s  %s' "$1" "$2" "$3" "$4")"); [ "$1" = OK ] && PASS=$((PASS+1)) || FAIL=$((FAIL+1)); }
version() { curl -sf --max-time 2 "http://127.0.0.1:$1/version" || echo DOWN; }

# ---- a fake "systemctl restart": stop whatever listens on the port, start <base>/current there -----------------
cat >"$ROOT/fake-service.sh" <<'SVC'
#!/usr/bin/env bash
base=$1; port=$2
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    for p in $(netstat -ano | awk -v P=":$port" '$2 ~ P"$" && $4 == "LISTENING" {print $5}' | sort -u); do taskkill //F //T //PID "$p" >/dev/null 2>&1; done
    py="$base/current/.venv/Scripts/python.exe";;
  *) [ -f "$base/.svc.pid" ] && kill "$(cat "$base/.svc.pid")" 2>/dev/null; sleep 0.3
     py="$base/current/.venv/bin/python";;
esac
cd "$base/current" || exit 1
PORTAL_DATA="$base/data" nohup "$py" -m uvicorn app:app --host 127.0.0.1 --port "$port" >"$base/service.log" 2>&1 </dev/null &
echo $! >"$base/.svc.pid"
SVC

# ---- the stub portal and its five commits ----------------------------------------------------------------------
git init -q --bare -b main "$ROOT/origin.git"
W=$ROOT/work; git init -q -b main "$W"; git -C "$W" config user.email dryrun@localhost; git -C "$W" config user.name dryrun; git -C "$W" config core.autocrlf false
mkdir -p "$W/deploy" "$W/chips"
cp "$SRC/deploy/deploy.sh" "$SRC/deploy/settings.py" "$SRC/deploy/portal.service.in" "$W/deploy/"
cp "$SRC/chips/deploy.settings.json" "$W/chips/"
printf 'fastapi\nuvicorn\n' >"$W/requirements.txt"
printf 'data/\nreleases/\ncurrent\nvenvs/\n.deploy.lock/\n' >"$W/.gitignore"
app() {   # $1 version, $2 health mode: ok | 500 | live500
cat >"$W/app.py" <<APP
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
app = FastAPI()
VERSION = "$1"
MODE = "$2"
@app.get("/health", response_class=PlainTextResponse)
def health():
    live = Path(os.environ.get("PORTAL_DATA", "data"), "live.marker").exists()
    if MODE == "500" or (MODE == "live500" and live):
        return PlainTextResponse("broken", status_code=500)
    return "ok"
@app.get("/version", response_class=PlainTextResponse)
def version():
    return VERSION
APP
}
selfcheck() { printf 'import app\nassert app.VERSION\n%s\nprint("All checks passed.")\n' "${1:-}" >"$W/selfcheck.py"; }
commit() { git -C "$W" add -A; git -C "$W" commit -qm "$1"; git -C "$W" tag "$1"; }
app v1 ok;      selfcheck;                                   commit v1
app v2 ok;      selfcheck;                                   commit v2
app v3 ok;      selfcheck 'assert False, "v3: a check that fails"'; commit v3
app v4 500;     selfcheck;                                   commit v4
app v5 live500; selfcheck;                                   commit v5
git -C "$W" remote add origin "$ROOT/origin.git"; git -C "$W" push -q origin main --tags

# ---- two targets ----------------------------------------------------------------------------------------------
git clone -q "$ROOT/origin.git" "$ROOT/prod"
git clone -q "$ROOT/origin.git" "$ROOT/staging"
mkdir -p "$ROOT/prod/data"; echo "the live data" >"$ROOT/prod/data/live.marker"
export DEPLOY_PYTHON=$PY DEPLOY_VENV_ARGS=--system-site-packages DEPLOY_HEALTH_WAIT_S=12 DEPLOY_USER= DEPLOY_ALSO_RESTART= \
       DEPLOY_KEEP_RELEASES=3
d() {   # $1 prod|staging, rest = deploy.sh command
  local t=$1; shift
  if [ "$t" = prod ]; then
    DEPLOY_BASE=$ROOT/prod DEPLOY_PORT=$PROD_PORT DEPLOY_PROBE_PORT=$((PROD_PORT+100)) \
      DEPLOY_RESTART_CMD="bash $ROOT/fake-service.sh $ROOT/prod $PROD_PORT" bash "$ROOT/prod/deploy/deploy.sh" --target prod "$@"
  else
    DEPLOY_BASE=$ROOT/staging DEPLOY_PORT=$STAGE_PORT DEPLOY_PROBE_PORT=$((STAGE_PORT+100)) \
      DEPLOY_RESTART_CMD="bash $ROOT/fake-service.sh $ROOT/staging $STAGE_PORT" bash "$ROOT/staging/deploy/deploy.sh" --target staging "$@"
  fi
}
step() {   # $1 label, $2 expect exit (0|1), $3 port, $4 expected version, rest = d args
  local label=$1 want=$2 port=$3 ver=$4; shift 4
  echo; echo "################ $label"
  local t; t=$(ms)
  d "$@" 2>&1 | sed 's/^/  /'; local rc=${PIPESTATUS[0]}
  local took=$(( $(ms) - t )) got; got=$(version "$port")
  local secs; secs=$(printf '%d.%01ds' $((took/1000)) $((took%1000/100)))
  if [ "$rc" = "$want" ] && [ "$got" = "$ver" ]; then row OK "$label" "$secs" "exit $rc, port $port serves $got"
  else row BAD "$label" "$secs" "exit $rc (want $want), port $port serves $got (want $ver)"; fi
}

echo "dry run in $ROOT  (python: $PY)"
T0=$(ms)
echo; echo "################ init prod at v1 + first start (the owner's one-time switch-over)"
d prod init v1 2>&1 | sed 's/^/  /'; bash "$ROOT/fake-service.sh" "$ROOT/prod" "$PROD_PORT"
for _ in $(seq 1 20); do [ "$(version $PROD_PORT)" = v1 ] && break; sleep 0.5; done
[ "$(version $PROD_PORT)" = v1 ] && row OK "init prod at v1, service started" "-" "port $PROD_PORT serves v1" || row BAD "init prod at v1" "-" "port $PROD_PORT serves $(version $PROD_PORT)"

step "deploy v2 (good)"                                  0 "$PROD_PORT" v2 prod deploy v2
step "deploy v3 (selfcheck fails) -> v2 keeps serving"   1 "$PROD_PORT" v2 prod deploy v3
step "deploy v4 (/health 500) -> probe stops it"         1 "$PROD_PORT" v2 prod deploy v4
step "deploy v5 (fails on live data) -> switched back"   1 "$PROD_PORT" v2 prod deploy v5
step "rollback (one command) -> v1"                      0 "$PROD_PORT" v1 prod rollback
step "deploy v2 again (roll forward, release reused)"    0 "$PROD_PORT" v2 prod deploy v2

echo; echo "################ staging: its own folder and port, same script"
d staging init v1 2>&1 | sed 's/^/  /'; bash "$ROOT/fake-service.sh" "$ROOT/staging" "$STAGE_PORT"
for _ in $(seq 1 20); do [ "$(version $STAGE_PORT)" = v1 ] && break; sleep 0.5; done
step "staging: deploy v2 on port $STAGE_PORT"            0 "$STAGE_PORT" v2 staging deploy v2
[ "$(version $PROD_PORT)" = v2 ] && row OK "prod untouched by the staging deploy" "-" "port $PROD_PORT serves v2" || row BAD "prod untouched by staging" "-" "port $PROD_PORT serves $(version $PROD_PORT)"

echo; echo "################ status"
d prod status 2>&1 | sed 's/^/  /'
n=$(find "$ROOT/prod/releases" -mindepth 1 -maxdepth 1 -type d | wc -l)
[ "$n" -ge 1 ] && [ "$n" -le 4 ] && row OK "prune keeps keep_releases (3) + live/rollback" "-" "$n release folders" || row BAD "prune" "-" "$n release folders"

echo; echo "################ unit for prod (as deploy.sh renders it from chip deploy.settings, no overrides)"
(unset DEPLOY_BASE DEPLOY_PORT DEPLOY_USER; DEPLOY_PYTHON=$PY bash "$SRC/deploy/deploy.sh" --target prod unit | grep -E '^(User|WorkingDirectory|Environment=PORT|ExecStart)=' | sed 's/^/  /')

# stop the stub services
for p in $PROD_PORT $STAGE_PORT; do
  if windows; then for q in $(netstat -ano | awk -v P=":$p" '$2 ~ P"$" && $4 == "LISTENING" {print $5}' | sort -u); do taskkill //F //T //PID "$q" >/dev/null 2>&1; done
  else for b in prod staging; do [ -f "$ROOT/$b/.svc.pid" ] && kill "$(cat "$ROOT/$b/.svc.pid")" 2>/dev/null; done; fi
done

echo; echo "================ RESULT ($(( ($(ms) - T0) / 1000 )) s in all, folder $ROOT)"
printf '%s\n' "${ROWS[@]}"
echo "passed $PASS, failed $FAIL"
[ "$FAIL" = 0 ]
