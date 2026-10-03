"""User Manual Builder — the page model, the HTML it renders to, and where a published one lives.

A manual is a cover page plus ordered pages (Header · Background · Picture · Picture Label ·
Description). One renderer produces all three outputs — the preview, the standalone .html file you
can hand out on a USB stick, and the public page at /m/<slug> — so they can never drift.

There is no external publishing site to configure: this portal serves the published manual itself,
read-only and without a login, at `/m/<slug>`. A manual page that names a screen also becomes a
"How to Use" link on that screen, deep-linked at its own section.

Every choice lives in chips (tv/chips): `manuals.allow_list` (which author HTML survives),
`manuals.settings` (background swatches, defaults, limits, slug rule, anchors, stylesheets),
`manuals.layout` (the HTML each part renders to) and `manuals.messages` (every word a reader sees).
This file holds the HTMLParser plumbing, the model and the storage.
"""
from __future__ import annotations

import html as _html
import re
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path

import store
from core import engine, ops

engine.register_dir(Path(__file__).resolve().parent / "chips")

_rx = lru_cache(maxsize=64)(re.compile)   # a pattern from a chip, compiled once


def __getattr__(name: str):
    """`manuals.BACKGROUNDS` still answers for callers written before the chips — read live from the chip."""
    if name == "BACKGROUNDS":
        return engine.setting("manuals.settings", "backgrounds")
    raise AttributeError(name)


def bg(key: str, swatches: list | None = None) -> dict:
    """Backgrounds are preset KEYS, never raw CSS — an author picks a swatch, not a stylesheet."""
    swatches = swatches if swatches is not None else engine.setting("manuals.settings", "backgrounds")
    return next((b for b in swatches if b["id"] == key), swatches[0])


def esc(v) -> str:
    return _html.escape(str(v if v is not None else ""), quote=True)


# --- the description is author HTML, so it is cleaned on the way into every output ---------------

class _Clean(HTMLParser):
    """Allow-list cleaner. Anything not on the list is dropped, tags and attributes alike.
    The lists and patterns are the chip `manuals.allow_list`."""

    def __init__(self, rules: dict):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.open: list[str] = []
        self.skip = 0          # inside <script>/<style>/…: the TEXT goes too, not just the tag
        self.tags, self.attrs = set(rules["allowed_tags"]), set(rules["allowed_attrs"])
        self.void, self.drop = set(rules["void_tags"]), set(rules["drop_content_tags"])
        self.url_attrs, self.style_attrs = set(rules["url_attrs"]), set(rules["style_attrs"])
        self.safe_url, self.safe_style = _rx(rules["safe_url"]), _rx(rules["safe_style"])
        self.style_banned = [w.lower() for w in rules["style_banned_words"]]
        # 2026-10-02 Articles: a tag may carry its own stricter URL rule (an <iframe> only from youtube.com/embed)
        self.tag_url = {t: _rx(r) for t, r in (rules.get("tag_safe_url") or {}).items()}
        self.tag = ""

    def _attrs(self, attrs):
        keep = []
        for name, value in attrs:
            name, value = (name or "").lower(), value or ""
            if name not in self.attrs:
                continue
            if name in self.url_attrs and not (self.tag_url.get(self.tag) or self.safe_url).search(value.strip()):
                continue
            if name in self.style_attrs and (not self.safe_style.search(value)
                                             or any(w in value.lower() for w in self.style_banned)):
                continue
            keep.append(f' {name}="{esc(value)}"')
        return "".join(keep)

    def handle_starttag(self, tag, attrs):
        self.tag = tag
        if tag in self.drop:
            self.skip += 1
            return
        if tag not in self.tags:
            return
        self.out.append(f"<{tag}{self._attrs(attrs)}" + (" />" if tag in self.void else ">"))
        if tag not in self.void:
            self.open.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.tag = tag
        if tag not in self.drop and tag in self.tags:
            self.out.append(f"<{tag}{self._attrs(attrs)} />")

    def handle_endtag(self, tag):
        if tag in self.drop:
            self.skip = max(0, self.skip - 1)
            return
        if tag in self.tags and tag not in self.void and tag in self.open:
            while self.open:
                last = self.open.pop()
                self.out.append(f"</{last}>")
                if last == tag:
                    break

    def handle_data(self, data):
        if not self.skip:
            self.out.append(_html.escape(data, quote=False))

    def result(self) -> str:
        while self.open:
            self.out.append(f"</{self.open.pop()}>")
        return "".join(self.out)


