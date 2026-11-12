"""Lint and type gate that only ratchets down (W1.3, 2026-11-11 - scorecard B9: no ruff, no mypy, no CI).

    python tools/quality_gate.py             ruff + mypy counts within chip selfcheck.quality's ceilings; the ratchet never
                                             loosened against git HEAD; every selfcheck part has its CI job
    python tools/quality_gate.py --selftest

The ceilings are TODAY's counts. A count above its ceiling fails with the new findings; a count below it says what to
lower the ceiling to (Chip Builder, chip selfcheck.quality). Raising a ceiling (or lowering the coverage floor) against
the last commit fails: the gate only tightens.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHIP = "chips/selfcheck.quality.json"
BIN = Path(sys.executable).parent


def knobs(text: str) -> dict:
    return {p["name"]: p["default"] for p in json.loads(text)["params"]}


def chip() -> dict:
    return knobs((ROOT / CHIP).read_text(encoding="utf-8"))


def at_head() -> dict | None:
    r = subprocess.run(["git", "show", f"HEAD:{CHIP}"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    return knobs(r.stdout) if r.returncode == 0 and r.stdout.strip() else None


def loosened(now: dict, before: dict | None) -> list[str]:
    """Every knob that moved the wrong way since the last commit (ceilings only fall, floors only rise)."""
    if not before:
        return []
    bad = [f"{k} {before[k]} -> {now[k]}" for k in now.get("ceilings", []) if k in before and now[k] > before[k]]
    return bad + [f"{k} {before[k]} -> {now[k]}" for k in now.get("floors", []) if k in before and now[k] < before[k]]


def places() -> list[Path]:
    """Where a dev tool may sit: beside python, or the user Scripts folder (Windows Store Python / pip --user - 2026-11-12
    the gate said 'ruff is not installed' on a machine that had it there)."""
    import sysconfig
    return [BIN, Path(sysconfig.get_path("scripts")), Path(sysconfig.get_path("scripts", f"{os.name}_user"))]


def tool(name: str) -> str:
    file = name + (".exe" if sys.platform == "win32" else "")
    exe = next((d / file for d in places() if (d / file).exists()), BIN / file)
    if not exe.exists():
        raise SystemExit(f"{name} is not installed in this Python - pip install --require-hashes -r requirements-dev.lock")
    return str(exe)


def ruff() -> list[str]:
    r = subprocess.run([tool("ruff"), "check", ".", "-q", "--output-format=concise"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return [x for x in r.stdout.splitlines() if re.match(r"\S+:\d+:\d+: ", x)]


def mypy() -> list[str]:
    r = subprocess.run([tool("mypy")], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode not in (0, 1) or not re.search(r"^(Found \d+ error|Success)", r.stdout, re.M):
        raise SystemExit(f"mypy did not run: {(r.stdout + r.stderr)[-800:]}")
    return [x for x in r.stdout.splitlines() if re.match(r"\S+:\d+: error:", x)]


def selfcheck_parts() -> set[str]:
    """The part names selfcheck.py runs (its own dict + selfcheck_quality.PARTS)."""
    text = (ROOT / "selfcheck.py").read_text(encoding="utf-8")
    line = next(x for x in text.splitlines() if "for name, fn in {" in x)
    sys.path.insert(0, str(ROOT))
    import selfcheck_quality  # noqa: PLC0415
    return set(re.findall(r'"(\w+)":\s*\w', line)) | set(selfcheck_quality.PARTS) | set(selfcheck_quality.SLOW)


def ci_parts() -> set[str]:
    wf = (ROOT / ".github" / "workflows" / "check.yml").read_text(encoding="utf-8")
    m = re.search(r"part:\s*\[([^\]]*)\]", wf)
    return {x.strip() for x in m.group(1).split(",")} if m else set()


def gate() -> int:
    k, fails = chip(), []
    moved = loosened(k, at_head())
    if moved:
        fails.append("a ratchet only tightens - chip selfcheck.quality moved the wrong way: " + "; ".join(moved))
    missing = selfcheck_parts() - ci_parts() - set(k["ci_elsewhere"])
    if missing:
        fails.append(f"selfcheck parts with no CI job (.github/workflows/check.yml matrix part): {sorted(missing)}")
    for name, found, cap in (("ruff", ruff(), k["ruff_ceiling"]), ("mypy", mypy(), k["mypy_ceiling"])):
        if len(found) > cap:
            fails.append(f"{name}: {len(found)} findings, ceiling {cap} - fix the new ones:\n    " + "\n    ".join(found[-15:]))
        elif len(found) < cap:
            print(f"  {name}: {len(found)} < ceiling {cap} - lower ruff/mypy ceiling to {len(found)} in chip selfcheck.quality")
        print(f"  {name}: {len(found)} findings (ceiling {cap})")
    for f in fails:
        print("FAILED", f)
    return 1 if fails else 0


def selftest() -> None:
    import sysconfig
    assert Path(sysconfig.get_path("scripts", f"{os.name}_user")) in places(), "the user Scripts folder must be searched for ruff/mypy/pip-audit"
    k = {"ceilings": ["ruff_ceiling"], "floors": ["coverage_floor"], "ruff_ceiling": 10, "coverage_floor": 50.0}
    assert loosened(k | {"ruff_ceiling": 11}, k) == ["ruff_ceiling 10 -> 11"], "a raised ceiling must fail"
    assert loosened(k | {"coverage_floor": 49.0}, k) == ["coverage_floor 50.0 -> 49.0"], "a lowered floor must fail"
    assert loosened(k | {"ruff_ceiling": 9, "coverage_floor": 51.0}, k) == [], "tightening is always fine"
    assert loosened(k, None) == [], "no history, nothing to compare"
    print("quality gate self-check OK")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
        sys.exit(0)
    sys.exit(gate())
