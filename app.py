"""Training & Video Portal — the whole server.

Three modules over any project, in any language, on any domain:
  How to Use          — the training and video links each screen carries, served to that app.
  User Manual Builder — write a manual, publish it here, read it at /m/<slug>.
  Video Narrator      — turn a screen recording into a narrated MP4 with subtitles and chapters.
plus Setup (register a project folder, Scan it for screens) and Key Management.

Run it:  python -m uvicorn app:app --port 8800      (or start.cmd / start.sh)
Mount it anywhere:  TV_BASE=/tv  when it sits behind a path on another site.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from html import escape
from pathlib import Path

from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (FileResponse, HTMLResponse, JSONResponse, PlainTextResponse)
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

import store  # first: maps TV_* settings onto PORTAL_* before core reads them
import core
from core import auth, demo, engine, lists, rules

_UR = engine.run("portal.upload_rule")                   # 2026-09-26: the labels are a chip, not code
rules.subject("upload", _UR["subject_label"], _UR["fields"])
rules.trigger("upload.start", "upload", _UR["trigger_label"], _UR["outcomes"], _UR["trigger_note"])


def _model_watch(o: dict, facts: dict, context: dict) -> None:
    """Outcome model_watch (rule models_daily): the daily model check; the owner is told when anything changed."""
    import providers  # noqa: PLC0415
    got = providers.watch()
    if got["changed"] or engine.run("providers.watch")["notify_when_nothing"]:
        rules.KINDS["notify"]["act"]({"to": "owner", "rule_id": o["rule_id"], "n": o.get("n", 0),
                                      "subject": providers.say("watch_subject", gone=got["gone"], new=got["new"]),
                                      "text": providers.say("watch_text", date=str(got.get("at", ""))[:10], lines="\n".join(got["lines"]))},
                                     facts, context)


rules.kind("model_watch", "Check models", [{"name": "cooldown_minutes", "type": "number", "label": "At most once every (minutes)", "default": 720}],
           "Asks every provider for its models; gone ones hand over to their successor (chip providers.watch).", _model_watch)
from core import memwatch  # noqa: E402 - registers the daily trigger this outcome belongs to
rules.TRIGGERS["daily"]["kinds"].append("model_watch")
from core import access
from core.access import screen
from core.auth import owner, signed_in, who
import manuals
import narrator
import edition
import guideme
import landing
from core import linkcard
import clients
import firms
import intake
import recon
import audit
import changelog
import compute
import company
import itr_json
import analytics
import chipchat
import delegation
import dock_issues
import notes
import portal_stats
import server
import itr_import
import myreturn
import wizard
import taxwatch
import providers
import keyshare
import keysales
import tourvideo
import wallet
import projects
import scan
import source

ROOT = Path(__file__).resolve().parent
BASE = auth.BASE                                      # "/tv" when hosted under a path (TV_BASE)

app = FastAPI(title="Training & Video Portal", docs_url=None, redoc_url=None, openapi_url=None, root_path=BASE)   # 2026-10-02: no public API map
# Only the two /api/public/* reads and /embed/howto.js are meant to be fetched cross-origin, and
# they carry no credentials — so a wildcard here never exposes a signed-in session.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False,
                   allow_methods=["GET"], allow_headers=["*"])
# Login, people & access, activity, visitors, memory watch, How to Use: the framework, see core/.
# One codebase, two products: the edition (PORTAL_EDITION, chip edition.settings) picks the screens.
core.install(app, catalog=edition.catalog(json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))),
             chips=ROOT / "chips", rules_dir=ROOT / "rules")   # tv's own decisions: chips/*.json, rules/*.json
STORAGE_LIMITS = ("max_upload_mb", "quota_gb", "keep_source_days")
# "Buy a key" does not exist until somebody puts a key up for sale: not a locked door, simply absent
# (catalog.json marks it hide_when_denied, chip access.decide refuses it, the shell leaves it out).
access.register_available("buykey", keysales.anything_to_buy)
firms.install()
changelog.install()
if demo.ON:
    demo.SEATERS.append(firms.seat_demo)


@app.middleware("http")
async def who_changes(request: Request, call_next):
    """2026-10-05 change log: whoever is signed in on a request that may change something is the 'who' of every field it
    changes (changelog.py)."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.url.path.startswith("/api/"):
        u = auth.current_user(request)
        if u:
            changelog.WHO.set(changelog.who_of(u))
    return await call_next(request)


@app.middleware("http")
async def stage_moves_by_itself(request: Request, call_next):
    """2026-10-04 owner: "Stage should move automatically". After any change to a client's year - a statement, a ref, a portal
    file, a note, a sign-off, a filing - the stage is worked out again from the facts (compute.refresh, chip close.stage)."""
    response = await call_next(request)
    m = re.match(r"^/api/(?:intake|recon|compute|clients)/([0-9a-f]{6,32})/(?:years/)?(\d{4}-\d{2})(?:/|$)", request.url.path)
    if m and request.method in ("POST", "PUT", "DELETE") and response.status_code < 400:
        try:
            await run_in_threadpool(compute.refresh, m.group(1), m.group(2))
        except HTTPException:
            pass
    return response                                     # Filing opens when the firm is approved, per the role
# 2026-10-01 owner "Avatar Card is taking lot of time to load": MediaPipe's first start (~1.6 s) and the caption probes
# (ffmpeg per script) ran inside the first Avatar Home list after every restart. Done here, in the background (avatar.warm).


def say(key: str, **values) -> str:
    """One sentence from portal.messages."""
    return engine.say("portal.messages", key, **values)


def knob(key: str):
    """One length, rate or sample from portal.settings."""
    return engine.setting("portal.settings", key)


def settings() -> dict:
    # The three numbers a hosted portal lives or dies by, defaulted by the chip portal.defaults.
    # Sign-up mode, product name and portal address are the framework's: core/auth.py.
    return dict(engine.run("portal.defaults")) | auth.settings()


def whole_number(v) -> int | None:
    """What was typed into a box, as a whole number of at least 0; None when it is not a number."""
    try:
        return max(0, int(float(v or 0)))
    except (TypeError, ValueError):
        return None


PERSON_LIMITS = ("max_upload_mb", "quota_gb")          # what the owner may set for one person (Setup -> Each person)


def person_limits(uid: str) -> dict:
    """One person's own limits, as the owner typed them - {} = the portal's defaults (store storage_limits)."""
    return dict(store.read("storage_limits", {}).get(uid) or {})


def limits(u: dict | None = None) -> dict:
    """The storage limits as numbers, whatever was typed into the boxes: the person's own (2026-09-30 owner: "the 1 GB
    is the same for everyone - a default, and I set it for each person") over the portal's over chip portal.defaults.
    Chip portal.storage_limits decides what 0 and an unreadable box mean."""
    s = settings()
    mine = person_limits(u["id"]) if u else {}
    return engine.run("portal.storage_limits", {k: whole_number(s.get(k)) for k in STORAGE_LIMITS}
                      | {f"person_{k}": whole_number(mine[k]) if k in mine else None for k in PERSON_LIMITS})


def storage_of(u: dict) -> dict:
    """What this account is holding, and what it is allowed to hold."""
    lim = limits(u)
    used = narrator.used_bytes(lambda p: owns(p, u), u) + core.storage.more_bytes(u["id"])   # + what other modules keep for them
    quota = lim["quota_gb"] * 1024 ** 3
    return {"used_bytes": used, "quota_bytes": quota,
            "left_bytes": engine.run("portal.room_left", {"used_bytes": used, "quota_bytes": quota}),
            "max_upload_mb": lim["max_upload_mb"], "keep_source_days": lim["keep_source_days"],
            "tight_pct": engine.setting("portal.settings", "storage_tight_pct")}   # 2026-09-26: the page's 85 became a knob


def over_quota(st: dict, incoming: int) -> bool:
    return engine.run("portal.over_quota", {"used_bytes": st["used_bytes"], "incoming_bytes": incoming,
                                            "quota_bytes": st["quota_bytes"]}) is True


def room_for(u: dict, incoming: int = 0) -> None:
    """Refuse before writing, never half-way through. `incoming` is what is about to be added."""
    st = storage_of(u)
    if over_quota(st, incoming):
        raise HTTPException(413, say("over_quota", quota_gb=st["quota_bytes"] / 1024 ** 3,
                                     used_gb=st["used_bytes"] / 1024 ** 3))


async def upload_bytes(u: dict, file, most: int) -> bytes:
    """THE way a route takes an uploaded file (2026-10-01 portal assessment: the person's storage quota was checked on
    4 of ~15 upload roads, and one road read a file of any size into memory). Reads at most `most` bytes - the caller
    passes its cap + 1, so a bigger file is refused by the caller's own words, never cut - then refuses it if it would
    take this person over their quota (Setup -> Storage). Guard: tv/selfcheck.py (no raw upload read outside it)."""
    data = await file.read(int(most))
    room_for(u, len(data))
    return data


# --- whose row is this ----------------------------------------------------------------------------
# Anyone may sign up, so every stored thing belongs to the person who made it. A row written before
# accounts were plural has no owner_id at all: those belong to the portal owner, which is who wrote
# them when this portal had one seat.

def owns(row: dict, u: dict) -> bool:
    return narrator.owns(row, u)                        # one rule for whose row this is (narrator.owns)


def only_mine(row: dict | None, u: dict, what: str = "that"):
    """404, not 403 — an id someone else owns must not even confirm that it exists.
    `what` names a portal.messages key: that, that_project, that_manual, that_recording."""
    if not row or not owns(row, u):
        raise HTTPException(404, say("not_yours", what=say(what)))
    return row


def tv_bootstrap(request: Request, u: dict | None) -> dict:
    return {
        # Whether THIS person has their own AI key, so the shell can point a newcomer at the one
        # step that unlocks Draft with AI instead of letting them find it by failing.
        "has_key": bool(u and store.keys_of(u["id"]).get("gemini_api_key")),
        # 2026-09-19 the currency this person sees money in (chip money.currencies) - every screen formats with it
        "currency": store.currency_of(u["id"]) if u else None,
        # Which machine "a folder on this machine" means. A hosted portal looks on ITS disk.
        "server": {"windows": os.name == "nt",
                   "sample_path": knob("sample_path_windows" if os.name == "nt" else "sample_path_posix")}}


