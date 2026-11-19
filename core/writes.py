"""Writes that happen once - ONE helper for every state-changing route of every portal (2026-11-18, DomainTemplate gap audit
C1-15 and week class 30: UV-50 / UV-118 / UV-338 / UV-339; CodyFy G-42 a second Send re-made a list over the partner's
edits, G-63 a data fix rewrote two signed agreements).

  once(request, who, body, make)   an `Idempotency-Key` header (or body key) - a repeat within the chip's time gets the FIRST
                                   answer and makes no second effect; two at once with one key run one after the other.
                                   No key: make() runs as before (normal callers see no change).
  check_version(row, body) / bump  compare-and-set on a row's `version`: a write naming an older version -> 409.
                                   store.update(name, id, fields, expect_version=) does the same for a list file.
  send_once(kind, key, send)       a message marked sent for (kind, key) is never sent again (mailer.send(once=...)).
  sign(row, fields) / broken(...)  a SIGNED row (sha256 of its signed fields) is never rewritten - core/store.write refuses
                                   a write that changes one (a data fix included).
Every name and number: chip writes.settings; every sentence: chip writes.messages.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any, Callable

from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder

from core import engine, store

_STRIPES: list[threading.Lock] = []
_STRIPE_GUARD = threading.Lock()


def settings() -> dict:
    return engine.run("writes.settings")


def say(key: str, **values) -> str:
    return engine.say("writes.messages", key, **values)


def _sha(x: Any) -> str:
    return hashlib.sha256(json.dumps(x, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def _stripe(key: str) -> threading.Lock:
    with _STRIPE_GUARD:
        if not _STRIPES:
            _STRIPES.extend(threading.Lock() for _ in range(max(1, int(settings()["lock_stripes"]))))
    return _STRIPES[int(key[:8], 16) % len(_STRIPES)]


# --- idempotency --------------------------------------------------------------------------------------------------------

def key_of(request: Request, body: Any) -> str:
    k = settings()
    got = request.headers.get(k["header"]) or (body.get(k["body_key"]) if isinstance(body, dict) else "") or ""
    return str(got).strip()[: int(k["key_max"])]


def once(request: Request, who: str, body: Any, make: Callable[[], Any]) -> Any:
    """The route's answer, made at most once per (person, route, key) while the key lives. A refusal (an exception) is not
    kept - the caller may try again. The same key with a different body is refused (409), never answered with another's."""
    key = key_of(request, body)
    if not key:
        return make()
    k = settings()
    scope = _sha([who, request.method, request.url.path, key])
    body_sha = _sha({x: v for x, v in body.items() if x != k["body_key"]} if isinstance(body, dict) else body)
    with _stripe(scope):
        kept = (store.read(k["answers_file"], {}) or {}).get(scope)
        if kept and time.time() - float(kept.get("at") or 0) < float(k["ttl_seconds"]):
            if kept.get("body") != body_sha:
                raise HTTPException(409, say("key_reused"))
            return kept["answer"]
        answer = make()
        with store._LOCK:                                          # noqa: SLF001 - one read-change-write of the answers file
            rows = store.read(k["answers_file"], {}) or {}
            now = time.time()
            rows = {s: r for s, r in rows.items() if now - float(r.get("at") or 0) < float(k["ttl_seconds"])}
            rows[scope] = {"at": now, "body": body_sha, "answer": jsonable_encoder(answer)}
            most = int(k["answers_most"])
            if len(rows) > most:
                rows = dict(sorted(rows.items(), key=lambda kv: kv[1]["at"])[-most:])
            store.write(k["answers_file"], rows)
        return answer


# --- compare-and-set on a row's version ---------------------------------------------------------------------------------

def expected(body: Any) -> Any:
    """The version a caller says it read (None = it did not say: no check, as before)."""
    return body.get(settings()["version_body_key"]) if isinstance(body, dict) else None


