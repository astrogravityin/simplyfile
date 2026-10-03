"""The portal framework's store: JSON files under data/, plus accounts, sessions and one-shot links.

Every portal built on core/ keeps its small, precious state here: people, sign-ins, access rules,
settings. It fits in a folder you can zip and hand to someone. No database to install, no
migrations, nothing to configure. (High-volume rows — the activity ledger and page views — live in
SQLite instead; see ledger.py.)

ponytail: one process-wide lock, whole-file atomic writes. Move to SQLite the day two processes
need to write at once or data/ stops fitting in memory.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

#: The HOST portal's folder (core/ sits inside it), so data/ lands beside the portal, not inside core/.
ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.getenv("PORTAL_DATA", ROOT / "data"))
_LOCK = threading.RLock()

#: Files that hold secrets, written owner-only. A host portal adds its own (e.g. API keys).
SECRET_FILES = {"users", "sessions", "smtp", "tokens", "codes", "secret"}


def keep_aside(path, copy: bool = False) -> Path | None:
    """2026-09-26 (seven paid film clips lost to one press): a made, paid or uploaded file is never overwritten or
    deleted outright - it moves to replaced/ beside it (copy=True leaves it in place until the new one lands), so
    putting it back is a file copy. Returns where it went. # ponytail: kept for good; prune replaced/ when disk matters."""
    import shutil  # noqa: PLC0415
    import time  # noqa: PLC0415
    path = Path(path)
    if not path.is_file():
        return None
    stamp, n = time.strftime("%Y%m%d-%H%M%S"), 1
    dest = path.parent / "replaced" / f"{stamp}-{path.name}"
    while dest.exists():                                # the same file put aside twice in one second keeps both
        n += 1
        dest = path.parent / "replaced" / f"{stamp}-{n}-{path.name}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest) if copy else path.replace(dest)
    return dest


_VERSION = re.compile(r"^(\d{8}-\d{6})(?:-\d+)?-(.+)$")


def versions_of(path) -> list[dict]:
    """2026-09-26 owner: "let me redo anything - warn me, and let me download or put back the old one". Every earlier
    version keep_aside() put in replaced/ for this file, newest first: {v (its file name), at (when it was put aside), size}."""
    path = Path(path)
    d = path.parent / "replaced"
    out = []
    for f in d.iterdir() if d.is_dir() else []:
        m = _VERSION.match(f.name)
        if f.is_file() and m and m.group(2) == path.name:
            out.append({"v": f.name, "at": datetime.strptime(m.group(1), "%Y%m%d-%H%M%S").isoformat(), "size": f.stat().st_size})
    return sorted(out, key=lambda r: r["v"], reverse=True)


def keep_record(path, obj) -> Path | None:
    """A TEXT being replaced (a script, a story, a chapter's pages - kept inside a record, not as a file of its own):
    written as JSON at `path` and set aside like a file, so Earlier versions lists, downloads and puts it back."""
    import json  # noqa: PLC0415
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return keep_aside(path)


def restore_version(path, v: str) -> Path:
    """Put an earlier version back: the one in use goes to replaced/ first (so this can be undone the same way)."""
    path = Path(path)
    if v not in {r["v"] for r in versions_of(path)}:
        raise FileNotFoundError(v)
    keep_aside(path)
    (path.parent / "replaced" / v).replace(path)
    return path


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def seconds_since(iso: str) -> float:
    """How long ago a store.now() stamp was; a stamp that cannot be read counts as long ago."""
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(str(iso))).total_seconds()
    except (TypeError, ValueError):
        return float("inf")


def new_id() -> str:
    return uuid.uuid4().hex[:12]


# --- raw files ---------------------------------------------------------------------------------

def path_of(name: str) -> Path:
    return DATA / f"{name}.json"


_TEXT: dict = {}


def read(name: str, default):
    # 2026-09-30 "thousands of assets": one list page read the same small file hundreds of times. The file's text is
    # kept until its time or size changes; every caller still gets its own parsed copy.
    with _LOCK:
        p = path_of(name)
        try:
            st = p.stat()
        except OSError:
            _TEXT.pop(name, None)
            return default
        sig = (str(p), st.st_mtime_ns, st.st_size)
        try:
            if (_TEXT.get(name) or (None,))[0] != sig:
                _TEXT[name] = (sig, p.read_text(encoding="utf-8"))
            return json.loads(_TEXT[name][1])
        except (OSError, ValueError):
            _TEXT.pop(name, None)
            return default


