"""Is this Python on requirements.lock - and if not, which venv on this computer is? (owner 2026-11-23, "make the gate venv
the default for DT checks" -> "carry it to all the portals").

    python tools/lockenv.py --selftest

selfcheck.py calls locked_python() first: off the lock, it runs itself again in the first venv of chip deps.lock gate_venvs
whose packages ARE the lock. Off the lock the counts are wrong (2026-11-13: the VPS, which installs the lock, counted 3 more
mypy errors and its deploy stopped). No such venv (CI, the VPS) = runs as before.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def knobs(text: str) -> dict:
    return {p["name"]: p["default"] for p in json.loads(text)["params"]}


def off_lock(root: Path = ROOT) -> list[str]:
    """Locked packages installed here at another version. The counts depend on them: 2026-11-13 the ceilings were measured
    in a venv with other fastapi/httpx versions and the VPS (which installs the lock) counted 3 more mypy errors, so its
    deploy stopped. A locked package that is not installed is off the lock too, unless chip deps.lock names it in `extra`
    (Linux-only, uvloop): 2026-11-16 a hash install of the Linux lock failed on Windows, the venv stayed empty, every
    package was skipped and the mypy ceiling was set from the wrong count (481; the lock counts 483)."""
    from importlib import metadata
    lk = knobs((root / "core" / "chips" / "deps.lock.json").read_text(encoding="utf-8"))
    out, linux_only = [], {x.lower() for x in lk.get("extra", [])}
    for f in (lk[k] for k in ("lock", "dev_lock") if k in lk):     # an older deps.lock chip has no dev_lock
        p = root / f
        for name, ver in re.findall(r"^([A-Za-z0-9_.\-]+)==([^\s;\\]+)", p.read_text(encoding="utf-8") if p.exists() else "", re.M):
            try:
                have = metadata.version(name)
            except metadata.PackageNotFoundError:
                if name.lower() not in linux_only:
                    out.append(f"{name} not installed (lock {ver})")
                continue
            if have != ver:
                out.append(f"{name} {have} (lock {ver})")
    return out



def locked_python(root: Path = ROOT) -> str | None:
    """2026-11-23 owner ("make the gate venv the default for DT checks"): this computer's Python is off the lock, so the counts
    are wrong. The first venv in chip deps.lock gate_venvs whose packages ARE the lock -> its python; None when this Python is
    already on the lock, or no such venv exists (CI, the VPS: they install the lock)."""
    import glob  # noqa: PLC0415
    if not off_lock(root):
        return None
    lk = knobs((root / "core" / "chips" / "deps.lock.json").read_text(encoding="utf-8"))
    for pat in lk.get("gate_venvs") or []:
        for d in sorted(glob.glob(pat)):
            py = Path(d) / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            if py.is_file() and Path(py).resolve() != Path(sys.executable).resolve():
                r = subprocess.run([str(py), "-c", "import sys; sys.path.insert(0, 'tools'); import lockenv; sys.exit(1 if lockenv.off_lock() else 0)"],
                                   cwd=root, capture_output=True, timeout=120)
                if r.returncode == 0:
                    return str(py)
    return None


def selftest() -> None:
    import tempfile  # noqa: PLC0415
    with tempfile.TemporaryDirectory() as t:
        (Path(t) / "core" / "chips").mkdir(parents=True)
        (Path(t) / "core" / "chips" / "deps.lock.json").write_text(json.dumps({"params": [{"name": "lock", "default": "a.lock"},
                                                                                       {"name": "dev_lock", "default": "b.lock"},
                                                                                       {"name": "extra", "default": ["linux-only-xyz"]}]}))
        (Path(t) / "a.lock").write_text("pip==0.0.1 --hash=sha256:x\nno-such-package-xyz==1.0 --hash=sha256:y\n"
                                        "linux-only-xyz==1.0 --hash=sha256:z\n")
        assert [x.split()[0] for x in off_lock(Path(t))] == ["pip", "no-such-package-xyz"], \
            "a locked package at another version, or not installed at all (an empty venv), must be named; a Linux-only extra skipped"
        assert locked_python(Path(t)) is None, "no gate_venvs knob -> no other Python (runs as before)"
        bad = Path(t) / "venvs" / "gate-x"   # a venv that is not on the lock either is never picked
        (bad / ("Scripts" if os.name == "nt" else "bin")).mkdir(parents=True)
        (Path(t) / "core" / "chips" / "deps.lock.json").write_text(json.dumps({"params": [{"name": "lock", "default": "a.lock"},
                                                                                       {"name": "gate_venvs", "default": [str(Path(t) / "venvs" / "gate-*")]}]}))
        assert locked_python(Path(t)) is None, "a gate venv with no python (or off the lock) must never be picked"
    print("lockenv self-check OK")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
