"""Restore drill (2026-11-18 gap audit C1-13; gap plan: "a backup nobody restored is a hope, not a backup").

Monthly from /etc/cron.d/starter-restore-drill (DEPLOY.md step 6, beside the backup line):
  1. the newest backup in $SF_BACKUPS (chip health.settings drill_backup_glob) is unpacked into a temp folder;
  2. store integrity: every .json file parses, every .sqlite3 file passes PRAGMA integrity_check;
  3. api smoke: the portal is started on the restored copy (PORTAL_DATA) and drill_smoke_path must answer 200;
  4. the date and the result go to the live data folder (record drill_record) - core/health.py's `drill` probe turns the
     owners' bar red when the last drill failed or the last good one is older than drill_max_days.
The live portal is never stopped or touched; the temp folder is removed afterwards. Exit 0 = good, 1 = failed.

    python tools/restore_drill.py [--app DIR] [--backups DIR]       (defaults: $SF_APP or this checkout, $SF_BACKUPS)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from core import engine  # noqa: E402

SMOKE = ("import sys\nfrom fastapi.testclient import TestClient\nimport app\n"
         "r = TestClient(app.app).get(sys.argv[1])\nprint(r.status_code)\nsys.exit(0 if r.status_code == 200 else 1)\n")


def newest(backups: Path, glob: str) -> Path | None:
    found = [p for p in backups.glob(glob) if p.is_file()] if backups.is_dir() else []
    return max(found, key=lambda p: p.stat().st_mtime) if found else None


def integrity(data: Path) -> int:
    """How many files were checked; raises with the first bad file's name."""
    n = 0
    for f in sorted(data.rglob("*.json")):
        try:
            json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            raise RuntimeError(f"{f.relative_to(data)}: {type(e).__name__}") from None
        n += 1
    for f in sorted(data.rglob("*.sqlite3")):
        c = sqlite3.connect(f)
        try:
            got = c.execute("PRAGMA integrity_check").fetchone()[0]
        except sqlite3.Error as e:
            got = str(e)
        finally:
            c.close()
        if got != "ok":
            raise RuntimeError(f"{f.relative_to(data)}: {got}")
        n += 1
    return n


def smoke(app: Path, data: Path, path: str, timeout: float) -> None:
    env = os.environ | {"PORTAL_DATA": str(data), "TV_DATA": str(data)}
    r = subprocess.run([sys.executable, "-c", SMOKE, path], cwd=app, env=env, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        tail = (r.stdout.strip().splitlines() or r.stderr.strip().splitlines() or ["no answer"])[-1]
        raise RuntimeError(engine.say("health.messages", "drill_smoke_bad", path=path, got=tail[:200]))


def record(app: Path, name: str, rec: dict) -> None:
    """Written beside the store's own files, the way the store writes (temp file + rename)."""
    data = Path(os.getenv("PORTAL_DATA") or app / "data")
    data.mkdir(parents=True, exist_ok=True)
    tmp = data / f"{name}.json.tmp"
    tmp.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    os.chmod(tmp, 0o644)
    os.replace(tmp, data / f"{name}.json")


def drill(app: Path, backups: Path) -> dict:
    k = engine.run("health.settings")
    rec: dict = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "ok": False, "backup": "", "checked": 0, "why": ""}
    work = Path(tempfile.mkdtemp(prefix="restore-drill."))
    try:
        b = newest(backups, k["drill_backup_glob"])
        if b is None:
            raise RuntimeError(engine.say("health.messages", "drill_no_backup", folder=backups))
        rec["backup"] = b.name
        with tarfile.open(b) as t:
            t.extractall(work, filter="data") if hasattr(tarfile, "data_filter") else t.extractall(work)  # noqa: S202
        data = work / "data"
        if not data.is_dir():
            raise RuntimeError(engine.say("health.messages", "drill_no_data", backup=b.name))
        rec["checked"] = integrity(data)
        smoke(app, data, k["drill_smoke_path"], float(k["drill_smoke_timeout_s"]))
        rec["ok"] = True
    except (RuntimeError, OSError, tarfile.TarError, subprocess.TimeoutExpired) as e:
        rec["why"] = str(e)[: int(k["reason_chars"])]
    finally:
        shutil.rmtree(work, ignore_errors=True)
    record(app, k["drill_record"], rec)
    return rec


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--app", default=os.getenv("SF_APP") or str(HERE))
    ap.add_argument("--backups", default=os.getenv("SF_BACKUPS") or "")
    a = ap.parse_args()
    if not a.backups:
        sys.exit("say where the backups are: --backups DIR or SF_BACKUPS (the same folder as the backup cron line)")
    got = drill(Path(a.app), Path(a.backups))
    print(json.dumps(got))
    sys.exit(0 if got["ok"] else 1)
