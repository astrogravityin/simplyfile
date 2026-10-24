"""Health check - is everything the portal needs working? (2026-10-15 owner: "I see email but they are too many. Can we
give a warning in the portal that replaces the message and does not add to the list continuously"; built 2026-10-23 as
the first agent, recipe agents.recipe.ag_health.)

A module attaches one probe:   health.probe("free_voice", fn)      fn() -> {"ok": bool, "say": "plain words"}
Core attaches the disk probe; the portal attaches the rest (its voice, its AI keys, YouTube, its own certificate).

Two agent actions (chip agents.actions):
  health.check  (read)   every probe once - a probe that raises is a problem in its own words, never a crash
  health.warn   (write)  the owners' warning bar becomes exactly this answer (replaced, never appended); the bell rings
                         ONCE for a problem that is new since the last check (feedback: alert once, not daily)
The shell shows the bar to owners on every page (bootstrap `health`); a fixed problem leaves it at the next check.
Every number is chip health.settings; every sentence chip health.messages.
"""
from __future__ import annotations

import shutil
import socket
import ssl
import time
from typing import Callable

from fastapi import Request

from core import agents, bell, engine, store

PROBES: dict[str, Callable[[], dict]] = {}
BAR = "health_bar"


def settings() -> dict:
    return engine.run("health.settings")


def say(key: str, **values) -> str:
    return engine.say("health.messages", key, **values)


def probe(probe_id: str, fn: Callable[[], dict]) -> None:
    PROBES[probe_id] = fn


def disk() -> dict:
    free_gb = shutil.disk_usage(store.DATA if store.DATA.exists() else ".").free / 1024 ** 3
    ok = engine.run("health.disk_ok", {"free_gb": free_gb, "min_free_gb": settings()["min_free_gb"]}) is True
    return {"ok": ok, "say": say("disk_ok" if ok else "disk_low", gb=round(free_gb, 1))}


def cert_days(host: str) -> float:
    """Days until this host's https certificate ends (a refused or broken https raises - that is the problem)."""
    ctx = ssl.create_default_context()
    with socket.create_connection((host, 443), timeout=float(settings()["timeout_s"])) as raw, ctx.wrap_socket(raw, server_hostname=host) as s:
        return (ssl.cert_time_to_seconds(s.getpeercert()["notAfter"]) - time.time()) / 86400


def certificates(hosts: list[str]) -> Callable[[], dict]:
    """The probe a portal attaches for its own hosts (its edition row names them)."""
    def run() -> dict:
        low = []
        for h in hosts:
            days = cert_days(h)
            if engine.run("health.cert_ok", {"days_left": days, "min_days": settings()["cert_min_days"]}) is not True:
                low.append(say("cert_host", host=h, days=max(0, int(days))))
        return {"ok": not low, "say": say("cert_ok", n=len(hosts)) if not low else say("cert_low", hosts=", ".join(low))}
    return run


def check(_args: dict | None = None, _ctx: dict | None = None) -> dict:
    """Every probe once, each in its own words. One that raises says why - the check itself never fails."""
    rows = []
    for pid, fn in sorted(PROBES.items()):
        name = engine.run("health.messages").get(f"probe_{pid}") or pid
        try:
            got = fn() or {}
            rows.append({"id": pid, "name": name, "ok": bool(got.get("ok")), "say": str(got.get("say") or "")})
        except Exception as e:  # noqa: BLE001 - the probe's own reason is the problem the owner reads
            rows.append({"id": pid, "name": name, "ok": False, "say": say("probe_failed", why=str(getattr(e, "detail", "") or e)[:200])})
    return {"checked": len(rows), "problems": [r for r in rows if not r["ok"]], "fine": [r for r in rows if r["ok"]], "at": store.now()}


def warn(args: dict, ctx: dict) -> dict:
    """The bar becomes this answer. A dry run only says what the bar would show."""
    problems = list((args.get("found") or {}).get("problems") or [])
    old = store.read(BAR, {}) or {}
    new_ids = sorted({p["id"] for p in problems} - set(old.get("told") or []))
    if ctx.get("preview"):
        return {"would_show": len(problems), "new": new_ids}
    store.write(BAR, {"at": store.now(), "problems": problems, "told": sorted(p["id"] for p in problems)})
    if new_ids:
        names = ", ".join(p["name"] for p in problems if p["id"] in new_ids)
        for uid in agents._owners():   # noqa: SLF001 - the one list of owners the runtime keeps
            bell.push(uid, say("bell_new", n=len(new_ids), names=names), "#/agents")
    return {"shown": len(problems), "new": new_ids}


def bootstrap_extra(request: Request, u: dict | None) -> dict:
    """Owners see the bar on every page; everyone else never does."""
    if not u or engine.run("people.is_owner", {"role": u.get("role") or ""}) is not True:
        return {}
    bar = store.read(BAR, {}) or {}
    return {"health": {"at": bar.get("at", ""), "problems": bar.get("problems") or []}} if bar.get("problems") else {}


probe("disk", disk)
agents.action("health.check", check)
agents.action("health.warn", warn)


if __name__ == "__main__":  # ponytail: a probe that raises is a problem, the bar is replaced, the bell rings once per new problem
    import tempfile
    from pathlib import Path
    store.DATA = Path(tempfile.mkdtemp())
    rang = []
    bell.push = lambda uid, text, href="": rang.append(text)
    agents._owners = lambda: ["o"]   # noqa: SLF001
    PROBES.clear()
    state = {"voice": True}
    probe("voice", lambda: {"ok": state["voice"], "say": "voice"})
    probe("broken", lambda: (_ for _ in ()).throw(OSError("no route")))
    got = check()
    assert got["checked"] == 2 and [p["id"] for p in got["problems"]] == ["broken"] and "no route" in got["problems"][0]["say"]
    assert warn({"found": got}, {"preview": True}) == {"would_show": 1, "new": ["broken"]} and not store.read(BAR, {}), "a dry run writes nothing"
    warn({"found": got}, {"preview": False})
    assert len(rang) == 1 and len(store.read(BAR, {})["problems"]) == 1
    warn({"found": check()}, {"preview": False})
    assert len(rang) == 1, "the same problem the next day: the bar stays, the bell does not ring again"
    state["voice"] = False
    warn({"found": check()}, {"preview": False})
    assert len(rang) == 2 and len(store.read(BAR, {})["problems"]) == 2, "a new problem rings once"
    state["voice"] = True
    PROBES.pop("broken")
    warn({"found": check()}, {"preview": False})
    assert store.read(BAR, {})["problems"] == [] and len(rang) == 2, "fixed: the bar clears by itself, nothing piles up"
    assert bootstrap_extra(None, {"role": "owner"}) == {}, "an empty bar is not shown"
    assert engine.run("health.disk_ok", {"free_gb": 1, "min_free_gb": 5}) is False and disk()["say"]
    print("health self-check OK")
