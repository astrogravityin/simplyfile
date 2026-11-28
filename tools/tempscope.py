"""One temp folder per self-check run, removed after the run's process has ended (2026-11-28, chip selfcheck.temp).

    python tools/tempscope.py --selftest

C: held 7,720 tmp*/perm-* folders (46 GB): every self-check part made its own temp folder (mkdtemp with no cleanup, or
TemporaryDirectory(ignore_cleanup_errors=True) beaten by a sqlite file still held on Windows) and nothing said so. Main
Machine then failed machine.check min_disk_gb and every request sat at Sent.

So selfcheck.py's __main__ calls scoped(): the run goes on in a child process whose TEMP/TMP/TMPDIR is ONE run folder
(on D: per the chip); when the child has ended every handle it held is closed, and the folder goes. A folder that will not
go is retried, then named on stderr and the run FAILS - never a silent leftover. A run folder left by a killed run is
removed by the next run.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARK = "SELFCHECK_TEMP_SCOPE"


def knobs(root: Path = ROOT) -> dict:
    return {p["name"]: p["default"] for p in json.loads((root / "core" / "chips" / "selfcheck.temp.json").read_text(encoding="utf-8"))["params"]}


def base(k: dict) -> Path:
    for r in k["roots"]:
        p = Path(r)
        if p.is_absolute() and Path(p.anchor).exists():
            return p
    # 2026-11-28 VPS: /tmp/selfcheck made by a root-run check (0755 root) refused gymyfy.service's run folder - one parent
    # per user, so no user's parent ever blocks another's (and a sweep only sees its own user's runs)
    return Path(tempfile.gettempdir()) / (f"selfcheck-{os.getuid()}" if hasattr(os, "getuid") else "selfcheck")


def _writable(fn, path, _exc) -> None:
    """A read-only file (git's objects, 2026-11-28 ValueStreamCC's assurance check) is made writable and removed again."""
    for x in {path, os.path.dirname(path)}:       # 2026-11-28 review: Linux - add write, keep the rest; the folder too
        os.chmod(x, os.stat(x).st_mode | stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC * os.path.isdir(x))
    fn(path)


def remove(d: Path, k: dict) -> str:
    """'' when d is gone; else the last error, after chip retries."""
    err = ""
    kw = {"onexc": _writable} if sys.version_info >= (3, 12) else {"onerror": _writable}
    for _ in range(int(k["retries"])):
        try:
            shutil.rmtree(d, **kw)
            return ""
        except FileNotFoundError:
            return ""
        except OSError as e:
            err = f"{type(e).__name__}: {e}"
            time.sleep(float(k["wait_s"]))
    return err


def sweep(b: Path, k: dict) -> list[str]:
    """Run folders older than stale_hours (a killed run) -> removed; the ones that will not go are returned."""
    old = time.time() - float(k["stale_hours"]) * 3600
    left = []
    for d in b.iterdir() if b.is_dir() else []:
        try:                                          # 2026-11-28 review: two runs sweeping at once - the other took it
            stale = d.is_dir() and d.stat().st_mtime < old
        except OSError:
            continue
        if stale and remove(d, k | {"retries": 1}):
            left.append(str(d))
    return left


def scoped(argv: list[str], name: str, root: Path = ROOT) -> int | None:
    """None inside a scoped run (go on). Else: run argv with TEMP = a fresh run folder, remove it, return the exit code
    (1 when the folder could not be removed, with the reason printed)."""
    # inside a scope only when the mark IS this process's temp folder (2026-11-28 review: a stale mark from an old shell
    # skipped the scope and the run leaked to the system temp again)
    if os.environ.get(MARK) and os.environ[MARK] == tempfile.gettempdir() and Path(os.environ[MARK]).is_dir():
        return None
    k = knobs(root)
    b = base(k)
    b.mkdir(parents=True, exist_ok=True)
    for s in sweep(b, k):
        print(f"tempscope: an old run folder will not go: {s}", file=sys.stderr, flush=True)
    d = Path(tempfile.mkdtemp(prefix=f"{name}-", dir=b))
    env = os.environ | {MARK: str(d), "TEMP": str(d), "TMP": str(d), "TMPDIR": str(d)}
    try:                                              # 2026-11-28 review: Ctrl-C or any error still removes the folder
        rc = subprocess.run(argv, env=env, check=False).returncode
    finally:
        err = remove(d, k)
    if err:
        print(f"tempscope: FAILED - the run left {d} and it will not go ({err}). A process of the run still holds a file in it:"
              " close it (a sqlite connection, a server child) before the run ends.", file=sys.stderr, flush=True)
        return rc or 1
    return rc


def _selftest() -> None:
    with tempfile.TemporaryDirectory() as t:
        r = Path(t)
        (r / "core" / "chips").mkdir(parents=True)
        k = knobs() | {"roots": [str(r / "runs")], "retries": 2, "wait_s": 0}
        (r / "core" / "chips" / "selfcheck.temp.json").write_text(json.dumps({"params": [{"name": n, "default": v} for n, v in k.items()]}), encoding="utf-8")
        assert base(k) == r / "runs"
        own = base({"roots": ["Q:/nowhere", "relative/x"]})
        assert own.parent == Path(tempfile.gettempdir()) and own.name == ("selfcheck-%d" % os.getuid() if hasattr(os, "getuid") else "selfcheck"),             "the fallback parent is shared between users: a root-made one refuses a service user's run (VPS 2026-11-28)"
        saved = dict(os.environ)
        # a run that leaks the way the self-check did: mkdtemp never removed, TemporaryDirectory with an open sqlite file
        leak = ("import tempfile, sqlite3, pathlib; d = pathlib.Path(tempfile.mkdtemp()); (d / 'secret.json').write_text('{}');"
                "t = tempfile.TemporaryDirectory(ignore_cleanup_errors=True); c = sqlite3.connect(pathlib.Path(t.name) / 'connect.db');"
                "c.execute('create table runs (id integer primary key)'); c.commit(); t.cleanup(); import os, stat;"
                "(d / 'obj').write_text('x'); os.chmod(d / 'obj', stat.S_IREAD);"   # read-only, like a git object
                " assert pathlib.Path(os.environ['SELFCHECK_TEMP_SCOPE']) in d.parents, 'the leak landed outside the run folder'")
        os.environ.pop(MARK, None)
        try:
            assert scoped([sys.executable, "-c", leak], "leak", r) == 0
            assert list((r / "runs").iterdir()) == [], "a run left a folder behind"
            assert scoped([sys.executable, "-c", "raise SystemExit(3)"], "rc", r) == 3, "the run's exit code is kept"
            real_run = subprocess.run
            subprocess.run = lambda *a, **kw: (_ for _ in ()).throw(KeyboardInterrupt())  # type: ignore[assignment]
            try:
                scoped([sys.executable, "-c", "0"], "ctrlc", r)
                raise AssertionError("Ctrl-C was swallowed")
            except KeyboardInterrupt:
                pass
            finally:
                subprocess.run = real_run
            assert list((r / "runs").iterdir()) == [], "a Ctrl-C left the run folder behind"
            os.environ[MARK] = str(r / "old-shell")          # a stale mark from another shell: still scoped
            assert scoped([sys.executable, "-c", "0"], "stale", r) == 0, "a stale mark skipped the scope"
            os.environ.pop(MARK)
            # a folder held open past the run's end: retried, named, and the run fails
            (r / "runs" / "held").mkdir()
            orig = shutil.rmtree
            shutil.rmtree = lambda p, *a, **kw: (_ for _ in ()).throw(PermissionError("held"))  # type: ignore[assignment]
            try:
                assert remove(r / "runs" / "held", k).startswith("PermissionError"), "a folder that will not go is reported"
            finally:
                shutil.rmtree = orig
            old = r / "runs" / "killed-run"
            old.mkdir()
            os.utime(old, (0, 0))
            assert sweep(r / "runs", k) == [] and not old.exists(), "a killed run's folder is removed by the next run"
        finally:
            os.environ.clear()
            os.environ.update(saved)
    print("tempscope selftest OK")


if __name__ == "__main__" and "--selftest" in sys.argv:
    _selftest()