auth.BOOTSTRAP_EXTRAS.append(tv_bootstrap)
auth.BOOTSTRAP_EXTRAS.append(edition.bootstrap_extra)
auth.BOOTSTRAP_EXTRAS.append(firms.bootstrap_extra)   # a self-filer lands on My return
core.find.register_menu(edition.menu_ids)   # 2026-10-01: Ctrl+K offers what THIS address's menu shows (sm: no door section)


_owner_of = narrator.owner_of                           # a recording with no owner_id is the first owner's


# The owner's Storage screen counts recordings as the files people hold, and deletes them whole.
core.storage.register(items=lambda: narrator.storage_items(_owner_of), delete=narrator.delete_project,
                      manage_hash="#/video")
# 2026-09-30: a person's own deck templates are files they keep too - they count in their total and on the Storage screen


# --- keys and money -----------------------------------------------------------------------------

@app.get("/api/keys")
def get_keys(u: dict = Depends(screen("keys"))):
    """YOUR keys, YOUR balance, YOUR runs. Nobody shares a key here — see store.KEY_FIELDS."""
    k = store.keys_of(u["id"])
    return {"fields": store.KEY_FIELDS,
            "values": {f: (store.mask(k.get(f, "")) if meta["secret"] else k.get(f, ""))
                       for f, meta in store.KEY_FIELDS.items()},
            "set": {f: bool(k.get(f)) for f in store.KEY_FIELDS},
            # 2026-09-19 a budget per provider: Gemini always, any other whose key is in
            "funds": {p["id"]: store.funds_for(u["id"], p["id"]) for p in providers.rows()
                      if p["id"] == providers.settings()["gemini_id"] or (p.get("key_field") and providers.have_key(u["id"], p["id"]))},
            "providers": providers.offered(u["id"]),
            "pool": providers.pool_view(u["id"]),
            "key_name_max": providers.name_max(),
            "currency": store.currency_of(u["id"]),
            "help_video_url": settings()["help_video_url"],
            "shares": keyshare.shares_view(u["id"]),
            "bills": keyshare.bills_view(u["id"]),
            "usage": keyshare.usage(u["id"], edition.current()["product_name"]),
            "runs": store.runs_of(u["id"])[:knob("runs_shown")],
            "wallet": wallet.view(u["id"]), "wallets_owner": u.get("role") == "owner"}


# 2026-09-28 managed credits: the owner adds what someone paid (in the owner's own currency) and sets a daily cap
@app.post("/api/wallet/add")
def post_wallet_add(body: dict = Body(...), u: dict = Depends(screen("keys"))):
    b = body or {}
    try:
        usd = store.to_usd(u["id"], float(b.get("amount") or 0))
    except (TypeError, ValueError):
        usd = 0.0
    return wallet.add(u, str(b.get("email") or ""), usd, str(b.get("note") or ""))


@app.post("/api/wallet/cap")
def post_wallet_cap(body: dict = Body(...), u: dict = Depends(screen("keys"))):
    b = body or {}
    cap = b.get("cap")
    try:
        cap = None if cap in (None, "") else store.to_usd(u["id"], float(cap))
    except (TypeError, ValueError):
        cap = None
    return wallet.set_cap(u, str(b.get("email") or ""), cap)


@app.get("/api/keys/usage")
def get_key_usage(q: str = "", page: int = 1, u: dict = Depends(screen("keys"))):
    """Every paid run this person made OR paid for — own key and borrowed alike. What they see of a
    run somebody else made is chip keyshare.name_seen, never this route."""
    return keyshare.usage(u["id"], edition.current()["product_name"], q, page)


@app.post("/api/keys/pool/{key_id}/share")
def post_key_share(key_id: str, body: dict = Body(...), u: dict = Depends(screen("keys"))):
    """Lend one of my keys to somebody with an account here, on my terms: a mark-up on what each run
    really costs, and a cap per day, per week and per month. Their runs spend MY balance."""
    return keyshare.share(u["id"], key_id, str(body.get("email") or ""), who(u), body)


@app.put("/api/keys/shares/{grant_id}/terms")
def put_share_terms(grant_id: str, body: dict = Body(...), u: dict = Depends(screen("keys"))):
    """Change the mark-up or a cap on a live share. It applies from now on — a run already made keeps
    the mark-up it was charged at."""
    return keyshare.set_terms(u["id"], grant_id, body or {})


@app.get("/api/keys/report")
def get_key_report(group: str = "", q: str = "", page: int = 1, u: dict = Depends(screen("keys"))):
    """Every key this person lent: per key, per key and person, or per key, person and sitting — with
    what it really cost them beside what they charge for it."""
    return keyshare.report(u["id"], group, q, page)


# --- selling credit on a key: the shop, and the desk that answers it -----------------------------
# Billing only. Nothing here takes money; approving a request hands over prepaid credit and raises a
# bill, which the two people settle between themselves and mark paid.

@app.get("/api/buykey")
def get_buykey(u: dict = Depends(screen("buykey"))):
    """What is on sale (never my own key) and what I have asked for."""
    return keysales.shop(u)


@app.post("/api/buykey/orders")
def post_buy_order(body: dict = Body(...), u: dict = Depends(screen("buykey"))):
    """Ask a seller for credit. Nothing is handed over until they say yes."""
    return keysales.place_order(u, str(body.get("offer_id") or ""), body.get("amount_usd"),
                                str(body.get("note") or ""))


@app.delete("/api/buykey/orders/{order_id}")
def delete_buy_order(order_id: str, u: dict = Depends(screen("buykey"))):
    return keysales.withdraw_order(u["id"], order_id)


# --- Tour Video (2026-10-02 owner: "bring Tour Video from the studio to sm, visible to portal admin") ------------------
@app.get("/api/tourvideo/job")
def api_tourvideo_job(_: dict = Depends(screen("tourvideo"))):
    return tourvideo.job()


@app.post("/api/tourvideo/{what}")
def api_tourvideo_start(what: str, request: Request, body: dict = Body(default={}), me: dict = Depends(screen("tourvideo"))):
    if what not in ("check", "record", "login"):
        raise HTTPException(404, tourvideo.say("empty"))
    return tourvideo.start(what, str((body or {}).get("key") or ""), str(request.base_url).rstrip("/"), me["id"], u=me)


@app.get("/api/tourvideo/{key}/file/{fid}")
def api_tourvideo_file(key: str, fid: str, _: dict = Depends(screen("tourvideo"))):
    path, typ = tourvideo.file_of(key, fid)
    return FileResponse(path, media_type=typ, headers=named(f"Tour - {key}", path.suffix))


@app.get("/api/keysales")
def get_keysales(u: dict = Depends(screen("keysales"))):
    """The seller's desk: my offers, my own keys to sell on, and the requests waiting."""
    return keysales.desk(u)


@app.put("/api/keysales/offers")
def put_keysales_offer(body: dict = Body(...), u: dict = Depends(screen("keysales"))):
    """Put one of my keys up for sale, or change its mark-up, its name or whether it is on sale."""
    return keysales.save_offer(u, body or {})


@app.delete("/api/keysales/offers/{offer_id}")
def delete_keysales_offer(offer_id: str, u: dict = Depends(screen("keysales"))):
    """Off the shelf. Credit somebody already bought keeps working."""
    return keysales.delete_offer(u, offer_id)


@app.post("/api/keysales/orders/{order_id}")
def post_keysales_decision(order_id: str, body: dict = Body(...), u: dict = Depends(screen("keysales", "decide"))):
    """Yes hands over prepaid credit (the offer's mark-up, no day/week/month cap, the amount bought as
    the only ceiling) and raises the bill for it. No is on the record with its reason."""
    return keysales.decide_order(u, order_id, bool(body.get("approve")), str(body.get("reason") or ""))


@app.get("/api/keys/rates")
def get_key_rates(markup_pct: float = 0, u: dict = Depends(screen("keys"))):
    """Roughly what a minute of video, a still and a thousand words will cost at this mark-up — what a
    borrower is shown before they take a key. An estimate, and it says so (chip keyshare.rate_card)."""
    return keyshare.rate_card(u["id"], markup_pct)


@app.delete("/api/keys/shares/{grant_id}")
def delete_key_share(grant_id: str, u: dict = Depends(screen("keys"))):
    """The owner takes a key back, or the borrower gives it back. Either way it stops working at once
    and the record keeps who ended it and when."""
    return keyshare.revoke(u["id"], grant_id, who(u))


@app.post("/api/keys/bills")
def post_key_bill(body: dict = Body(...), u: dict = Depends(screen("keys"))):
    """Send a borrower what they have spent on my key since the last bill."""
    return keyshare.push_bill(u["id"], str(body.get("key_id") or ""), str(body.get("holder_id") or ""),
                              str(body.get("note") or ""))


@app.post("/api/keys/bills/{bill_id}/settle")
def post_bill_settled(bill_id: str, body: dict = Body(default={}), u: dict = Depends(screen("keys"))):
    """The person billed says it is paid. Money moves outside this portal; this is the receipt."""
    return keyshare.settle_bill(u["id"], bill_id, str((body or {}).get("note") or ""))


@app.post("/api/keys/pool")
def post_pool_key(body: dict = Body(...), u: dict = Depends(screen("keys"))):
    """One more key for a provider (chip providers.rotate keys_max). The first becomes the default."""
    return providers.pool_add(u["id"], str(body.get("provider") or ""), str(body.get("secret") or ""), str(body.get("name") or ""))


@app.post("/api/keys/pool/{key_id}/default")
def post_pool_default(key_id: str, u: dict = Depends(screen("keys"))):
    providers.pool_default(u["id"], key_id)
    return {"ok": True}


