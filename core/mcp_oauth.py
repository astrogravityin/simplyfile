"""Sign in from the AI app - the no-terminal road to Connect your AI (portal-builder never-again 2026-10-23, owner: "No one
should open the terminal"; the AstroStage backend/services/mcp_oauth.py, same standard, same rules).

The MCP door (core/mcp.py) is an OAuth 2.1 protected resource; this module is its authorization server - what every AI
app's "Add custom connector" speaks:
  1. discovery - /.well-known/oauth-protected-resource[/mcp] and /.well-known/oauth-authorization-server
  2. register  - POST /oauth/register: the AI app registers itself (RFC 7591: its name + return addresses)
  3. authorize - GET /oauth/authorize sends the person to this site's Allow card (Connect your AI), signed in with their
                 normal account; Allow -> a one-time code back to the app
  4. token     - POST /oauth/token: code + PKCE S256 verifier -> access + refresh tokens (refresh rotates)
Only SHA-256 hashes of codes and tokens are kept (mcp.sqlite3 grants = the connections). Every knob and word is chip
mcp.server (oauth, local_hosts, words). Who may connect: an owner (the screen is theirs).
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import sqlite3
import threading
import time
from typing import Any
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from core import access, engine, store

router = APIRouter()
_LOCAL = threading.local()
_WRITE = threading.Lock()
SCHEMA = """
CREATE TABLE IF NOT EXISTS clients(client_id TEXT PRIMARY KEY, name TEXT NOT NULL, redirect_uris TEXT NOT NULL, made REAL NOT NULL) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS grants(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, client_id TEXT NOT NULL, client_name TEXT NOT NULL,
  code_hash TEXT NOT NULL DEFAULT '', challenge TEXT NOT NULL DEFAULT '', redirect_uri TEXT NOT NULL DEFAULT '', made REAL NOT NULL,
  code_exp REAL NOT NULL DEFAULT 0, access_hash TEXT NOT NULL DEFAULT '', access_exp REAL NOT NULL DEFAULT 0,
  refresh_hash TEXT NOT NULL DEFAULT '', refresh_exp REAL NOT NULL DEFAULT 0, connected_at REAL NOT NULL DEFAULT 0,
  last_used REAL NOT NULL DEFAULT 0, calls INTEGER NOT NULL DEFAULT 0, revoked_at REAL NOT NULL DEFAULT 0) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS grants_user ON grants(user_id, connected_at);
"""


class OAuthError(Exception):
    def __init__(self, code: str, key: str, **slots: Any):
        super().__init__(key)
        self.code, self.key, self.slots = code, key, slots

    def body(self) -> dict:
        from core import mcp  # noqa: PLC0415
        return {"error": self.code, "error_description": mcp.say(self.key, **self.slots)}


def cfg() -> dict:
    return engine.run("mcp.server")["oauth"]


def db() -> sqlite3.Connection:
    path = str(store.DATA / cfg()["db"])
    c = getattr(_LOCAL, "c", None)
    if c is None or getattr(_LOCAL, "path", "") != path:
        store.DATA.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(path, timeout=15)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript(SCHEMA)
        _LOCAL.c, _LOCAL.path = c, path
    return c


def _hash(raw: str) -> str:
    return hashlib.sha256((raw or "").encode("utf-8")).hexdigest()


def _secret(prefix_key: str) -> str:
    return f"{cfg()[prefix_key]}{secrets.token_urlsafe(int(cfg()['bytes']))}"


def local_hosts() -> set[str]:
    return set(engine.run("mcp.server")["local_hosts"])


def api_base(request: Request) -> str:
    """This site's public origin as the caller reached it (behind nginx: X-Forwarded-*). Not this computer = https."""
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc).split(",")[0].strip()
    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "http").split(",")[0].strip()
    bare = host.split(":")[0] if not host.startswith("[") else host.split("]")[0] + "]"
    return f"{proto if bare in local_hosts() else 'https'}://{host}"


def resource_metadata(api: str) -> dict:
    from core import mcp  # noqa: PLC0415
    return {"resource": f"{api}/mcp", "authorization_servers": [api], "bearer_methods_supported": ["header"],
            "scopes_supported": [cfg()["scope"]], "resource_name": (mcp.cfg()["server"] | mcp.naming())["title"]}


