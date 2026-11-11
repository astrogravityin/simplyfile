#!/usr/bin/env bash
# Deploy you can undo (W1.4, scorecard B10). One folder per target:
#
#   <base>/            the git checkout (pulled; nothing runs from it)
#   <base>/releases/<commit>/   one worktree per release, .venv -> <base>/venvs/<requirements hash>
#   <base>/current  -> releases/<commit>   what the service runs (WorkingDirectory in the unit)
#   <base>/data/       the portal's memory - never inside a release
#
#   bash deploy/deploy.sh [--target prod|staging] deploy [<commit>]   build, check, probe, switch, health
#   bash deploy/deploy.sh [--target ...] rollback [<commit>]          back to the release before (or the one named)
#   bash deploy/deploy.sh [--target ...] status                       what is live, what can be rolled back to
#   bash deploy/deploy.sh [--target ...] init                         first release from HEAD + current (no restart)
#   bash deploy/deploy.sh [--target ...] unit                         print the systemd unit for this target
#
# The live release is replaced only when the new one passed its selfcheck AND answered /health on the probe port; if
# the live /health then fails, current moves back and the old release is restarted. Every value comes from chip
# deploy.settings (deploy/settings.py); env DEPLOY_<NAME> overrides one run (the dry-run harness uses that).
set -euo pipefail

say()  { printf '%s\n' "$*"; }
die()  { printf 'DEPLOY FAILED - %s\n' "$*" >&2; exit 1; }
ms()   { date +%s%3N; }
since(){ local d=$(( $(ms) - $1 )); printf '%d.%03d s' $((d / 1000)) $((d % 1000)); }

TARGET=${DEPLOY_TARGET:-}
if [ "${1:-}" = "--target" ]; then TARGET=$2; shift 2; fi
CMD=${1:-deploy}; shift || true
ARG=${1:-}
HERE=$(cd "$(dirname "$0")/.." && pwd)
SYS_PY=${DEPLOY_PYTHON:-python3}

load_settings() {   # $1 = the checkout whose chip is read
  local lines
  lines=$(PORTAL_DATA="${DEPLOY_BASE:-$1}/data" "$SYS_PY" "$1/deploy/settings.py" "$1" "$TARGET") || die "cannot read chip deploy.settings"
  eval "$lines"
  BASE=$DEPLOY_BASE; TARGET=$DEPLOY_TARGET; SYS_PY=$DEPLOY_PYTHON
  REL=$BASE/releases; CUR=$BASE/current; HIST=$REL/.history
}
load_settings "$HERE"

# The target's own checkout runs its own copy of this script.
if [ "$(cd "$BASE" 2>/dev/null && pwd)" != "$HERE" ] && [ "$CMD" != unit ]; then
  [ -f "$BASE/deploy/deploy.sh" ] || die "$BASE has no deploy/deploy.sh - clone the repo there first (DEPLOY.md, staging)"
  exec bash "$BASE/deploy/deploy.sh" --target "$TARGET" "$CMD" "$@"
fi

windows() { case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) return 0;; esac; return 1; }

# Run as the service user, never root: a root shell (today's ssh login) hands itself to that user once it exists
# (the restart then goes through the sudoers line in DEPLOY.md).
if ! windows && [ "$(id -u)" = 0 ] && [ -n "${DEPLOY_USER:-}" ] && id -u "$DEPLOY_USER" >/dev/null 2>&1 && [ "$CMD" != unit ]; then
  exec runuser -u "$DEPLOY_USER" -- env DEPLOY_REEXEC="${DEPLOY_REEXEC:-}" bash "$0" --target "$TARGET" "$CMD" "$@"
fi

stop_tree() {   # $1 pid of a background job: it and what it started
  if windows && [ -r "/proc/$1/winpid" ]; then taskkill //F //T //PID "$(cat "/proc/$1/winpid")" >/dev/null 2>&1 || true
  else kill "$1" 2>/dev/null || true; fi
  wait "$1" 2>/dev/null || true
}