@app.post("/api/keys/pool/{key_id}/test")
def post_pool_test(key_id: str, u: dict = Depends(screen("keys"))):
    """One cheap real call on that key alone; a pass revives an exhausted or invalid key."""
    return providers.test_key(u["id"], key_id)


@app.put("/api/keys/pool/{key_id}/name")
def put_pool_name(key_id: str, body: dict = Body(...), u: dict = Depends(screen("keys"))):
    """Label a key with the account it came from, so a limit message names the account to top up."""
    return providers.pool_rename(u["id"], key_id, str(body.get("name") or ""))


@app.delete("/api/keys/pool/{key_id}")
def delete_pool_key(key_id: str, u: dict = Depends(screen("keys"))):
    providers.pool_remove(u["id"], key_id)
    return {"ok": True}


@app.put("/api/providers/choice")
def put_provider_choice(body: dict = Body(...), u: dict = Depends(screen("keys"))):
    """Who does one kind of work for this person (text / image / video) - chips providers.settings + providers.models."""
    return providers.save_choice(u["id"], str(body.get("kind") or ""), str(body.get("provider") or ""), str(body.get("model") or ""))


@app.put("/api/keys")
def put_keys(body: dict = Body(...), u: dict = Depends(screen("keys"))):
    # A blank or masked secret means "leave it alone" — the browser was never sent the real one.
    # Wiping a key is a separate, deliberate act: `clear: true`.
    try:
        store.save_keys_for(u["id"],
                            {f: v for f, v in (body.get("values") if isinstance(body.get("values"), dict) else {}).items() if not str(v).startswith("•")},
                            keep_blank_secrets=not body.get("clear"))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.post("/api/keys/test")
def test_key(u: dict = Depends(screen("keys"))):
    """Four words to Google on this person's own key, so "is my key working?" has an answer here
    instead of surfacing as a failed job an hour later. Costs a fraction of a cent, and says so."""
    return narrator.check_key(u["id"], who(u))


@app.put("/api/funds")
def put_funds(body: dict = Body(...), u: dict = Depends(screen("keys"))):
    """`loaded_usd` in dollars, or `loaded` in the person's own currency (chip money.currencies)."""
    try:                                   # W1.3 shape walk: "abc" here was a 500
        usd = float(body.get("loaded_usd") or 0) if "loaded_usd" in body else store.to_usd(u["id"], body.get("loaded"))
    except (TypeError, ValueError):
        raise HTTPException(400, say("not_a_number", field="loaded")) from None
    provider = str(body.get("provider") or "gemini")   # W1.3: a list here was a 500
    store.set_loaded(u["id"], provider, usd)
    return {"funds": store.funds_for(u["id"], provider)}


@app.put("/api/currency")
def put_currency(body: dict = Body(...), u: dict = Depends(screen("keys"))):
    """Which currency this person sees every amount in. The books stay in US dollars."""
    try:
        return {"currency": store.save_currency(u["id"], str(body.get("code") or ""))}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/settings")
def get_settings(_: dict = Depends(signed_in)):
    return {"settings": settings(), "lexicon": store.read("lexicon", {})}


@app.put("/api/settings")
def put_settings(body: dict = Body(...), _: dict = Depends(owner)):
    auth.save_settings(body)                          # portal address, name, who may sign up
    s = store.read("settings", {})
    if "help_video_url" in body:
        s["help_video_url"] = str(body["help_video_url"] or "").strip()[:knob("help_video_url_max")]
    for f in STORAGE_LIMITS:
        if f in body:
            n = whole_number(body[f])
            if n is None:
                raise HTTPException(400, say("not_a_number", field=f.replace("_", " ")))
            s[f] = n
    store.write("settings", s)
    s = settings()
    if isinstance(body.get("lexicon"), dict):
        term, words = knob("lexicon_term_max"), knob("lexicon_say_max")
        store.write("lexicon", {str(k)[:term]: str(v)[:words] for k, v in body["lexicon"].items() if str(k).strip()})
    return {"settings": s, "lexicon": store.read("lexicon", {})}


# --- One person's own upload cap and storage (2026-09-30 owner) - edited on Admin -> Storage (register_limits below) -----


def _usable_videos(u: dict, args: dict) -> list[dict]:
    """Combine's bin (2026-10-01, Phase 3): this person's recordings that can be cut into a new one - list.video_usable
    pages them, so the dialog never loads every recording with a video preview each."""
    return [{"id": v["id"], "title": v.get("title") or "", "duration": v.get("duration"), "created_at": v.get("created_at") or ""}
            for v in narrator.listing(mine=lambda p: owns(p, u), user=u) if v.get("has_source") is not False and float(v.get("duration") or 0) > 0]


lists.source("video_usable", _usable_videos)
# every recording of this person (Shorts from YouTube: attach a recording) - list.my_recordings pages it
lists.source("my_recordings", lambda u, args: [{"id": v["id"], "title": v.get("title") or v["id"], "created_at": v.get("created_at") or ""}
                                               for v in narrator.listing(mine=lambda p: owns(p, u), user=u)])


def save_person_limits(uid: str, body: dict) -> dict:
    """One person's own limits: a box left blank = the portal's default for that limit; {} = back on the defaults."""
    who = store.user_by_id(uid)
    if not who:
        raise HTTPException(404, say("no_person"))
    own = {}
    for f in PERSON_LIMITS:
        v = body.get(f)
        if v in (None, ""):
            continue
        n = whole_number(v)
        if n is None:
            raise HTTPException(400, say("not_a_number", field=f.replace("_", " ")))
        own[f] = n
    kept = store.read("storage_limits", {})
    kept.pop(uid, None)
    if own:
        kept[uid] = own
    store.write("storage_limits", kept)
    return {"message": say("person_limits_saved" if own else "person_limits_default"), "own": own,
            "storage": storage_of(who)}


# 2026-10-01 owner "move it under Storage": the limits are edited on the framework's Storage screen, beside what each
# person holds. This portal tells it the boxes (chip portal.limit_fields), the numbers and how to save them.
def _limit_of(u: dict) -> dict:
    lim = limits(u)
    return {"quota_bytes": lim["quota_gb"] * 1024 ** 3, "max_upload_mb": lim["max_upload_mb"],
            "tight_pct": engine.setting("portal.settings", "storage_tight_pct"), "own": person_limits(u["id"])}


core.storage.register_limits(
    of=_limit_of, defaults=lambda: {k: settings()[k] for k in STORAGE_LIMITS},
    fields=lambda: engine.run("portal.limit_fields")["rows"],
    save_defaults=lambda body: put_settings({k: body[k] for k in STORAGE_LIMITS if k in body}),
    save_person=lambda uid, body: save_person_limits(uid, {k: body.get(k) for k in PERSON_LIMITS})["message"])


# --- Setup: projects and screens ------------------------------------------------------------------

@app.get("/api/projects")
def api_projects(u: dict = Depends(signed_in)):
    return {"projects": [projects.public_project(p) for p in projects.all_projects() if owns(p, u)],
            "git_available": source.have_git(), "can_scan_local": bool(local_scan_ok(u)),
            "storage": storage_of(u)}


@app.post("/api/projects")
def api_save_project(body: dict = Body(...), u: dict = Depends(screen("setup"))):
    if body.get("id"):
        only_mine(projects.get_project(body["id"]), u, "that_project")
    try:
        row = projects.save_project(
            body.get("id"), str(body.get("name") or ""), str(body.get("folder") or ""), str(body.get("site_url") or ""), who(u),   # W1.3 shapes
            source_kind=str(body.get("source_kind") or "local"), git_url=str(body.get("git_url") or ""),
            git_branch=str(body.get("git_branch") or ""), git_token=None if body.get("git_token") is None else str(body.get("git_token")),
            owner_id=u["id"])
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"project": projects.public_project(row)}


@app.delete("/api/projects/{project_id}")
def api_delete_project(project_id: str, u: dict = Depends(screen("setup"))):
    only_mine(projects.get_project(project_id), u, "that_project")
    projects.delete_project(project_id)
    return {"ok": True}


def local_scan_ok(u: dict) -> list[Path]:
    """Which folders on THIS server this person may point a project at.

    Reading a folder tells you its file names, and a hosted portal's disk is not the visitor's
    business: only the portal owner may name any path. Everyone else is held to TV_SCAN_ROOTS, and
    with that unset a non-owner may not scan a local folder at all — a Git URL still works, and
    clones land under the portal's own data folder."""
    if u.get("role") == "owner":
        return [Path("/")]
    roots = [Path(r.strip()).expanduser() for r in os.getenv("TV_SCAN_ROOTS", "").split(os.pathsep)
             if r.strip()]
    return [r for r in roots if r.exists()]


def check_scan_path(row: dict, u: dict) -> None:
    if (row.get("source_kind") or "local") != "local":
        return                                        # a clone is written by the portal, into its own data
    allowed = local_scan_ok(u)
    if not allowed:
        raise HTTPException(403, say("scan_owner_only"))
    if u.get("role") == "owner":
        return
    try:
        here = Path(row.get("folder") or "").expanduser().resolve()
    except OSError:
        raise HTTPException(400, say("folder_unreadable"))
    if not any(here == root or root in here.parents for root in allowed):
        raise HTTPException(403, say("folder_outside", allowed=", ".join(str(r) for r in allowed)))


@app.post("/api/projects/{project_id}/scan")
def api_scan(project_id: str, body: dict = Body(default={}), u: dict = Depends(screen("setup"))):
    row = only_mine(projects.get_project(project_id), u, "that_project")
    check_scan_path(row, u)
    try:
        # A local project is read where it sits; a Git project is cloned or pulled first.
        where = source.sync(row)
        found = scan.scan(str(where["path"]))
        found["source"] = {"kind": where["kind"], "note": where["note"]}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except (OSError, subprocess.TimeoutExpired) as e:
        raise HTTPException(400, say("project_unreadable", error=str(e)))
    # A screen already saved keeps its label and its links: a rescan adds, it does not overwrite.
    known = {s["key"]: s for s in row.get("screens", [])}
    for s in found["screens"]:
        if s["key"] in known:
            s["label"] = known[s["key"]]["label"]
            s["group"] = known[s["key"]].get("group", "")
            s["selected"], s["confidence"] = True, "saved"
    have = {s["key"] for s in found["screens"]}
    found["screens"] = [dict(s, why=say("screen_added_by_hand"), confidence="saved", selected=True)
                        for s in row.get("screens", []) if s["key"] not in have] + found["screens"]
    return found