_VIEW: dict = {}


def view(name: str, default):
    """The file parsed ONCE and shared, READ-ONLY, until its time or size changes (or `write` replaces it).

    2026-10-01 owner "1000s of cards ... cannot take so much time": `read` parses on every call, so a list of works,
    users or circles was parsed again for every row, every cover and every byte-range of a video. A caller that will
    change what it gets uses `read` (its own copy); a caller that only looks uses `view` and never mutates it.
    Guard: core/store.py self-check (a write is seen at once; the same object comes back while nothing changed)."""
    with _LOCK:
        p = path_of(name)
        try:
            st = p.stat()
        except OSError:
            _VIEW.pop(name, None)
            return default
        sig = (str(p), st.st_mtime_ns, st.st_size)
        hit = _VIEW.get(name)
        if hit and hit[0] == sig:
            return hit[1]
        try:
            text = p.read_text(encoding="utf-8")
            val = json.loads(text)
        except (OSError, ValueError):
            _VIEW.pop(name, None)
            return default
        _VIEW[name] = (sig, val, {}, text)
        return val


_MEMO: dict = {}


def kept_while(key: tuple, names: list[str], make, most: int = 512):
    """make()'s answer kept until any of these files changes (time or size) - for a whole-list scan many requests ask
    alike (2026-10-02 load test: a reader's Shared-with-you scanned all 15,000 works on every Home / Watch / Read).
    The answer is SHARED: callers copy before they change it.
    ponytail: oldest-first eviction at `most`; stale entries wait for eviction. A chip change is not seen until a file moves."""
    sig = (key, *((n, *((lambda st: (st.st_mtime_ns, st.st_size))(path_of(n).stat()) if path_of(n).exists() else ())) for n in names))
    with _LOCK:
        if sig in _MEMO:
            return _MEMO[sig]
    val = make()
    with _LOCK:
        while len(_MEMO) >= most:
            _MEMO.pop(next(iter(_MEMO)))
        _MEMO[sig] = val
    return val


def views_intact() -> list[str]:
    """The shared copies some reader CHANGED (they must stay as the file says) - the self-checks' tripwire."""
    with _LOCK:
        return sorted(n for n, h in _VIEW.items() if json.loads(h[3]) != h[1])


def index(name: str, key: str) -> dict:
    """`view(name)` (a list of rows) as {row[key]: row}, built once per change of the file - a lookup by id never scans
    the whole file again. READ-ONLY, like `view`."""
    with _LOCK:
        rows = view(name, [])
        hit = _VIEW.get(name)
        if not hit or hit[1] is not rows:
            return {str(r.get(key)): r for r in rows if isinstance(r, dict)} if isinstance(rows, list) else {}
        if key not in hit[2]:
            hit[2][key] = {str(r.get(key)): r for r in rows if isinstance(r, dict)} if isinstance(rows, list) else {}
        return hit[2][key]


def row(name: str, row_id: str, key: str = "id") -> dict | None:
    """One row of a list file by id, as the caller's OWN copy (safe to change and write back) - from the shared index,
    so a per-card lookup never parses the person's whole file again (2026-10-01 owner "1000s of cards")."""
    rid = str(row_id or "")
    with _LOCK:
        r = index(name, key).get(rid)
        if r is None:
            return None
        hit = _VIEW.get(name)
        texts = hit[2].setdefault(("text", key), {}) if hit else {}
        if rid not in texts:                       # a copy at C speed: the row's own JSON, made once per file change
            texts[rid] = json.dumps(r, ensure_ascii=False)
        return json.loads(texts[rid])


def write(name: str, value) -> None:
    with _LOCK:
        _VIEW.pop(name, None)                          # the shared copy is never older than the file
        _TEXT.pop(name, None)                          # nor read()'s kept text (a same-size write inside one mtime tick)
        DATA.mkdir(parents=True, exist_ok=True)
        p = path_of(name)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)
        # Keys and sessions are secrets: keep them owner-only where the OS supports it.
        if name in SECRET_FILES:
            try:
                os.chmod(p, 0o600)
            except OSError:
                pass


# --- users and sign-in -------------------------------------------------------------------------

def hash_password(password: str, salt: str = "") -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
    return f"pbkdf2$200000${salt}${digest.hex()}"


