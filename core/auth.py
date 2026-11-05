"""The way in: first owner, sign up with an emailed code, sign in by user name or email, forgot password
with a code, change password, forced change after an owner's reset, invitations, mail settings.

The standard is `.agents/skills/portal-builder/AUTH.md` (a sibling portal's sign-in card and User Access
reset, with their gaps closed). Built the chip way: this module gathers facts (who, which address, what
was typed, can mail be sent) and does the I/O (sessions, codes, email). Every decision — who may sign up,
what a good user name or password is, how long a code lives, how many tries, lockouts, every sentence —
is an `auth.*` / `mail.texts` chip in core/chips/.

Generic to any portal built on core/. The host adds its own fields to /api/bootstrap through
`BOOTSTRAP_EXTRAS` and never touches a password, a session or a code itself.
"""
from __future__ import annotations

import os
import secrets
import time

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from core import engine, mailer, rules, store

rules.subject("signup", "Somebody signing up", [
    {"name": "email", "type": "text", "label": "Email, lower-cased"},
    {"name": "domain", "type": "text", "label": "The part after @"},
    {"name": "username", "type": "text", "label": "User name chosen"},
    {"name": "name", "type": "text", "label": "Display name typed"},
    {"name": "accounts", "type": "number", "label": "Accounts the portal has now"}])
rules.trigger("signup.submit", "signup", "A sign-up is submitted", ["refuse", "banner", "notify", "flag"],
              "Before the account is made. A refuse outcome stops it with its message.")

BASE = os.getenv("PORTAL_BASE", "").rstrip("/")          # "/tv" when hosted under a path
COOKIE = os.getenv("PORTAL_COOKIE", "portal_session")
KNOWN = COOKIE + "_known"                                 # "this browser has signed in here before" (see known())
#: Reserve the owner seat for one address, so "whoever opens it first owns it" is not a race.
OWNER_EMAIL = os.getenv("PORTAL_OWNER_EMAIL", "").strip().lower()
HTTPS = os.getenv("PORTAL_HTTPS", "").lower() in {"1", "true", "yes"}
#: Tests loosen the limits here; production reads chip auth.limits (and PORTAL_AUTH_PER_MINUTE, when set).
OVERRIDES: dict = {}

#: Callables (request, user|None) -> dict merged into /api/bootstrap. The host's own fields go here.
BOOTSTRAP_EXTRAS: list = []

router = APIRouter()


def msg(key: str, **values) -> str:
    return engine.say("auth.messages", key, **values)


def limits() -> dict:
    lim = dict(engine.run("auth.limits"))
    if os.getenv("PORTAL_AUTH_PER_MINUTE", "").strip().isdigit():
        lim["auth_per_minute"] = int(os.environ["PORTAL_AUTH_PER_MINUTE"])
    if os.getenv("PORTAL_SESSION_DAYS", "").strip().isdigit():
        lim["session_days"] = int(os.environ["PORTAL_SESSION_DAYS"])
    return lim | OVERRIDES


def codes() -> dict:
    return engine.run("auth.code_policy")


def fail(status: int, key: str, field: str = "", **values):
    """An HTTPException whose detail is the sentence (and, for a form, which field it is about)."""
    text = msg(key, **values)
    return HTTPException(status, {"message": text, "field": field} if field else text)


# --- settings the way in depends on ---------------------------------------------------------------

CORE_SETTINGS = ("portal_url", "product_name", "signup_mode", "signup_domains")


def settings() -> dict:
    # open: anyone may sign themselves up — the default, because a door that needs an introduction
    # is a door nobody comes through. closed: the owner creates every account.
    # domain: anyone whose address ends in one of signup_domains.
    return ({"portal_url": "", "product_name": os.getenv("PORTAL_PRODUCT_NAME", "Portal"),
             "signup_mode": "open", "signup_domains": ""}
            | store.read("settings", {}))


