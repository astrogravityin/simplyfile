#!/usr/bin/env bash
# SimplyFy (sf.valuestream.in) - macOS/Linux. First run installs what it needs into .venv.
set -e
cd "$(dirname "$0")"

[ -d .venv ] || python3 -m venv .venv
# shellcheck disable=SC1091
. .venv/bin/activate
python -c "import fastapi, openpyxl, jsonschema" 2>/dev/null || {
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
}

# 2026-11-22 (DomainTemplate lesson feedback_port_identify_then_next_free): reuse the port only if THIS folder answers there, else the next free one
read -r PICK PORT < <(python -I tools/pick_port.py "${TV_PORT:-8830}") || true
[ -n "$PICK" ] || { echo "  No free port near ${TV_PORT:-8830}"; exit 1; }
if [ "$PICK" = running ]; then echo; echo "  SimplyFy is already running  ->  http://localhost:$PORT"; echo; exit 0; fi
export PORTAL_COOKIE="${PORTAL_COOKIE:-sf_session}"
echo
echo "  SimplyFy  ->  http://localhost:$PORT"
echo "  Stop it with Ctrl+C."
echo
exec python -m uvicorn app:app --host 0.0.0.0 --port "$PORT"