def check_password(password: str, stored: str) -> bool:
    try:
        _, _, salt, _ = (stored or "").split("$", 3)
    except ValueError:
        return False
    return secrets.compare_digest(hash_password(password, salt), stored)


def users() -> list[dict]:
    return read("users", [])


def user_by_id(user_id: str) -> dict | None:
    """One person by id, from the shared index (READ-ONLY) - never a scan of every account per request."""
    u = index("users", "id").get(str(user_id or ""))
    return dict(u) if u else None                      # a caller may add to its own copy; the index stays clean


def find_user(identity: str) -> dict | None:
    """By email or by user name — people sign in with either."""
    key = (identity or "").strip().lower()
    if not key:
        return None
    u = index("users", "email").get(key) or index("users", "username").get(key)   # 2026-10-02 audit: no scan per call
    return dict(u) if u else None


def username_taken(username: str, except_id: str = "") -> bool:
    key = (username or "").strip().lower()
    u = index("users", "username").get(key)            # 2026-10-04 audit: a lookup, not a scan of every account
    return bool(u) and u["id"] != except_id


def _free_username(base: str, rows: list[dict]) -> str:
    """A user name nobody has, made from an email's local part: "Ravi.K+x" → "ravi.k.x" → "ravi.k.x2".
    2026-10-04 audit: the making is chip auth.username_make, and a made name passes the same chip a typed one does
    (auth.username_problem: length, characters, RESERVED) - admin@... no longer became the user name "admin"."""
    from core import engine  # noqa: PLC0415 - engine imports store
    k = engine.run("auth.username_make")
    stem = re.sub(k["strip_pattern"], ".", (base or k["fallback"]).lower()).strip("._-")[:int(k["stem_max"])] or k["fallback"]
    if not stem[0].isalnum():
        stem = f"{k['lead']}{stem}"
    taken = {u.get("username") for u in rows}
    name, n = stem, 1
    while name in taken or engine.run("auth.username_problem", {"username": name}):
        n += 1
        if n > int(k["most_tries"]):
            raise ValueError(_say("auth.messages", "taken_username"))
        name = f"{stem}{n}"
    return name


def add_user(email: str, password: str, name: str = "", role: str = "",
             verified: bool = True, username: str = "") -> dict:
    """Stores an account. The CALLER has already checked every field against the auth.* chips — the store
    keeps data, it does not decide what a good password is."""
    email = (email or "").strip().lower()
    with _LOCK:
        rows = users()
        if any(u["email"] == email for u in rows):
            raise ValueError(_say("auth.messages", "taken_email"))
        uname = (username or "").strip().lower() or _free_username(email.split("@")[0], rows)
        if any(u.get("username") == uname for u in rows):
            raise ValueError(_say("auth.messages", "taken_username"))
        u = {"id": new_id(), "email": email, "username": uname, "name": name.strip() or email.split("@")[0],
             "role": role or _chip("people.new_account_role"), "password": hash_password(password), "created_at": now(),
             # Accounts an owner creates are trusted already; self-signup without a code is False until the
             # person proves the address is theirs.
             "verified": verified}
        rows.append(u)
        write("users", rows)
    return u


def ensure_usernames() -> None:
    """Accounts made before user names existed get one, once."""
    with _LOCK:
        rows = users()
        if all(u.get("username") for u in rows):
            return
        for u in rows:
            if not u.get("username"):
                u["username"] = _free_username(u["email"].split("@")[0], rows)
        write("users", rows)


def set_password(email: str, password: str, must_change: bool = False) -> None:
    with _LOCK:
        rows = users()
        for u in rows:
            if u["email"] == (email or "").strip().lower():
                u["password"] = hash_password(password)
                u["must_change_password"] = bool(must_change)
                write("users", rows)
                return
    raise ValueError(_say("access.messages", "no_account"))


def _say(chip: str, key: str) -> str:
    """A refusal the person reads (callers pass str(e) on) is a chip word - 2026-10-02 audit found English here."""
    from core import engine  # noqa: PLC0415 - engine imports store
    return engine.say(chip, key)


def _chip(chip_id: str, args: dict | None = None):
    from core import engine  # noqa: PLC0415 - engine imports store
    return engine.run(chip_id, args)


def delete_user(user_id: str) -> None:
    with _LOCK:
        rows = [u for u in users() if u["id"] != user_id]
        if not any(_chip("people.is_owner", {"role": u.get("role") or ""}) is True for u in rows):
            raise ValueError(_say("access.messages", "last_owner"))
        write("users", rows)