def save_settings(body: dict) -> dict:
    """Writes only the framework's own keys; the host's keys in the same file are left alone."""
    with store._LOCK:                       # noqa: SLF001 - part of the store's own tooling
        s = store.read("settings", {})
        for f in CORE_SETTINGS:
            if f in body:
                s[f] = str(body[f] or "").strip()[:200]
        if s.get("signup_mode", "open") not in {"open", "domain", "closed"}:
            raise HTTPException(400, msg("signup_mode_bad"))
        store.write("settings", s)
    return settings()


def portal_base(request: Request) -> str:
    """Where to point a link in an email. The configured address wins; otherwise work it out from
    the request, so a portal nobody has configured yet still sends usable links."""
    configured = settings()["portal_url"].strip().rstrip("/")
    if configured:
        return configured
    return f"{request.headers.get('x-forwarded-proto', request.url.scheme)}://{request.headers.get('host', request.url.netloc)}{BASE}"


def signup_allowed(email: str) -> bool:
    s = settings()
    return engine.run("auth.signup_open", {"mode": s["signup_mode"], "domains": s["signup_domains"],
                                           "domain": (email or "").strip().lower().partition("@")[2]}) is True


# --- how hard one address may knock ---------------------------------------------------------------
# ponytail: a dict per process. One process serves a portal; move it to the store the day a
# second one does.
_HITS: dict[str, list[float]] = {}
_FAILS: dict[str, list[float]] = {}


def _recent(bucket: dict[str, list[float]], key: str, window: float) -> list[float]:
    now = time.time()
    kept = [t for t in bucket.get(key, []) if now - t < window]
    bucket[key] = kept
    if len(bucket) > 5000:             # a flood must not grow the dict without bound
        for dead in [k for k, v in bucket.items() if not v][:2500]:
            bucket.pop(dead, None)
    return kept


def rate_ok(ip: str, per_minute: int | None = None, bucket: dict | None = None) -> bool:
    hits = _recent(_HITS if bucket is None else bucket, ip, 60)
    hits.append(time.time())
    return len(hits) <= (limits()["auth_per_minute"] if per_minute is None else per_minute)


def locked_out(identity: str) -> int:
    """Seconds this account must wait, 0 when it may try now."""
    lim = limits()
    fails = _recent(_FAILS, (identity or "").strip().lower(), lim["lock_for_seconds"])
    return 0 if len(fails) < lim["lock_after"] else int(lim["lock_for_seconds"] - (time.time() - fails[0])) + 1


def note_fail(identity: str) -> None:
    _recent(_FAILS, (identity or "").strip().lower(), limits()["lock_for_seconds"]).append(time.time())


def clear_fails(identity: str) -> None:
    """Every count for this account, from every address (a sign-in counts per account AND address)."""
    k = (identity or "").strip().lower()
    for x in [x for x in _FAILS if x == k or x.startswith(k + "|")]:
        _FAILS.pop(x, None)


#: Who names the caller's address. Only a hop YOU run may be believed: the browser can send any
#: X-Forwarded-For it likes and nginx appends to it, so its FIRST entry is the attacker's choice.
#:   nginx      (default; tv.valuestream.in) X-Real-IP, which nginx overwrites with $remote_addr,
#:              else the LAST X-Forwarded-For hop — the one nginx itself appended.
#:   cloudflare CF-Connecting-IP. Only safe when the origin answers nobody but Cloudflare.
#:   none       the socket peer, for a portal with nothing in front of it.
#: A hosting fact, not a business setting: an environment variable, never an editable chip.
TRUSTED_PROXY = os.getenv("PORTAL_TRUSTED_PROXY", "nginx").strip().lower()
if TRUSTED_PROXY not in {"nginx", "cloudflare", "none"}:
    raise RuntimeError(f"PORTAL_TRUSTED_PROXY must be nginx, cloudflare or none, not {TRUSTED_PROXY!r}")


def client_ip(request: Request) -> str:
    h = request.headers
    if TRUSTED_PROXY == "nginx":
        ip = h.get("x-real-ip", "") or h.get("x-forwarded-for", "").split(",")[-1]
    elif TRUSTED_PROXY == "cloudflare":
        ip = h.get("cf-connecting-ip", "")
    else:
        ip = ""
    return ip.strip() or (request.client.host if request.client else "?")