def check_version(row: dict, expect: Any) -> None:
    if expect in (None, ""):
        return
    try:
        stale = int(row.get(settings()["version_field"]) or 0) != int(expect)
    except (TypeError, ValueError):
        stale = True
    if stale:
        raise HTTPException(409, say("stale"))


def bump(row: dict) -> dict:
    f = settings()["version_field"]
    row[f] = int(row.get(f) or 0) + 1
    return row


# --- send once ----------------------------------------------------------------------------------------------------------

def send_once(kind: str, key: str, send: Callable[[], Any]) -> bool:
    """send() at most once for (kind, key): marked BEFORE it runs (a crash mid-send never sends twice), unmarked if it
    raises (a failed send may be tried again). False = it was sent before, nothing done."""
    k = settings()
    mark = _sha([kind, key])
    with _stripe(mark):
        with store._LOCK:                                          # noqa: SLF001
            rows = store.read(k["sent_file"], {}) or {}
            if mark in rows:
                return False
            keep = float(k["sent_keep_days"]) * 86400
            now = time.time()
            rows = {m: at for m, at in rows.items() if now - float(at) < keep}
            rows[mark] = now
            store.write(k["sent_file"], rows)
        try:
            send()
        except BaseException:
            with store._LOCK:                                      # noqa: SLF001
                rows = store.read(k["sent_file"], {}) or {}
                rows.pop(mark, None)
                store.write(k["sent_file"], rows)
            raise
    return True


# --- signed rows --------------------------------------------------------------------------------------------------------

def sign(row: dict, fields: list[str]) -> dict:
    """Mark a row signed over these fields: from now on store.write refuses any change to them (or to the mark)."""
    k = settings()
    row[k["signed_fields_field"]] = list(fields)
    row[k["signed_hash_field"]] = _sha({f: row.get(f) for f in fields})
    return row


