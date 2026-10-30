"""What the commit checks. A change to one area runs chip commit.scope's fast groups; a change to the shared core, or
anything this cannot read, runs everything (prints nothing). deploy.sh runs the full selfcheck on the server before a
restart either way. Owner 2026-10-30: why check files that did not change?"""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


def scope() -> str:
    try:
        k = {p["name"]: p["default"] for p in json.loads((HERE / "chips" / "commit.scope.json").read_text(encoding="utf-8"))["params"]}
        out = subprocess.run(["git", "status", "--porcelain"], cwd=HERE, capture_output=True, text=True, encoding="utf-8", check=True).stdout
        changed = [ln[3:].strip().strip('"') for ln in out.splitlines()]
        known = re.findall(r'"([a-z_]+)"', (HERE / "selfcheck.py").read_text(encoding="utf-8"))
        if not changed or any(re.search(k["full_when"], f) for f in changed) or not set(k["fast_groups"]) <= set(known):
            return ""
        return " ".join(k["fast_groups"])
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        return ""


def check() -> None:
    """The guard: one area = fast groups, the shared core or an unknown group = everything."""
    real, k = subprocess.run, {p["name"]: p["default"] for p in json.loads((HERE / "chips" / "commit.scope.json").read_text(encoding="utf-8"))["params"]}
    try:
        subprocess.run = lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, " M guides/x.json\n", "")
        assert scope() == " ".join(k["fast_groups"]), "a one-area commit no longer runs only the fast groups"
        subprocess.run = lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, " M core/x.py\n", "")
        assert scope() == "", "a change to the shared core must run the whole selfcheck"
    finally:
        subprocess.run = real


if __name__ == "__main__":
    if "--check" in sys.argv:
        check()
    print(scope())