async def limit_auth(request: Request, call_next):
    if request.url.path.startswith((f"{BASE}/api/auth/", "/api/auth/")):
        if not rate_ok(client_ip(request)):
            return JSONResponse({"detail": msg("rate_limited")}, status_code=429)
    return await call_next(request)


async def force_password_change(request: Request, call_next):
    """After an owner's reset with "require change at next login", nothing but the way in answers until
    the person has chosen their own password. On the SERVER: a page can be skipped, a request cannot."""
    token = request.cookies.get(COOKIE)
    if token:
        u = store.session_user(token)
        path = request.url.path[len(BASE):] if BASE and request.url.path.startswith(BASE) else request.url.path
        if u and u.get("must_change_password") and path.startswith("/api/") \
                and engine.run("auth.must_change_allows", {"path": path}) is not True:
            return JSONResponse({"detail": {"message": msg("must_change"), "must_change_password": True}}, status_code=403)
    return await call_next(request)


# --- who is asking ------------------------------------------------------------------------------

def current_user(request: Request) -> dict | None:
    token = request.cookies.get(COOKIE) or ""
    u = store.session_user(token)
    if u and u.get("blocked"):                         # 2026-11-05 blocked (People & access / CC Clean-up): no way in
        from core import artifacts  # noqa: PLC0415 - except this process's own clean-up call (core/artifacts.py)
        u = u if artifacts.lets_blocked_in(request) else None
    if u:
        # Which sitting this person is in, so work paid for on somebody else's key can be reported
        # per sitting. Only a digest of the token is kept, never the token.
        store.note_session(u["id"], token)
    return u


def signed_in(request: Request) -> dict:
    u = current_user(request)
    if not u:
        raise HTTPException(401, msg("sign_in_first"))
    return u


def owner(request: Request) -> dict:
    u = signed_in(request)
    if u.get("role") != "owner":
        raise HTTPException(403, msg("owner_only"))
    return u


def who(u: dict) -> str:
    return u.get("email", "")


def _secure() -> bool:
    """2026-10-20 critical review: Secure rode on PORTAL_HTTPS alone - a portal whose own address is https always sets it."""
    return HTTPS or str(settings().get("portal_url") or "").startswith("https://")


def _sign_in(response: Response, u: dict) -> dict:
    if u.get("blocked"):                               # every road in (password, code, one sign-in) comes through here
        raise fail(403, "blocked")
    ttl = int(limits()["session_days"]) * 86400
    response.set_cookie(COOKIE, store.start_session(u, ttl), httponly=True, samesite="lax",
                        max_age=ttl, path=BASE or "/", secure=_secure())
    # 2026-10-05 owner: a returning visitor skips the landing page. Only "this browser has signed in here" - no one's
    # identity; sign-out leaves it, so the next visit opens on sign-in.
    response.set_cookie(KNOWN, "1", httponly=True, samesite="lax", max_age=int(limits()["known_days"]) * 86400,
                        path=BASE or "/", secure=_secure())
    return {"user": store.public_user(u)}


def known(request: Request) -> bool:
    """This browser has signed in to this portal before (cookie set by _sign_in)."""
    return request.cookies.get(KNOWN) == "1"


# --- field checks (all chips) ---------------------------------------------------------------------

def check_fields(*, email: str | None = None, username: str | None = None, name: str | None = None,
                 password: str | None = None, confirm: str | None = None, known_user: str = "") -> None:
    """Raises 400 with the first problem and the field it belongs to. Only the fields given are checked."""
    checks = []
    if name is not None:
        checks.append(("name", "auth.display_name_problem", {"name": name}))
    if username is not None:
        checks.append(("username", "auth.username_problem", {"username": username, "email": email or ""}))
    if email is not None:
        checks.append(("email", "auth.email_problem", {"email": email}))
    if password is not None:
        checks.append(("password", "auth.password_problem",
                       {"password": password, "confirm": password if confirm is None else confirm,
                        "password_lower": password.lower(), "username": (username or known_user or "").lower(),
                        "email": (email or "").lower()}))
    for field, chip_id, facts in checks:
        problem = engine.run(chip_id, facts)
        if problem:
            mismatch = chip_id == "auth.password_problem" and problem == engine.knobs(chip_id)["msg_mismatch"]
            raise HTTPException(400, {"message": problem, "field": "confirm" if mismatch else field})


