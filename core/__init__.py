"""The portal framework: everything a new portal needs before its first product screen.

    Login           core/auth.py      first owner, sign in/up, confirm, reset, invite, mail
    People & access core/access.py    accounts, groups, allow/deny per screen and function
    Portal activity core/ledger.py    every request, body-free, with reports and archive
    Visitors        core/ledger.py    page views, sessions, places, devices; world + India maps
                    core/geo.py       places without a CDN: local DB-IP database, stdlib reader
    Storage         core/storage.py   who holds the disk; ask to clean up (3 requests), then delete
    Memory watch    core/memwatch.py  memory, whole server (CPU, memory, disk, bandwidth), verdict, offenders
    Chips & ops     core/engine.py    every decision is a JSON chip (core/chips, <portal>/chips) built from
                    core/ops.py       generic primitives — the studio's architecture, stdlib only
    Rules           core/rules.py     at a trigger, when chips hold, do: refuse · banner · email · value · flag
    Builders        core/builder.py   Ops & Chips Builder + Rule Chip Builder: draft → review → publish,
                                      history, scenarios; owner / editor / author (chip builder.can)
    How to Use      core/howto.py     training links per page, shown in the top bar
    Menu builder    core/menus.py     name, group, icon and order of every screen; a found screen stays a draft until Live
    Screen guide    core/guide.py     a step-by-step spotlight tour of each screen (chips guide.<screen>)
    Search          core/find.py      one box in the top bar that reaches every screen and action (chip find.score)
    Jobs            core/jobs.py      long work as saved steps: resume, stop cleanly, never pay twice (chips jobs.*)
    Words           core/words.py     every word on every screen is chip ui.<screen>; ui.<screen>.<lang> translates

A new portal:

    from fastapi import FastAPI
    import core
    app = FastAPI()
    core.install(app, catalog="catalog.json")        # its own screens; core adds the Admin ones
    @app.get("/api/things")
    def things(u = Depends(core.screen("things"))): ...

and in the browser, `startPortal({...})` from core/static/shell.js. See core/README.md.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi.staticfiles import StaticFiles

from core import about  # noqa: E402 - 2026-11-09 About us: who we are + the live build (GET /api/about/build)
from core import access, auth, bell, builder, demo, doctor, engine, find, geo, guide, health, howto, issues, jobs, ledger, lists, mcp, mcp_oauth, memwatch, menus, rules, storage, store, words
from core import artifacts  # noqa: E402,F401 - 2026-11-05 ValueStream CC Clean-up: artifacts_scan / artifacts_delete on the MCP door
from core import agents  # noqa: E402 - 2026-10-24 Agents (the SteadyMove / AstroStage runtime)

screen = access.screen
signed_in, owner, current_user = auth.signed_in, auth.owner, auth.current_user
HERE = Path(__file__).resolve().parent


# 2026-09-28 owner: after a restart an open tab kept the OLD page scripts against the NEW server ("Cannot read
# properties of undefined (reading 'filter')"). Every answer names the server build; a page that sees a new one
# reloads on its next screen change (core/static/shell.js). The build is the page code itself (every static file's
# name, size and time), so a restart with the same code asks nobody to reload, and two workers agree.
BUILD = ""


def build_of(*folders: Path) -> str:
    import hashlib  # noqa: PLC0415
    h = hashlib.sha1()
    for folder in folders:
        for f in sorted(folder.rglob("*")) if folder.is_dir() else []:
            if f.is_file():
                st = f.stat()
                h.update(f"{f.relative_to(folder)}|{st.st_size}|{int(st.st_mtime)}".encode())
    return h.hexdigest()[:12]


async def _no_nul(request, call_next):
    """2026-10-02 security test: a NUL in a path (/api/frames/%00/video) reached a file helper and answered 500. No id,
    name or path ever holds one - refused at the door, for every route at once."""
    if "\0" in request.url.path or "%00" in request.url.query:
        from fastapi.responses import Response  # noqa: PLC0415
        return Response(status_code=404)
    return await call_next(request)


async def _multipart_cap(request, call_next):
    """2026-10-21 reviews: a multipart upload had no overall cap (each file route capped its own part, nginx allowed 50 MB). A form
    upload bigger than chip limits.request multipart_most_mb - or with no length given - is refused before anything is read."""
    if "multipart" in request.headers.get("content-type", ""):
        k, mb = engine.run("limits.request"), int(request.headers.get("content-length") or 0) / (1024 * 1024)
        if "chunked" in request.headers.get("transfer-encoding", "").lower():
            mb = float("inf")
        if engine.run("limits.request_too_big", {"request_mb": mb, "json_most_mb": k["multipart_most_mb"]}) is True:
            from fastapi.responses import JSONResponse  # noqa: PLC0415
            return JSONResponse({"detail": engine.say("limits.request", "too_big", mb=k["multipart_most_mb"])}, status_code=413)
    return await call_next(request)


_ONE_COPY: list = []


def _one_copy_only() -> None:
    """2026-10-21 reviews: a second copy of the portal on the same data folder (a second service, a replica) would split the
    in-process locks, throttles and jobs silently. An OS lock on data/.portal.lock: a second copy refuses to start, saying why.
    The lock goes with the process, so a crash never leaves it held."""
    if _ONE_COPY:
        return                                            # this process holds it already (an app built twice in one test run)
    store.DATA.mkdir(parents=True, exist_ok=True)
    f = open(store.DATA / ".portal.lock", "a+")
    try:
        if os.name == "nt":
            import msvcrt  # noqa: PLC0415
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl  # noqa: PLC0415
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        raise RuntimeError(f"another copy of this portal is already running on {store.DATA} - stop it first (one copy per data folder)")
    _ONE_COPY.append(f)


async def _json_cap(request, call_next):
    """2026-10-02 security test: any JSON body was read whole (nginx passes 1200 MB for uploads). A JSON request bigger
    than chip limits.request json_most_mb is refused before it is read; file uploads keep their own limits."""
    if "json" in request.headers.get("content-type", ""):
        k, mb = engine.run("limits.request"), int(request.headers.get("content-length") or 0) / (1024 * 1024)
        if "chunked" in request.headers.get("transfer-encoding", "").lower():
            mb = float("inf")                            # 2026-10-02 review: no length given = never read whole on trust
        if engine.run("limits.request_too_big", {"request_mb": mb, "json_most_mb": k["json_most_mb"]}) is True:
            from fastapi.responses import JSONResponse  # noqa: PLC0415
            return JSONResponse({"detail": engine.say("limits.request", "too_big", mb=k["json_most_mb"])}, status_code=413)
    return await call_next(request)


async def _stamp_build(request, call_next):
    response = await call_next(request)
    response.headers["X-Portal-Build"] = BUILD
    # 2026-10-01 portal assessment: one list of security headers for every answer of every site (chip security.headers);
    # an answer that sets its own (a deck file's CSP) keeps it; a page others may frame (/m/, /embed/) is not denied
    try:
        k = engine.run("security.headers")
    except Exception:  # noqa: BLE001 - no chip library yet (a bare test): the answer goes out as it is
        return response
    path = request.url.path
    framed_ok = any(path.startswith(p) for p in k.get("frame_ok_paths") or [])
    for name, value in (k.get("headers") or {}).items():
        if framed_ok and name in ("X-Frame-Options", "Content-Security-Policy"):
            continue
        if name not in response.headers:
            response.headers[name] = value
    https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "").lower() == "https"
    if https and k.get("hsts") and "Strict-Transport-Security" not in response.headers:
        response.headers["Strict-Transport-Security"] = k["hsts"]
    return response


async def _head_as_get(request, call_next):
    """2026-11-02 link cards: WhatsApp (and most link checkers) ask HEAD before reading a page. Every page route is GET only, so
    HEAD answered 405 and a pasted link showed no card at all. HEAD = the GET's status and headers, never its body."""
    if request.method != "HEAD":
        return await call_next(request)
    request.scope["method"] = "GET"
    try:
        got = await call_next(request)
    finally:
        request.scope["method"] = "HEAD"     # the server below still knows it is a HEAD (no body is sent)
    from starlette.responses import Response  # noqa: PLC0415
    out = Response(status_code=got.status_code)
    out.raw_headers = got.raw_headers
    return out