def delete_user_by_email(email: str) -> None:
    """Used when an account was created but its email could not be sent — never leave a row nobody
    can claim and nobody can see."""
    email = (email or "").strip().lower()
    with _LOCK:
        write("users", [u for u in users() if u["email"] != email])


def public_user(u: dict) -> dict:
    return {k: u[k] for k in _chip("people.public_fields")["fields"] if k in u}


def start_session(user: dict, ttl_seconds: int | None = None) -> str:
    token = secrets.token_urlsafe(32)
    with _LOCK:
        rows = [s for s in read("sessions", []) if s["expires"] > int(_epoch())]
        rows.append({"token": token, "user_id": user["id"], "expires": int(_epoch()) + int(ttl_seconds or _limit("session_days") * 86400)})
        # 2026-10-01: a fixed 500 signed out everyone older once 500 people were signed in - chip auth.limits sessions_kept
        write("sessions", rows[-_limit("sessions_kept"):])
    return token


def end_sessions_for(user_id: str, keep_token: str = "") -> None:
    """Signs a person out everywhere (a reset, a changed password) — except, optionally, this browser."""
    with _LOCK:
        write("sessions", [s for s in read("sessions", []) if s["user_id"] != user_id or
                           (keep_token and secrets.compare_digest(s["token"], keep_token))])


def end_session(token: str) -> None:
    with _LOCK:
        write("sessions", [s for s in read("sessions", []) if s["token"] != token])


# Which sitting a person is in right now. A background job runs in its own thread long after the
# request that started it, so a ContextVar cannot carry this — a small in-memory map can, and a
# restart only means later work joins a new sitting. The session TOKEN is never kept: only a digest.
_SESSION_NOW: dict[str, str] = {}


def note_session(user_id: str, token: str) -> None:
    """auth.current_user on every signed-in request."""
    if user_id and token:
        _SESSION_NOW[user_id] = hashlib.sha256(token.encode()).hexdigest()[:12]


def session_now(user_id: str) -> str:
    return _SESSION_NOW.get(user_id, "")


def session_user(token: str) -> dict | None:
    if not token:
        return None
    # 2026-10-01: every request parsed sessions + users and scanned both (2-3 times a request) - now one shared index each
    row = index("sessions", "token").get(token)
    if not row or not secrets.compare_digest(str(row.get("token") or ""), token) or row["expires"] <= int(_epoch()):
        return None
    return user_by_id(row["user_id"])


def _limit(key: str) -> int:
    """A cap or a time of chip auth.limits (with the portal's env overrides, auth.limits()) - 2026-10-04 audit: the store
    held 14 days, 500 links, 2000 codes, 5000 log rows and one day of its own."""
    from core import auth  # noqa: PLC0415 - auth imports store
    return int(auth.limits()[key])


def _epoch() -> float:
    import time
    return time.time()


# --- one-shot links: verify an address, reset a password, accept an invitation ------------------
# Each token is a single-use coupon with an expiry. Kept in one file because there are never many
# of them alive at once, and a used or stale one is deleted the moment it is looked at.

def make_token(kind: str, email: str, ttl_seconds: int) -> str:
    token = secrets.token_urlsafe(32)
    with _LOCK:
        rows = [t for t in read("tokens", []) if t["expires"] > _epoch()]
        rows.append({"token": token, "kind": kind, "email": (email or "").strip().lower(),
                     "expires": _epoch() + ttl_seconds, "created_at": now()})
        write("tokens", rows[-_limit("tokens_kept"):])
    return token


def peek_token(token: str, kind: str) -> str | None:
    """Whose token this is, without spending it — so a reset page can greet you before you type."""
    row = next((t for t in read("tokens", [])
                if t["kind"] == kind and secrets.compare_digest(t["token"], token or "")), None)
    return row["email"] if row and row["expires"] > _epoch() else None


def use_token(token: str, kind: str) -> str | None:
    """Spend it. Returns the email it was issued for, or None if it is wrong, stale or already used."""
    with _LOCK:
        rows = read("tokens", [])
        row = next((t for t in rows
                    if t["kind"] == kind and secrets.compare_digest(t["token"], token or "")), None)
        if not row:
            return None
        write("tokens", [t for t in rows if t["token"] != row["token"] and t["expires"] > _epoch()])
        return row["email"] if row["expires"] > _epoch() else None


