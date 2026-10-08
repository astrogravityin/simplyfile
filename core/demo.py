"""Demo mode (2026-10-05 owner: one public demo link per product, "OTP based login that way we know who are seeing").

A portal started with PORTAL_DEMO=1 is a demo copy: its sign-in card leads with "Try the demo" - a name and an email, a code
mailed to that address, and the visitor is in, on a seat of their own (a real, named account: the owner sees who came and what
they opened under People and Activity, as for anyone). What the seat may do is the host's business: each product appends a
seater to SEATERS (SimplyFile: a Partner in the demo firm). The data is put back every night from a snapshot, outside this
module (deploy/demo/reset.sh), so a visitor may try everything.

Built the chip way: the lifetimes, tries and throttle are chip demo.settings; every sentence is ui.demo. This module gathers
the facts and does the I/O (codes, mail, the account, the session) through auth and store.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, Request, Response

from core import auth, engine, mailer, store

ON = os.getenv("PORTAL_DEMO", "").lower() in {"1", "true", "yes"}
PURPOSE = "demo"
#: Callables (user) -> None run once when a visitor's seat is first made: the host puts it where the demo data is.
SEATERS: list = []

router = APIRouter()


def settings() -> dict:
    return engine.run("demo.settings")


def say(key: str, **v) -> str:
    return engine.say("ui.demo", key, **v)


def next_reset(now: datetime | None = None) -> int:
    """Epoch seconds of the next nightly reset (chip demo.settings reset_utc) - the banner counts down to it."""
    hh, mm = (int(x) for x in str(settings()["reset_utc"]).split(":"))
    now = now or datetime.now(timezone.utc)
    t = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    return int((t if t > now else t + timedelta(days=1)).timestamp())


def bootstrap_extra(_request: Request, u: dict | None) -> dict:
    return {"demo": ON, "demo_visitor": bool(u and u.get("demo")), "demo_reset_at": next_reset() if ON else 0}


def _on() -> None:
    if not ON:
        raise HTTPException(404, say("not_demo"))


@router.post("/api/demo/code/send")
def send_code(request: Request, body: dict = Body(...)):
    """Name and email: a code to that address. The same answer whether or not the address has been here before."""
    _on()
    if not auth.rate_ok(auth.client_ip(request)):
        raise HTTPException(429, auth.msg("rate_limited"))
    email = str(body.get("email") or "").strip().lower()
    name = str(body.get("name") or "").strip()
    auth.check_fields(email=email, name=name)
    if not mailer.configured():
        raise HTTPException(503, say("no_mail"))
    k = settings()
    if store.recent_codes(PURPOSE, email, 3600) < int(k["sends_per_hour"]):
        code = "".join(secrets.choice("0123456789") for _ in range(int(k["digits"])))
        store.put_code(PURPOSE, email, code, int(k["code_ttl_seconds"]))
        store.log_code(PURPOSE, email)
        product = auth.settings()["product_name"]
        try:
            mailer.send(email, say("mail_subject", product=product, code=code),
                        say("mail_body", product=product, code=code, name=name, minutes=int(k["code_ttl_seconds"]) // 60,
                            url=auth.portal_base(request)))
        except RuntimeError as e:          # the owner sees mail trouble on Setup's Test button; a visitor learns nothing
            print(f"[demo] could not send a code: {e}", flush=True)
    return {"message": say("code_sent", email=email), "resend_after_seconds": int(k["resend_after_seconds"])}


@router.post("/api/demo/code/check")
def check_code(response: Response, body: dict = Body(...)):
    """The right code signs the visitor in - on a seat made now, the first time, or the seat they had."""
    _on()
    email = str(body.get("email") or "").strip().lower()
    name = str(body.get("name") or "").strip()
    outcome = store.check_code(PURPOSE, email, str(body.get("code") or ""), int(settings()["max_attempts"]))
    if outcome != "ok":
        raise HTTPException(400, {"message": say("code_burned" if outcome == "burned" else "code_wrong"), "field": "code"})
    if is_owner(email):   # the demo's owner, named by the server's env - never by the snapshot
        return auth._sign_in(response, _owner_seat(email, name)) | {"signed_in": True}  # noqa: SLF001
    u = store.find_user(email)
    if not u:
        auth.check_fields(email=email, name=name)
        u = store.add_user(email, secrets.token_urlsafe(24), name, settings()["seat_role"] or "", verified=True)
        _mark_visitor(u["id"])
        for seat in SEATERS:
            seat(u)
        u = store.find_user(email)
    return auth._sign_in(response, u) | {"signed_in": True}  # noqa: SLF001 - the one way a session starts


def is_owner(email: str) -> bool:
    """2026-10-08 owner: "How will I know how many people logged in the demo site unless I am owner?" The service file names
    the demo's owner (PORTAL_DEMO_OWNER, set by deploy/demo/setup.sh), so no real address ever sits in a snapshot: that email,
    after its code, is the portal owner - People, Activity, Visitors - and never a visitor seat."""
    want = os.getenv("PORTAL_DEMO_OWNER", "").strip().lower()
    return bool(want) and str(email or "").strip().lower() == want


def _owner_seat(email: str, name: str) -> dict:
    """The owner's account on this copy: made on first sign-in after each nightly reset, kept an owner."""
    u = store.find_user(email) or store.add_user(email, secrets.token_urlsafe(24), name, "owner", verified=True)
    if u.get("role") != "owner" or u.get("demo"):
        with store._LOCK:  # noqa: SLF001 - part of the store's own tooling
            rows = store.users()
            for x in rows:
                if x["id"] == u["id"]:
                    x["role"] = "owner"
                    x.pop("demo", None)
            store.write("users", rows)
        u = store.find_user(email)
    return u