def install(app, *, catalog, chips=None, rules_dir=None, scenarios=None) -> None:
    """`chips`, `rules_dir`, `scenarios` = the portal's own folders (its business), beside core's."""
    global BUILD
    # 2026-10-20 critical review: locks, sign-in throttles, previews and jobs live in this one process. Several web workers would
    # split them silently - refused at start, with the reason, until they move to shared storage.
    if int(os.getenv("WEB_CONCURRENCY", "1") or 1) > 1 or any(a.startswith("--workers") for a in sys.argv):
        raise RuntimeError("this portal runs as ONE web worker (shared locks, sign-in throttles, previews and jobs are in-process); "
                           "remove --workers / WEB_CONCURRENCY")
    _one_copy_only()
    BUILD = build_of(HERE / "static", *([Path(chips).resolve().parent / "static"] if chips else []))
    if chips:
        engine.register_dir(chips)
    if rules_dir:
        rules.register_dir(rules_dir)
    if scenarios:
        builder.SCENARIO_DIRS.append(Path(scenarios).resolve())
    access.migrate_roles()
    jobs.recover()                       # a job running when the server stopped is stopped, not stuck
    store.ensure_usernames()
    problems = engine.certify(builder.scenarios()) + rules.certify(builder.scenarios())
    if problems:  # loud, not fatal: a portal with one bad chip or rule still serves every other screen
        print("[chips] certification problems:\n  " + "\n  ".join(problems), file=sys.stderr, flush=True)
    access.load(catalog)
    auth.BOOTSTRAP_EXTRAS.extend([access.bootstrap_extra, storage.bootstrap_extra, rules.bootstrap_extra,
                                  find.bootstrap_extra, guide.bootstrap_extra, issues.bootstrap_extra, bell.bootstrap_extra,
                                  demo.bootstrap_extra, health.bootstrap_extra])
    # Added last = runs first: the ledger times everything, including a request the limiter refuses.
    app.middleware("http")(_stamp_build)
    app.middleware("http")(auth.limit_auth)
    app.middleware("http")(auth.force_password_change)
    app.middleware("http")(ledger.track)
    app.middleware("http")(_no_nul)
    app.middleware("http")(_json_cap)
    app.middleware("http")(_multipart_cap)
    app.middleware("http")(_head_as_get)
    app.middleware("http")(doctor.catch)     # added last = runs first: every unexpected error, from any layer (Error Doctor)
    for module in (about, auth, access, ledger, memwatch, howto, menus, guide, storage, builder, find, jobs, words, lists, issues, bell, demo, doctor, mcp, mcp_oauth, agents):
        app.include_router(module.router)
    app.mount("/core-static", StaticFiles(directory=str(HERE / "static")), name="core-static")
    memwatch.start()
    agents.start()                       # 2026-10-24: Agents - schedule triggers (core/agents.py)
    doctor.heal_notes()       # 2026-10-21: older Doctor notes sent as the owner could never be resolved
    store.heal_sessions()     # 2026-10-21: sessions kept as they were become fingerprints (nobody is signed out)
    geo.start(on_loaded=ledger.backfill_places)
    _fold_http(app)          # 2026-11-05: the http middlewares above (and the portal's own) run as ONE layer