# Point a link at a folder in one step: on Linux a symlink renamed over the old one (atomic); in Git Bash on Windows
# (no symlink right) a directory junction - used only by the dry-run harness.
set_link() {   # $1 link, $2 target folder (absolute)
  if windows; then
    if [ -e "$1" ] || [ -L "$1" ]; then cmd //c rmdir "$(cygpath -w "$1")" >/dev/null; fi
    cmd //c mklink //J "$(cygpath -w "$1")" "$(cygpath -w "$2")" >/dev/null
  else
    ln -sfn "$2" "$1.new" && mv -Tf "$1.new" "$1"
  fi
}
live_sha() { [ -e "$CUR" ] && basename "$(readlink -f "$CUR")" || true; }
vpy() { if [ -x "$1/bin/python" ]; then echo "$1/bin/python"; else echo "$1/Scripts/python.exe"; fi; }
fill() { local s=$1; s=${s//\{python\}/$2}; s=${s//\{port\}/$3}; s=${s//\{service\}/$DEPLOY_SERVICE}; printf '%s' "$s"; }

health() {   # $1 port -> 0 when /health answers within health_wait_s
  local i
  for i in $(seq 1 "$DEPLOY_HEALTH_WAIT_S"); do
    curl -sf -o /dev/null --max-time 2 "http://127.0.0.1:$1$DEPLOY_HEALTH_PATH" && return 0
    sleep 1
  done
  return 1
}

restart() {
  local c; c=$(fill "$DEPLOY_RESTART_CMD" "" "$DEPLOY_PORT")
  case "$c" in systemctl*) [ "$(id -u)" = 0 ] || c="sudo -n $c";; esac
  bash -c "$c"
}

lock() {
  local l=$BASE/.deploy.lock
  if ! mkdir "$l" 2>/dev/null; then
    local pid; pid=$(cat "$l/pid" 2>/dev/null || true)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then die "another deploy (pid $pid) is running on $TARGET"; fi
    say "a stale lock (pid ${pid:-?}) was left - taking it over"
    rm -f "$l/pid"; rmdir "$l" 2>/dev/null || true; mkdir "$l"
  fi
  echo $$ >"$l/pid"
  trap 'rm -f "'"$l"'/pid"; rmdir "'"$l"'" 2>/dev/null || true' EXIT
}

# Build releases/<sha>: worktree, venv (shared by every release with the same requirements file), selfcheck.
build() {   # $1 sha
  local sha=$1 rel=$REL/$1 t; t=$(ms)
  if [ -d "$rel" ] && [ -f "$rel/.ok" ]; then say "release $sha already built - reusing it"; return 0; fi
  if [ -d "$rel" ]; then git -C "$BASE" worktree remove --force "$rel" 2>/dev/null || true; fi
  git -C "$BASE" worktree prune
  git -C "$BASE" worktree add -q --detach --force "$rel" "$sha"
  local req="" f
  for f in $DEPLOY_REQUIREMENTS; do [ -f "$rel/$f" ] && { req=$f; break; }; done
  [ -n "$req" ] || die "release $sha has none of: $DEPLOY_REQUIREMENTS"
  local key; key=$(cat "$rel/$req" | sha256sum | cut -c1-16)-$("$SYS_PY" -c 'import sys;print("%d%d" % sys.version_info[:2])')
  local venv=$BASE/venvs/$key
  if [ ! -f "$venv/.ready" ]; then
    say "  packages: new venv $key from $req"
    mkdir -p "$BASE/venvs"
    # shellcheck disable=SC2086
    "$SYS_PY" -m venv $DEPLOY_VENV_ARGS "$venv"
    "$(vpy "$venv")" -m pip install -q -r "$rel/$req" || die "pip install failed for $sha - the live release keeps serving"
    touch "$venv/.ready"
  else
    say "  packages: venv $key (same $req as before)"
  fi
  set_link "$rel/.venv" "$venv"
  local py; py=$(vpy "$rel/.venv")
  say "  selfcheck in releases/$sha ..."
  if ! (cd "$rel" && bash -c "$(fill "$DEPLOY_SELFCHECK" "$py" "")") >"$rel/.selfcheck.log" 2>&1; then
    tail -n 15 "$rel/.selfcheck.log" | sed 's/^/    | /'
    touch "$rel/.failed"
    die "selfcheck failed for $sha ($(since "$t")) - $(live_sha || echo nothing) keeps serving"
  fi
  touch "$rel/.ok"; rm -f "$rel/.failed"
  say "  built + selfcheck passed in $(since "$t")"
}

# Start the release on the probe port with an empty data folder and ask its health; stop it again.
probe() {   # $1 sha
  [ "$DEPLOY_PROBE" = 1 ] || { say "  probe: off (chip deploy.settings)"; return 0; }
  local rel=$REL/$1 t tmp pid ok=0; t=$(ms)
  tmp=$(mktemp -d "${TMPDIR:-/tmp}/deploy-probe.XXXXXX")
  local c; c=$(fill "$DEPLOY_START_CMD" "$(vpy "$rel/.venv")" "$DEPLOY_PROBE_PORT")
  (cd "$rel" && PORTAL_DATA=$tmp TV_DATA=$tmp PORT=$DEPLOY_PROBE_PORT exec bash -c "exec $c") >"$rel/.probe.log" 2>&1 &
  pid=$!
  health "$DEPLOY_PROBE_PORT" && ok=1
  stop_tree "$pid"
  rm -rf "${tmp:?}"
  if [ $ok != 1 ]; then
    tail -n 15 "$rel/.probe.log" | sed 's/^/    | /'
    touch "$rel/.failed"
    die "the new release did not answer $DEPLOY_HEALTH_PATH on probe port $DEPLOY_PROBE_PORT ($(since "$t")) - $(live_sha || echo nothing) keeps serving"
  fi
  say "  probe: $DEPLOY_HEALTH_PATH answered on port $DEPLOY_PROBE_PORT in $(since "$t")"
}

# Move current to <sha>, restart, ask live health; on failure move back to <prev> and restart that.
switch() {   # $1 sha, $2 why (deploy|rollback)
  local sha=$1 prev t; prev=$(live_sha); t=$(ms)
  set_link "$CUR" "$REL/$sha"
  restart
  if health "$DEPLOY_PORT"; then
    echo "$sha $(date -u +%FT%TZ) $2" >>"$HIST"
    say "  switch: $prev -> $sha, live $DEPLOY_HEALTH_PATH answered on port $DEPLOY_PORT in $(since "$t")"
    return 0
  fi
  say "  live health FAILED on port $DEPLOY_PORT - moving back to $prev"
  touch "$REL/$sha/.failed"
  if [ -n "$prev" ]; then
    set_link "$CUR" "$REL/$prev"; restart
    health "$DEPLOY_PORT" && say "  $prev is serving again ($(since "$t"))" || say "  $prev did not answer either - read the service log"
  fi
  return 1
}

also_restart() {
  [ -n "${DEPLOY_ALSO_RESTART:-}" ] && command -v systemctl >/dev/null || return 0
  local d
  for d in $(systemctl list-units --type=service --all --no-legend "$DEPLOY_ALSO_RESTART" | awk '{print $1}'); do
    (DEPLOY_SERVICE=${d%.service}; restart) && say "  restarted $d onto the same code"
  done
}

# Keep the newest keep_releases folders, never the live one or the one rollback would use.
prune() {
  local live keep back; live=$(live_sha); back=$(rollback_target || true)
  keep=$(tac "$HIST" 2>/dev/null | awk '{print $1}' | awk '!s[$0]++' | head -n "$DEPLOY_KEEP_RELEASES")
  local d n
  for d in "$REL"/*/; do
    n=$(basename "$d")
    [ "$n" = "$live" ] || [ "$n" = "$back" ] || grep -qx "$n" <<<"$keep" && continue
    case "$d" in "$REL"/?*) git -C "$BASE" worktree remove --force "$d" 2>/dev/null || rm -rf "${d:?}"; say "  pruned old release $n";; esac
  done
  git -C "$BASE" worktree prune
}

# The newest release in history before the live one that still exists, passed, and was not itself rolled back from.
rollback_target() {
  local live; live=$(live_sha)
  tac "$HIST" 2>/dev/null | awk '{print $1}' | while read -r s; do
    [ "$s" = "$live" ] && continue
    [ -f "$REL/$s/.ok" ] && [ ! -f "$REL/$s/.failed" ] && [ ! -f "$REL/$s/.rolled_back" ] && { echo "$s"; break; }
  done
}

case "$CMD" in
  deploy)
    T0=$(ms)
    if [ -z "${DEPLOY_REEXEC:-}" ]; then
      git -C "$BASE" fetch -q origin
      git -C "$BASE" checkout -q "$DEPLOY_BRANCH" 2>/dev/null || true
      git -C "$BASE" merge -q --ff-only "origin/$DEPLOY_BRANCH"
      # this script may have just changed: run the new copy from the top
      DEPLOY_REEXEC=1 exec bash "$BASE/deploy/deploy.sh" --target "$TARGET" deploy "$ARG"
    fi
    # (this copy is the one just pulled, so the settings above already come from the pulled chip)
    say "=== deploy $TARGET on $(hostname) - $BASE ==="
    lock
    mkdir -p "$REL" "$BASE/data"
    SHA=$(git -C "$BASE" rev-parse --short=12 "${ARG:-HEAD}^{commit}") || die "no commit ${ARG:-HEAD}"
    LIVE=$(live_sha)
    say "code: ${LIVE:-none} -> $SHA"
    if [ "$SHA" = "$LIVE" ]; then say "DEPLOY OK - $SHA is already live"; exit 0; fi
    rm -f "$REL/$SHA/.rolled_back"
    build "$SHA"
    probe "$SHA"
    switch "$SHA" deploy || die "$SHA failed its live health and was switched back ($(since "$T0"))"
    also_restart
    prune
    say "DEPLOY OK - $SHA is live on port $DEPLOY_PORT ($TARGET) in $(since "$T0"); undo: bash deploy/deploy.sh --target $TARGET rollback"
    ;;
  rollback)
    T0=$(ms); lock
    LIVE=$(live_sha)
    TO=${ARG:-$(rollback_target)}
    [ -n "$TO" ] || die "no earlier release to roll back to (deploy/deploy.sh status)"
    TO=$(basename "$(cd "$REL" && ls -d "$TO"* 2>/dev/null | head -n1)")
    [ -f "$REL/$TO/.ok" ] || die "release $TO is not a built, checked release"
    say "=== rollback $TARGET: $LIVE -> $TO ==="
    switch "$TO" rollback || die "rollback to $TO failed its health - $LIVE is serving again"
    [ -n "$LIVE" ] && touch "$REL/$LIVE/.rolled_back"
    also_restart
    say "ROLLBACK OK - $TO is live on port $DEPLOY_PORT ($TARGET) in $(since "$T0")"
    ;;
  status)
    say "target $TARGET  base $BASE  port $DEPLOY_PORT"
    say "live     : $(live_sha || true)  ($(curl -sf --max-time 2 "http://127.0.0.1:$DEPLOY_PORT$DEPLOY_HEALTH_PATH" >/dev/null && echo answers || echo 'NOT answering'))"
    say "rollback : $(rollback_target || true)"
    for d in "$REL"/*/; do
      [ -d "$d" ] || continue
      n=$(basename "$d"); m=""
      [ -f "$d/.ok" ] && m="$m checked"; [ -f "$d/.failed" ] && m="$m FAILED"; [ -f "$d/.rolled_back" ] && m="$m rolled-back-from"
      say "  $n$m"
    done
    ;;
  init)
    lock
    mkdir -p "$REL" "$BASE/data" "$BASE/venvs"
    if [ -n "$(live_sha)" ]; then say "already in release layout - live $(live_sha)"; exit 0; fi
    SHA=$(git -C "$BASE" rev-parse --short=12 "${ARG:-HEAD}^{commit}")
    build "$SHA"
    set_link "$CUR" "$REL/$SHA"
    echo "$SHA $(date -u +%FT%TZ) init" >>"$HIST"
    say "INIT OK - current -> releases/$SHA. Nothing was restarted: install the unit (bash deploy/deploy.sh --target $TARGET unit) and restart once (DEPLOY.md, switch-over)."
    ;;
  unit)
    sed -e "s#{{BASE}}#$BASE#g" -e "s#{{SERVICE}}#$DEPLOY_SERVICE#g" -e "s#{{USER}}#$DEPLOY_USER#g" \
        -e "s#{{TARGET}}#$TARGET#g" -e "s#{{PORT}}#$DEPLOY_PORT#g" \
        -e "s#{{EXEC}}#$(fill "$DEPLOY_START_CMD" "$BASE/current/.venv/bin/python" "$DEPLOY_PORT")#g" \
        "$HERE/deploy/portal.service.in"
    ;;
  *) die "unknown command $CMD (deploy | rollback | status | init | unit)";;
esac
