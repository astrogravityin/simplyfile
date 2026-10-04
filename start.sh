#!/usr/bin/env bash
# SimplyFile (sf.valuestream.in) - macOS/Linux. First run installs what it needs into .venv.
set -e
cd "$(dirname "$0")"

[ -d .venv ] || python3 -m venv .venv
# shellcheck disable=SC1091
. .venv/bin/activate
python -c "import fastapi, openpyxl, jsonschema" 2>/dev/null || {
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
}

PORT="${TV_PORT:-8830}"
export PORTAL_COOKIE="${PORTAL_COOKIE:-sf_session}"
echo
echo "  SimplyFile  ->  http://localhost:$PORT"
echo "  Stop it with Ctrl+C."
echo
exec python -m uvicorn app:app --host 0.0.0.0 --port "$PORT"
