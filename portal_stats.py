"""Portal analytics - every firm on SimplyFile, for the portal admin (2026-10-04 owner: "I as portal admin should have
Analytics in sf ... making me in control and in charge").

Facts only: each firm (state, team, clients, returns, files, when anyone in it was last seen), each account (role, seen
this week / month) and requests per day from Portal activity. Chip portalstats.firm decides what a firm needs from the
admin; portalstats.rollup adds the portal up. Settings: portalstats.settings. Words: ui.portalstats.
"""
from __future__ import annotations

import datetime

import clients
import firms
from core import engine, ledger, lists, store


def _days_since(iso: str, now: datetime.datetime) -> int:
    try:
        return (now - datetime.datetime.fromisoformat(iso[:19])).days
    except ValueError:
        return -1


def _bytes(folder) -> int:
    return sum(p.stat().st_size for p in folder.rglob("*") if p.is_file()) if folder.exists() else 0


def report(ay: str = "") -> dict:
    k = engine.run("portalstats.settings", {})
    cs = clients.settings()
    ay = ay if ay in cs["years"] else cs["current_ay"]
    now = datetime.datetime.utcnow()
    since = (now - datetime.timedelta(days=30)).isoformat(timespec="seconds")
    with ledger.db() as c:
        seen = {r["user_id"]: r["at"] for r in ledger.rows(c, "SELECT user_id, MAX(at) AS at FROM activity WHERE user_id != '' GROUP BY user_id")}
        days = ledger.rows(c, "SELECT substr(at, 1, 10) AS day, COUNT(*) AS n FROM activity WHERE at >= ? GROUP BY day ORDER BY day", (since,))
    users = [u for u in store.users() if u.get("role") != "owner"]
    by_firm: dict[str, list] = {}
    for u in users:
        by_firm.setdefault(u.get("firm_id") or "", []).append(u)
    all_clients = [c for c in clients._all() if not c.get("archived_at")]  # noqa: SLF001
    rows = []
    for f in firms._all():  # noqa: SLF001
        team = by_firm.get(f["id"], [])
        mine = [c for c in all_clients if c.get("firm_id") == f["id"]]
        years = [c["years"][ay] for c in mine if ay in (c.get("years") or {})]
        filings = [x for c in mine for y in (c.get("years") or {}).values() for x in (y.get("filings") or []) if x.get("status") == "current"]
        last = max((seen.get(u["id"], "") for u in team), default="")
        facts = {"state": f.get("state", ""), "age_days": _days_since(f.get("created_at", ""), now),
                 "idle_days": _days_since(last, now) if last else -1, "clients": len(mine)}
        rows.append({"id": f["id"], "name": f.get("name") or f.get("email") or f["id"], "kind": f.get("kind", ""), "month": f.get("created_at", "")[:7],
                     **facts, "team": len(team), "years": len(years),
                     "filed": sum(1 for y in years if any(x.get("status") == "current" for x in (y.get("filings") or []))),
                     "returns": len(filings), "last_seen": last[:10],
                     "bytes": _bytes(store.DATA / "sf_firms" / f["id"]) + sum(_bytes(store.DATA / "sf_files" / c["id"]) for c in mine),
                     **engine.run("portalstats.firm", {**facts, "dormant_days": k["dormant_days"], "stuck_days": k["stuck_days"]})})
    week, month = k["active_days"]
    ago = {u["id"]: _days_since(seen[u["id"]], now) if seen.get(u["id"]) else -1 for u in users}
    people = [{"role": u.get("firm_role") or "self", "seen7": 0 <= ago[u["id"]] < week, "seen30": 0 <= ago[u["id"]] < month} for u in users]
    roll = engine.run("portalstats.rollup", {"firms": rows, "users": people, "days": days})
    rows.sort(key=lambda r: (-r["returns"], -r["clients"], r["name"]))
    return {"ay": ay, "years": cs["years"], "roll": roll, "firms": rows, "days": days, "kinds": {x["id"]: x["label"] for x in firms.settings()["kinds"]},
            "states": {x["id"]: {"label": x["label"], "tag": x["tag"]} for x in firms.settings()["states"]},
            "roles": {g["key"]: (firms.role_of(g["key"]) or {}).get("label") or g["key"] for g in roll["by_role"]}}


# the firms table and each "needs a look" card in full, searched and paged on the server (chips list.portal_firms, list.portal_flags)
# ponytail: each page rebuilds the report (disk sizes too) - fine for tens of firms; cache per ay for a few minutes if it shows
lists.source("portal_firms", lambda u, a: report(str(a.get("ay") or ""))["firms"], screen="portalstats")
lists.source("portal_flags", lambda u, a: [{"name": n} for n in report(str(a.get("ay") or ""))["roll"].get(str(a.get("flag") or ""), [])
                                           if isinstance(n, str)], screen="portalstats")


if __name__ == "__main__":  # ponytail: a firm's age reads, and the roll-up adds up on an empty portal
    import store as _s  # noqa: F401 - registers this portal's chips
    n = datetime.datetime(2026, 10, 4)
    assert _days_since("2026-10-01T09:00:00+00:00", n) == 2 and _days_since("", n) == -1
    r = engine.run("portalstats.rollup", {"firms": [], "users": [], "days": []})
    assert r["firms"] == 0 and r["review"] == [], r
    print("portal_stats OK")
