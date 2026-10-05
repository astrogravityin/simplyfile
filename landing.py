"""The landing page - a public showcase for a visitor who is not signed in (boilerplate: every domain portal has it).

2026-10-05 owner: "do the same [as SteadyMove] for SimplyFile" - the showcase is the landing for a visitor (chip
showcase.settings sites: edition + door -> the words chip, here showcase.page); Start here goes to /start, the portal
itself. The page (static/showcase.js, shared with SteadyMove and Katha) only draws the chip; an old /#/... link (invite,
reset) that lands on / is sent on to /start by the page before anything loads.
2026-10-05 owner: a returning visitor skips it - a browser that has signed in here before (core.auth.known) opens / on
sign-in (chip showcase.settings returning_skip); the landing stays at /showcase and is linked from the sign-in pitch.

app.py calls install(app, page=..., ui_sizes=..., named=...) with its own page builder, HTML spacing and download-name
helper - the only three things the landing borrows from the host."""
from __future__ import annotations

import html as _html
import re
from pathlib import Path

from fastapi import HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse

import edition
from core import auth, demo, engine

ROOT = Path(__file__).resolve().parent
BASE = auth.BASE


def ranged(request: Request, path: Path, media_type: str, name: str, named, download: bool = False) -> Response:
    """Serve a file with byte-range support, always under its asset's `name` (+ the file's extension).

    Starlette's FileResponse sends the whole file and ignores `Range`, which is fine for a download
    and useless for a <video>: the browser cannot seek, and Safari refuses to play at all. Video is
    the reason this exists, so video is what it has to do properly."""
    size = path.stat().st_size
    head = {"Accept-Ranges": "bytes"} | named(name, path.suffix, inline=not download)
    raw = request.headers.get("range", "")
    m = re.match(r"bytes=(\d*)-(\d*)$", raw.strip()) if raw else None
    if not m:
        return FileResponse(str(path), media_type=media_type, headers=head)

    start = int(m.group(1)) if m.group(1) else None
    end = int(m.group(2)) if m.group(2) else None
    if start is None:                       # "bytes=-500" — the last 500 bytes
        length = min(end or 0, size)
        start, end = size - length, size - 1
    else:
        end = min(end if end is not None else size - 1, size - 1)
    if start > end or start >= size:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})

    def chunks():
        with path.open("rb") as fh:
            fh.seek(start)
            left = end - start + 1
            while left > 0:
                block = fh.read(min(1024 * 256, left))
                if not block:
                    break
                left -= len(block)
                yield block

    head["Content-Range"] = f"bytes {start}-{end}/{size}"
    return StreamingResponse(chunks(), status_code=206, media_type=media_type,
                             headers=head | {"Content-Length": str(end - start + 1)})


def chip_for(request: Request) -> str:
    """The words chip of THIS site's showcase ("" = this site has none)."""
    door = (edition.door(request.headers.get("host") or "") or {}).get("product_name", "")
    ed = edition.current()["id"]
    return next((r["page"] for r in engine.run("showcase.settings")["sites"] if r["edition"] == ed and r["door"] == door), "")


def lands_on_showcase(request: Request, signed_in: bool) -> bool:
    """/ shows the showcase to a visitor: not signed in, and (when returning_skip) not a browser that signed in here before."""
    if signed_in or demo.ON or not chip_for(request):   # a demo copy's pitch is the demo hub: its links go straight in
        return False
    return not (engine.run("showcase.settings").get("returning_skip") and auth.known(request))


def bootstrap_extra(request: Request, _u) -> dict:
    """The sign-in pitch links to the showcase only where this site has one."""
    return {"showcase": bool(chip_for(request))}


def install(app, *, page, ui_sizes, named) -> None:
    auth.BOOTSTRAP_EXTRAS.append(bootstrap_extra)

    @app.get("/showcase", response_class=HTMLResponse)
    def showcase_page(request: Request):
        chip = chip_for(request)
        if not chip:
            raise HTTPException(404)
        d = engine.run(chip)                                   # the tab, the search result and the share card: this site's words
        html = ui_sizes((ROOT / "static" / "showcase.html").read_text(encoding="utf-8")).replace("{{title}}", _html.escape(d["meta"]["title"])).replace(
            "{{description}}", _html.escape(d["meta"]["description"])).replace("{{brand}}", _html.escape(d["nav"]["brand"]))
        return HTMLResponse(html.replace('"static/', f'"{BASE}/static/').replace('"core-static/', f'"{BASE}/core-static/'))

    @app.get("/api/showcase")
    def showcase_words(request: Request):
        if not chip_for(request):
            raise HTTPException(404)
        return engine.run(chip_for(request))

    @app.get("/showcase/media/{name}")
    def showcase_media(name: str, request: Request):
        """A part's film (seekable - ranged), poster or captions: only names THIS site's chapters own."""
        chip = chip_for(request)
        stem, _, ext = name.rpartition(".")
        kinds = {"mp4": "video/mp4", "jpg": "image/jpeg", "vtt": "text/vtt"}
        path = ROOT / "static" / "showcase" / name
        if not chip or ext not in kinds or stem not in {c["key"] for c in engine.run(chip)["chapters"]} or not path.is_file():
            raise HTTPException(404)
        return ranged(request, path, kinds[ext], stem, named)

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        if lands_on_showcase(request, bool(auth.current_user(request))):
            return showcase_page(request)
        return HTMLResponse(page(request.headers.get("host") or ""))

    @app.get("/start", response_class=HTMLResponse)
    def start_page(request: Request):
        """The portal itself (sign in / sign up / the screens) - where the showcase's Start here goes."""
        return HTMLResponse(page(request.headers.get("host") or ""))
