"""Coverage gate (W1.3, 2026-11-11 - scorecard B9: no coverage measure). coverage.py over the whole self-check (every
module self-test and the API walks run as child processes; [tool.coverage.run] patch = subprocess follows them).

    python tools/coverage_gate.py             measure; fail under chip selfcheck.quality coverage_floor (the floor only
                                              rises - tools/quality_gate.py refuses a lower one against git HEAD)
    python tools/coverage_gate.py --selftest

Slow (it runs the self-check again): CI runs it as its own job; locally `python selfcheck.py coverage`.
The number and the least-covered files are written to tmp/coverage/summary.txt.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tmp" / "coverage"
BIN = Path(sys.executable).parent


def verdict(pct: float, floor: float, step: float) -> tuple[bool, str]:
    if pct < floor:
        return False, f"coverage {pct:.1f}% is under the floor {floor}% - a test went missing, or new code came without one"
    if pct >= floor + step:
        return True, f"coverage {pct:.1f}% - raise coverage_floor to {int(pct * 10) / 10} in chip selfcheck.quality"
    return True, f"coverage {pct:.1f}% (floor {floor}%)"


def measure() -> tuple[float, list[str]]:
    cov = str(BIN / ("coverage" + (".exe" if sys.platform == "win32" else "")))
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    r = subprocess.run([cov, "run", "selfcheck.py"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise SystemExit(f"the self-check failed under coverage:\n{(r.stdout + r.stderr)[-2000:]}")
    subprocess.run([cov, "combine", "-q"], cwd=ROOT, check=True)
    subprocess.run([cov, "json", "-q", "-o", str(OUT / "coverage.json")], cwd=ROOT, check=True)
    d = json.loads((OUT / "coverage.json").read_text(encoding="utf-8"))
    files = sorted(((v["summary"]["percent_covered"], f) for f, v in d["files"].items() if v["summary"]["num_statements"] >= 50))
    return d["totals"]["percent_covered"], [f"{p:5.1f}%  {f}" for p, f in files[:15]]


def selftest() -> None:
    assert verdict(49.9, 50.0, 1.0)[0] is False, "under the floor must fail"
    assert verdict(50.4, 50.0, 1.0) == (True, "coverage 50.4% (floor 50.0%)")
    assert "raise coverage_floor to 52.3" in verdict(52.37, 50.0, 1.0)[1], "a clear rise says to raise the floor"
    print("coverage gate self-check OK")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
        sys.exit(0)
    k = {p["name"]: p["default"] for p in json.loads((ROOT / "chips" / "selfcheck.quality.json").read_text(encoding="utf-8"))["params"]}
    pct, low = measure()
    ok, say = verdict(pct, k["coverage_floor"], k["coverage_raise_step"])
    (OUT / "summary.txt").write_text(f"{say}\n\nleast covered (50+ statements):\n" + "\n".join(low) + "\n", encoding="utf-8")
    print(f"  {say}")
    sys.exit(0 if ok else 1)
