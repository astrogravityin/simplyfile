"""The site's face outside its own pages: the browser-tab icon and the card a shared link shows (2026-10-31 owner).

WhatsApp, Telegram, LinkedIn and Google run no script, so all of this must be in the served head. Every page's head comes
through head() (app.py _ui_sizes); chip share.card holds the words and the file names; the pictures are made from the
portal's one mark by .agents/skills/domain-portal/make_share_assets.py. The screens' own logo reads the tab icon, so one
file draws them all. `python -m core.linkcard` fails a portal whose card or icon is missing, blank or the wrong size."""
from __future__ import annotations

import html
import json
import re
import struct
from pathlib import Path

from core import engine

ROOT = Path(__file__).resolve().parent.parent
ICON_TAG = re.compile(r'\s*<link rel="icon" href="[^"]*"[^>]*>')
CARD_SIZE = (1200, 630)
CARD_MAX_BYTES = 600 * 1024        # WhatsApp drops a heavier picture and shows the card bare


def head(page: str) -> str:
    """The page's head with the one icon and the full share card, in place of whatever icon the page carried."""
    c = engine.run("share.card")
    e = lambda s: html.escape(str(s), quote=True)  # noqa: E731
    base = c["url"].rstrip("/")
    tags = [f'<link rel="icon" type="image/svg+xml" href="{e(c["icon"])}"/>',
            f'<link rel="icon" type="image/png" sizes="192x192" href="{e(c["touch_icon"])}"/>',
            f'<link rel="apple-touch-icon" href="{e(c["touch_icon"])}"/>',
            f'<meta name="theme-color" content="{e(c["theme"])}"/>']
    if 'name="description"' not in page:
        tags.append(f'<meta name="description" content="{e(c["description"])}"/>')
    props = {"og:type": "website", "og:site_name": c["site_name"], "og:title": c["title"], "og:description": c["description"],
             "og:url": base + "/", "og:image": f'{base}/{c["image"]}', "og:image:width": CARD_SIZE[0],
             "og:image:height": CARD_SIZE[1], "og:image:alt": c["title"]}
    tags += [f'<meta property="{k}" content="{e(v)}"/>' for k, v in props.items()]
    tags += [f'<meta name="twitter:{k}" content="{e(v)}"/>' for k, v in
             {"card": "summary_large_image", "title": c["title"], "description": c["description"], "image": props["og:image"]}.items()]
    return ICON_TAG.sub("", page).replace("</head>", "".join(tags) + "</head>", 1)


def png_size(path: Path) -> tuple[int, int]:
    return struct.unpack(">II", path.read_bytes()[16:24])


def problems() -> list[str]:
    """Everything that would show a person a blank tab or a bare card."""
    c = engine.run("share.card")
    bad = [f"share.card {k} is empty" for k in ("title", "description", "site_name", "url", "icon", "touch_icon", "image", "theme") if not c[k]]
    if not c["url"].startswith("https://"):
        bad.append("share.card url must be the https:// address")
    site = ROOT / "valuestream.site.json"
    if site.is_file() and c["url"] != "https://" + json.loads(site.read_text(encoding="utf-8"))["host"]:
        bad.append("share.card url is not this site's host: a new portal copies the chip, then writes its own words and pictures")
    for k in ("icon", "touch_icon", "image"):
        if c[k] and not (ROOT / c[k]).is_file():
            bad.append(f"share.card {k}: {c[k]} is not here")
    card = ROOT / c["image"]
    if card.is_file():
        if png_size(card) != CARD_SIZE:
            bad.append(f"{c['image']} is {png_size(card)}, a share card is {CARD_SIZE}")
        if card.stat().st_size > CARD_MAX_BYTES:
            bad.append(f"{c['image']} is over {CARD_MAX_BYTES} bytes")
    touch = ROOT / c["touch_icon"]
    if touch.is_file() and png_size(touch) != (192, 192):
        bad.append(f"{c['touch_icon']} is {png_size(touch)}, not 192x192")
    return bad


if __name__ == "__main__":
    engine.register_dir(ROOT / "chips")
    assert not problems(), problems()
    sample = head('<head><title>x</title><link rel="icon" href="data:,"/>\n<link rel="icon" href="data:image/svg+xml,<svg></svg>"/></head>')
    assert "data:" not in sample, "no blank or typed tab icon survives"
    for tag in ('property="og:title"', 'property="og:image"', 'name="twitter:card"', 'rel="apple-touch-icon"', 'name="description"'):
        assert tag in sample, tag
    img = re.search(r'og:image" content="([^"]+)"', sample).group(1)
    assert img.startswith("https://"), "a link preview needs the picture's full address"
    print("linkcard OK")