def clean_html(raw: str, rules: dict | None = None) -> str:
    c = _Clean(rules or engine.run("manuals.allow_list"))
    c.feed(str(raw or ""))
    c.close()
    return c.result().strip()


# --- the model ----------------------------------------------------------------------------------

def new_page(cfg: dict | None = None) -> dict:
    cfg = cfg or engine.run("manuals.settings")
    return {"id": store.new_id(), "header": "", "background": cfg["page_background"], "image": "",
            "image_label": "", "description": "", "screen_key": ""}


def empty_manual(cfg: dict | None = None) -> dict:
    cfg = cfg or engine.run("manuals.settings")
    return {"cover": {"title": "", "subtitle": "", "author": "", "version": cfg["cover_version"],
                      "date_stamp": store.now()[:10], "time_stamp": store.now()[11:16],
                      "image": "", "background": cfg["cover_background"]},
            "pages": [new_page(cfg)]}


def normalize(m: dict | None, cfg: dict | None = None) -> dict:
    cfg = cfg or engine.run("manuals.settings")
    base = empty_manual(cfg)
    m = m if isinstance(m, dict) else {}
    cover = base["cover"] | (m.get("cover") if isinstance(m.get("cover"), dict) else {})
    pages = [dict(new_page(cfg), **p) for p in (m.get("pages") or []) if isinstance(p, dict)]
    return {"cover": cover, "pages": pages or base["pages"]}


# --- rendering ----------------------------------------------------------------------------------

def _ctx() -> dict:
    """Everything one render needs, fetched once."""
    lib = engine.chips()
    return {"cfg": engine.run("manuals.settings", lib=lib), "layout": engine.run("manuals.layout", lib=lib),
            "say": engine.run("manuals.messages", lib=lib), "rules": engine.run("manuals.allow_list", lib=lib)}


def anchor(i: int, cfg: dict | None = None) -> str:
    """Derived from POSITION, so reordering renumbers the contents and its targets together."""
    cfg = cfg or engine.run("manuals.settings")
    return ops.template(cfg["page_anchor"], {"n": i + 1})


def _cover_html(c: dict, ctx: dict) -> str:
    L, say, s = ctx["layout"], ctx["say"], bg(c.get("background", ""), ctx["cfg"]["backgrounds"])
    swatch = {"css": s["css"], "fg": s["fg"], "muted": s["muted"]}
    out = [ops.template(L["cover_open"], swatch)]
    if c.get("image"):
        out.append(ops.template(L["cover_image"], {"src": esc(c["image"])}))
    out.append(ops.template(L["cover_title"], {"title": esc(c.get("title") or say["default_title"])}))
    for field in ("subtitle", "author", "version"):
        if c.get(field):
            out.append(ops.template(L[f"cover_{field}"], swatch | {field: esc(c[field])}))
    when = ctx["cfg"]["stamp_joiner"].join(x for x in (c.get("date_stamp"), c.get("time_stamp")) if x)
    if when:
        out.append(ops.template(L["cover_when"], swatch | {"when": esc(when)}))
    return "".join(out) + L["section_close"]


