"""Agent & MCP door (2026-10-23 owner: "Claude can drive these flows end-to-end for testing and demos instead of the owner clicking";
owner-only, every portal of the family). Claude Code on the owner's laptop runs tools/mcp/server.py (stdio); each tool there is ONE
of the portal's own routes (chip mcp.tools) - this door adds no business logic, it only lets an owner key stand in for a sign-in:

    laptop  tools/mcp/server.py  --(X-Portal-Agent-Key: <key>)-->  door (this middleware)  -->  the route, as the owner

  - the key is made on Admin > Agent & MCP, shown once, kept as its fingerprint only (store mcp_keys, a secret file);
  - EVERY call: the key's person must still be the Portal Admin (chip mcp.settings who_role), else 401 - a demoted or
    planted key never works;
  - a key reaches only the tools' own routes (+ always_open); a person's step (sign-in, permissions, payments: mcp.tools
    kind human) is refused with its own words, never attempted;
  - the browser's cookies are dropped and the door's own short sign-in is put in their place, so the route and Portal
    Activity (core/ledger.py) see the owner - nothing per route.
Words: chip ui.mcp. Guard: the portal's selfcheck_mcp.py (bitten on a copy)."""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import time
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse

from core import access, auth, engine, lists, ops, store

router = APIRouter()
FILE = "mcp_keys"                # {user_id: {th, hint, made_at, used_at, uses}} - a key's fingerprint, never the key
store.SECRET_FILES.add(FILE)
_SESS: dict[str, tuple[str, float]] = {}     # user id -> (the door's short session token, until) - one process
_HITS: dict[str, list[float]] = {}           # key fingerprint -> call times in the last minute
_PAT: dict[str, re.Pattern] = {}
ABOUT: list[Callable[[], dict]] = []         # the portal adds what only it knows (its commit) - install(about=...)
ROOT: list[Path] = []


def K() -> dict:
    return engine.run("mcp.settings")


def W(key: str, **v) -> str:
    return ops.template(engine.run("ui.mcp")[key], v)


def tools() -> list[dict]:
    return engine.run("mcp.tools")["tools"]


def _th(key: str) -> str:
    return hashlib.sha256((key or "").encode()).hexdigest()


def _rx(pattern: str) -> re.Pattern:
    if pattern not in _PAT:
        _PAT[pattern] = re.compile(pattern)
    return _PAT[pattern]


def _route_rx(path: str) -> re.Pattern:
    """A tool's path with {slot}s -> the addresses it may reach (a slot is one address part, never a '/')."""
    return _rx("^" + re.sub(r"\\\{[a-z_]+\\\}", "[^/]+", re.escape(path)) + "$")


def human_hit(path: str) -> dict | None:
    """The person's step this address is (mcp.tools kind human), or None."""
    return next((t for t in tools() if t["kind"] == "human" and any(_rx(p).search(path) for p in t.get("paths") or [])), None)


def allowed(method: str, path: str) -> bool:
    if f"{method} {path}" in K()["always_open"]:
        return True
    return any(c["method"] == method and _route_rx(c["path"]).match(path)
               for t in tools() if t["kind"] != "human" for c in t.get("calls") or [])


def whose(key: str) -> dict | None:
    """The person a key belongs to - only while they are still the Portal Admin (who_role), checked on every call."""
    if not key:
        return None
    th = _th(key)
    uid = next((u for u, r in (store.read(FILE, {}) or {}).items() if secrets.compare_digest(r.get("th", ""), th)), None)
    u = store.user_by_id(uid) if uid else None
    return u if u and u.get("role") == K()["who_role"] and not u.get("disabled") else None


def _session(u: dict) -> str:
    tok, until = _SESS.get(u["id"], ("", 0.0))
    if not tok or until < time.time() or not store.session_user(tok):
        tok = store.start_session(u, int(K()["session_s"]) + 60)
        _SESS[u["id"]] = (tok, time.time() + int(K()["session_s"]))
    return tok


def _end(uid: str) -> None:
    tok, _ = _SESS.pop(uid, ("", 0.0))
    if tok:
        store.end_session(tok)


def _note_use(uid: str) -> None:
    with store._LOCK:  # noqa: SLF001
        rows = store.read(FILE, {}) or {}
        r = rows.get(uid)
        if not r:
            return
        r["uses"], r["used_at"] = int(r.get("uses") or 0) + 1, store.now()
        store.write(FILE, rows)


def _no(status: int, text: str) -> JSONResponse:
    return JSONResponse({"detail": text}, status_code=status)