def server_metadata(api: str) -> dict:
    return {"issuer": api, "authorization_endpoint": f"{api}/oauth/authorize", "token_endpoint": f"{api}/oauth/token",
            "registration_endpoint": f"{api}/oauth/register", "scopes_supported": [cfg()["scope"]],
            "response_types_supported": ["code"], "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"], "token_endpoint_auth_methods_supported": ["none"]}


# --- 2. register ------------------------------------------------------------------------------------------------------------

def _redirect_ok(uri: str) -> bool:
    """https anywhere, or http only on the person's own computer (an AI app's loopback callback)."""
    try:
        u = urlparse(uri)
    except ValueError:
        return False
    if u.fragment or not u.netloc:
        return False
    return u.scheme == "https" or (u.scheme == "http" and (u.hostname or "") in {h.strip("[]") for h in local_hosts()})


def register(body: dict) -> dict:
    uris = body.get("redirect_uris")
    if not isinstance(uris, list) or not uris or len(uris) > int(cfg()["max_redirect_uris"]) \
            or not all(isinstance(u, str) and _redirect_ok(u) for u in uris):
        raise OAuthError("invalid_redirect_uri", "oauth_redirect_rule")
    from core import mcp  # noqa: PLC0415
    name = str(body.get("client_name") or "").strip()[: int(cfg()["name_chars"])] or mcp.say("oauth_app_default")
    cid = secrets.token_urlsafe(18)
    with _WRITE, db():
        db().execute("INSERT INTO clients(client_id, name, redirect_uris, made) VALUES(?,?,?,?)", (cid, name, json.dumps(uris), time.time()))
    return {"client_id": cid, "client_name": name, "redirect_uris": uris, "client_id_issued_at": int(time.time()),
            "token_endpoint_auth_method": "none", "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"]}


# --- 3. authorize + Allow ---------------------------------------------------------------------------------------------------

def checked_request(q: dict) -> dict:
    """The authorize parameters, checked: a known app, a return address it registered, code + S256 PKCE. A bad app or
    return address raises - the person is never sent to an unknown place."""
    client = db().execute("SELECT * FROM clients WHERE client_id=?", (str(q.get("client_id") or ""),)).fetchone()
    if not client:
        raise OAuthError("invalid_client", "oauth_client_unknown")
    redirect = str(q.get("redirect_uri") or "")
    if redirect not in json.loads(client["redirect_uris"] or "[]"):
        raise OAuthError("invalid_request", "oauth_redirect_bad")
    if q.get("response_type") != "code":
        raise OAuthError("unsupported_response_type", "oauth_response_type")
    if q.get("code_challenge_method") != "S256" or not q.get("code_challenge"):
        raise OAuthError("invalid_request", "oauth_pkce")
    return {"client_id": client["client_id"], "client_name": client["name"], "redirect_uri": redirect,
            "state": str(q.get("state") or ""), "challenge": str(q["code_challenge"])}


def may_connect(user: dict | None) -> bool:
    return bool(user) and access.may(user, "connect-ai")


def _back(redirect: str, **params: str) -> str:
    return redirect + ("&" if "?" in redirect else "?") + urlencode({k: v for k, v in params.items() if v})


def approve(user: dict, q: dict, allow: bool) -> str:
    """Where the Allow card sends the person: the app's return address with a one-time code, or access_denied."""
    req = checked_request(q)
    if not allow:
        return _back(req["redirect_uri"], error="access_denied", state=req["state"])
    if not may_connect(user):
        raise OAuthError("access_denied", "oauth_not_allowed")
    code, now = _secret("code_prefix"), time.time()
    with _WRITE, db():
        db().execute("INSERT INTO grants(id, user_id, client_id, client_name, code_hash, challenge, redirect_uri, made, code_exp) VALUES(?,?,?,?,?,?,?,?,?)",
                     (store.new_id(), user["id"], req["client_id"], req["client_name"], _hash(code), req["challenge"], req["redirect_uri"], now,
                      now + float(cfg()["code_minutes"]) * 60))
    return _back(req["redirect_uri"], code=code, state=req["state"])


# --- 4. token ---------------------------------------------------------------------------------------------------------------