def recent_tokens(kind: str, email: str, within_seconds: int) -> int:
    """How many of these went out lately — the throttle that stops the portal mailbombing someone."""
    email = (email or "").strip().lower()
    cutoff = _epoch() - within_seconds
    return sum(1 for t in read("tokens", [])
               if t["kind"] == kind and t["email"] == email and t.get("expires", 0) > _epoch()
               and _stamp(t.get("created_at", "")) > cutoff)


def _stamp(iso: str) -> float:
    try:
        return datetime.fromisoformat(iso).timestamp()
    except ValueError:
        return 0.0


# --- emailed codes: hashed, per address AND purpose, with a try counter -----------------------------

def portal_secret() -> str:
    """A random secret made once per portal; codes are stored as a hash keyed by it, never as typed."""
    with _LOCK:
        got = read("secret", {})
        if not got.get("value"):
            got = {"value": secrets.token_hex(32), "created_at": now()}
            write("secret", got)
        return got["value"]


def _code_hash(purpose: str, email: str, code: str) -> str:
    return hashlib.sha256(f"{portal_secret()}|{purpose}|{email}|{code}".encode()).hexdigest()


def put_code(purpose: str, email: str, code: str, ttl_seconds: int) -> None:
    """Replaces only the code of the SAME purpose for this address — a sign-up code never cancels a reset."""
    email = (email or "").strip().lower()
    with _LOCK:
        rows = [c for c in read("codes", []) if c["expires"] > _epoch()
                and not (c["email"] == email and c["purpose"] == purpose)]
        rows.append({"purpose": purpose, "email": email, "hash": _code_hash(purpose, email, code),
                     "expires": _epoch() + ttl_seconds, "attempts": 0, "created_at": now()})
        write("codes", rows[-_limit("codes_kept"):])


def check_code(purpose: str, email: str, code: str, max_attempts: int) -> str:
    """ok | wrong | burned. A right code is spent; max_attempts wrong ones burn it."""
    email = (email or "").strip().lower()
    with _LOCK:
        rows = [c for c in read("codes", []) if c["expires"] > _epoch()]
        row = next((c for c in rows if c["email"] == email and c["purpose"] == purpose), None)
        if not row:
            write("codes", rows)
            return "wrong"
        if secrets.compare_digest(row["hash"], _code_hash(purpose, email, str(code or "").strip())):
            write("codes", [c for c in rows if c is not row])
            return "ok"
        row["attempts"] += 1
        if row["attempts"] >= max_attempts:
            write("codes", [c for c in rows if c is not row])
            return "burned"
        write("codes", rows)
        return "wrong"


def recent_codes(purpose: str, email: str, within_seconds: int) -> int:
    """Codes sent to this address lately (the mail throttle). Spent or burned codes still count."""
    email = (email or "").strip().lower()
    sent = [t for t in read("code_log", []) if t["email"] == email and t["purpose"] == purpose
            and _stamp(t["at"]) > _epoch() - within_seconds]
    return len(sent)


def log_code(purpose: str, email: str) -> None:
    with _LOCK:
        rows = [t for t in read("code_log", []) if _stamp(t["at"]) > _epoch() - _limit("code_log_seconds")]
        rows.append({"purpose": purpose, "email": (email or "").strip().lower(), "at": now()})
        write("code_log", rows[-_limit("code_log_kept"):])


def verify_user(email: str) -> None:
    with _LOCK:
        rows = users()
        for u in rows:
            if u["email"] == (email or "").strip().lower():
                u["verified"] = True
                write("users", rows)
                return