async def door(request: Request, call_next):
    """A call carrying an owner key: checked, limited to the tools, then answered as the owner. No key: untouched."""
    k = K()
    key = request.headers.get(k["header"]) or ""
    if not key:
        return await call_next(request)
    path = request.url.path[len(auth.BASE):] if auth.BASE and request.url.path.startswith(auth.BASE) else request.url.path
    th = _th(key)
    now = time.time()
    hits = [t for t in _HITS.get(th, []) if now - t < 60]
    if len(hits) >= int(k["per_minute"]):
        return _no(429, W("e_rate"))
    _HITS[th] = hits + [now]
    u = whose(key)
    if not u:
        return _no(401, W("e_key"))
    h = human_hit(path)
    if h:
        return _no(403, W("e_human", title=h["title"], say=h["say"]))
    if not allowed(request.method, path):
        return _no(403, W("e_not_tool"))
    cookie = f"{auth.COOKIE}={_session(u)}".encode()
    request.scope["headers"] = [(n, v) for n, v in request.scope["headers"] if n.lower() != b"cookie"] + [(b"cookie", cookie)]
    request.state.user = u
    _note_use(u["id"])
    return await call_next(request)


# --- the owner's screen: Admin > Agent & MCP ------------------------------------------------------------------------------

def _row_of(t: dict, n: int) -> dict:
    return {"n": n, "name": t["name"], "kind": t["kind"], "kind_word": W(f"kind_{t['kind']}"), "title": t["title"], "say": t["say"],
            "calls": [f"{c['method']} {c['path']}" for c in t.get("calls") or []]}


def _local_dir() -> str:
    """The portal's folder on the owner's laptop (valuestream.site.json local.dir), for the line to paste."""
    try:
        site = json.loads((ROOT[0] / K()["site_file"]).read_text(encoding="utf-8"))
        return str((site.get("local") or {}).get("dir") or "").rstrip("/\\")
    except (OSError, IndexError, ValueError):
        return ""


def command(request: Request, key: str = "") -> str:
    k = K()
    folder = _local_dir()
    client = f"{folder}/{k['client_path']}" if folder else f"{W('folder_here')}/{k['client_path']}"
    return ops.template(k["command"], {"name": re.sub(r"[^a-z0-9-]", "", k["server_name"].lower()) or "portal", "env_url": k["env_url"],
                                       "url": auth.portal_base(request), "env_key": k["env_key"], "key": key or W("key_here"), "client": client})


def view(u: dict, request: Request) -> dict:
    r = (store.read(FILE, {}) or {}).get(u["id"]) or {}
    ts = tools()
    return {"key": {"hint": r.get("hint", ""), "made_at": r.get("made_at", ""), "used_at": r.get("used_at", ""), "uses": int(r.get("uses") or 0)}
            if r else None, "command": command(request),
            "counts": {kind: sum(1 for t in ts if t["kind"] == kind) for kind in ("read", "change", "human")}}


def make(u: dict, request: Request) -> dict:
    k = K()
    key = k["key_prefix"] + secrets.token_urlsafe(int(k["key_bytes"]))
    with store._LOCK:  # noqa: SLF001
        rows = store.read(FILE, {}) or {}
        rows[u["id"]] = {"th": _th(key), "hint": key[-int(k["hint_len"]):], "made_at": store.now(), "used_at": "", "uses": 0}
        store.write(FILE, rows)
    _end(u["id"])                      # the old key's short sign-in ends with it
    return view(u, request) | {"once": command(request, key)}


def drop(u: dict, request: Request) -> dict:
    with store._LOCK:  # noqa: SLF001
        rows = store.read(FILE, {}) or {}
        rows.pop(u["id"], None)
        store.write(FILE, rows)
    _end(u["id"])
    return view(u, request)


@router.get("/api/mcp")
def api_view(request: Request, u: dict = Depends(access.screen("mcp"))):
    return view(u, request)


@router.post("/api/mcp/key")
def api_make(request: Request, _b: dict = Body(default={}), u: dict = Depends(access.screen("mcp"))):
    return make(u, request)


@router.delete("/api/mcp/key")
def api_drop(request: Request, u: dict = Depends(access.screen("mcp"))):
    return drop(u, request)


@router.get("/api/mcp/tools")
def api_tools(_: dict = Depends(auth.owner)):
    """What the laptop's client lists to Claude Code (the chip's rows, words filled), plus its own words."""
    words = engine.run("ui.mcp")
    return {"tools": tools(), "words": {k_: v for k_, v in words.items() if k_.startswith("c_")}, "product": engine.product_name()}


@router.get("/api/mcp/about")
def api_about(_: dict = Depends(auth.owner)):
    from core import BUILD  # noqa: PLC0415 - set by core.install
    out = {"product": engine.product_name(), "build": BUILD, "now": store.now()}
    for f in ABOUT:
        out |= f() or {}
    return out


lists.source("mcp_tools", lambda u, a: [_row_of(t, i) for i, t in enumerate(tools())], screen="mcp")


def install(app, root: Path, about: Callable[[], dict] | None = None) -> None:
    """In the portal's app.py, LAST of its middlewares (added last = runs first: before the ledger and every guard)."""
    ROOT[:] = [Path(root)]
    if about:
        ABOUT.append(about)
    app.include_router(router)
    app.middleware("http")(door)
