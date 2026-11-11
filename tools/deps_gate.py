"""Dependencies gate (W1.3, 2026-11-11 - scorecard B13: no lock file, no audit, a pip install of >= ranges at every deploy).

    python tools/deps_gate.py             requirements.lock (and requirements-dev.lock) pin every package with its hashes,
                                          the lock meets requirements.txt, CI uses the one Python version, pip-audit finds
                                          no known vulnerability (ids allowed only in chip selfcheck.quality audit_ignore)
    python tools/deps_gate.py --selftest

Make the locks again after changing requirements.txt / requirements-dev.txt:  python tools/make_lock.py
Install:  pip install --require-hashes -r requirements.lock
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parent.parent
BIN = Path(sys.executable).parent


def knobs() -> dict:
    return {p["name"]: p["default"] for p in json.loads((ROOT / "chips" / "selfcheck.quality.json").read_text(encoding="utf-8"))["params"]}


def pins(lock_text: str) -> tuple[dict[str, str], list[str]]:
    """{name: version} of a pip-compile lock, and the pins that carry no hash."""
    got, unhashed = {}, []
    for block in re.split(r"\n(?=[A-Za-z0-9])", lock_text):
        m = re.match(r"([A-Za-z0-9._-]+)==([^\s\\;]+)", block)
        if m:
            got[canonicalize_name(m.group(1))] = m.group(2)
            if "--hash=sha256:" not in block:
                unhashed.append(m.group(1))
    return got, unhashed


def unmet(req_text: str, locked: dict[str, str]) -> list[str]:
    bad = []
    for line in req_text.splitlines():
        line = line.split("#")[0].strip()
        if not line or line.startswith("-"):
            continue
        r = Requirement(line)
        v = locked.get(canonicalize_name(r.name))
        if v is None or not r.specifier.contains(v, prereleases=True):
            bad.append(f"{line} (lock has {v or 'nothing'})")
    return bad


def audit(lock: Path, ignore: list[str]) -> list[str]:
    exe = BIN / ("pip-audit" + (".exe" if sys.platform == "win32" else ""))
    if not exe.exists():
        raise SystemExit("pip-audit is not installed - pip install --require-hashes -r requirements-dev.lock")
    r = subprocess.run([str(exe), "-r", str(lock), "--require-hashes", "--no-deps", "--disable-pip", "-f", "json", "--progress-spinner", "off"],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        deps = json.loads(r.stdout)["dependencies"]
    except (ValueError, KeyError):
        raise SystemExit(f"pip-audit could not run (it needs the network): {(r.stderr or r.stdout)[-600:]}") from None
    return [f"{d['name']} {d['version']}: {v['id']} (fix {', '.join(v.get('fix_versions') or ['none'])})"
            for d in deps for v in d.get("vulns", []) if v["id"] not in ignore and not set(v.get("aliases", [])) & set(ignore)]


def gate() -> int:
    k, fails = knobs(), []
    for lock, req in (("requirements.lock", "requirements.txt"), ("requirements-dev.lock", "requirements-dev.txt")):
        if not (ROOT / lock).is_file():
            fails.append(f"{lock} is missing - make it: python tools/make_lock.py")
            continue
        locked, unhashed = pins((ROOT / lock).read_text(encoding="utf-8"))
        if unhashed:
            fails.append(f"{lock}: pins with no hash {unhashed}")
        miss = unmet((ROOT / req).read_text(encoding="utf-8"), locked)
        if miss:
            fails.append(f"{lock} does not meet {req}: {miss} - run python tools/make_lock.py")
        print(f"  {lock}: {len(locked)} packages, every one pinned with its hash")
    wf = (ROOT / ".github" / "workflows" / "check.yml").read_text(encoding="utf-8")
    ver = k["python_version"]
    if set(re.findall(r"python-version:\s*\"?([\d.]+)", wf)) != {ver}:
        fails.append(f"CI must use the one Python version {ver} (chip selfcheck.quality python_version)")
    if f'python_version = "{ver}"' not in (ROOT / "pyproject.toml").read_text(encoding="utf-8"):
        fails.append(f"pyproject.toml [tool.mypy] python_version must be {ver}")
    if not fails:
        vulns = audit(ROOT / "requirements.lock", k["audit_ignore"])
        if vulns:
            fails.append("pip-audit found known vulnerabilities - upgrade, re-lock:\n    " + "\n    ".join(vulns))
        else:
            print("  pip-audit: no known vulnerabilities in requirements.lock")
    for f in fails:
        print("FAILED", f)
    return 1 if fails else 0


def selftest() -> None:
    lock = "fastapi==0.110.0 \\\n    --hash=sha256:aa\nuvicorn==0.20.0\n    # via x\n"
    got, unhashed = pins(lock)
    assert got == {"fastapi": "0.110.0", "uvicorn": "0.20.0"} and unhashed == ["uvicorn"], (got, unhashed)
    assert unmet("fastapi>=0.110\nuvicorn[standard]>=0.27\n# note\n", got) == ["uvicorn[standard]>=0.27 (lock has 0.20.0)"], "a lock below requirements.txt must fail"
    assert unmet("pypdf>=6\n", got) == ["pypdf>=6 (lock has nothing)"], "a package missing from the lock must fail"
    print("dependencies gate self-check OK")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
        sys.exit(0)
    sys.exit(gate())