def _fold_http(app) -> None:
    """Every run of `@app.middleware("http")` functions becomes ONE BaseHTTPMiddleware layer that calls them in the same
    order (2026-11-05 portal-builder 6a: 14 layers cost ~25 ms of server time on EVERY request, a static file too, so the
    first page's ~39 scripts queued for ~1.1 s; their own work was ~2 ms in all). Done when the stack is first built, so
    the portal's own middlewares (added after install) are folded too; any other middleware keeps its place."""
    from starlette.middleware import Middleware  # noqa: PLC0415
    from starlette.middleware.base import BaseHTTPMiddleware  # noqa: PLC0415
    build = app.build_middleware_stack

    def chain(fns):
        async def dispatch(request, call_next):
            async def at(i, req):
                return await (call_next(req) if i == len(fns) else fns[i](req, lambda r: at(i + 1, r)))
            return await at(0, request)
        dispatch.folded = fns
        return dispatch

    def folded():
        out, run = [], []
        for m in [*app.user_middleware, None]:
            if m is not None and m.cls is BaseHTTPMiddleware and "dispatch" in m.kwargs:
                d = m.kwargs["dispatch"]
                run += getattr(d, "folded", [d])
                continue
            if run:
                out.append(Middleware(BaseHTTPMiddleware, dispatch=chain(run)))
                run = []
            if m is not None:
                out.append(m)
        app.user_middleware[:] = out
        return build()
    app.build_middleware_stack = folded