def _mark_visitor(uid: str) -> None:
    with store._LOCK:  # noqa: SLF001 - part of the store's own tooling
        rows = store.users()
        for x in rows:
            if x["id"] == uid:
                x["demo"] = True
        store.write("users", rows)


def visitor(u: dict | None) -> bool:
    """A seat made by the demo sign-in (hosts keep these out of team lists and show them as 'a demo visitor')."""
    return bool(u and u.get("demo"))


_DAY = re.compile(r"(\d{4}-\d{2}-\d{2})(T[\d:.]+(?:Z|[+-]\d{2}:\d{2})?)?")


def _moved(v, days: int):
    """Every value that is a date or a timestamp, moved by days; the rest as it was."""
    if isinstance(v, dict):
        return {k: _moved(x, days) for k, x in v.items()}
    if isinstance(v, list):
        return [_moved(x, days) for x in v]
    if isinstance(v, str) and (m := _DAY.fullmatch(v)):
        try:
            return (date.fromisoformat(m[1]) + timedelta(days=days)).isoformat() + (m[2] or "")
        except ValueError:
            return v
    return v


def freshen(data: Path, packed_at: float, now: datetime | None = None) -> int:
    """After the nightly reset: move every date in the restored data forward by the days since the snapshot was packed
    (chip demo.host move_dates), so the demo's tomorrow is tomorrow. Returns the days moved.
    ponytail: free text ("heard on 28 Oct") and period folders (jf_docs/<cid>/2026) stay as packed - repack yearly."""
    if not engine.run("demo.host").get("move_dates"):
        return 0
    tz = timezone(timedelta(minutes=int(settings()["local_offset_minutes"])))
    days = ((now or datetime.now(timezone.utc)).astimezone(tz).date() - datetime.fromtimestamp(packed_at, tz).date()).days
    if days > 0:
        for p in data.rglob("*.json"):
            p.write_text(json.dumps(_moved(json.loads(p.read_text(encoding="utf-8")), days), indent=2, ensure_ascii=False),
                         encoding="utf-8")
    return days


if __name__ == "__main__" and sys.argv[1:2] == ["freshen"]:   # deploy/demo/reset.sh: python -m core.demo freshen <data> <snapshot>
    import core  # noqa: F401 - registers core's chips
    engine.register_dir(Path("chips"))
    print("dates moved", freshen(Path(sys.argv[2]), (Path(sys.argv[3]) / "users.json").stat().st_mtime), "days")
elif __name__ == "__main__":  # ponytail: the chip's numbers are sane and every sentence the card needs is there
    import core  # noqa: F401 - registers core's chips
    k = settings()
    assert int(k["digits"]) >= 6 and int(k["max_attempts"]) >= 3 and int(k["code_ttl_seconds"]) >= 300, k
    for key in ("tab", "title", "lede", "name", "email", "send", "code", "enter", "code_sent", "code_wrong", "code_burned",
                "mail_subject", "mail_body", "no_mail", "not_demo", "banner", "visitor", "left", "resetting"):
        assert say(key, product="P", code="123456", name="N", minutes=15, url="u", email="e", when="3:00 AM", h=1, m=2, s=3), key
    t0 = datetime(2026, 10, 5, 21, 29, tzinfo=timezone.utc)
    assert next_reset(t0) - int(t0.timestamp()) == 60 and next_reset(t0 + timedelta(minutes=1)) - int(t0.timestamp()) == 86460
    assert visitor({"demo": True}) and not visitor({}) and not visitor(None)
    assert _moved({"a": ["2026-10-06", "2026-10-06T03:34:11+00:00", "2025-26", "28 Oct", 9000000001]}, 26) == \
        {"a": ["2026-11-01", "2026-11-01T03:34:11+00:00", "2025-26", "28 Oct", 9000000001]}
    assert _moved("2026-02-31", 1) == "2026-02-31"
    os.environ["PORTAL_DEMO_OWNER"] = " Boss@Demo.Example "
    assert is_owner("boss@demo.example") and not is_owner("someone@demo.example") and not is_owner("")
    os.environ["PORTAL_DEMO_OWNER"] = ""
    assert not is_owner("") and not is_owner("boss@demo.example"), "no owner named = nobody is the demo's owner"
    print("demo OK")