def _s256(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")


def _issue(g) -> dict:
    acc, ref, now = _secret("access_prefix"), _secret("refresh_prefix"), time.time()
    with _WRITE, db():
        db().execute("UPDATE grants SET access_hash=?, access_exp=?, refresh_hash=?, refresh_exp=?, connected_at=CASE WHEN connected_at=0 THEN ? ELSE connected_at END WHERE id=?",
                     (_hash(acc), now + float(cfg()["access_minutes"]) * 60, _hash(ref), now + float(cfg()["refresh_days"]) * 86400, now, g["id"]))
    return {"access_token": acc, "token_type": "Bearer", "expires_in": int(cfg()["access_minutes"]) * 60, "refresh_token": ref, "scope": cfg()["scope"]}


def token(form: dict) -> dict:
    kind, now = form.get("grant_type"), time.time()
    if kind == "authorization_code":
        g = db().execute("SELECT * FROM grants WHERE code_hash=? AND code_hash!=''", (_hash(str(form.get("code") or "")),)).fetchone()
        if not g or g["revoked_at"] or g["code_exp"] < now or g["client_id"] != form.get("client_id") or g["redirect_uri"] != form.get("redirect_uri"):
            raise OAuthError("invalid_grant", "oauth_code_bad")
        with _WRITE, db():
            db().execute("UPDATE grants SET code_hash='' WHERE id=?", (g["id"],))        # one use only, whatever happens next
        if _s256(str(form.get("code_verifier") or "")) != g["challenge"]:
            raise OAuthError("invalid_grant", "oauth_verifier_bad")
        return _issue(g)
    if kind == "refresh_token":
        g = db().execute("SELECT * FROM grants WHERE refresh_hash=? AND refresh_hash!=''", (_hash(str(form.get("refresh_token") or "")),)).fetchone()
        if not g or g["revoked_at"] or g["refresh_exp"] < now or (form.get("client_id") and g["client_id"] != form.get("client_id")):
            raise OAuthError("invalid_grant", "oauth_refresh_bad")
        return _issue(g)                                                                    # rotates: the old refresh token stops
    raise OAuthError("unsupported_grant_type", "oauth_grant_type")


def bearer_grant(raw: str):
    """(user, grant id) for a live access token, else (None, None). The person must still be allowed to connect."""
    g = db().execute("SELECT * FROM grants WHERE access_hash=? AND access_hash!=''", (_hash(raw),)).fetchone()
    if not g or g["revoked_at"] or g["access_exp"] < time.time():
        return None, None
    user = store.user_by_id(g["user_id"])
    if not may_connect(user):
        return None, None
    with _WRITE, db():
        db().execute("UPDATE grants SET last_used=?, calls=calls+1 WHERE id=?", (time.time(), g["id"]))
    return user, g["id"]


def connections(user: dict) -> list[dict]:
    rows = db().execute("SELECT * FROM grants WHERE user_id=? AND connected_at>0 AND revoked_at=0 ORDER BY connected_at DESC LIMIT 50", (user["id"],))
    return [{"id": g["id"], "client": g["client_name"], "connected_at": g["connected_at"], "last_used": g["last_used"], "calls": g["calls"]} for g in rows]


def disconnect(user: dict, grant_id: str) -> None:
    with _WRITE, db():
        n = db().execute("UPDATE grants SET revoked_at=?, access_hash='', refresh_hash='' WHERE id=? AND user_id=? AND revoked_at=0",
                         (time.time(), grant_id, user["id"])).rowcount
    if n != 1:
        raise HTTPException(404, OAuthError("invalid_request", "connection_missing").body()["error_description"])


# --- routes -----------------------------------------------------------------------------------------------------------------

def _refuse(e: OAuthError, status: int = 400) -> JSONResponse:
    return JSONResponse(e.body(), status_code=status)


@router.get("/.well-known/oauth-protected-resource")
@router.get("/.well-known/oauth-protected-resource/mcp")
def wk_resource(request: Request):
    return resource_metadata(api_base(request))


@router.get("/.well-known/oauth-authorization-server")
@router.get("/.well-known/oauth-authorization-server/mcp")
def wk_server(request: Request):
    return server_metadata(api_base(request))


@router.post("/oauth/register")
def oauth_register(body: dict = Body(...)):
    try:
        return JSONResponse(register(body or {}), status_code=201)
    except OAuthError as e:
        return _refuse(e)


@router.get("/oauth/authorize")
def oauth_authorize(request: Request):
    """Checked first (a bad app or address is told here, never redirected); then the site's own Allow card."""
    q = dict(request.query_params)
    try:
        checked_request(q)
    except OAuthError as e:
        return _refuse(e)
    return RedirectResponse(f"/#/connect-ai?{urlencode({'allow': '1', **q})}", status_code=302)


@router.post("/oauth/token")
async def oauth_token(request: Request):
    try:
        form = dict(await request.form()) if "form" in (request.headers.get("content-type") or "") else (await request.json() or {})
    except ValueError:                       # W1.3 shape walk: a body that is not JSON was a 500
        form = {}
    form = form if isinstance(form, dict) else {}
    try:
        return JSONResponse(token(form), headers={"Cache-Control": "no-store"})
    except OAuthError as e:
        return _refuse(e)


@router.post("/api/core/mcp/allow-info")
def api_allow_info(body: dict = Body(...), _: dict = Depends(access.screen("connect-ai"))):
    try:
        q = (body or {}).get("query")
        req = checked_request(q if isinstance(q, dict) else {})   # W1.3: a non-object query was a 500
    except OAuthError as e:
        raise HTTPException(400, e.body()["error_description"]) from None
    return {"client": req["client_name"]}


@router.post("/api/core/mcp/approve")
def api_approve(body: dict = Body(...), u: dict = Depends(access.screen("connect-ai"))):
    try:
        q = (body or {}).get("query")
        return {"go": approve(u, q if isinstance(q, dict) else {}, bool((body or {}).get("allow")))}
    except OAuthError as e:
        raise HTTPException(400, e.body()["error_description"]) from None


@router.delete("/api/core/mcp/connections/{grant_id}")
def api_disconnect(grant_id: str, u: dict = Depends(access.screen("connect-ai"))):
    disconnect(u, grant_id)
    from core import mcp  # noqa: PLC0415
    return {"message": mcp.say("disconnected")}


if __name__ == "__main__":  # ponytail: the whole sign-in round trip, each refusal once
    import tempfile
    from pathlib import Path
    store.DATA = Path(tempfile.mkdtemp())
    access.load([])                                       # core's own screens (Connect your AI is one)
    o = store.add_user("o@x.io", "password-o", role="owner")
    m = store.add_user("m@x.io", "password-m")

    def refused(fn, code):
        try:
            fn()
            raise AssertionError(f"not refused: {code}")
        except OAuthError as e:
            assert e.code == code, (e.code, code)
    refused(lambda: register({"redirect_uris": ["http://evil.example/cb"]}), "invalid_redirect_uri")
    app_ = register({"client_name": "Claude", "redirect_uris": ["https://claude.ai/api/mcp/auth_callback", "http://localhost:6274/cb"]})
    verifier = secrets.token_urlsafe(40)
    q = {"client_id": app_["client_id"], "redirect_uri": "https://claude.ai/api/mcp/auth_callback", "response_type": "code",
         "code_challenge": _s256(verifier), "code_challenge_method": "S256", "state": "xyz"}
    refused(lambda: checked_request(q | {"redirect_uri": "https://evil.example/cb"}), "invalid_request")
    refused(lambda: checked_request(q | {"code_challenge_method": "plain"}), "invalid_request")
    assert "error=access_denied" in approve(o, q, False)
    refused(lambda: approve(m, q, True), "access_denied")
    back = approve(o, q, True)
    code = back.split("code=")[1].split("&")[0]
    assert "state=xyz" in back and code.startswith(cfg()["code_prefix"])
    refused(lambda: token({"grant_type": "authorization_code", "code": code, "client_id": app_["client_id"], "redirect_uri": q["redirect_uri"],
                           "code_verifier": "wrong"}), "invalid_grant")
    refused(lambda: token({"grant_type": "authorization_code", "code": code, "client_id": app_["client_id"], "redirect_uri": q["redirect_uri"],
                           "code_verifier": verifier}), "invalid_grant")        # a code is used once, even after a bad verifier
    code = approve(o, q, True).split("code=")[1].split("&")[0]
    tok = token({"grant_type": "authorization_code", "code": code, "client_id": app_["client_id"], "redirect_uri": q["redirect_uri"], "code_verifier": verifier})
    assert bearer_grant(tok["access_token"])[0]["id"] == o["id"] and connections(o)[0]["calls"] == 1
    new = token({"grant_type": "refresh_token", "refresh_token": tok["refresh_token"], "client_id": app_["client_id"]})
    refused(lambda: token({"grant_type": "refresh_token", "refresh_token": tok["refresh_token"]}), "invalid_grant")   # rotated
    assert bearer_grant(tok["access_token"]) == (None, None) and bearer_grant(new["access_token"])[0]
    disconnect(o, connections(o)[0]["id"])
    assert bearer_grant(new["access_token"]) == (None, None) and connections(o) == [], "disconnected = stopped at once"
    print("mcp_oauth self-check OK")