def _norm(v) -> str:
    return str(v or "").strip().lower()


# --- sign in ------------------------------------------------------------------------------------

@router.get("/api/bootstrap")
def bootstrap(request: Request):
    u = current_user(request)
    s = settings()
    c = codes()
    first = not store.users()
    # 2026-10-01 assessment: the owner's address went to every anonymous visitor - only the first-run screen needs it
    out = {"needs_first_account": first, "user": store.public_user(u) if u else None,
           "reserved_owner": OWNER_EMAIL if first else "", "product_name": s["product_name"],
           "portal_url": s["portal_url"], "base": BASE,
           "can_email": mailer.configured(),
           "no_mail_policy": engine.run("auth.no_mail_policy"),
           "can_signup": s["signup_mode"] in {"open", "domain"},
           "verify_email": mailer.configured(),
           "code": {"digits": c["digits"], "resend_after_seconds": c["resend_after_seconds"]},
           "password_min_length": engine.knobs("auth.password_problem")["min_length"],
           "username_length": [engine.knobs("auth.username_problem")[k] for k in ("min_length", "max_length")],
           "signup_domains": s["signup_domains"] if s["signup_mode"] == "domain" else ""}
    for extra in BOOTSTRAP_EXTRAS:
        out |= extra(request, u)
    return out


