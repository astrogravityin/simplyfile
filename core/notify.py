"""Business events that notify (A20; Invoice Ninja / Cal.com / Healthchecks bar): one call -> the bell of whoever the chip
names, a mail from a chip mail.texts template, and an optional webhook - all chosen by chip events.notify.

    notify.fire(event_id, **values)

The caller names only its event id and hands its values; who hears, the bell words, the screen link, the mail template
and the webhook are rows of chip events.notify (switch `on`). Recipients: "owners" (chip people.is_owner) or
"value:<name>" (a person id among the values). Mail and webhook go out on a thread so the request never waits.
"""
from __future__ import annotations

import json
import threading
import urllib.request

from core import auth, bell, egress, engine, mailer, ops, store


def K() -> dict:
    return engine.run("events.notify")


def spec(event: str) -> dict:
    s = (K().get("events") or {}).get(event) or {}
    return s if s.get("on", True) else {}


def recipients(to: list[str], values: dict) -> list[dict]:
    people = store.users()
    out: list[dict] = []
    for sel in to or []:
        if sel == "owners":
            out += [p for p in people if engine.run("people.is_owner", {"role": p.get("role") or ""}) is True]
        elif sel.startswith("value:"):
            uid = str(values.get(sel.split(":", 1)[1]) or "")
            out += [p for p in people if p["id"] == uid]
    return list({p["id"]: p for p in out}.values())       # a person rings once, first-named order kept


def _mail(template: str, people: list[dict], values: dict) -> None:
    texts = engine.run("mail.texts")
    subject, text = (ops.template(texts.get(f"{template}_{part}", ""), values) for part in ("subject", "text"))
    for p in people:
        if p.get("email") and subject:
            try:
                mailer.send(p["email"], subject, text)
            except Exception:  # noqa: BLE001 - a mail that fails never undoes the event; Recent mail logs it
                pass


def _hook(url: str, body: dict) -> None:
    try:
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        egress.fetch(req, timeout=float(K()["webhook_timeout_s"]), purpose="webhook").close()   # https, public address only
    except Exception:  # noqa: BLE001 - the receiver being down never breaks the event
        pass


def fire(event: str, **values) -> dict:
    """Bell + mail + webhook for one business event, as chip events.notify says. Returns who rang (for tests)."""
    s = spec(event)
    if not s:
        return {"bell": [], "mail": "", "webhook": ""}
    values = {"product": auth.settings()["product_name"]} | values
    people = recipients(s.get("to") or [], values)
    text, href = ops.template(s.get("bell", ""), values), s.get("href", "")
    for p in people:
        bell.push(p["id"], text, href)
    if s.get("mail") and mailer.configured():
        threading.Thread(target=_mail, args=(s["mail"], people, values), daemon=True).start()
    if s.get("webhook"):
        threading.Thread(target=_hook, args=(s["webhook"], {"event": event, "text": text, **values}), daemon=True).start()
    return {"bell": [p["id"] for p in people], "mail": s.get("mail", ""), "webhook": s.get("webhook", "")}


if __name__ == "__main__":  # ponytail: one runnable self-check - chip-chosen recipients, words filled, switch off = silent
    import tempfile
    from pathlib import Path
    store.DATA = Path(tempfile.mkdtemp())
    users = [{"id": "o1", "role": "owner", "email": "o@x.example"}, {"id": "m1", "role": "member", "email": "m@x.example"}]
    store.users = lambda: users
    ev = next(iter(K()["events"]))
    rung = fire(ev, user_id="m1", who="m@x.example", screen="S", firm="F", verdict="approved")
    want = [p["id"] for p in recipients(spec(ev)["to"], {"user_id": "m1"})]
    assert rung["bell"] == want and want, (rung, want)
    assert all(bell.unread(uid) == 1 for uid in want) and "{" not in bell.mine(want[0])[0]["text"], "words filled, one note each"
    assert recipients(["owners"], {}) == [users[0]] and recipients(["value:user_id"], {"user_id": "m1"}) == [users[1]]
    assert recipients(["owners", "owners"], {}) == [users[0]], "a person rings once"
    assert fire("no_such_event") == {"bell": [], "mail": "", "webhook": ""}
    hooks = []
    globals()["_hook"] = lambda url, body: hooks.append((url, body))
    real = K
    globals()["K"] = lambda: real() | {"events": {"x": {"on": True, "to": ["owners"], "bell": "hi {who}", "webhook": "http://h.example/x"}}}
    fire("x", who="A")
    import time
    time.sleep(0.2)
    assert hooks and hooks[0][1]["event"] == "x" and hooks[0][1]["text"] == "hi A", hooks
    globals()["K"] = lambda: real() | {"events": {"x": {"on": False, "to": ["owners"], "bell": "hi"}}}
    assert fire("x")["bell"] == [], "switch off = silent"
    print("notify self-check OK")