@app.put("/api/projects/{project_id}/screens")
def api_set_screens(project_id: str, body: dict = Body(...), u: dict = Depends(screen("setup"))):
    only_mine(projects.get_project(project_id), u, "that_project")
    try:
        return {"project": projects.set_screens(project_id, body.get("screens") or [])}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.put("/api/projects/{project_id}/links/{screen_key}")
def api_set_links(project_id: str, screen_key: str, body: dict = Body(...), u: dict = Depends(screen("howto"))):
    only_mine(projects.get_project(project_id), u, "that_project")
    try:
        return {"links": projects.set_links(project_id, screen_key, body.get("links") or [])}
    except ValueError as e:
        raise HTTPException(400, str(e))


# --- what any application reads ------------------------------------------------------------------

@app.get("/api/public/howto/{project_key}")
def api_public_howto(project_key: str):
    """Every screen's live links, for the app itself to draw. No login, any origin, any framework."""
    return {"project": project_key, "screens": projects.public_links(project_key)}


@app.get("/embed/howto.js")
def embed_js():
    """Drop-in button for an app that would rather not write one:
        <script src="{portal}/embed/howto.js" data-project="my-app" data-screen="billing"></script>"""
    portal = (settings()["portal_url"] or BASE).rstrip("/")
    body = EMBED_JS.replace("__PORTAL__", json.dumps(portal)).replace("__LABEL__", json.dumps(say("embed_label")))
    return Response(body, media_type="application/javascript",
                    headers={"Cache-Control": f"public, max-age={int(knob('embed_cache_seconds'))}"})


EMBED_JS = r"""
/* Training & Video Portal — How to Use button. Include it on any page, in any framework:
   <script src="PORTAL/embed/howto.js" data-project="my-app" data-screen="billing"></script>
   Optional: data-mount="#css-selector" to place it, data-label="Help". */
(function () {
  var portal = __PORTAL__;
  var me = document.currentScript;
  var project = me.getAttribute('data-project') || '';
  var screenKey = me.getAttribute('data-screen') || '';
  var label = me.getAttribute('data-label') || __LABEL__;
  if (!project || !screenKey) return;
  fetch(portal + '/api/public/howto/' + encodeURIComponent(project))
    .then(function (r) { return r.json(); })
    .then(function (d) {
      var links = (d.screens || {})[screenKey] || [];
      if (!links.length) return;
      var wrap = document.createElement('div');
      wrap.style.cssText = 'position:relative;display:inline-block;font:600 12px system-ui,sans-serif;z-index:2147483000';
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = '? ' + label;
      btn.style.cssText = 'cursor:pointer;border:1px solid #c7d2fe;background:#fff;color:#4f46e5;border-radius:8px;padding:6px 10px;font:inherit';
      var menu = document.createElement('div');
      menu.style.cssText = 'display:none;position:absolute;right:0;top:100%;margin-top:4px;min-width:220px;background:#fff;border:1px solid #e2e8f0;border-radius:10px;box-shadow:0 10px 30px rgba(15,23,42,.18);overflow:hidden';
      links.forEach(function (l) {
        var a = document.createElement('a');
        a.href = l.url; a.target = '_blank'; a.rel = 'noopener noreferrer';
        a.textContent = l.label || l.url;
        a.style.cssText = 'display:block;padding:9px 12px;color:#334155;text-decoration:none;border-bottom:1px solid #f1f5f9;white-space:nowrap;overflow:hidden;text-overflow:ellipsis';
        a.onmouseenter = function () { a.style.background = '#eef2ff'; };
        a.onmouseleave = function () { a.style.background = ''; };
        menu.appendChild(a);
      });
      btn.onclick = function () { menu.style.display = menu.style.display === 'block' ? 'none' : 'block'; };
      document.addEventListener('click', function (e) { if (!wrap.contains(e.target)) menu.style.display = 'none'; });
      wrap.appendChild(btn); wrap.appendChild(menu);
      var mount = me.getAttribute('data-mount');
      var host = mount && document.querySelector(mount);
      if (host) { host.appendChild(wrap); }
      else { wrap.style.position = 'fixed'; wrap.style.right = '18px'; wrap.style.bottom = '18px'; document.body.appendChild(wrap); }
    })
    .catch(function () { /* the portal is down; the app is not */ });
})();
"""


# --- User Manual Builder ---------------------------------------------------------------------------

@app.get("/api/manuals")
def api_manuals(project_id: str = "", u: dict = Depends(screen("manuals"))):
    # 2026-10-01 (Phase 3): the manuals themselves are list manuals (one page at a time); here how many and the backgrounds
    return {"rows_n": len(manuals.rows_for(project_id, mine=lambda m: owns(m, u))), "backgrounds": manuals.BACKGROUNDS}


lists.source("manuals", lambda u, args: manuals.rows_for(str(args.get("project_id") or ""), mine=lambda m: owns(m, u)))


@app.get("/api/manuals/{manual_id}")
def api_manual(manual_id: str, u: dict = Depends(screen("manuals"))):
    row = only_mine(manuals.get(manual_id), u, "that_manual")
    return {"row": row, "html": manuals.body_html(row["manual"]),
            "public_url": public_manual_url(row)}


@app.post("/api/manuals/render")
def api_render_manual(body: dict = Body(...), _: dict = Depends(screen("manuals"))):
    """The live preview and the print window read the same renderer the published page uses."""
    return {"html": manuals.body_html(body.get("manual") or {})}


@app.post("/api/manuals")
def api_save_manual(body: dict = Body(...), u: dict = Depends(screen("manuals"))):
    if body.get("id"):
        only_mine(manuals.get(body["id"]), u, "that_manual")
    if body.get("project_id"):
        only_mine(projects.get_project(body["project_id"]), u, "that_project")
    m = body.get("manual") if isinstance(body.get("manual"), dict) else {}   # W1.3 shape walk: a string here was a 500
    row = manuals.save(body.get("id"), str(body.get("project_id") or ""), str(body.get("title") or ""),
                       m, who(u), body.get("published"), owner_id=u["id"])
    wired = projects.merge_manual_links(row["project_id"], row["id"],
                                        manuals.help_targets(row, settings()["portal_url"]))
    return {"row": row, "public_url": public_manual_url(row), "wired_screens": wired}


@app.delete("/api/manuals/{manual_id}")
def api_delete_manual(manual_id: str, u: dict = Depends(screen("manuals"))):
    only_mine(manuals.get(manual_id), u, "that_manual")
    projects.drop_manual_links(manual_id)
    manuals.delete(manual_id)
    return {"ok": True}


@app.get("/api/manuals/{manual_id}/download")
def api_download_manual(manual_id: str, u: dict = Depends(screen("manuals"))):
    row = only_mine(manuals.get(manual_id), u, "that_manual")
    return Response(manuals.doc_html(row["manual"]), media_type="text/html; charset=utf-8",
                    headers=named(row["title"] or say("dl_manual"), ".html"))


def public_manual_url(row: dict) -> str:
    if not (row.get("published") and row.get("slug")):
        return ""
    base = (settings()["portal_url"] or BASE).rstrip("/")
    return f'{base}/m/{row["slug"]}'


@app.get("/m/{slug}", response_class=HTMLResponse)
def read_manual(slug: str):
    """The published manual: read-only, no login, shareable. This IS the publishing site."""
    row = manuals.by_slug(slug)
    if not row:
        return HTMLResponse(f"<!doctype html><meta charset=utf-8><title>{escape(say('manual_missing_title'))}</title>"
                            f"<body style='font:16px system-ui;padding:40px'>{escape(say('manual_missing'))}</body>",
                            status_code=404)
    return HTMLResponse(manuals.doc_html(row["manual"]))


# --- file names on download ------------------------------------------------------------------------------


def named(name: str, ext: str = "", inline: bool = False) -> dict:
    """The one Content-Disposition every file route sends (2026-09-24 owner: "every download should have a proper
    name", not video.mp4 / file / board-003-t1.png). The asset's own name plus its extension; `inline` still plays or
    shows in the page, and the player's own Download / Save as takes the same name. filename* keeps any language."""
    from urllib.parse import quote  # noqa: PLC0415
    base = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "", str(name or "")).strip(" .")[: int(knob("file_name_max"))] or say("dl_file")
    full = base + ext
    plain = full.encode("ascii", "ignore").decode().strip() or f"file{ext}"
    return {"Content-Disposition": f"{'inline' if inline else 'attachment'}; filename=\"{plain}\"; filename*=UTF-8''{quote(full)}"}


# --- How to Use videos: a recording is a LINK in How to Use pages (core/howto.py), on any page, as many as needed ---
help_index = narrator.help_index   # {recording id: [page id, ...]}, read from the How to Use links; narrator refuses to delete one in use


def _help_recordings(u: dict, args: dict) -> list[dict]:
    """The recordings a How to Use page may play (2026-10-01, Phase 3: was every recording in one dialog)."""
    if u.get("role") != "owner":                         # the same door as the route: the portal owner only
        return []
    return [{"id": v["id"], "title": v.get("title") or "", "url": f"/api/help/play/{v['id']}"}
            for v in narrator.listing(mine=lambda p: owns(p, u), user=u) if v.get("has_output") or v.get("has_source")]


lists.source("help_recordings", _help_recordings)


# --- Firms (SimplyFile, 2026-10-04): tenants - sign-up papers, the portal admin's approval, the team (firms.py) ------
@app.get("/api/firm")
def api_firm(u: dict = Depends(screen("firm"))):
    return firms.me(u)


@app.post("/api/firm/start")
def api_firm_start(body: dict = Body(...), u: dict = Depends(screen("firm"))):
    return firms.start(u, str(body.get("kind") or ""))