@router.post("/api/auth/signin")
def signin(request: Request, response: Response, body: dict = Body(...)):
    identity = _norm(body.get("identity") or body.get("email"))
    # 2026-10-02 security test: 8 wrong passwords from ANYONE locked the owner out for 15 minutes, again and again. Wrong
    # tries now count per account AND address - a stranger locks out only their own tries
    tries = f"{identity}|{client_ip(request)}"
    wait = locked_out(tries)
    if wait:
        raise fail(429, "locked", minutes=max(1, wait // 60))
    u = store.find_user(identity)
    if not u or not store.check_password(body.get("password", ""), u.get("password", "")):
        note_fail(tries)
        raise fail(401, "wrong_password")
    clear_fails(identity)
    if engine.run("auth.signin_gate", {"verified": u.get("verified") is not False, "mail": mailer.configured()}) == "verify_first":
        raise fail(403, "verify_first")
    return _sign_in(response, u)


@router.post("/api/auth/first-account")
def first_account(response: Response, body: dict = Body(...)):
    """Only ever works once: the first person to open the portal becomes its owner.
    With `PORTAL_OWNER_EMAIL` set that seat is RESERVED — nobody else can take it, however early."""
    if store.users():
        raise fail(409, "owner_exists")
    email, username = _norm(body.get("email")), _norm(body.get("username"))
    if OWNER_EMAIL and email != OWNER_EMAIL:
        raise fail(403, "owner_reserved", email=OWNER_EMAIL)
    name = str(body.get("display_name") or body.get("name") or email.split("@")[0]).strip()
    check_fields(email=email, name=name, username=username or None,
                 password=body.get("password", ""), confirm=body.get("confirm"))
    u = store.add_user(email, body.get("password", ""), name, role="owner", username=username)
    return _sign_in(response, u)


# --- emailed codes ------------------------------------------------------------------------------

def _held(purpose: str, email: str, logged_as: str) -> bool:
    """The throttle: too many codes to one address this hour. A held send is logged, not mailed."""
    if store.recent_codes(purpose, email, 3600) < limits()["sends_per_hour"]:
        return False
    store.log_mail(logged_as, email, "throttled", next_at=store.code_free_at(purpose, email, 3600))
    return True


def _mail(purpose: str, email: str, subject: str, text: str) -> None:
    """Sends, and records what happened for the owner's Recent mail (Setup -> Email). A stranger learns nothing."""
    try:
        mailer.send(email, subject, text)
    except RuntimeError as e:  # the owner sees the reason on Recent mail and on the Test button
        print(f"[auth] could not send a {purpose} mail: {e}", flush=True)
        store.log_mail(purpose, email, "failed", error=str(e))
        return
    store.log_mail(purpose, email, "sent")


def _send_code(purpose: str, email: str) -> None:
    c = codes()
    if _held(purpose, email, purpose):
        return
    code = "".join(secrets.choice("0123456789") for _ in range(int(c["digits"])))
    ttl = int(c[f"{purpose}_ttl_seconds"])
    store.put_code(purpose, email, code, ttl)
    store.log_code(purpose, email)
    subject, text = mailer.compose(f"code_{purpose}", product=settings()["product_name"], code=code, minutes=ttl // 60)
    _mail(purpose, email, subject, text)


def _send_notice(kind: str, email: str) -> None:
    """A letter instead of a code, under the same throttle (someone typed an address that has an account)."""
    if _held("signup", email, kind):
        return
    store.log_code("signup", email)
    subject, text = mailer.compose(kind, product=settings()["product_name"])
    _mail(kind, email, subject, text)


@router.post("/api/auth/code/send")
def send_code(body: dict = Body(...)):
    """Emails a code for `signup` (identity = the address to confirm) or `reset` (identity = user name or
    email). Always the same answer, so it cannot be used to find out who has an account."""
    purpose = body.get("purpose")
    if purpose not in ("signup", "reset"):
        raise HTTPException(400, msg("bad_purpose"))
    identity = _norm(body.get("identity") or body.get("email"))
    # 2026-10-08 owner: a too-short user name was only refused at the password step, after the code was mailed. The
    # details step checks every field it carries (chips auth.*_problem) and a taken user name before any mail goes out
    if purpose == "signup" and ("username" in body or "display_name" in body):
        username = _norm(body.get("username"))
        check_fields(name=str(body.get("display_name") or "").strip(), username=username, email=identity)
        if username and store.username_taken(username):
            raise fail(409, "taken_username", field="username")
    if not mailer.configured():
        if purpose == "reset":
            return {"mail": False, "message": msg("no_mail_reset")}
        if engine.run("auth.no_mail_policy") == "closed":
            raise fail(503, "signup_waits_for_mail")
        return {"mail": False, "message": ""}          # sign-up goes straight to the password step
    if purpose == "signup":
        check_fields(email=identity)
        if not store.users():
            raise fail(409, "no_owner_yet")
        if not signup_allowed(identity):
            s = settings()
            raise fail(403, "signup_closed") if s["signup_mode"] == "closed" else fail(403, "signup_domains", domains=s["signup_domains"])
        if not store.find_user(identity):
            _send_code("signup", identity)
        else:
            _send_notice("signup_exists", identity)
    else:
        u = store.find_user(identity)
        if u and u.get("email"):
            _send_code("reset", u["email"])
        else:   # the owner's Recent mail says why nothing went; the answer below stays the same for everyone
            store.log_mail("reset", identity, "no_email" if u else "no_account")
    return {"mail": True, "message": msg("code_sent"), "resend_after_seconds": codes()["resend_after_seconds"]}


@router.post("/api/auth/code/check")
def check_code(body: dict = Body(...)):
    """A right code becomes a single-use proof for the next step. A wrong one counts; too many burn it.
    An unknown account and a wrong code get the same answer."""
    purpose = body.get("purpose")
    if purpose not in ("signup", "reset"):
        raise HTTPException(400, msg("bad_purpose"))
    identity = _norm(body.get("identity") or body.get("email"))
    email = identity if purpose == "signup" else ((store.find_user(identity) or {}).get("email") or "")
    c = codes()
    outcome = store.check_code(purpose, email, str(body.get("code") or ""), int(c["max_attempts"])) if email else "wrong"
    if outcome == "burned":
        raise fail(400, "code_burned", field="code")
    if outcome != "ok":
        raise fail(400, "code_wrong", field="code")
    return {"proof": store.make_token(f"proof_{purpose}", email, int(c["proof_ttl_seconds"]))}


# --- sign up ------------------------------------------------------------------------------------

@router.post("/api/auth/signup")
def signup(response: Response, body: dict = Body(...)):
    """Display name + user name + email, a code that proves the address (when mail can be sent), then a
    password twice. The proof is spent only after every check passes — a taken user name never wastes it."""
    email, username = _norm(body.get("email")), _norm(body.get("username"))
    name = str(body.get("display_name") or body.get("name") or "").strip()
    s = settings()
    if not store.users():
        raise fail(409, "no_owner_yet")
    if not signup_allowed(email):
        raise fail(403, "signup_closed") if s["signup_mode"] == "closed" else fail(403, "signup_domains", domains=s["signup_domains"])
    mail = mailer.configured()
    if not mail and engine.run("auth.no_mail_policy") == "closed":
        raise fail(503, "signup_waits_for_mail")
    check_fields(name=name, username=username, email=email,
                 password=body.get("password", ""), confirm=body.get("confirm"))
    proof = str(body.get("proof") or "")
    if mail and store.peek_token(proof, "proof_signup") != email:
        raise fail(400, "proof_expired", field="code")
    if store.find_user(email):
        raise fail(409, "taken_email", field="email")
    if username and store.username_taken(username):
        raise fail(409, "taken_username", field="username")
    said = rules.fire("signup.submit", {"email": email, "domain": email.partition("@")[2], "username": username,
                                        "name": name, "accounts": len(store.users())})
    if rules.refusal(said):
        raise HTTPException(403, rules.refusal(said))
    if mail and store.use_token(proof, "proof_signup") != email:
        raise fail(400, "proof_expired", field="code")
    u = store.add_user(email, body.get("password", ""), name, engine.run("people.new_account_role"),
                       verified=mail, username=username)
    return _sign_in(response, u) | {"signed_in": True}


# --- another ValueStream portal's Connect Store -----------------------------------------------------

def _site_key(request: Request) -> None:
    """Machines only: the key both portals hold in env CONNECT_STORE_KEY. No key set here = the door is shut."""
    key = os.environ.get("CONNECT_STORE_KEY", "")
    if not key or not secrets.compare_digest(key, request.headers.get("X-Site-Key", "")):
        raise HTTPException(403)


@router.post("/api/auth/site-account")
def site_account(body: dict = Body(...), _: None = Depends(_site_key)):
    """Connect Store on another portal has proved this email with its own code. With only an email: is there an account?
    With a user name and password: make one (2026-10-30, framework for every connector that lives on a portal)."""
    email, username = _norm(body.get("email")), _norm(body.get("username"))
    check_fields(email=email)
    if "password" not in body:
        return {"exists": bool(store.find_user(email))}
    name = str(body.get("name") or username).strip()
    check_fields(name=name, username=username, email=email, password=body.get("password", ""), confirm=body.get("confirm"))
    if store.find_user(email):
        raise fail(409, "taken_email", field="email")
    if username and store.username_taken(username):
        raise fail(409, "taken_username", field="username")
    said = rules.fire("signup.submit", {"email": email, "domain": email.partition("@")[2], "username": username,
                                        "name": name, "accounts": len(store.users())})
    if rules.refusal(said):
        raise HTTPException(403, rules.refusal(said))
    store.add_user(email, body.get("password", ""), name, engine.run("people.new_account_role"), verified=True, username=username)
    return {"created": True}


# --- forgot, reset, change ---------------------------------------------------------------------------

@router.post("/api/auth/reset")
def reset(body: dict = Body(...)):
    """Forgot password, last step: a proof from the emailed code, the new password twice. Every session of
    that account ends; the person signs in again with the new password."""
    u = store.find_user(_norm(body.get("identity") or body.get("email")))
    proof = str(body.get("proof") or "")
    if not u or store.peek_token(proof, "proof_reset") != u["email"]:
        raise fail(400, "proof_expired", field="code")
    check_fields(password=body.get("password", ""), confirm=body.get("confirm"), known_user=u.get("username", ""))
    if store.use_token(proof, "proof_reset") != u["email"]:
        raise fail(400, "proof_expired", field="code")
    store.set_password(u["email"], body.get("password", ""), must_change=False)
    store.verify_user(u["email"])                  # the code proved the address
    store.end_sessions_for(u["id"])
    clear_fails(u["email"])
    clear_fails(u.get("username", ""))
    return {"ok": True, "message": msg("reset_done")}


@router.post("/api/auth/password")
def change_password(request: Request, body: dict = Body(...)):
    """Signed in: current password, new one twice. Also the way out of a forced change (current = the
    temporary password). Other sessions end; this one stays."""
    me = signed_in(request)
    if not store.check_password(body.get("current", ""), me.get("password", "")):
        raise fail(400, "current_wrong", field="current")
    if body.get("password", "") == body.get("current", ""):
        raise fail(400, "same_password", field="password")
    check_fields(password=body.get("password", ""), confirm=body.get("confirm"), known_user=me.get("username", ""))
    store.set_password(me["email"], body.get("password", ""), must_change=False)
    store.end_sessions_for(me["id"], keep_token=request.cookies.get(COOKIE) or "")
    return {"ok": True}


# --- invitations (the owner created the account; the person chooses the password) -------------------

@router.get("/api/auth/token/{kind}/{token}")
def token_owner(kind: str, token: str):
    """Who an invitation link belongs to, so the page can greet them. Does not spend it."""
    if kind != "invite":
        raise HTTPException(404, msg("unknown_link"))
    email = store.peek_token(token, "invite")
    if not email:
        raise fail(400, "invite_bad")
    return {"email": email}


@router.post("/api/auth/invite")
def accept_invite(response: Response, body: dict = Body(...)):
    email = store.peek_token(str(body.get("token") or ""), "invite")
    u = store.find_user(email or "")
    if not u:
        raise fail(400, "invite_bad")
    check_fields(password=body.get("password", ""), confirm=body.get("confirm"), known_user=u.get("username", ""))
    if store.use_token(str(body.get("token") or ""), "invite") != email:
        raise fail(400, "invite_bad")
    store.set_password(email, body.get("password", ""), must_change=False)
    store.verify_user(email)                       # opening a link sent to the address proves it
    return _sign_in(response, store.find_user(email))


@router.post("/api/auth/signout")
def signout(request: Request, response: Response):
    store.end_session(request.cookies.get(COOKIE) or "")
    response.delete_cookie(COOKIE, path=BASE or "/")
    return {"ok": True}


# --- mail ---------------------------------------------------------------------------------------

@router.get("/api/smtp")
def get_smtp(_: dict = Depends(owner)):
    c = mailer.config()
    masked = lambda v: f"••••••••{str(v)[-4:]}" if len(str(v or "")) > 8 else ("••••••••" if v else "")  # noqa: E731
    fields = mailer.smtp_fields()
    return {"fields": fields,
            "values": {f: (masked(c.get(f, "")) if meta["secret"] else c.get(f, ""))
                       for f, meta in fields.items()},
            "configured": mailer.configured()}


@router.put("/api/smtp")
def put_smtp(body: dict = Body(...), _: dict = Depends(owner)):
    # A masked value coming back means "leave it alone" — the browser never had the real one.
    mailer.save({f: v for f, v in (body.get("values") or {}).items() if not str(v).startswith("•")})
    return {"configured": mailer.configured()}


@router.post("/api/smtp/test")
def test_smtp(body: dict = Body(default={}), me: dict = Depends(owner)):
    """Prove it before anyone depends on it. Errors come back as one sentence, not a stack trace."""
    to = (body.get("to") or me["email"]).strip()
    subject, text = mailer.compose("test", product=settings()["product_name"])
    try:
        mailer.send(to, subject, text)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    return {"sent_to": to}


@router.get("/api/smtp/log")
def smtp_log(_: dict = Depends(owner)):
    """Recent mail: every code and notice the portal tried to send, newest first, and what became of it.
    How a row is shown (its tone) is chip mail.outcomes; its words are ui.access."""
    shown = int(engine.setting("mail.settings", "log_shown"))
    return {"rows": list(reversed(store.mail_log()))[:shown], "tones": engine.run("mail.outcomes"),
            "sender": mailer.config().get("from_email", ""), "per_hour": limits()["sends_per_hour"]}
