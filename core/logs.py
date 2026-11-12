"""Request IDs and JSON log lines (owner 2026-11-12, "Yes, A and B" on the VS standards review).

Every request carries one id: the caller's `X-Request-ID` when it is well-formed, else a new one. It goes back on the answer's
header and into every log line written while the request runs - so an error a person reports (the Error Doctor's reference)
leads to its exact lines in the journal. Header name, id shape and the JSON switch are chip log.settings.

    logs.line("job_failed", job=j, why=str(e))     # one JSON line on stderr: at, level, event, request_id, fields
    logs.current()                                 # the id of the request running now ("" outside one)

Python's logging gets the same: install() puts a JSON formatter on the root logger, so `logging.getLogger(x).warning(...)` lines
carry the request id too. ponytail: stderr only - journald keeps and rotates it; a log service can read the JSON as it is.
"""
from __future__ import annotations

import contextvars
import json
import logging
import re
import secrets
import sys
import time

from core import engine

_ID: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


def K() -> dict:
    return engine.run("log.settings")


def current() -> str:
    return _ID.get()


def _stamp() -> str:
    return time.strftime(K()["time_format"], time.gmtime())


def line(event: str, level: str = "info", **fields) -> None:
    rec = {"at": _stamp(), "level": level, "event": event, "request_id": current(), **fields}
    print(json.dumps(rec, default=str, ensure_ascii=False) if K()["json"] else " ".join(f"{k}={v}" for k, v in rec.items()),
          file=sys.stderr, flush=True)


async def request_id(request, call_next):
    """Middleware: the id for this request - the caller's if it is well-formed (chip id_pattern), else a new one."""
    k = K()
    given = request.headers.get(k["header"], "")
    rid = given if re.fullmatch(k["id_pattern"], given or "") else secrets.token_hex(int(k["id_bytes"]))
    token = _ID.set(rid)
    try:
        response = await call_next(request)
    finally:
        _ID.reset(token)
    response.headers[k["header"]] = rid
    return response


class _Json(logging.Formatter):
    def format(self, r: logging.LogRecord) -> str:
        rec = {"at": _stamp(), "level": r.levelname.lower(), "event": r.getMessage(), "logger": r.name, "request_id": current()}
        if r.exc_info:
            rec["error"] = self.formatException(r.exc_info)
        return json.dumps(rec, default=str, ensure_ascii=False)


def install() -> None:
    """Python logging writes JSON lines with the request id (chip log.settings json); called once at start."""
    if not K()["json"]:
        return
    h = logging.StreamHandler(sys.stderr)
    h.setFormatter(_Json())
    root = logging.getLogger()
    root.handlers = [x for x in root.handlers if not isinstance(getattr(x, "formatter", None), _Json)] + [h]
    root.setLevel(str(K()["level"]).upper())


if __name__ == "__main__":
    import asyncio
    import io
    from contextlib import redirect_stderr

    class _Req:
        def __init__(self, h): self.headers = h

    class _Resp:
        def __init__(self): self.headers = {}

    seen: dict = {}

    async def nxt(_r):
        seen["inside"] = current()
        return _Resp()

    k = K()
    out = asyncio.run(request_id(_Req({}), nxt))
    assert out.headers[k["header"]] == seen["inside"] and len(seen["inside"]) == 2 * int(k["id_bytes"]), "no id, or not the same inside"
    assert current() == "", "the id leaked past its request"
    good = "a" * 16
    assert asyncio.run(request_id(_Req({k["header"]: good}), nxt)).headers[k["header"]] == good, "a caller's well-formed id was not kept"
    bad = "x\nInjected: 1"
    assert asyncio.run(request_id(_Req({k["header"]: bad}), nxt)).headers[k["header"]] != bad, "a malformed id was trusted"
    buf = io.StringIO()
    with redirect_stderr(buf):
        tok = _ID.set("rid123")
        line("job_failed", job="j1")
        _ID.reset(tok)
    rec = json.loads(buf.getvalue())
    assert rec["event"] == "job_failed" and rec["request_id"] == "rid123" and rec["job"] == "j1", rec
    print("core.logs OK")