@app.post("/api/firm/discard")
def api_firm_discard(_: dict = Body(default={}), u: dict = Depends(screen("firm"))):
    return firms.discard(u)


@app.put("/api/firm")
def api_firm_update(body: dict = Body(...), u: dict = Depends(screen("firm"))):
    return firms.update(u, body)


@app.post("/api/firm/docs/{kind}")
async def api_firm_doc(kind: str, file: UploadFile = File(...), u: dict = Depends(screen("firm"))):
    data = await upload_bytes(u, file, int(firms.settings()["doc_max_mb"]) * 1024 * 1024 + 1)
    return firms.add_doc(u, kind, file.filename or "paper", data)


@app.get("/api/firm/{fid}/docs/{did}")
def api_firm_doc_get(fid: str, did: str, u: dict = Depends(signed_in)):
    path, name = firms.doc_path(u, fid, did)
    return FileResponse(path, filename=name, content_disposition_type="inline")


@app.post("/api/firm/{fid}/move")
def api_firm_move(fid: str, body: dict = Body(...), u: dict = Depends(signed_in)):
    return firms.move(u, fid, str(body.get("action") or ""), str(body.get("note") or ""))


@app.post("/api/firm/team")
def api_firm_team_add(request: Request, body: dict = Body(...), u: dict = Depends(screen("firm"))):
    return firms.add_member(request, u, body)


@app.put("/api/firm/team/{uid}")
def api_firm_team_role(uid: str, body: dict = Body(...), u: dict = Depends(screen("firm"))):
    return firms.set_member(u, uid, str(body.get("role") or ""))


@app.delete("/api/firm/team/{uid}")
def api_firm_team_remove(uid: str, u: dict = Depends(screen("firm"))):
    return firms.set_member(u, uid, None)


@app.post("/api/itrimport/read")
async def api_itrimport_read(file: UploadFile = File(...), u: dict = Depends(firms.gate("itrimport"))):
    """Step 1 of Import old returns: what the ITR JSON says, and which client has its PAN - nothing is written."""
    data = await upload_bytes(u, file, itr_import.settings()["max_kb"] * 1024 + 1)
    return await run_in_threadpool(itr_import.preview, u, data)


@app.post("/api/itrimport")
async def api_itrimport(file: UploadFile = File(...), body: str = Form("{}"), u: dict = Depends(firms.gate("itrimport"))):
    """Steps 2-3: record the return as filed for the chosen (or a new) client; chip itr.import_ok refuses or replaces."""
    data = await upload_bytes(u, file, itr_import.settings()["max_kb"] * 1024 + 1)
    return await run_in_threadpool(itr_import.commit, u, data, json.loads(body or "{}"))


@app.get("/api/itrimport/{cid}/{ay}/statement")
def api_itrimport_statement(cid: str, ay: str, which: str = "filed", _: dict = Depends(firms.gate("itrimport"))):
    """Step 4: the return's statement as filed, or next year's statement to fill - an Excel SimplyFile reads."""
    name, data = itr_import.statement_xlsx(cid, ay, "next" if which == "next" else "filed")
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers=named(name.removesuffix(".xlsx"), ".xlsx"))


@app.get("/api/analytics")
def api_analytics(ay: str = "", u: dict = Depends(firms.gate("analytics"))):
    """Firm analytics for one assessment year: deadlines, workload, money handled, advisory leads (chips analytics.*)."""
    r = analytics.report(u, ay)
    # the radar and the leads themselves come one page at a time (list.due_radar, list.advice_leads); here only counts and the first few
    return r | {"radar": len(r["radar"]), "lead_n": {k: len(v) for k, v in r["leads"].items()}, "leads": {k: v[:r["top_n"]] for k, v in r["leads"].items()}}


# --- Chip Chat (2026-10-04 owner, as the studio): questions answered from chips and the person's own work, by firm and
# role; rotating examples, Surprise me, Ask next; the Train tab for the firm admin and the portal owner (chipchat.py) -------
@app.get("/api/chat/examples")
def api_chat_examples(screen: str = "", u: dict = Depends(signed_in)):
    return chipchat.examples(u, screen)


@app.get("/api/chat/surprise")
def api_chat_surprise(n: int = 0, u: dict = Depends(signed_in)):
    return chipchat.surprise(u, n)


@app.post("/api/chat/ask")
def api_chat_ask(body: dict = Body(...), u: dict = Depends(signed_in)):
    return chipchat.ask(u, str((body or {}).get("q") or ""))


@app.get("/api/chat/answer/{eid}")
def api_chat_answer(eid: str, u: dict = Depends(signed_in)):
    return chipchat.answer_id(u, eid)


@app.get("/api/chat/train")
def api_chat_train(u: dict = Depends(signed_in)):
    return chipchat.train(u)


@app.post("/api/chat/train/{tid}/teach")
def api_chat_teach(tid: str, body: dict = Body(...), u: dict = Depends(signed_in)):
    return chipchat.teach(u, tid, body or {})


@app.post("/api/chat/train/{tid}/skip")
def api_chat_skip(tid: str, u: dict = Depends(signed_in)):
    return chipchat.skip(u, tid)


@app.delete("/api/chat/taught/{aid}")
def api_chat_taught_delete(aid: str, u: dict = Depends(signed_in)):
    return chipchat.drop_taught(u, aid)


@app.get("/api/chat/export", response_class=PlainTextResponse)
def api_chat_export(u: dict = Depends(signed_in)):
    return chipchat.export_jsonl(u)


@app.get("/api/chat/unanswered.csv", response_class=PlainTextResponse)
def api_chat_unanswered(u: dict = Depends(signed_in)):
    return chipchat.unanswered_csv(u)


@app.post("/api/chat/custom")
def api_chat_custom(body: dict = Body(...), u: dict = Depends(signed_in)):
    return chipchat.add_custom(u, body or {})


@app.delete("/api/chat/custom/{cid}")
def api_chat_custom_delete(cid: str, u: dict = Depends(signed_in)):
    return chipchat.delete_custom(u, cid)


# --- Notes - the bottom bar's notebook, as the studio has it (2026-10-04 owner), private to each person (notes.py) --------
@app.get("/api/notes")
def api_notes(q: str = "", u: dict = Depends(signed_in)):
    return {"notes": notes.listed(u, q)}


@app.get("/api/notes/{nid}")
def api_note(nid: str, u: dict = Depends(signed_in)):
    return notes.one(u, nid)


@app.post("/api/notes")
def api_notes_new(body: dict = Body(...), u: dict = Depends(signed_in)):
    return notes.save(u, body or {})


@app.put("/api/notes/{nid}")
def api_notes_put(nid: str, body: dict = Body(...), u: dict = Depends(signed_in)):
    return notes.save(u, body or {}, nid)


@app.delete("/api/notes/{nid}")
def api_notes_delete(nid: str, u: dict = Depends(signed_in)):
    return notes.delete(u, nid)


@app.post("/api/notes/{nid}/voice")
def api_notes_voice(nid: str, body: dict = Body(...), u: dict = Depends(signed_in)):
    return notes.add_voice(u, nid, body or {})


@app.delete("/api/notes/{nid}/files/{fid}")
def api_notes_drop(nid: str, fid: int, u: dict = Depends(signed_in)):
    return notes.drop_file(u, nid, fid)


# --- Issues on the bottom bar (2026-10-04 owner, as the studio): own issues, one issue, the unread-reply badge ----------
@app.get("/api/dock/issues")
def api_dock_issues(q: str = "", status: str = "", u: dict = Depends(signed_in)):
    return dock_issues.listed(u, q, status)


@app.get("/api/dock/issues/unseen")
def api_dock_issues_unseen(u: dict = Depends(signed_in)):
    return {"n": dock_issues.unseen(u)}


@app.get("/api/dock/issues/{iid}")
def api_dock_issue(iid: str, u: dict = Depends(signed_in)):
    return dock_issues.one(u, iid)


# --- Delegations (2026-10-04 owner): lend your own powers to a colleague, for a scope and dates (delegation.py) ---------
@app.get("/api/delegate")
def api_delegate(u: dict = Depends(screen("delegate"))):
    return delegation.page(u)


@app.post("/api/delegate")
def api_delegate_create(body: dict = Body(...), u: dict = Depends(screen("delegate"))):
    return delegation.create(u, body or {})


@app.post("/api/delegate/{did}/revoke")
def api_delegate_revoke(did: str, u: dict = Depends(screen("delegate"))):
    return delegation.revoke(u, did)


@app.get("/api/portalstats")
def api_portalstats(ay: str = "", _: dict = Depends(screen("portalstats"))):
    """Portal analytics (2026-10-04 owner): firms, people, returns, files, and the firms that need the admin (chips portalstats.*)."""
    r = portal_stats.report(ay)
    # the firms and each card's names come one page at a time (list.portal_firms, list.portal_flags); here only counts and the first few
    look = engine.run("page.portalstats")
    n = look["flag_chips"]
    flags = {k: r["roll"][k] for k in look["flags"]}
    return {k: v for k, v in r.items() if k != "firms"} | {"roll": r["roll"] | {k: v[:n] for k, v in flags.items()},
                                                          "flag_n": {k: len(v) for k, v in flags.items()}}


@app.get("/api/taxwatch")
def api_taxwatch(ay: str = "", u: dict = Depends(firms.gate("taxwatch"))):
    """Tax rules (2026-10-06 owner): the live figures beside the new year's as fetched - Fetch, Compare, Apply (chips taxwatch.*).
    Everyone in Filing reads it; only the portal owner fetches, edits and applies (the owner guard on those routes)."""
    can = u.get("role") == "owner"
    return taxwatch.compare(ay or taxwatch.compare("")["next"]) | {"can_change": can, "ais": taxwatch.ai_choices(u) if can else []}