def _toc_html(m: dict, ctx: dict) -> str:
    L, say, cfg = ctx["layout"], ctx["say"], ctx["cfg"]
    s = bg(m["cover"].get("background", ""), cfg["backgrounds"])
    rows = "".join(
        ops.template(L["toc_row"], {"anchor": anchor(i, cfg), "n": i + 1, "muted": s["muted"],
                                    "header": esc(p.get("header") or say["untitled_page"])})
        for i, p in enumerate(m["pages"]))
    return ops.template(L["toc"], {"toc_anchor": cfg["toc_anchor"], "css": s["css"], "fg": s["fg"],
                                   "muted": s["muted"], "contents": say["contents"], "rows": rows})


def _page_html(p: dict, i: int, show_toc: bool = True, ctx: dict | None = None) -> str:
    ctx = ctx or _ctx()
    L, say, cfg = ctx["layout"], ctx["say"], ctx["cfg"]
    s = bg(p.get("background", ""), cfg["backgrounds"])
    swatch = {"css": s["css"], "fg": s["fg"], "muted": s["muted"]}
    toc_link = (ops.template(L["page_toc_link"], swatch | {"toc_anchor": cfg["toc_anchor"], "back": say["back_to_contents"]})
                if show_toc else "")
    out = [ops.template(L["page_open"], swatch | {
        "anchor": anchor(i, cfg), "page_label": ops.template(say["page_label"], {"n": i + 1}),
        "toc_link": toc_link, "header": esc(p.get("header") or say["untitled_page"])})]
    if p.get("image"):
        caption = (ops.template(L["page_caption"], swatch | {"label": esc(p["image_label"])})
                   if p.get("image_label") else "")
        out.append(ops.template(L["page_figure"], {"src": esc(p["image"]), "alt": esc(p.get("image_label")),
                                                   "caption": caption}))
    desc = clean_html(p.get("description", ""), ctx["rules"])
    if desc:
        out.append(ops.template(L["page_description"], {"html": desc}))
    return "".join(out) + L["section_close"]


def body_html(m: dict) -> str:
    ctx = _ctx()
    m = normalize(m, ctx["cfg"])
    pages = m["pages"]
    # One page is its own contents — a list of one helps nobody.
    many = len(pages) >= ctx["cfg"]["contents_min_pages"]
    return ops.template(ctx["layout"]["body"], {
        "css": ctx["cfg"]["body_css"], "cover": _cover_html(m["cover"], ctx),
        "toc": _toc_html(m, ctx) if many else "",
        "pages": "".join(_page_html(p, i, many, ctx) for i, p in enumerate(pages))})


def doc_html(m: dict) -> str:
    """A standalone file: no external stylesheet, font or script — it opens from a USB stick."""
    cfg, say, L = engine.run("manuals.settings"), engine.run("manuals.messages"), engine.run("manuals.layout")
    title = esc(normalize(m, cfg)["cover"].get("title") or say["default_title"])
    return ops.template(L["document"], {"title": title, "css": cfg["document_css"], "body": body_html(m)})


# --- storage ------------------------------------------------------------------------------------

def all_manuals() -> list[dict]:
    return store.read("manuals", [])


def rows_for(project_id: str = "", mine: callable | None = None) -> list[dict]:
    """`mine` decides which rows this person may see — see app.owns. Left out, every row is listed,
    which is only right for a caller that has already narrowed them."""
    seen = [m for m in all_manuals() if mine is None or mine(m)]
    rows = [{k: m.get(k) for k in ("id", "project_id", "title", "slug", "published", "updated_at", "updated_by")}
            | {"pages": len(m.get("manual", {}).get("pages", []))} for m in seen]
    rows = [r for r in rows if not project_id or r["project_id"] == project_id]
    return sorted(rows, key=lambda r: r.get("updated_at") or "", reverse=True)


def get(manual_id: str) -> dict | None:
    return next((m for m in all_manuals() if m["id"] == manual_id), None)


def by_slug(slug: str) -> dict | None:
    return next((m for m in all_manuals() if m.get("slug") == slug and m.get("published")), None)


