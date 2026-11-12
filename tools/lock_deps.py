"""requirements.lock - every package the server installs, at one exact version, with the sha256 of each file (owner 2026-11-12,
"Yes, A and B" on the VS standards review: the same build on every server, a tampered package refused).

    python tools/lock_deps.py            make or refresh requirements.lock from requirements.txt, for the server (chip deps.lock)
    python tools/lock_deps.py --check    exit 1 when requirements.txt names a package the lock lacks (selfcheck runs this)
    python tools/lock_deps.py --audit    pip-audit on the lock (the commit script; a warning, never a stop)

deploy.sh installs from the lock when it exists (pip --require-hashes --no-deps), else from requirements.txt as before - so a
portal moves over by committing its lock, after its self-check passed with those versions on the server.
ponytail: pip's own resolver (--dry-run --report) for the server's platform and Python; no pip-tools or uv needed. pip judges
platform markers by THIS machine, so a package the server needs only on Linux is named in chip deps.lock extra (uvloop).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def K() -> dict:
    from core import engine  # noqa: PLC0415
    return engine.run("deps.lock")


def norm(n: str) -> str:
    return re.sub(r"[-_.]+", "-", n).lower()


def wanted(req: Path) -> set[str]:
    return {norm(m.group(1)) for ln in req.read_text(encoding="utf-8").splitlines()
            if (m := NAME.match(ln.split("#", 1)[0])) and not ln.lstrip().startswith("-")}


def lines(lock: Path) -> list[str]:
    """The lock's entries, one per package: a pip-compile style entry continued with a trailing backslash is joined first."""
    return re.sub(r"\\\r?\n", " ", lock.read_text(encoding="utf-8")).splitlines()


def locked(lock: Path) -> set[str]:
    return {norm(m.group(1)) for ln in lines(lock) if (m := NAME.match(ln)) and "==" in ln}


def problems(req: Path, lock: Path) -> list[str]:
    if not lock.is_file():
        return []
    w = K()["words"]
    bad = [w["missing"].format(name=n, req=req.name, lock=lock.name) for n in sorted(wanted(req) - locked(lock))]
    bad += [w["unpinned"].format(lock=lock.name, line=ln[:60]) for ln in lines(lock)
            if NAME.match(ln) and not ("==" in ln and "--hash=sha256:" in ln)]
    return bad


def make(req: Path, lock: Path) -> int:
    k = K()
    with tempfile.TemporaryDirectory() as t:
        src = Path(t) / "req.txt"
        src.write_text(req.read_text(encoding="utf-8") + "\n" + "\n".join(k["extra"]) + "\n", encoding="utf-8")
        cmd = [sys.executable, "-m", "pip", "install", *k["resolve_args"], "--report", str(Path(t) / "r.json"),
               "--python-version", str(k["python_version"]), "--target", str(Path(t) / "x"), "-r", str(src)]
        if k.get("constraints") and (HERE / k["constraints"]).is_file():   # the portal's tested pins: the lock stays inside them
            cmd += ["-c", str(HERE / k["constraints"])]
        cmd += [a for p in k["platforms"] for a in ("--platform", p)]
        r = subprocess.run(cmd, capture_output=True, text=True, env={**__import__("os").environ, **k["resolve_env"]})
        if r.returncode:
            print(r.stdout + r.stderr, file=sys.stderr)
            return 1
        rep = json.loads((Path(t) / "r.json").read_text(encoding="utf-8"))
    rows = sorted((i["metadata"]["name"], i["metadata"]["version"], i["download_info"]["archive_info"]["hashes"]["sha256"]) for i in rep["install"])
    head = [f"# {line}" for line in k["header"]]
    lock.write_text("\n".join([*head, *(f"{n}=={v} --hash=sha256:{h}" for n, v, h in rows)]) + "\n", encoding="utf-8", newline="\n")
    print(k["words"]["made"].format(lock=lock.name, n=len(rows), platform=k["platforms"][0], python=k["python_version"]))
    return 0


if __name__ == "__main__":
    req, lock = HERE / K()["requirements"], HERE / K()["lock"]
    if "--audit" in sys.argv:   # the commit script: known holes in the locked versions - a warning, never a stop
        if not lock.is_file():
            sys.exit(0)
        import shutil  # noqa: PLC0415
        if not shutil.which("pip-audit"):
            print(K()["words"]["no_audit"])
            sys.exit(0)
        r = subprocess.run(["pip-audit", "-r", str(lock), *K()["audit_args"]], capture_output=True, text=True)
        print((r.stdout + r.stderr).strip()[-3000:])
        sys.exit(0)
    if "--check" in sys.argv:
        bad = problems(req, lock)
        print("\n".join(bad) or K()["words"]["matches" if lock.is_file() else "none"].format(lock=lock.name, req=req.name))
        sys.exit(1 if bad else 0)
    sys.exit(make(req, lock))
