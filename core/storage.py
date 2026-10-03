"""Storage: who holds the disk, and the owner's way to get it back.

Per account: bytes held, how many files, holding since when. From the same page the owner asks that
person to clean up, and the portal enforces the fair order of it:

    day 0   first request             (email, and a banner in the portal)
    day 3+  second request            (at least 3 days after the first)
    day 6+  third and final request   (at least 3 days after the second)
    day 7+  the owner may delete some or all of that person's items

The dates are enforced here, not in the browser — and decided by chip `storage.stage` (gap, delete-after,
how many requests); every sentence and email is chip `storage.messages`. With no mail server the request is still recorded
and still reaches the person as a banner the next time they open the portal, so the process never
depends on SMTP.

The framework does not know what a "file" is in a given portal. The host registers a provider:

    storage.register(items=lambda: [{"id", "owner_id", "title", "bytes", "files", "created_at"}],
                     delete=lambda item_id: None,          # raise ValueError("why") to refuse one
                     manage_hash="#/video")                # where a person goes to clean up
"""
from __future__ import annotations

import shutil
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from core import access, auth, engine, lists, mailer, store
from core.access import screen

router = APIRouter()

DAY = 86400             # seconds in a day: a unit, not a policy

_PROVIDER: dict = {"items": lambda: [], "delete": None, "manage_hash": ""}


def register(items, delete, manage_hash: str = "") -> None:
    _PROVIDER.update(items=items, delete=delete, manage_hash=manage_hash)


#: Other things a person keeps on the portal's disk beside the main provider's files. A module reports its own:
#:   storage.register_more("name", items=lambda user_id="": [{"id", "owner_id", "title", "bytes", "files", "created_at"}],
#:                         delete=lambda item_id: None)      # items("") = everyone's; raise to refuse one
#: They count in every total (a person's quota, the owner's Storage screen) and are deleted through their own module.
_MORE: dict[str, dict] = {}


def register_more(name: str, items, delete) -> None:
    _MORE[name] = {"items": items, "delete": delete}


#: What each person MAY hold (2026-10-01 owner: "move it under Storage - give the option to edit, and show how much is
#: used out of what is allocated"). A portal that limits its people tells this screen how; nothing registered = no limits shown.
#:   storage.register_limits(of=lambda user: {"quota_bytes", "max_upload_mb", "tight_pct", "own": {field: value}},
#:                           defaults=lambda: {field: value}, fields=lambda: [{"key", "label", "note", "unit", "person"}],
#:                           save_defaults=lambda body: None, save_person=lambda user_id, body: "message")
#: The fields and every word on them are the portal's chip; save_* raise HTTPException to refuse; save_person(id, {}) =
#: back on the defaults. Only the owner changes them (an admin with this screen sees them).
_LIMITS: dict = {}


def register_limits(of, defaults, fields, save_defaults, save_person) -> None:
    _LIMITS.update(of=of, defaults=defaults, fields=fields, save_defaults=save_defaults, save_person=save_person)


def limits_view(me: dict) -> dict | None:
    """The defaults for everyone and the boxes that set them; None when the portal limits nobody."""
    if not _LIMITS:
        return None
    return {"fields": _LIMITS["fields"](), "defaults": _LIMITS["defaults"](), "can_edit": me.get("role") == "owner"}


def _owner_only(me: dict) -> None:
    if not _LIMITS:
        raise HTTPException(404, say("no_limits"))
    if me.get("role") != "owner":
        raise HTTPException(403, auth.msg("owner_only"))


def more_items(user_id: str = "") -> list[dict]:
    return [it | {"via": name} for name, m in _MORE.items() for it in m["items"](user_id)]


def more_bytes(user_id: str) -> int:
    """What this person's other files weigh - added to their used total wherever a quota is asked."""
    return sum(int(it.get("bytes") or 0) for it in more_items(user_id))


def _ts(iso: str) -> float:
    try:
        return datetime.fromisoformat(iso).timestamp()
    except (TypeError, ValueError):
        return 0.0


