"""Make requirements.lock and requirements-dev.lock (W1.3, 2026-11-11): every package pinned with the sha256 of every file
PyPI has for that version, resolved for EACH platform we run on (CI and the VPS are Linux, the owner's PC is Windows), and
a package only one platform needs carries its marker - a lock made on Windows alone misses uvloop (uvicorn[standard] on
Linux) and a hash-checked install there fails.

    python tools/make_lock.py          (needs the network; a few minutes)
Install:  pip install --require-hashes -r requirements.lock   (+ -r requirements-dev.lock for the gate's tools)

Platforms and the Python version are in chip selfcheck.quality (lock_platforms, python_version).
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parent.parent


def knobs() -> dict:
    return {p["name"]: p["default"] for p in json.loads((ROOT / "chips" / "selfcheck.quality.json").read_text(encoding="utf-8"))["params"]}


MARKERS = {"linux": {"sys_platform": "linux", "platform_system": "Linux", "os_name": "posix", "platform_machine": "x86_64"},
           "win32": {"sys_platform": "win32", "platform_system": "Windows", "os_name": "nt", "platform_machine": "AMD64"}}
TMP = ROOT / "tmp" / "lock"


def tested() -> Path:
    """The versions this portal's own environment runs and its self-check passed on: the lock holds THOSE, never whatever
    PyPI has today (scorecard B13: an unpinned deploy may pull an untested major version)."""
    out = subprocess.run([sys.executable, "-m", "pip", "freeze", "--exclude-editable"], capture_output=True, text=True, check=True).stdout
    TMP.mkdir(parents=True, exist_ok=True)
    (TMP / "tested.txt").write_text("\n".join(x for x in out.splitlines() if "==" in x and not x.startswith(("pip==", "setuptools=="))) + "\n", encoding="utf-8")
    return TMP / "tested.txt"


def dry_run(reqs: list[Path], tags: list[str], python: str, constraints: Path) -> list[dict]:
    args = [sys.executable, "-m", "pip", "install", "--dry-run", "--ignore-installed", "--quiet", "--report", "-", "-c", str(constraints),
            *[x for t in tags for x in ("--platform", t)], "--python-version", python, "--only-binary=:all:", "--timeout", "90", "--retries", "8"]
    for r in reqs:
        args += ["-r", str(r)]
    return json.loads(subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True).stdout)["install"]


def resolve(reqs: list[str], plat: str, tag: list[str], python: str, constraints: Path) -> dict[str, str]:
    """{name: version} for that platform. pip evaluates markers against THIS machine, so a dependency only the target
    needs (uvloop under uvicorn[standard] on Linux) is found by reading each package's requires_dist with the target's
    markers and asking again until nothing is missing."""
    env = MARKERS[plat] | {"python_version": python, "python_full_version": python + ".0", "implementation_name": "cpython",
                           "platform_python_implementation": "CPython"}
    extra: list[str] = []
    while True:
        (TMP / f"extra-{plat}.txt").write_text("\n".join(extra) + "\n", encoding="utf-8")
        items = dry_run([ROOT / r for r in reqs] + [TMP / f"extra-{plat}.txt"], tag, python, constraints)
        got = {canonicalize_name(i["metadata"]["name"]): i["metadata"]["version"] for i in items}
        missing = []
        for i in items:
            for spec in i["metadata"].get("requires_dist") or []:
                r = Requirement(spec)
                wanted = any(r.marker is None or r.marker.evaluate(env | {"extra": e}) for e in [""] + (i.get("requested_extras") or []))
                if wanted and canonicalize_name(r.name) not in got:
                    missing.append(f"{r.name}{'[' + ','.join(sorted(r.extras)) + ']' if r.extras else ''}{r.specifier}")
        if not missing:
            return got
        extra += sorted(set(missing) - set(extra))


def hashes(name: str, version: str, tries: int = 6) -> list[str]:
    for i in range(tries):            # PyPI over a slow link times out now and then
        try:
            with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json", timeout=90) as r:   # noqa: S310 - PyPI
                return sorted({u["digests"]["sha256"] for u in json.load(r)["urls"]})
        except OSError:
            if i == tries - 1:
                raise
            time.sleep(5 * (i + 1))
    return []


def lines(per_platform: dict[str, dict[str, str]], skip: set[str]) -> list[str]:
    names = sorted({n for pins in per_platform.values() for n in pins} - skip)
    out = []
    for n in names:
        where = {p: pins[n] for p, pins in per_platform.items() if n in pins}
        for ver in sorted(set(where.values())):
            plats = [p for p, v in where.items() if v == ver]
            marker = "" if len(plats) == len(per_platform) else " ; " + " or ".join(f'sys_platform == "{p}"' for p in plats)
            out.append(f"{n}=={ver}{marker} \\\n" + " \\\n".join(f"    --hash=sha256:{h}" for h in hashes(n, ver)))
    return out


def main() -> None:
    k = knobs()
    plats = k["lock_platforms"]            # {"linux": [manylinux tags...], "win32": ["win_amd64"]}
    head = "# Made by tools/make_lock.py - do not edit; change {src} and run it again.\n# Install: pip install --require-hashes -r {out}\n"
    pins = tested()
    run = {p: resolve(["requirements.txt"], p, tag, k["python_version"], pins) for p, tag in plats.items()}
    (ROOT / "requirements.lock").write_text(head.format(src="requirements.txt", out="requirements.lock") + "\n".join(lines(run, set())) + "\n",
                                            encoding="utf-8", newline="\n")
    both = {p: resolve(["requirements.txt", "requirements-dev.txt"], p, tag, k["python_version"], pins) for p, tag in plats.items()}
    dev = {p: {n: v for n, v in pins.items() if run[p].get(n) != v} for p, pins in both.items()}
    (ROOT / "requirements-dev.lock").write_text(head.format(src="requirements-dev.txt", out="requirements-dev.lock") + "\n".join(lines(dev, set())) + "\n",
                                                encoding="utf-8", newline="\n")
    print(f"requirements.lock: {len(set().union(*run.values()))} packages; requirements-dev.lock: {len(set().union(*dev.values()))}")


if __name__ == "__main__":
    main()
