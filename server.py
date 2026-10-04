"""Server & sites - the VPS's sites, backups and disk, for the portal admin (2026-10-04 owner: "bring AstroStage's VPS
Console utilities under sf Portal Admin").

READ-ONLY by construction (2026-10-04 owner: "wire it read-only, no restart button"): every command only reads -
systemctl is-active/show, df, du, find, grep, tail - fixed here or built from chip server.settings rows (shlex-quoted),
never the caller's text. Restarts, deletes, cron edits, the terminal and deploys stay in AstroStage's VPS Console on
the owner's own machine. Chips decide what each reading means: server.disk, server.backup, server.site, server.trend.
"""
from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
import time
import urllib.request

from fastapi import HTTPException

from core import engine


def settings() -> dict:
    return engine.run("server.settings", {})


def say(key: str, **v) -> str:
    s = str(engine.run("ui.server", {}).get(key, key))
    for k, x in v.items():
        s = s.replace("{" + k + "}", str(x))
    return s


def _here() -> None:
    if not shutil.which("systemctl"):   # a laptop / Windows: there are no such sites here
        raise HTTPException(409, say("not_here"))


def _sh(cmd: str, timeout: int = 120) -> str:
    try:
        return subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=timeout).stdout
    except subprocess.TimeoutExpired:
        return ""


def _health(url: str) -> dict:
    """The site's own health answer, asked on 127.0.0.1 (so /health/run tells commit and jobs)."""
    try:
        with urllib.request.urlopen(url, timeout=5) as r:  # noqa: S310 - urls are chip rows, all http://127.0.0.1
            body = r.read(20000).decode("utf-8", "replace")
        try:
            j = json.loads(body)
            return j if isinstance(j, dict) else {"status": "healthy"}
        except ValueError:
            return {"status": "healthy"} if body.strip() == "ok" else {}
    except Exception:  # noqa: BLE001 - not answering is the fact
        return {}


def _site(s: dict) -> dict:
    active = _sh(f"systemctl is-active {shlex.quote(s['service'])}", 10).strip()
    h = _health(s["health"]) if s.get("health") else {}
    ok = str(h.get("status", "")).lower() in ("healthy", "ok")
    since = _sh(f"systemctl show -p ActiveEnterTimestamp --value {shlex.quote(s['service'])}", 10).strip()
    v = engine.run("server.site", {"active": active, "healthy": ok, "jobs": int(h.get("jobs_running") or 0)})
    return {**{k: s[k] for k in ("id", "label", "host", "service")}, **v, "active": active,
            "commit": str(h.get("commit") or "")[:7], "jobs": int(h.get("jobs_running") or 0), "since": since}


def _df(path: str = "/") -> dict:
    nums = [int(x) for x in _sh(f"df -B1 --output=size,used,avail {shlex.quote(path)} | tail -1").split()[:3] if x.isdigit()]
    total, used = (nums + [0, 0])[:2]
    return {"total": total, "used": used, **engine.run("server.disk", {"used": used, "total": total, "bands": settings()["bands"]})}


def _every_hours(line: str) -> float:
    """How often a cron line runs, in hours: `* * ...` hourly, `*/N` every N hours, a fixed hour = daily."""
    f = line.split()
    if len(f) < 6:
        return 0
    hour = f[1]
    return 1 if hour == "*" else int(hour[2:]) if re.fullmatch(r"\*/\d+", hour) else 24