@app.get("/api/rulebook")
def api_rulebook(_: dict = Depends(firms.gate("taxwatch"))):
    """The rule book (2026-10-06 owner): every rule the engine follows, built from the chips now - so after Apply it is current."""
    import rulebook  # noqa: PLC0415
    return HTMLResponse('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                        + rulebook.build() + "</html>")


@app.post("/api/taxwatch/{ay}/fetch")
def api_taxwatch_fetch(ay: str, body: dict = Body(default={}), u: dict = Depends(owner)):
    return taxwatch.fetch(u, ay, str((body or {}).get("provider") or ""))


@app.put("/api/taxwatch/{ay}/{item}")
def api_taxwatch_edit(ay: str, item: str, body: dict = Body(...), u: dict = Depends(owner)):
    return taxwatch.edit(u, ay, item, body.get("value"))


@app.post("/api/taxwatch/{ay}/apply")
def api_taxwatch_apply(ay: str, body: dict = Body(...), u: dict = Depends(owner)):
    return taxwatch.apply(u, ay, [str(x) for x in (body.get("ids") if isinstance(body.get("ids"), list) else [])])


@app.get("/api/server")
def api_server(_: dict = Depends(screen("server"))):
    """Server & sites (2026-10-04 owner, read-only): each site's state, the disk, the backups, disk over time (chips server.*)."""
    return server.report()


@app.get("/api/server/du")
def api_server_du(path: str = "/", _: dict = Depends(screen("server"))):
    """One folder's children by size - read-only."""
    return server.du(path)


@app.get("/api/approvals")
def api_approvals(state: str = "", _: dict = Depends(screen("approvals"))):
    return {"counts": firms.counts(), "settings": firms.settings()}   # the rows: list.firm_requests


# --- Clients & years (SimplyFile, 2026-10-03): the client master, carried into each assessment year (clients.py) ----
@app.get("/api/clients/settings")
def api_clients_settings(_: dict = Depends(firms.gate("clients"))):
    return clients.settings() | {"company": company.settings()}    # 2026-10-11 ITR-6: the company part's kinds, options, blocks (chip company.settings)


@app.get("/api/clients/summary")
def api_clients_summary(ay: str = "", u: dict = Depends(firms.gate("clients"))):
    return clients.summary(ay or clients.settings()["current_ay"], u)


@app.get("/api/clients/{cid}")
def api_clients_get(cid: str, _: dict = Depends(firms.gate("clients"))):
    return clients.get(cid)


@app.post("/api/clients")
def api_clients_create(body: dict = Body(...), u: dict = Depends(firms.gate("clients", "create"))):
    firms.may_add_client(u, clients.count(u))        # a self-filer holds one client (chip firm.client_room)
    return clients.save(u, body)


@app.put("/api/clients/{cid}")
def api_clients_update(cid: str, body: dict = Body(...), u: dict = Depends(firms.gate("clients"))):
    return clients.save(u, body, cid)


@app.post("/api/clients/{cid}/parties/learn")
def api_clients_parties_learn(cid: str, ay: str = "", u: dict = Depends(firms.gate("clients"))):
    """2026-10-05 owner (3CD): the parties this year's 3CD rows name, into the client's party master."""
    return clients.learn_parties(u, cid, itr_json.statement_parties(cid, ay or clients.settings()["current_ay"]))


@app.put("/api/clients/{cid}/years/{ay}")
def api_clients_year(cid: str, ay: str, body: dict = Body(...), u: dict = Depends(firms.gate("clients"))):
    return clients.set_year(u, cid, ay, body)        # form, 3CD audit, preparer; the stage moves by itself


@app.post("/api/clients/archive")
def api_clients_archive_many(body: dict = Body(...), u: dict = Depends(firms.gate("clients", "archive"))):
    """The ticked clients at once - each with every filing of theirs (2026-10-04 owner)."""
    return clients.archive_many(u, list(body.get("ids") if isinstance(body.get("ids"), list) else []), bool(body.get("archived", True)))


@app.post("/api/clients/{cid}/years/{ay}/archive")
def api_clients_year_archive(cid: str, ay: str, body: dict = Body(...), u: dict = Depends(firms.gate("clients", "archive"))):
    """One year's filing alone - the client stays active."""
    return clients.archive_year(u, cid, ay, bool(body.get("archived", True)))


@app.post("/api/clients/{cid}/archive")
def api_clients_archive(cid: str, body: dict = Body(...), u: dict = Depends(firms.gate("clients", "archive"))):
    return clients.archive(u, cid, bool(body.get("archived", True)))


# --- Intake & map (SimplyFile phase 2, 2026-10-03): statements per client and year, each row's SF Ref (intake.py) ----
@app.get("/api/intake/{cid}/{ay}")
def api_intake_files(cid: str, ay: str, _: dict = Depends(firms.gate("intake"))):
    return intake.files(cid, ay)


@app.post("/api/intake/{cid}/{ay}")
async def api_intake_upload(cid: str, ay: str, file: UploadFile = File(...), replace: str = "", u: dict = Depends(firms.gate("intake"))):
    data = await upload_bytes(u, file, intake.settings()["max_mb"] * 1024 * 1024 + 1)
    return await run_in_threadpool(intake.add, u, cid, ay, file.filename or "", data, replace)


@app.get("/api/intake/{cid}/{ay}/{fid}")
def api_intake_view(cid: str, ay: str, fid: str, _: dict = Depends(firms.gate("intake"))):
    return intake.view(cid, ay, fid)


@app.put("/api/intake/{cid}/{ay}/{fid}/tags")
def api_intake_tags(cid: str, ay: str, fid: str, body: dict = Body(...), u: dict = Depends(firms.gate("intake"))):
    return intake.set_tags(u, cid, ay, fid, body.get("tags") or {})


@app.post("/api/intake/{cid}/{ay}/{fid}/accept")
def api_intake_accept(cid: str, ay: str, fid: str, u: dict = Depends(firms.gate("intake"))):
    return intake.accept_all(u, cid, ay, fid)


@app.get("/api/intake/{cid}/{ay}/{fid}/download")
def api_intake_download(cid: str, ay: str, fid: str, _: dict = Depends(firms.gate("intake"))):
    name, data = intake.tagged_book(cid, ay, fid)
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers=named(name.removesuffix(".xlsx"), ".xlsx"))


@app.delete("/api/intake/{cid}/{ay}/{fid}")
def api_intake_delete(cid: str, ay: str, fid: str, _: dict = Depends(firms.gate("intake", "delete"))):
    intake.delete(cid, ay, fid)
    return {"ok": True}


# --- Compute & close (SimplyFile phases 4 + 5, 2026-10-04): the computation, the filing files, sign-off, close (compute.py) ---
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@app.get("/api/compute/{cid}/{ay}")
def api_compute(cid: str, ay: str, _: dict = Depends(firms.gate("compute"))):
    return compute.compute(cid, ay)


@app.put("/api/compute/{cid}/{ay}")
def api_compute_set(cid: str, ay: str, body: dict = Body(...), u: dict = Depends(firms.gate("compute"))):
    return compute.set_state(u, cid, ay, body)


@app.post("/api/compute/{cid}/{ay}/signoff")
def api_compute_signoff(cid: str, ay: str, body: dict = Body(...), u: dict = Depends(firms.gate("compute", "signoff"))):
    return compute.sign_off(u, cid, ay, bool(body.get("on", True)))


@app.post("/api/compute/{cid}/{ay}/file")
def api_compute_file(cid: str, ay: str, body: dict = Body(...), u: dict = Depends(firms.gate("compute", "file"))):
    """Mark the return filed (acknowledgement no. + date filed); the kind - original, belated, revised, ITR-U - is chip close.dates."""
    return compute.act(u, cid, ay, "file", body)


@app.post("/api/compute/{cid}/{ay}/{action}")
def api_compute_act(cid: str, ay: str, action: str, body: dict = Body(default={}), u: dict = Depends(firms.gate("compute", "reopen"))):
    """withdraw (undo a wrong 'filed', with a reason) / revise (start a revised or updated return) / discard (drop the revision)."""
    if action not in ("withdraw", "revise", "discard"):
        raise HTTPException(404)
    return compute.act(u, cid, ay, action, body)


@app.get("/api/compute/{cid}/{ay}/computation.xlsx")
def api_compute_xlsx(cid: str, ay: str, _: dict = Depends(firms.gate("compute"))):
    name, data = compute.computation_xlsx(cid, ay)
    return Response(data, media_type=XLSX, headers=named(name.removesuffix(".xlsx"), ".xlsx"))


@app.get("/api/compute/{cid}/{ay}/utility.zip")
def api_compute_zip(cid: str, ay: str, _: dict = Depends(firms.gate("compute"))):
    name, data = compute.utility_zip(cid, ay)
    return Response(data, media_type="application/zip", headers=named(name.removesuffix(".zip"), ".zip"))


@app.get("/api/compute/{cid}/{ay}/3cd-check")
def api_compute_3cd_check(cid: str, ay: str, _: dict = Depends(firms.gate("compute"))):
    """The Form 3CA/3CB-3CD JSON checked against the CBDT schema."""
    return itr_json.report(cid, ay, "tar")


@app.get("/api/compute/{cid}/{ay}/3cd.json")
def api_compute_3cd_json(cid: str, ay: str, _: dict = Depends(firms.gate("compute"))):
    name, data = itr_json.export(cid, ay, "tar")
    return Response(data, media_type="application/json", headers=named(name.removesuffix(".json"), ".json"))


@app.get("/api/compute/{cid}/{ay}/itr-check")
def api_compute_itr_check(cid: str, ay: str, _: dict = Depends(firms.gate("compute"))):
    """The ITR JSON checked against the CBDT schema: valid?, and every problem with its path."""
    return itr_json.report(cid, ay)


@app.get("/api/compute/{cid}/{ay}/itr.json")
def api_compute_itr_json(cid: str, ay: str, _: dict = Depends(firms.gate("compute"))):
    name, data = itr_json.export(cid, ay)
    return Response(data, media_type="application/json", headers=named(name.removesuffix(".json"), ".json"))