if __name__ == "__main__":  # ponytail: one runnable self-check
    h = hash_password("correct horse battery")
    assert check_password("correct horse battery", h)
    assert not check_password("wrong", h)

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        globals()["DATA"] = Path(tmp)
        # 2026-10-02: kept_while answers again only when one of its files changes
        calls_ = []
        mk_ = lambda: (calls_.append(1), len(calls_))[1]    # noqa: E731
        assert kept_while(("k",), ["memo_"], mk_) == 1 and kept_while(("k",), ["memo_"], mk_) == 1
        write("memo_", [1])
        assert kept_while(("k",), ["memo_"], mk_) == 2 and kept_while(("j",), ["memo_"], mk_) == 3, calls_
        # 2026-09-30 "thousands of assets": a file is read from disk once until it changes; a write is seen at once
        write("kept_", {"a": 1})
        _rt, _reads = Path.read_text, []
        Path.read_text = lambda self, *a, **k: (_reads.append(self.name), _rt(self, *a, **k))[1]
        _x, _y = read("kept_", {}), read("kept_", {})
        Path.read_text = _rt
        assert _x == _y == {"a": 1} and _x is not _y and _reads.count("kept_.json") == 1, ("read() went to the disk again for an unchanged file", _reads)
        write("kept_", {"a": 22})
        assert read("kept_", {}) == {"a": 22}, "a write is seen by the next read"
        path_of("kept_").unlink()
        assert read("kept_", 7) == 7
        # 2026-10-01 "1000s of cards": view() parses once and shares; index() finds a row without a scan; write() is seen
        write("rows_", [{"id": "a", "n": 1}, {"id": "b", "n": 2}])
        _loads, _real = [], json.loads
        json.loads = lambda t, *a, **k: (_loads.append(1), _real(t, *a, **k))[1]
        try:
            v1, v2, i1 = view("rows_", []), view("rows_", []), index("rows_", "id")
        finally:
            json.loads = _real
        assert v1 is v2 and len(_loads) == 1 and i1["b"]["n"] == 2 and index("rows_", "id") is i1, "view() parsed an unchanged file again"
        assert views_intact() == []
        v1[0]["n"] = 5
        assert views_intact() == ["rows_"], "a reader that changes the shared copy is caught"
        write("rows_", [{"id": "a", "n": 9}])
        assert view("rows_", [])[0]["n"] == 9 and "b" not in index("rows_", "id"), "a write is seen by the next view / index"
        write("users", [{"id": "u1", "email": "a@x.io"}])
        tok = start_session({"id": "u1"})
        assert session_user(tok)["email"] == "a@x.io" and session_user(tok + "x") is None and session_user("") is None
        session_user(tok)["email"] = "changed"
        assert session_user(tok)["email"] == "a@x.io", "a caller's change to its user never reaches the shared index"
        end_sessions_for("u1")
        assert session_user(tok) is None, "signed out everywhere is seen at once"
        t = make_token("reset", "A@Example.com", 60)
        assert peek_token(t, "reset") == "a@example.com", "peeking does not spend it"
        assert peek_token(t, "verify") is None, "a reset token is not a verify token"
        assert use_token(t, "reset") == "a@example.com"
        assert use_token(t, "reset") is None, "single use"
        dead = make_token("reset", "b@example.com", -1)
        assert use_token(dead, "reset") is None, "expired is refused"
        assert recent_tokens("reset", "c@example.com", 3600) == 0
        make_token("reset", "c@example.com", 600)
        assert recent_tokens("reset", "c@example.com", 3600) == 1

        # codes: hashed, per purpose, burned after N wrong tries
        put_code("reset", "d@example.com", "123456", 600)
        put_code("signup", "d@example.com", "654321", 600)
        assert "123456" not in path_of("codes").read_text(), "a code is never stored as typed"
        assert check_code("reset", "d@example.com", "000000", 3) == "wrong"
        assert check_code("signup", "d@example.com", "654321", 3) == "ok", "a sign-up code survives a reset code"
        assert check_code("reset", "d@example.com", "111111", 3) == "wrong"
        assert check_code("reset", "d@example.com", "222222", 3) == "burned", "the third wrong try burns it"
        assert check_code("reset", "d@example.com", "123456", 3) == "wrong", "a burned code is gone"
        rows = [{"id": "1", "email": "a@x.io", "username": "ravi.k"}]
        assert _free_username("Ravi.K", rows) == "ravi.k2" and _free_username("+", rows) == "user"
        assert _free_username("admin", rows) == "admin2", "a made user name obeys auth.username_problem (reserved)"
        write("users", [{"id": "o1", "email": "o@x.io", "username": "boss", "role": "owner"}, {"id": "m1", "email": "m@x.io", "role": "member"}])
        assert username_taken("BOSS") and not username_taken("boss", "o1") and not username_taken("nobody")
        assert "password" not in public_user({"id": "1", "password": "x", "role": "owner"}), "public_user never hands out the hash"
        try:
            delete_user("o1")
            raise AssertionError("the last owner was deleted")
        except ValueError:
            pass
    print("core.store self-check OK")
