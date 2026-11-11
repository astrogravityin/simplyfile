"""The quality gate's parts of the self-check (W1.3, 2026-11-11). Each part is its own tool; selfcheck.py adds PARTS to its
list with one line, and the CI (.github/workflows/check.yml) runs each part as its own parallel job.

    quality   ruff + mypy within chip selfcheck.quality's ceilings, which only fall (tools/quality_gate.py)
    shapes    every write route survives wrong-shape bodies: no 5xx (tools/shape_walk.py, chip selfcheck.shapes)
    words     a screen's name is the same in catalog.json, its ui chip, Guide me, tour and translations (tools/words_drift.py)
    clones    no copy-pasted function and no repeated run of lines (tools/clones.py, chip selfcheck.clones)
    deps      requirements.lock is hash-pinned, matches requirements.txt, and pip-audit finds nothing (tools/deps_gate.py)
    coverage  coverage.py over the whole self-check, floor in chip selfcheck.quality only rises (tools/coverage_gate.py);
              slow (runs the self-check again), so only when named: python selfcheck.py coverage
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(args: list[str], what: str) -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        data = str(Path(tmp) / "data")    # both names: the api part leaves PORTAL_DATA set to ITS locked folder
        env = os.environ | {"TV_DATA": data, "PORTAL_DATA": data, "PYTHONIOENCODING": "utf-8"}
        r = subprocess.run([sys.executable, "-W", "ignore::DeprecationWarning", *args], cwd=HERE, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (r.stdout + r.stderr).rstrip()
    if r.returncode:
        raise SystemExit(f"FAILED {what}:\n{out[-3000:]}")
    print("\n".join(x for x in out.splitlines() if x.startswith("  ")) or f"  {what} OK")


def tool(name: str, what: str):
    def part() -> None:
        run([f"tools/{name}.py", "--selftest"], f"{what} self-test")
        run([f"tools/{name}.py"], what)
    return part


PARTS = {"quality": tool("quality_gate", "lint and types"), "shapes": tool("shape_walk", "shape walk"),
         "words": tool("words_drift", "word drift"), "clones": tool("clones", "clones"), "deps": tool("deps_gate", "dependencies")}
SLOW = {"coverage": tool("coverage_gate", "coverage")}   # run only when named


def main(only: list[str]) -> None:
    for name, fn in (PARTS | {k: f for k, f in SLOW.items() if k in only}).items():
        if not only or name in only:
            fn()