# --- My return (2026-10-06): an individual's own ITR-1 / ITR-2 - documents in, both regimes, the JSON out (myreturn.py) ---
@app.get("/api/myreturn")
def api_myreturn_home(u: dict = Depends(firms.gate("myreturn"))):
    """Where the journey starts: a self-filer's own return (their one client, the year being worked), else the clients to pick from."""
    mine = [c for c in clients._mine(u) if not c.get("archived_at")]  # noqa: SLF001
    k = clients.settings()
    return {"current_ay": k["current_ay"], "years": k["years"],
            "clients": [{"id": c["id"], "name": c["name"], "pan": c["pan"], "status": c["status"]} for c in mine],
            "self": len(mine) == 1 and bool(firms.firm_of(u)) and firms.kind_of(firms.firm_of(u)["kind"])["self_client"]}


@app.get("/api/myreturn/{cid}/{ay}")
def api_myreturn(cid: str, ay: str, _: dict = Depends(firms.gate("myreturn"))):
    return myreturn.work(cid, ay)


@app.put("/api/myreturn/{cid}/{ay}")
def api_myreturn_set(cid: str, ay: str, body: dict = Body(...), u: dict = Depends(firms.gate("myreturn"))):
    """Answers, figures typed over the documents', houses, the regime, a check accepted, a step done."""
    return myreturn.answer(u, cid, ay, body)


@app.post("/api/myreturn/start/{ay}")
async def api_myreturn_start(ay: str, file: UploadFile = File(...), password: str = Form(""), on_old: str = Form(""), on_same: str = Form(""),
                             u: dict = Depends(firms.gate("myreturn"))):
    """A return begun from a document - the pre-filled JSON or a filed return names the person, who becomes the client."""
    data = await file.read()
    return await run_in_threadpool(myreturn.start, u, ay, file.filename or "file", data, password, on_old, on_same)


# --- New filing (2026-10-11): the guided way into My return - what applies, the documents, upload, review (wizard.py) -------
# The path names a filing ({wid}), not a client: wizard._load refuses another firm's (the tenant wall) - firms.gate checks the screen.
@app.get("/api/wizard")
def api_wizard_home(u: dict = Depends(firms.gate("wizard"))):
    """Who a return may be for, what may apply, and the filings waiting to be carried on."""
    return wizard.home(u)


@app.post("/api/wizard")
def api_wizard_start(body: dict = Body(...), u: dict = Depends(firms.gate("wizard"))):
    return wizard.start(u, body)


@app.get("/api/wizard/{wid}")
def api_wizard_get(wid: str, u: dict = Depends(firms.gate("wizard"))):
    return wizard.view_of(u, wid)


@app.put("/api/wizard/{wid}")
def api_wizard_set(wid: str, body: dict = Body(...), u: dict = Depends(firms.gate("wizard"))):
    """Who, what applies, the step reached, the popup's answers."""
    return wizard.update(u, wid, body)


@app.delete("/api/wizard/{wid}")
def api_wizard_discard(wid: str, u: dict = Depends(firms.gate("wizard"))):
    return wizard.discard(u, wid)


@app.post("/api/wizard/{wid}/files")
async def api_wizard_file(wid: str, file: UploadFile = File(...), password: str = Form(""), on_same: str = Form(""),
                          u: dict = Depends(firms.gate("wizard"))):
    data = await file.read()
    return await run_in_threadpool(wizard.upload, u, wid, file.filename or "file", data, password, on_same)


@app.delete("/api/wizard/{wid}/files/{fid}")
def api_wizard_file_remove(wid: str, fid: str, u: dict = Depends(firms.gate("wizard"))):
    return wizard.remove(u, wid, fid)


@app.post("/api/wizard/{wid}/finish")
def api_wizard_finish(wid: str, u: dict = Depends(firms.gate("wizard"))):
    return wizard.finish(u, wid)


@app.post("/api/myreturn/{cid}/{ay}/docs")
async def api_myreturn_doc(cid: str, ay: str, file: UploadFile = File(...), password: str = Form(""), on_same: str = Form(""),
                           u: dict = Depends(firms.gate("myreturn"))):
    """A document dropped in: kept, read (pre-filled JSON, AIS, Form 16, 26AS), and added to the return."""
    data = await file.read()
    return await run_in_threadpool(myreturn.add_doc, u, cid, ay, file.filename or "file", data, password, on_same)


@app.delete("/api/myreturn/{cid}/{ay}/docs/{fid}")
def api_myreturn_doc_delete(cid: str, ay: str, fid: str, u: dict = Depends(firms.gate("myreturn"))):
    return myreturn.remove_doc(u, cid, ay, fid)


@app.get("/api/myreturn/{cid}/{ay}/docs/{fid}/file")
def api_myreturn_doc_file(cid: str, ay: str, fid: str, _: dict = Depends(firms.gate("myreturn"))):
    path, name = myreturn.doc_file(cid, ay, fid)
    return FileResponse(path, filename=name)


@app.post("/api/myreturn/{cid}/{ay}/from-filed")
def api_myreturn_from_filed(cid: str, ay: str, u: dict = Depends(firms.gate("myreturn"))):
    """This year's filed return fills Already filed? and the tax paid (2026-10-06)."""
    return myreturn.from_filed(u, cid, ay)


@app.get("/api/myreturn/{cid}/{ay}/compare")
def api_myreturn_compare(cid: str, ay: str, _: dict = Depends(firms.gate("myreturn"))):
    """The return as filed beside the return as made here, figure by figure."""
    return myreturn.compare(cid, ay)


@app.get("/api/myreturn/{cid}/{ay}/itr-check")
def api_myreturn_check(cid: str, ay: str, _: dict = Depends(firms.gate("myreturn"))):
    """The ITR-1 / ITR-2 JSON checked against the department's schema."""
    return myreturn.report(cid, ay)


@app.get("/api/myreturn/{cid}/{ay}/itr.json")
def api_myreturn_json(cid: str, ay: str, _: dict = Depends(firms.gate("myreturn"))):
    name, data, _rep = myreturn.export(cid, ay)
    return Response(data, media_type="application/json", headers=named(name.removesuffix(".json"), ".json"))


@app.get("/api/compute/{cid}/{ay}/3cd.xlsx")
def api_compute_3cd(cid: str, ay: str, _: dict = Depends(firms.gate("compute"))):
    name, data = compute.schedule_3cd_xlsx(cid, ay)
    return Response(data, media_type=XLSX, headers=named(name.removesuffix(".xlsx"), ".xlsx"))


# --- History (2026-10-05 owner: "change log - field, old value, new value, when, who - and earlier versions of a document")
def _gate_either(*screens):
    """firms.gate for the first of these screens the person may use (2026-10-07: a self-filer's own History is reached from My
    return - they have no Clients & years; the client's firm is still checked by the gate)."""
    gates = [firms.gate(sc) for sc in screens]

    def guard(request: Request) -> dict:
        err = None
        for g in gates:
            try:
                return g(request)
            except HTTPException as e:
                err = e
        raise err
    guard.screen_id, guard.function_id = screens[0], ""
    return guard


@app.get("/api/changes/file/{cid}/{ay}/{kept_in}/{fid}/{v}")
def api_changes_file(cid: str, ay: str, kept_in: str, fid: str, v: int, name: str = "", _: dict = Depends(_gate_either("clients", "myreturn"))):
    p = changelog.kept_file(cid, ay, kept_in, fid, v)
    nice = re.sub(r"[^\w .()-]", "", name)[:120].strip()          # the file's own name, as the log shows it
    return FileResponse(p, filename=changelog.say("file_name", name=Path(nice).stem or p.stem, v=v) + p.suffix)


# --- Tax audit (2026-10-04 owner: "phase 1, tax audit for SMEs"): applicability, year on year, the 3CD checklist, points (audit.py)
@app.get("/api/audit/{cid}/{ay}")
def api_audit(cid: str, ay: str, u: dict = Depends(firms.gate("audit"))):
    return audit.page(u, cid, ay)


@app.put("/api/audit/{cid}/{ay}/facts")
def api_audit_facts(cid: str, ay: str, body: dict = Body(...), u: dict = Depends(firms.gate("audit"))):
    return audit.set_facts(u, cid, ay, body)


@app.post("/api/audit/{cid}/{ay}/gst")
async def api_audit_gst(cid: str, ay: str, files: list[UploadFile] = File(...), u: dict = Depends(firms.gate("audit"))):
    cap = int(engine.run("audit.gst_read")["max_mb"]) * 1024 * 1024 + 1
    got = [(f.filename or "", await upload_bytes(u, f, cap)) for f in files]
    return await run_in_threadpool(audit.add_gst, u, cid, ay, got)


@app.delete("/api/audit/{cid}/{ay}/gst/{gid}")
def api_audit_gst_remove(cid: str, ay: str, gid: str, u: dict = Depends(firms.gate("audit"))):
    return audit.remove_gst(u, cid, ay, gid)


@app.put("/api/audit/{cid}/{ay}/standards/{sid}")
def api_audit_standard(cid: str, ay: str, sid: str, body: dict = Body(...), u: dict = Depends(firms.gate("audit"))):
    return audit.set_as(u, cid, ay, sid, body)


@app.put("/api/audit/{cid}/{ay}/checks/{iid}")
def api_audit_check(cid: str, ay: str, iid: str, body: dict = Body(...), u: dict = Depends(firms.gate("audit"))):
    return audit.set_check(u, cid, ay, iid, body)


@app.post("/api/audit/{cid}/{ay}/points")
def api_audit_point(cid: str, ay: str, body: dict = Body(...), u: dict = Depends(firms.gate("audit"))):
    return audit.add_point(u, cid, ay, body)


@app.put("/api/audit/{cid}/{ay}/points/{pid}")
def api_audit_point_edit(cid: str, ay: str, pid: str, body: dict = Body(...), u: dict = Depends(firms.gate("audit"))):
    return audit.set_point(u, cid, ay, pid, {k: v for k, v in body.items() if k in ("owner", "note")})


@app.put("/api/audit/{cid}/{ay}/points/{pid}/status")
def api_audit_point_status(cid: str, ay: str, pid: str, body: dict = Body(...), u: dict = Depends(firms.gate("audit", "clear"))):
    return audit.set_point(u, cid, ay, pid, {"status": body.get("status")})


