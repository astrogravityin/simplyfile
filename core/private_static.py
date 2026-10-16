"""Screen code for members only (2026-10-16, CodyFy owner "yes hide": its screens must not be downloadable signed out).

A portal's screens are plain files under /static and /core-static. With chip static.signed_out `on`, a visitor who is NOT
signed in gets only the files the public pages need (chip static.public_files + the portal's static.signed_out
extra_public); every other file there answers 404, exactly like a file that does not exist - nothing says it is there.
A signed-in member gets every file, marked private and not stored (chip static.signed_out member_cache), so no shared
cache keeps a protected file for the next visitor; the 404 is never stored either.

Off by default (the chip ships `on: false`): a portal turns it on only after its app.js loads its screens after sign-in
(core/static/shell.js startPortal `screens`), because a public app.js that imports a screen statically would break the
sign-in page. app.py: private_static.install(app) AFTER its own static middlewares (added last = runs first, so the
member headers are the last word).
"""
from __future__ import annotations

import fnmatch
import posixpath
from http import HTTPStatus

from fastapi import Request
from fastapi.responses import JSONResponse

from core import auth, engine, store


def policy() -> dict:
    return engine.run("static.signed_out")


def public_patterns(p: dict | None = None) -> list[str]:
    p = p or policy()
    return list(engine.run("static.public_files")["files"]) + list(p.get("extra_public") or [])


def _norm(path: str) -> str:
    """The address as the file server will resolve it: BASE off, '..' and '//' folded, so a trick spelling of a protected
    file is judged as that file."""
    if auth.BASE and path.startswith(auth.BASE):
        path = path[len(auth.BASE):]
    out = posixpath.normpath("/" + path.replace("\\", "/").lstrip("/"))   # one leading slash: normpath keeps "//"
    return out + "/" if path.endswith("/") and out != "/" else out


def protected(path: str, p: dict | None = None) -> bool:
    """Is this address a file only a member may read? Default deny: under a root and not a public pattern."""
    p = p or policy()
    n = _norm(path)
    if not any(n.startswith(r) for r in p.get("roots") or []):
        return False
    return not any(fnmatch.fnmatchcase(n, pat) for pat in public_patterns(p))


def _member(request: Request) -> bool:
    return bool(store.session_user(request.cookies.get(auth.COOKIE) or ""))   # no note_session: a file is not a sitting


async def gate(request: Request, call_next):
    p = policy()
    if not p.get("on") or not protected(request.url.path, p):
        return await call_next(request)
    head = {"Cache-Control": p["member_cache"], "Vary": "Cookie"}
    if not _member(request):
        return JSONResponse({"detail": HTTPStatus.NOT_FOUND.phrase}, status_code=404, headers=head)
    response = await call_next(request)
    response.headers.update(head)
    return response


def install(app) -> None:
    app.middleware("http")(gate)