def _date(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%d %b %Y")


# --- the case file for one person -----------------------------------------------------------------

def cases() -> dict:
    return store.read("storage_cases", {})


def knobs() -> dict:
    return engine.knobs("storage.stage")


def stage(case: dict | None, now: float | None = None) -> dict:
    """Where one person's clean-up stands, and what the owner may do next — facts here, rules in the chip."""
    sent = (case or {}).get("requests", [])
    return engine.run("storage.stage", {"requests": len(sent), "now": now or time.time(),
                                         "first_at": _ts(sent[0]["at"]) if sent else None,
                                         "last_at": _ts(sent[-1]["at"]) if sent else None})


def say(key: str, **values) -> str:
    return engine.say("storage.messages", key, **values)


def holdings() -> dict[str, dict]:
    """{user_id: {bytes, files, since, items[]}} from whatever the host counts as files."""
    out: dict[str, dict] = {}
    for it in [*_PROVIDER["items"](), *more_items()]:
        h = out.setdefault(it["owner_id"], {"bytes": 0, "files": 0, "since": "", "items": []})
        h["bytes"] += int(it.get("bytes") or 0)
        h["files"] += int(it.get("files") or 0)
        h["items"].append(it)
        if it.get("created_at") and (not h["since"] or it["created_at"] < h["since"]):
            h["since"] = it["created_at"]
    return out


def _gb(n: int) -> str:
    return f"{n / 1024 ** 3:.2f} GB" if n >= 1024 ** 3 else f"{max(1, round(n / 1024 ** 2))} MB"


# --- the page -----------------------------------------------------------------------------------

# 2026-09-28 owner "tens of thousands": people are list storage_people (core/lists.py), one searched page at a time;
# a person's items (and their clean-up case) come only with their own row (?id=...), never for everyone.
def _people_rows(user: dict, args: dict) -> list[dict]:
    if not access.may(user, "storage"):
        raise HTTPException(403, access.say("no_access", label=access.label_of("storage", "")))
    held, all_cases, only = holdings(), cases(), str(args.get("id") or "")
    rows, calm = [], stage(None)                         # no case = the same stage for everyone: asked once
    for u in store.users():
        if only and u["id"] != only:
            continue
        h, c = held.get(u["id"], {"bytes": 0, "files": 0, "since": ""}), all_cases.get(u["id"])
        rows.append(store.public_user(u) | {k: h[k] for k in ("bytes", "files", "since")} | {"stage": stage(c) if c else calm})
    return rows


def _people_fill(user: dict, rows: list[dict], args: dict) -> list[dict]:
    if _LIMITS:                                          # each row on screen: what they may hold beside what they hold
        who = {u["id"]: u for u in store.users() if u["id"] in {p["id"] for p in rows}}
        rows = [p | {"limit": _LIMITS["of"](who[p["id"]])} if p["id"] in who else p for p in rows]
    if not args.get("id"):
        return rows
    held, all_cases = holdings(), cases()
    # 2026-10-01 (Phase 3): one heavy person can hold thousands of items - the biggest few are listed (chip
    # list.storage_people items_shown), with how many there are; Delete all still reaches every one of them
    keep = engine.run("list.storage_people")["items_shown"]
    out = []
    for p in rows:
        items = (held.get(p["id"]) or {}).get("items") or []
        out.append(p | {"items": engine.run("limits.newest", {"rows": items, "keep": keep, "by": "bytes"}) or [], "items_n": len(items),
                        "items_bytes": sum(int(i.get("bytes") or 0) for i in items), "case": all_cases.get(p["id"]) or {}})
    return out


lists.source("storage_people", _people_rows, _people_fill)


@router.get("/api/core/storage")
def overview(me: dict = Depends(screen("storage"))):
    """The totals over everyone; the people themselves are list storage_people."""
    held, all_cases = holdings(), cases()
    totals = {"bytes": sum(h["bytes"] for h in held.values()), "files": sum(h["files"] for h in held.values()),
              "holders": sum(1 for h in held.values() if h["files"]),
              "open": sum(1 for uid, c in all_cases.items() if not uid.startswith("_") and stage(c)["requests"]), "people": len(store.users()),
              "max_bytes": max([h["bytes"] for h in held.values()] or [0])}
    try:
        du = shutil.disk_usage(store.DATA if store.DATA.exists() else store.ROOT)
        disk = {"total": du.total, "free": du.free}
    except OSError:
        disk = {}
    k = knobs()
    return {"totals": totals, "disk": disk, "can_email": mailer.configured(), "limits": limits_view(me),
            "rules": {"gap_days": k["gap_days"], "delete_after_days": k["delete_after_days"], "max_requests": k["max_requests"]}}


@router.put("/api/core/storage/limits")
def save_defaults(body: dict = Body(...), me: dict = Depends(screen("storage"))):
    """The defaults for everyone - a person with limits of their own keeps them."""
    _owner_only(me)
    _LIMITS["save_defaults"](body)
    return {"message": say("limits_saved"), "limits": limits_view(me)}


@router.put("/api/core/storage/{user_id}/limits")
def save_person(user_id: str, body: dict = Body(...), me: dict = Depends(screen("storage"))):
    """One person's own limits; a box left blank follows the default."""
    _owner_only(me)
    return {"message": _LIMITS["save_person"](user_id, body)}


@router.delete("/api/core/storage/{user_id}/limits")
def person_back_to_defaults(user_id: str, me: dict = Depends(screen("storage"))):
    _owner_only(me)
    return {"message": _LIMITS["save_person"](user_id, {})}


def _message(u: dict, h: dict, n: int, note: str, request: Request) -> tuple[str, str]:
    s, k = auth.settings(), knobs()
    first = _ts((cases().get(u["id"]) or {}).get("requests", [{}])[0].get("at", "")) if n > 1 else time.time()
    values = {"product": s["product_name"], "n": n, "max": k["max_requests"], "name": u.get("name") or u["email"],
              "size": _gb(h["bytes"]), "files": h["files"],
              "since": say("since", date=_date(_ts(h["since"]))) if h["since"] else "",
              "link": f"{auth.portal_base(request)}/{_PROVIDER['manage_hash']}",
              "note_block": say("note_block", note=note) if note else "",
              "reminder_line": say("reminder_line", n=n, max=k["max_requests"]) if n > 1 else "",
              "delete_date": _date(first + k["delete_after_days"] * DAY)}
    return say("subject_first" if n == 1 else "subject_reminder", **values), say("body", **values)


@router.post("/api/core/storage/{user_id}/request")
def send_request(user_id: str, request: Request, body: dict = Body(default={}), me: dict = Depends(screen("storage"))):
    u = store.user_by_id(user_id)
    if not u:
        raise HTTPException(404, say("no_account"))
    h = holdings().get(user_id)
    if not h or not h["files"]:
        raise HTTPException(400, say("no_files"))
    with store._LOCK:                                  # noqa: SLF001
        all_cases = cases()
        case = all_cases.get(user_id) or {"requests": []}
        st = stage(case)
        k = knobs()
        if st["requests"] >= k["max_requests"]:
            raise HTTPException(409, say("all_sent", max=k["max_requests"]))
        if not st["can_request"]:
            raise HTTPException(409, say("too_soon", date=_date(st["next_request_at"]), gap_days=k["gap_days"]))
        n = st["requests"] + 1
        note = str(body.get("note") or "").strip()[:1000]
        subject, text = _message(u, h, n, note, request)
        emailed, why = False, say("no_mail")
        if mailer.configured():
            try:
                mailer.send(u["email"], subject, text)
                emailed, why = True, ""
            except RuntimeError as e:
                why = say("mail_failed", error=e)
        case["requests"].append({"at": store.now(), "by": auth.who(me), "emailed": emailed,
                                 "bytes": h["bytes"], "files": h["files"], "note": note})
        all_cases[user_id] = case
        store.write("storage_cases", all_cases)
    return {"stage": stage(case), "emailed": emailed, "why": why, "subject": subject, "text": text}


@router.post("/api/core/storage/{user_id}/delete")
def delete_items(user_id: str, request: Request, body: dict = Body(...), me: dict = Depends(screen("storage"))):
    u = store.user_by_id(user_id)
    if not u:
        raise HTTPException(404, say("no_account"))
    st = stage(cases().get(user_id))
    if not st["can_delete"]:
        k = knobs()
        raise HTTPException(409, say("not_yet", max=k["max_requests"], delete_after_days=k["delete_after_days"],
                                     when=say("delete_date_note", date=_date(st["delete_at"])) if st["delete_at"] else ""))
    theirs = {i["id"]: i for i in (holdings().get(user_id) or {}).get("items", [])}
    wanted = list(theirs) if body.get("all") else [i for i in body.get("ids") or [] if i in theirs]
    if not wanted:
        raise HTTPException(400, say("pick_one"))
    deleted, skipped, freed = [], [], 0
    for item_id in wanted:
        try:
            (_MORE[theirs[item_id]["via"]]["delete"] if theirs[item_id].get("via") else _PROVIDER["delete"])(item_id)
            deleted.append(theirs[item_id]["title"])
            freed += int(theirs[item_id].get("bytes") or 0)
        except Exception as e:  # noqa: BLE001 - one item that will not go must not stop the rest
            skipped.append({"title": theirs[item_id]["title"], "why": str(getattr(e, "detail", "") or e)})
    with store._LOCK:                                  # noqa: SLF001
        all_cases = cases()
        case = all_cases.get(user_id) or {"requests": []}
        case.setdefault("deletions", []).append({"at": store.now(), "by": auth.who(me), "items": len(deleted), "bytes": freed})
        left = holdings().get(user_id)
        if not left or not left["files"]:               # nothing left to ask about: the case is done
            case["closed_at"] = store.now()
            all_cases.setdefault("_history", []).append({"user_id": user_id} | case)
            all_cases.pop(user_id, None)
        else:
            all_cases[user_id] = case
        store.write("storage_cases", all_cases)
    if deleted and mailer.configured():
        s = auth.settings()
        values = {"product": s["product_name"], "name": u.get("name") or u["email"], "max": knobs()["max_requests"],
                  "count": len(deleted), "size": _gb(freed), "items": "".join(f"  - {t}\n" for t in deleted[:50])}
        try:
            mailer.send(u["email"], say("deleted_subject", **values), say("deleted_body", **values))
        except RuntimeError:
            pass
    return {"deleted": len(deleted), "freed_bytes": freed, "skipped": skipped}


@router.post("/api/core/storage/{user_id}/close")
def close_case(user_id: str, me: dict = Depends(screen("storage"))):
    """They cleaned up, or you decided to let it be. Starts the next request from scratch."""
    with store._LOCK:                                  # noqa: SLF001
        all_cases = cases()
        case = all_cases.pop(user_id, None)
        if case:
            all_cases.setdefault("_history", []).append({"user_id": user_id, "closed_at": store.now(),
                                                          "closed_by": auth.who(me)} | case)
            store.write("storage_cases", all_cases)
    return {"ok": True}


def bootstrap_extra(request: Request, u: dict | None) -> dict:
    """The person's own open request, so the shell can show it as a banner — mail or no mail."""
    case = cases().get(u["id"]) if u else None
    if not case or not case.get("requests"):
        return {}
    st, h = stage(case), holdings().get(u["id"]) or {"bytes": 0, "files": 0}
    return {"storage_request": {"requests": st["requests"], "max": knobs()["max_requests"], "bytes": h["bytes"],
                                "files": h["files"], "delete_from": _date(st["delete_at"]),
                                "note": case["requests"][-1].get("note", ""), "href": _PROVIDER["manage_hash"]}}


if __name__ == "__main__":  # ponytail: the timeline is the logic worth pinning
    def at(days_ago: float) -> str:
        return datetime.fromtimestamp(time.time() - days_ago * DAY, timezone.utc).isoformat(timespec="seconds")
    assert stage(None)["can_request"] and not stage(None)["can_delete"]
    one = {"requests": [{"at": at(1)}]}
    assert not stage(one)["can_request"], "no reminder a day after the first request"
    assert stage({"requests": [{"at": at(3.01)}]})["can_request"], "a reminder after 3 days"
    three = {"requests": [{"at": at(6.5)}, {"at": at(3.5)}, {"at": at(0.2)}]}
    assert not stage(three)["can_request"], "never a fourth"
    assert not stage(three)["can_delete"], "no deleting before day 7"
    ready = {"requests": [{"at": at(7.1)}, {"at": at(4)}, {"at": at(1)}]}
    assert stage(ready)["can_delete"], "day 7 with three requests: may delete"
    assert not stage({"requests": [{"at": at(30)}, {"at": at(20)}]})["can_delete"], "all three must have gone"
    print("core.storage self-check OK")