def _signed(node: Any, k: dict, path: str = "", out: dict | None = None) -> dict:
    """Every signed row in a JSON value, by id (or by its place when it has none)."""
    out = {} if out is None else out
    if isinstance(node, dict):
        if k["signed_hash_field"] in node:
            out[str(node.get(k["id_field"])) if node.get(k["id_field"]) not in (None, "") else path] = node
        for x, v in node.items():
            _signed(v, k, f"{path}/{x}", out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _signed(v, k, f"{path}/{i}", out)
    return out


def _places(node: Any, path: str = "") -> set[str]:
    """Where every object sits in a JSON value ("/0/versions/1")."""
    out = {path} if isinstance(node, dict) else set()
    for x, v in (node.items() if isinstance(node, dict) else enumerate(node) if isinstance(node, list) else []):
        out |= _places(v, f"{path}/{x}")
    return out


def broken(old: Any, new: Any) -> list[str]:
    """The signed rows this write would change: a kept signed row whose mark or fields differ, or any signed row whose
    text no longer matches its own hash. A signed row that is removed whole is not "rewritten" (an account deleted)."""
    k = settings()
    was, now = _signed(old, k), _signed(new, k)
    bad = []
    for rid, r in now.items():
        fields = r.get(k["signed_fields_field"]) or []
        if _sha({f: r.get(f) for f in fields}) != r.get(k["signed_hash_field"]):
            bad.append(rid)
        elif rid in was and (was[rid].get(k["signed_hash_field"]) != r.get(k["signed_hash_field"])
                             or was[rid].get(k["signed_fields_field"]) != fields):
            bad.append(rid)
    kept = set(_signed(new, {**k, "signed_hash_field": k["id_field"]})) | _places(new)   # a signed row that lost its mark but
    bad += [rid for rid in was if rid not in now and rid in kept]                          # kept its id (or place) was stripped
    return sorted(set(bad))


if __name__ == "__main__":  # ponytail: one runnable self-check - two identical POSTs -> one effect, stale version -> 409,
    import tempfile          # sent once, signed text never rewritten
    from pathlib import Path

    from fastapi import Body, FastAPI
    from fastapi.testclient import TestClient
    vars(store)["DATA"] = Path(tempfile.mkdtemp())
    effects: list = []
    app = FastAPI()

    @app.post("/charge")
    def charge(request: Request, body: dict = Body(...)):
        def make() -> dict:
            effects.append(body["usd"])
            return {"charged": len(effects)}
        return once(request, "u1", body, make)

    c = TestClient(app)
    a = c.post("/charge", json={"usd": 5}, headers={"Idempotency-Key": "k1"})
    b = c.post("/charge", json={"usd": 5}, headers={"Idempotency-Key": "k1"})
    assert a.json() == b.json() == {"charged": 1} and effects == [5], ("two identical POSTs with one key made two effects", effects)
    assert c.post("/charge", json={"usd": 9}, headers={"Idempotency-Key": "k1"}).status_code == 409, "one key, another body"
    c.post("/charge", json={"usd": 5})
    c.post("/charge", json={"usd": 5, "idempotency_key": "k2"})
    c.post("/charge", json={"usd": 5, "idempotency_key": "k2"})
    assert effects == [5, 5, 5], ("no key = as before; a body key works like the header", effects)
    # two at once with one key: one effect
    import concurrent.futures as cf
    slow: list = []

    @app.post("/slow")
    def slow_charge(request: Request, body: dict = Body(...)):
        def make() -> dict:
            time.sleep(0.3)
            slow.append(1)
            return {"n": len(slow)}
        return once(request, "u1", body, make)

    with cf.ThreadPoolExecutor(4) as ex:
        got = list(ex.map(lambda _: c.post("/slow", json={}, headers={"Idempotency-Key": "s"}).json(), range(4)))
    assert slow == [1] and all(g == {"n": 1} for g in got), ("concurrent identical POSTs made more than one effect", slow, got)
    # compare-and-set
    store.write("things", [{"id": "t1", "name": "a"}])
    assert store.update("things", "t1", {"name": "b"})["version"] == 1
    try:
        store.update("things", "t1", {"name": "c"}, expect_version=0)
        raise AssertionError("a stale version was written")
    except HTTPException as e:
        assert e.status_code == 409, e
    assert store.read("things", [])[0]["name"] == "b", "the stale write changed the row"
    assert store.update("things", "t1", {"name": "c"}, expect_version=1)["version"] == 2
    check_version({"version": 2}, None)            # a caller that names no version is not checked
    # send once
    sent: list = []
    send_once("mail", "a@x|decided:f1:1", lambda: sent.append(1))
    send_once("mail", "a@x|decided:f1:1", lambda: sent.append(2))
    assert sent == [1], ("a message marked sent was sent twice", sent)
    try:
        send_once("mail", "b@x|k", lambda: (_ for _ in ()).throw(RuntimeError("smtp down")))
    except RuntimeError:
        pass
    assert send_once("mail", "b@x|k", lambda: sent.append(3)) and sent == [1, 3], "a failed send may be tried again"
    # signed text is never rewritten - a data fix (find-replace over the whole file) is refused
    deal = sign({"id": "nda", "name": "Astrogarvity", "clauses": [{"text": "Astrogarvity keeps it secret"}]}, ["clauses"])
    store.write("deals", [deal])
    rows = json.loads(json.dumps(store.read("deals", [])).replace("Astrogarvity", "Astrogravity"))
    try:
        store.write("deals", rows)
        raise AssertionError("a data fix rewrote signed text")
    except store.SignedText as e:
        assert "nda" in str(e), e
    assert store.read("deals", [])[0]["clauses"][0]["text"] == "Astrogarvity keeps it secret", "signed text changed on disk"
    rows = store.read("deals", [])
    rows[0]["name"] = "Astrogravity"                # a field the signature does not cover: fine
    store.write("deals", rows)
    rows[0].pop("signed_hash")
    rows[0]["clauses"][0]["text"] = "x"
    try:
        store.write("deals", rows)
        raise AssertionError("stripping the signed mark let the text change")
    except store.SignedText:
        pass
    print("writes self-check OK")