def slugify(title: str, taken: set[str], cfg: dict | None = None) -> str:
    cfg = cfg or engine.run("manuals.settings")
    fallback = cfg["slug_fallback"]
    base = _rx(cfg["slug_unsafe"]).sub("-", (title or fallback).lower()).strip("-") or fallback
    slug, n = base, 2
    while slug in taken:
        slug, n = f"{base}-{n}", n + 1
    return slug


def save(manual_id: str | None, project_id: str, title: str, manual: dict, who: str,
         published: bool | None = None, owner_id: str = "") -> dict:
    cfg, say = engine.run("manuals.settings"), engine.run("manuals.messages")
    rows = all_manuals()
    row = next((m for m in rows if m["id"] == manual_id), None) if manual_id else None
    if row is None:
        row = {"id": store.new_id(), "project_id": project_id, "published": False, "slug": "",
               "owner_id": owner_id}
        rows.append(row)
    row["project_id"] = project_id or row.get("project_id", "")
    row["title"] = (title or manual.get("cover", {}).get("title") or say["untitled_manual"])[:cfg["max_title_length"]]
    row["manual"] = normalize(manual, cfg)
    row["updated_at"], row["updated_by"] = store.now(), who
    if published is not None:
        row["published"] = bool(published)
    if row["published"] and not row.get("slug"):
        row["slug"] = slugify(row["title"], {m.get("slug") for m in rows if m is not row}, cfg)
    store.write("manuals", rows)
    return row


def delete(manual_id: str) -> None:
    store.write("manuals", [m for m in all_manuals() if m["id"] != manual_id])


def help_targets(row: dict, base: str = "") -> list[dict]:
    """One How to Use link per manual page that names a screen, deep-linked at its own section.

    `base` is the portal's public address (Setup → Portal address). Leave it blank and the links are
    relative — right for a manual read inside this portal, wrong for an app on another domain that
    fetches them, which is exactly why Setup asks for it."""
    if not row.get("published") or not row.get("slug"):
        return []
    cfg, say = engine.run("manuals.settings"), engine.run("manuals.messages")
    base = (base or "").rstrip("/")
    out = []
    for i, p in enumerate(row["manual"]["pages"]):
        key = str(p.get("screen_key") or "").strip()
        if key:
            out.append({"screen_key": key,
                        "label": (ops.template(say["help_label_page"], {"header": p["header"]}) if p.get("header")
                                  else say["help_label"]),
                        "url": f'{base}/m/{row["slug"]}#{anchor(i, cfg)}', "type": cfg["help_link_type"],
                        "active": True, "manual_id": row["id"]})
    return out


if __name__ == "__main__":  # ponytail: one runnable self-check
    assert clean_html('<p onclick="x()">hi<script>bad()</script></p>') == "<p>hi</p>"
    assert clean_html('<a href="javascript:alert(1)">x</a>') == "<a>x</a>"
    assert clean_html('<a href="https://x.dev">x</a>') == '<a href="https://x.dev">x</a>'
    assert "<img" in clean_html('<img src="data:image/png;base64,AAA" />')
    assert clean_html('<p style="width:expression(alert(1))">x</p>') == "<p>x</p>", "IE expression() is not a style"
    m = normalize({"cover": {"title": "Guide"}, "pages": [{"header": "One"}, {"header": "Two"}]})
    body = body_html(m)
    assert "Contents" in body and 'id="mp-2"' in body and "Guide" in body
    assert "Contents" not in body_html(normalize({"pages": [{"header": "Only"}]})), "one page needs no contents"
    assert ".pg{padding:44px 48px" in body, "the stylesheet goes in whole, braces and all"
    assert doc_html(m).startswith("<!doctype html>\n<html") and "<title>Guide</title>" in doc_html(m)
    assert slugify("My Guide!", {"my-guide"}) == "my-guide-2"
    import sys
    assert sys.modules[__name__].BACKGROUNDS[0]["id"] == "white", "old callers still read manuals.BACKGROUNDS"
    print("manuals self-check OK")