def _backup(b: dict) -> dict:
    cron = _sh(f"grep -v '^#' {shlex.quote(b['cron'])} 2>/dev/null | grep -v '^[A-Z_]*=' | grep . | head -1", 10).strip()
    now = time.time()
    files = []
    for ln in _sh(f"find {shlex.quote(b['dir'])} -maxdepth 1 -type f -name {shlex.quote(b['pattern'])} -printf '%T@ %s\\n' 2>/dev/null").splitlines():
        p = ln.split()
        if len(p) == 2:
            files.append({"age_h": round((now - float(p[0])) / 3600, 2), "size": int(p[1])})
    mmin, mtime = re.search(r"-mmin \+(\d+)", cron), re.search(r"-mtime \+(\d+)", cron)
    keep_h = int(mmin.group(1)) // 60 if mmin else int(mtime.group(1)) * 24 if mtime else None
    every = _every_hours(cron) if cron else 0
    v = engine.run("server.backup", {"files": files, "every_h": every, "stale_factor": settings()["stale_factor"]})
    return {"id": b["id"], "label": b["label"], "dir": b["dir"], "plan": b.get("plan", ""), "cron": cron, "every_h": every, "keep_h": keep_h, **v}


def _history(k: dict, total: int) -> dict:
    """The last reading of each day from the hourly disk log, and which top folders grew over the same days."""
    days: dict[str, int] = {}
    for ln in _sh(f"tail -n 2000 {shlex.quote(k['history_file'])} 2>/dev/null").splitlines():
        p = ln.strip().split(",")
        if len(p) == 4 and p[2].isdigit():
            days[p[0][:10]] = int(p[2])
    keep = sorted(days)[-int(k["history_days"]):]
    series = [{"day": d, "used": days[d]} for d in keep]
    grew = []
    if len(keep) >= 2:
        first: dict[str, int] = {}
        last: dict[str, int] = {}
        for ln in _sh(f"tail -n 5000 {shlex.quote(k['history_folders'])} 2>/dev/null").splitlines():
            p = ln.strip().split(",")
            if len(p) == 3 and p[2].isdigit() and keep[0] <= p[0][:10] <= keep[-1]:
                first.setdefault(p[1], int(p[2]))
                last[p[1]] = int(p[2])
        grew = sorted(({"path": n, "size": last[n], "change": last[n] - first[n]} for n in last), key=lambda r: -r["change"])[:8]
    t0 = time.mktime(time.strptime(keep[0], "%Y-%m-%d")) if keep else 0
    t1 = time.mktime(time.strptime(keep[-1], "%Y-%m-%d")) if keep else 0
    trend = engine.run("server.trend", {"first": series[0]["used"] if series else 0, "last": series[-1]["used"] if series else 0,
                                        "days": round((t1 - t0) / 86400), "total": total})
    return {"series": series, "grew": grew, **trend}


def report() -> dict:
    _here()
    k = settings()
    disk = _df("/")
    return {"sites": [_site(s) for s in k["sites"]], "disk": disk, "backups": [_backup(b) for b in k["backups"]],
            "history": _history(k, disk["total"]), "roots": k["du_roots"]}


def du(path: str) -> dict:
    """One folder's children by size (this disk only). Read-only; any absolute folder."""
    _here()
    base = re.sub(r"/+", "/", "/" + str(path or "/").strip()).rstrip("/") or "/"
    if ".." in base.split("/") or "\0" in base:
        raise HTTPException(400, "bad path")
    rows = []
    for ln in _sh(f"du -x -d1 -B1 {shlex.quote(base)} 2>/dev/null", 600).splitlines():
        p = ln.split("\t", 1)
        if len(p) == 2 and p[0].isdigit() and p[1] != base:
            rows.append({"path": p[1], "size": int(p[0])})
    rows.sort(key=lambda r: -r["size"])
    return {"path": base, "rows": rows[: int(settings()["du_top"])], "disk": _df(base)}


if __name__ == "__main__":  # ponytail: the parsers that read the box
    assert _every_hours("23 * * * * root x") == 1 and _every_hours("0 */4 * * * root x") == 4 and _every_hours("5 3 * * * root x") == 24
    import store  # noqa: F401 - registers this portal's chips
    v = engine.run("server.backup", {"files": [{"age_h": 50, "size": 1}], "every_h": 1, "stale_factor": 2})
    assert v["state"] == "late", v
    print("server OK")