# --- Reconcile (SimplyFile phase 3, 2026-10-04): books against 26AS / AIS / TIS (recon.py) ------------------------------
@app.get("/api/recon/{cid}/{ay}")
def api_recon(cid: str, ay: str, _: dict = Depends(firms.gate("recon"))):
    return {"files": recon.files(cid, ay)} | recon.findings(cid, ay)


@app.post("/api/recon/{cid}/{ay}")
async def api_recon_upload(cid: str, ay: str, file: UploadFile = File(...), replace: str = "", u: dict = Depends(firms.gate("recon"))):
    data = await upload_bytes(u, file, recon.settings()["max_mb"] * 1024 * 1024 + 1)
    return await run_in_threadpool(recon.add, u, cid, ay, file.filename or "", data, replace)


@app.put("/api/recon/{cid}/{ay}/notes/{fid}")
def api_recon_note(cid: str, ay: str, fid: str, body: dict = Body(...), u: dict = Depends(firms.gate("recon"))):
    return {"files": recon.files(cid, ay)} | recon.explain(u, cid, ay, fid, body.get("note", ""))


@app.delete("/api/recon/{cid}/{ay}/{fid}")
def api_recon_delete(cid: str, ay: str, fid: str, _: dict = Depends(firms.gate("recon", "delete"))):
    recon.delete(cid, ay, fid)
    return {"ok": True}


# --- Guide Me Builder (2026-09-28): a Guide Me script checked, kept, previewed and exported (guideme.py) ----
@app.get("/api/guideme")
def api_guideme_list(q: str = "", page: int = 1, u: dict = Depends(screen("guideme"))):
    return guideme.find(u["id"], q, page)


@app.post("/api/guideme")
def api_guideme_create(body: dict = Body(...), u: dict = Depends(screen("guideme"))):
    """{script: {...}} or {script_text: "..."} (a dropped file or the paste box). Problems -> 422 {message, problems}."""
    return guideme.save(u["id"], body["script"] if body.get("script") is not None else body.get("script_text", ""))


@app.get("/api/guideme/{build_id}")
def api_guideme_get(build_id: str, u: dict = Depends(screen("guideme"))):
    return guideme.get(u["id"], build_id)


@app.post("/api/guideme/{build_id}/script")
def api_guideme_replace(build_id: str, body: dict = Body(...), u: dict = Depends(screen("guideme"))):
    return guideme.save(u["id"], body["script"] if body.get("script") is not None else body.get("script_text", ""), build_id)


@app.get("/api/guideme/{build_id}/export")
def api_guideme_export(build_id: str, u: dict = Depends(screen("guideme"))):
    """One zip: the kit, the script, a ready guide-me.<page>.js and a README (chip guideme.export)."""
    name, data = guideme.export(u["id"], build_id)
    return Response(data, media_type="application/zip", headers=named(name, ".zip"))


@app.delete("/api/guideme/{build_id}")
def api_guideme_delete(build_id: str, u: dict = Depends(screen("guideme"))):
    return guideme.delete(u["id"], build_id)


# --- Check models (2026-09-26 owner: "new models come and go very fast - how will the portal know?"): the owner asks
# every provider for its list; new ones are added and gone ones retired as new chip versions (providers.py)
@app.get("/api/models/check")
def api_models_check(u: dict = Depends(owner)):
    import providers  # noqa: PLC0415
    return providers.model_check(u["id"])


@app.post("/api/models/add")
def api_models_add(body: dict = Body(default={}), u: dict = Depends(owner)):
    import providers  # noqa: PLC0415
    return providers.model_add(u, body or {})


@app.post("/api/models/retire")
def api_models_retire(body: dict = Body(default={}), u: dict = Depends(owner)):
    import providers  # noqa: PLC0415
    return providers.model_retire(u, body or {})


# --- the pages ------------------------------------------------------------------------------------

@app.get("/help/gemini-key", response_class=HTMLResponse)
def help_gemini_key():
    """How to get a Gemini key and put money behind it, step by step. No sign-in: people read this
    BEFORE they have an account, and they forward it to whoever pays."""
    html = (ROOT / "static" / "help-gemini-key.html").read_text(encoding="utf-8")
    url = settings()["help_video_url"].strip()
    if url:
        embed = (f'<iframe src="{escape(url)}" title="{escape(say("guide_video_title"))}" '
                 f'allowfullscreen loading="lazy"></iframe>' if _embeddable(url)
                 else f'<p><a href="{escape(url)}" target="_blank" rel="noopener">{escape(say("guide_video_link"))}</a></p>')
        html = html.replace("<!--VIDEO-->",
                            f'<div class="card"><b>{escape(say("guide_video_heading"))}</b>{embed}</div>')
    return HTMLResponse(html)


def _embeddable(url: str) -> bool:
    """Only the players known to allow framing (portal.embeddable_video); anything else is a plain link."""
    return engine.run("portal.embeddable_video", {"url": url}) is True


@app.get("/health", response_class=PlainTextResponse)
def health():
    """2026-11-12: 200 "ok" only when the data folder takes a write and every Postgres db answers; else 503 with the reason."""
    from core import health as _health  # noqa: PLC0415
    why = _health.ready()
    return PlainTextResponse(why, status_code=503) if why else _health.say("ready_ok")


def _boot_commit() -> str:
    """The commit this process started on - read once, so a pull without a restart shows as old code."""
    try:
        out = subprocess.run(["git", "-C", str(Path(__file__).resolve().parent), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() if out.returncode == 0 else "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


_BOOT = {"commit": _boot_commit(), "started_at": store.now()}


@app.get("/health/run")
def health_run(request: Request):
    """2026-10-01 owner: Restart sites (the studio Portal Admin -> VPS Console) waits for this. Which code runs and
    how many jobs are mid-way - asked ON the VPS only: a call that came through nginx carries a forwarded header."""
    if request.headers.get("x-forwarded-for") or request.headers.get("x-real-ip"):
        raise HTTPException(404)
    running = sum(1 for j in list(narrator._JOBS.values()) if (j or {}).get("status") == "running")  # noqa: SLF001
    return {"status": "healthy", "commit": _BOOT["commit"][:7], "commit_full": _BOOT["commit"],
            "started_at": _BOOT["started_at"], "jobs_running": running, "edition": edition.current().get("id", "")}


def page(host: str = "") -> str:
    """The one HTML page. Asset links are rewritten to the mount point so the portal works at the
    site root, at /tv, and with or without the trailing slash. 2026-10-01 Phase 4: the tab title and the boot line name
    THIS site (its door's product name, else the edition's) - sm and its door showed "Training & Video Portal" until boot."""
    import html as _html  # noqa: PLC0415
    name = (edition.door(host or "") or {}).get("product_name") or edition.current()["product_name"]
    page_ = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    page_ = page_.replace("<title>Training &amp; Video Portal</title>", f"<title>{_html.escape(name)}</title>").replace(
        ">Loading the portal…<", f">{_html.escape(say('page_loading', product=name))}<")
    page_ = _ui_sizes(page_)
    return page_.replace('"static/', f'"{BASE}/static/').replace('"core-static/', f'"{BASE}/core-static/') if BASE else page_


def _ui_sizes(html_: str) -> str:
    """2026-10-03 owner "move spacing into a ui chip": chip ui.spacing -> :root CSS variables, before portal.css loads."""
    html_ = linkcard.head(html_)   # the tab icon and the share card: chip share.card
    vars_ = engine.css_vars("ui.spacing")
    return html_.replace("</head>", f'<style id="ui-spacing">{vars_}</style></head>', 1) if vars_ else html_


# 2026-09-28 owner: "make the door standard as the other sites". A second address is a DOOR of the same shell (chip
# edition.settings doors: its name, pitch and first screen) - the same sign-in card, menu and screens, never a page of
# its own. /k stays the public reader for a shared link, for someone with no account.
# The landing page (public showcase, returning visitors skip it), / and /start: landing.py (boilerplate).
landing.install(app, page=page, ui_sizes=_ui_sizes, named=named)
# Start here (2026-10-09): a newcomer's first steps, ticked from real work - core/startcard.py, chip start.steps
from core import startcard  # noqa: E402
startcard.install(app)


app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")


@app.middleware("http")
async def edition_routes(request: Request, call_next):
    """2026-10-01 portal assessment: an address of a screen THIS site does not have (chip edition.route_screens - the
    routes a screen guard does not already cover) answers 404, as if it were not there (tv never serves the door's
    reader, Decks or studio lists)."""
    path = request.url.path
    for start, screen_id in (engine.run("edition.route_screens") or {}).items():
        hit = path == start[1:] if start.startswith("=") else path.startswith(start)
        if hit and screen_id not in access._BY_ID:                          # noqa: SLF001 - this site's catalog
            return JSONResponse({"detail": say("not_found")}, status_code=404)
    return await call_next(request)


@app.middleware("http")
async def revalidate_static(request: Request, call_next):
    """The interface is edited in place — a browser must never serve yesterday's app.js from cache.
    no-cache still allows a 304, so this costs one conditional request, not a re-download."""
    response = await call_next(request)
    if request.url.path.startswith((f"{BASE}/static/", "/static/", f"{BASE}/core-static/", "/core-static/")):
        response.headers["Cache-Control"] = "no-cache"
    return response


# 2026-10-16: screen code for members only (chip static.signed_out, off here) - added after revalidate_static so it runs first
from core import private_static  # noqa: E402
private_static.install(app)


@app.exception_handler(404)
def not_found(request: Request, exc):
    # The portal is one page with a hash router, so any unknown non-API address is still the portal.
    if request.url.path.startswith(("/api/", "/static/", "/core-static/", "/m/", "/embed/", "/w/", "/k/art/", "/k/cover/", "/k/media/", "/showcase/media/")):
        return JSONResponse({"detail": exc.detail if hasattr(exc, "detail") else say("not_found")}, status_code=404)
    return HTMLResponse(page(request.headers.get("host") or ""))
