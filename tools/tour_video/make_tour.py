"""Tour Video from Guide me - one narrated screen-recording per page, rebuilt from the page's Guide me script.

ONE script, TWO outputs. A page's words and spotlights live in its Guide me script
(backend/data/guides/<portal>/<page>.json, format guide-me/1; skill guide-me-script) - the same script the
live "Guide me" button walks. This tool reads it (the studio's own folder first, else a workspace-<slug> folder) and
translates it at run time: a cover step (title + lede), then per step {chapter: title, say, do: [press `open`
when `target` is not on screen, spotlight `target`]} - both found exactly the way the kit finds them
(`|` alternatives, first on screen wins; `sel:has-text('X')` = the innermost `sel` showing X).

What a Guide me script has no word for - where recording starts, a demo chart to pick first, vars, signed out,
viewport, edge-tts voice, production host, blurred selectors - lives in ONE file, video_settings.json, keyed by
page key (`before` = demo actions run before step 1). It speaks each step (edge-tts, free neural voices),
drives the running portal with Playwright while recording, holds every step for as long as its narration
lasts, then muxes video + voice with ffmpeg and writes subtitles + YouTube chapters.

    pip install -r tools/tour_video/requirements.txt && python -m playwright install chromium
    python tools/tour_video/make_tour.py --login                 # once: sign in in the window, it saves + closes
    python tools/tour_video/make_tour.py tedbook --check         # walk the steps fast, no video/audio
    python tools/tour_video/make_tour.py tedbook                 # -> tmp/tour_video/tedbook/tedbook.mp4
    python tools/tour_video/make_tour.py tedbook --var book="Lean Startup"
    python tools/tour_video/make_tour.py tedbook --script x.json # the page's script from elsewhere (the DB copy)
    python tools/tour_video/make_tour.py tedbook --prod          # record the page's production site
    python tools/tour_video/make_tour.py --check-all [--prod]     # PASS/FAIL line per page
    python tools/tour_video/make_tour.py tv/docs/tour.json       # a raw {steps:[{say, do}]} tour (tv portal)

On a server (no screen) sign in with TOUR_USER / TOUR_PASSWORD in the environment: the form is
filled headless. Sessions are kept per site in one auth.json.

Output (tmp/, never committed): <key>.mp4, <key>.srt (upload as YouTube subtitles),
description.txt (title + chapter timestamps). Upload by hand, then paste the link in
Studio -> How to Use Config for that page key.

Credentials never touch this script: --login opens a real browser, the owner signs in, and only
the resulting session (tmp/tour_video/auth.json, gitignored) is reused.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = Path(__file__).resolve().parent
GUIDES = ROOT / "backend" / "data" / "guides"      # Guide me scripts: <portal with ':'->'-'>/<page>.json
SETTINGS = TOOL / "video_settings.json"            # video-only knobs per page key
OUT = ROOT / "tmp" / "tour_video"
AUTH = Path(os.environ["TOUR_AUTH"]) if os.environ.get("TOUR_AUTH") else OUT / "auth.json"   # 2026-10-11: a second session signs in to its own file
# Sign-in boxes on every portal: the studio names them username/password, this framework au-ident/au-pass;
# both carry the standard autocomplete words, so match either.
USER_BOX = "input[name=username], input[autocomplete=username] >> visible=true"
PASS_BOX = "input[name=password], input[autocomplete=current-password] >> visible=true"

ACTIONS = {"goto", "click", "fill", "select", "press", "hover", "highlight", "wait", "wait_for", "scroll", "scroll_to", "upload", "pick_chart",
           "click_target", "highlight_target"}   # *_target: a Guide me `open` / `target`, found as the kit finds it (FIND_JS)
ACTION_KEYS = ACTIONS | {"nth", "text", "value", "files", "frame", "optional", "timeout", "unless"}
DEMO = TOOL   # upload "files" are relative to tools/tour_video/


def upload_path(f: str) -> Path:
    """An upload file's path: under tools/tour_video/, or "@tmp/..." under the repo's gitignored tmp/ (2026-10-13: a real record
    for a private, masked recording stays out of the repo)."""
    return ROOT / "tmp" / f[5:] if f.startswith("@tmp/") else DEMO / f
STEP_KEYS = {"say", "speak", "chapter", "do", "hold", "picture"}
PICTURE = re.compile(r"^pictures/(?!\.\.?/)[\w.-]+/[0-9a-f]{8}\.(png|jpg)$")
TOUR_KEYS = {"page_key", "title", "start_url", "prod_base", "also", "anonymous", "review", "covers", "voice", "rate", "viewport", "vars", "steps", "note", "blur", "settle_ms", "type_emails", "locale", "tags", "mask", "mask_words"}
SETTING_KEYS = {"start_url", "anonymous", "vars", "before", "viewport", "voice", "rate", "prod_base", "blur", "note", "product", "settle_ms", "mask"}
PROD_BASE = "https://astrostage.in"   # a tour on another production host (tedbook.in) says so in prod_base

# Headless video has no mouse pointer - draw one, plus a ring on whatever the tour touches.
CURSOR_JS = """
(() => { if (window.__tourCursor) return; window.__tourCursor = 1;
  const add = () => { if (!document.body) return setTimeout(add, 50);
    const d = document.createElement('div'); d.id = '__tour_cursor';
    d.style.cssText = 'position:fixed;z-index:2147483647;width:18px;height:18px;margin:-9px 0 0 -9px;border-radius:50%;background:rgba(239,68,68,.55);border:2px solid #fff;box-shadow:0 0 0 1px rgba(0,0,0,.35);pointer-events:none;transition:left .25s,top .25s;left:-50px;top:-50px';
    document.body.appendChild(d);
    addEventListener('mousemove', e => { d.style.left = e.clientX + 'px'; d.style.top = e.clientY + 'px'; }, true);
  }; add();
  window.__tourFlash = el => { const o = el.style.outline, f = el.style.outlineOffset;
    el.style.outline = '3px solid #f59e0b'; el.style.outlineOffset = '2px';
    setTimeout(() => { el.style.outline = o; el.style.outlineOffset = f; }, 1400); };
})();
"""


# A demo account still has a real address, and a recording is forever. Any email that appears on
# screen is replaced with a placeholder while the tour runs - in text, in an input's value and in a
# placeholder - so nobody's inbox ends up in a published video. Nothing on the server changes; this
# lives in the page for the length of the recording only.
def blur_js(selectors: list[str]) -> str:
    """A tour's `blur` list: those elements are blurred for the length of the recording (the owner's name, the
    titles of their own recordings). Page-only, like MASK_JS - nothing on the server changes."""
    css = ",".join(selectors) + "{filter:blur(7px)!important}"
    return ("(() => { const add = () => { const s = document.createElement('style'); s.textContent = %s;"
            " document.head.appendChild(s); };"
            " document.readyState === 'loading' ? addEventListener('DOMContentLoaded', add) : add(); })();" % json.dumps(css))


def mask_config(tour: dict) -> dict | None:
    """2026-10-13 privacy mask: None when off. On with env TOUR_MASK=1 or a tour's "mask": true. What is blurred is chip tour.mask
    (patterns, selectors) plus every word of the JSON list file named by env TOUR_MASK_WORDS (a real record's holder and
    counterparty names, written at record time under tmp/ - never kept in the repo) and the tour's own "mask_words"."""
    if not (os.environ.get("TOUR_MASK") == "1" or tour.get("mask")):
        return None
    chip = json.loads((ROOT / "chips" / "tour.mask.json").read_text(encoding="utf-8"))
    cfg = {p["name"]: p["default"] for p in chip["params"]}
    words = list(tour.get("mask_words") or [])
    f = os.environ.get("TOUR_MASK_WORDS")
    if f and Path(f).is_file():
        words += json.loads(Path(f).read_text(encoding="utf-8"))
    mw = int(cfg["min_word"])
    cfg["words"] = sorted({w for w in (str(x).strip() for x in words) if len(w) >= mw}, key=len, reverse=True)
    return cfg


def mask_js(cfg: dict) -> str:
    """The recorder's privacy mask, in the page for the length of the recording (nothing on the server changes): text that matches a
    pattern or a word, and elements that match a selector, are blurred by a MutationObserver - before the next frame is painted -
    and window.__tourAudit() lists anything still readable (a leak), which a recording refuses."""
    return r"""
(() => { if (window.__tourMaskOn) return; window.__tourMaskOn = 1;
  const C = %s;
  const esc = (w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const parts = C.patterns.map((p) => p.regex).concat(C.words.length ? ['(?<![A-Za-z])(?:' + C.words.map(esc).join('|') + ')(?![A-Za-z])'] : []);
  const RX = () => new RegExp(parts.join('|'), 'gi');
  const css = document.createElement('style');
  css.textContent = '.__tourmask{filter:blur(' + C.blur_px + 'px)!important}' + C.selectors.join(',') + '{filter:blur(' + C.blur_px + 'px)!important}';
  const skip = (n) => { for (let e = n.parentElement; e; e = e.parentElement) { if (/^(SCRIPT|STYLE|TEXTAREA)$/.test(e.tagName) || e.classList.contains('__tourmask')) return true; } return false; };
  const pass = () => {
    if (!document.body) return;
    const it = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const hit = [];
    for (let n = it.nextNode(); n; n = it.nextNode()) { if (n.nodeValue && !skip(n) && RX().test(n.nodeValue)) hit.push(n); }
    for (const n of hit) {
      const text = n.nodeValue; const re = RX(); let last = 0; const frag = document.createDocumentFragment();
      for (let m = re.exec(text); m; m = re.exec(text)) {
        if (!m[0]) { re.lastIndex++; continue; }
        frag.append(text.slice(last, m.index));
        const sp = document.createElement('span'); sp.className = '__tourmask'; sp.textContent = m[0]; frag.append(sp); last = m.index + m[0].length;
      }
      frag.append(text.slice(last));
      n.replaceWith(frag);
    }
    for (const el of document.querySelectorAll('input,textarea,select')) {
      const v = el.tagName === 'SELECT' ? (el.selectedOptions[0] ? el.selectedOptions[0].textContent : '') : el.value;
      const ph = el.getAttribute('placeholder') || '';
      if ((v && RX().test(v)) || (ph && RX().test(ph))) el.classList.add('__tourmask');
    }
  };
  let queued = false;
  const later = () => { if (queued) return; queued = true; queueMicrotask(() => { queued = false; pass(); }); };
  const start = () => { document.head.appendChild(css); pass(); new MutationObserver(later).observe(document.documentElement, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ['value'] }); setInterval(pass, C.scan_ms || 250); };
  document.readyState === 'loading' ? addEventListener('DOMContentLoaded', start) : start();
  window.__tourAudit = () => {
    pass();
    const it = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); const bad = [];
    for (let n = it.nextNode(); n; n = it.nextNode()) { if (n.nodeValue && !skip(n) && RX().test(n.nodeValue)) bad.push('text'); }
    const inSel = C.selectors.length ? [...document.querySelectorAll(C.selectors.join(','))] : [];
    const unblurred = inSel.filter((e) => getComputedStyle(e).filter === 'none').length;
    for (let i = 0; i < unblurred; i++) bad.push('selector');
    return bad;
  };
})();
""" % json.dumps(cfg)


MASK_JS = r"""
(() => { if (window.__tourMask) return; window.__tourMask = 1;
  // 2026-10-16 (CodyFy demo): polled every 400 ms only, so a real address showed for 3 frames after Refresh. Now a
  // MutationObserver fixes every change before the next paint (its callback is a microtask, run before rendering) and the
  // interval stays as a back-stop (an input's value changes without a mutation). A value is written only when it changes -
  // SAFE maps to itself - so the observer never feeds itself. A fresh /g regex per string (no lastIndex carried over).
  const EMAIL = '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}';   // '\\.' in this JS string = a literal dot
  const SAFE = 'name@example.com';
  const fix = (t) => t.replace(new RegExp(EMAIL, 'g'), SAFE);
  const walk = () => {
    if (!document.body) return;
    const it = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n = it.nextNode(); n; n = it.nextNode()) {
      if (n.nodeValue) { const v = fix(n.nodeValue); if (v !== n.nodeValue) n.nodeValue = v; }
    }
    for (const el of document.querySelectorAll('input,textarea')) {
      if (window.__tourKeepInputs) break;   // a tour that types made-up emails (type_emails) must save what it typed
      if (el.value) { const v = fix(el.value); if (v !== el.value) el.value = v; }
      const ph = el.getAttribute('placeholder');
      if (ph && !/example\.com$/.test(ph)) { const v = fix(ph); if (v !== ph) el.setAttribute('placeholder', v); }
    }
  };
  new MutationObserver(walk).observe(document, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ['placeholder', 'value'] });
  const start = () => { walk(); setInterval(walk, 400); };
  document.readyState === 'loading' ? addEventListener('DOMContentLoaded', start) : start();
})();
"""


MASK_PROBE = r"""async () => {
  const el = document.createElement('p'); el.id = 'probe';
  document.body.append(el);
  el.textContent = 'machine account real.person@gmail.com';     // inserted the way a Refresh draws a row
  const seenInFrame = await new Promise((ok) => requestAnimationFrame(() => ok(document.getElementById('probe').textContent)));
  el.firstChild.nodeValue = 'changed to other.one@company.in';  // a text node changed in place
  await Promise.resolve();
  const seenAfterChange = el.textContent;
  return { seenInFrame, seenAfterChange };
}"""


def mask_probe() -> list[str]:
    """2026-10-16 guard (CodyFy demo: a real address showed for 3 frames after Refresh - MASK_JS only polled every 400 ms): in
    a real browser an email inserted or changed by the page is masked in the SAME frame (before the next paint). [] = OK; a
    missing Playwright / Chromium is said, never passed silently."""
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
    except ImportError:
        return ["playwright is not installed - pip install -r tools/tour_video/requirements.txt"]
    bad: list[str] = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        try:
            page = b.new_page()
            page.add_init_script(MASK_JS)
            page.route("http://mask-probe.test/", lambda r: r.fulfill(content_type="text/html", body="<html><body><main>start</main></body></html>"))
            page.goto("http://mask-probe.test/")          # a real navigation: init scripts run as in a recording
            got = page.evaluate(MASK_PROBE)
            for k, v in got.items():
                if "@gmail.com" in v or "@company.in" in v:
                    bad.append(f"{k}: a real email painted: {v}")
            page.wait_for_timeout(300)                    # the observer must not feed itself (a page that hangs fails here)
            if page.evaluate("() => 1") != 1:
                bad.append("the page hung")
        finally:
            b.close()
    return bad


def video_settings() -> dict:
    return json.loads(SETTINGS.read_text(encoding="utf-8"))


def guide_path(key: str) -> Path | None:
    """The page's Guide me seed: backend/data/guides/astrostage/<key>.json first, else a workspace's."""
    if not re.match(r"^[A-Za-z0-9][\w.-]{0,80}$", key or ""):
        return None
    for p in [GUIDES / "astrostage" / f"{key}.json", *sorted(GUIDES.glob(f"workspace-*/{key}.json"))]:
        if p.is_file():
            return p
    return None


def guide_portal(key: str) -> str | None:
    """The portal a page's Guide me lives on ('astrostage' or 'workspace:<slug>'), from its folder."""
    p = guide_path(key)
    return p.parent.name.replace("workspace-", "workspace:", 1) if p else None


def pages() -> list[str]:
    """Page keys a video can be made for: a Guide me script AND a row in video_settings.json."""
    return sorted(k for k in video_settings().get("pages", {}) if guide_path(k))


def settings_for(key: str) -> dict:
    vs = video_settings()
    row = vs.get("pages", {}).get(key)
    if row is None:
        raise SystemExit(f"no video settings for '{key}' - add it to tools/tour_video/video_settings.json (start_url at least)")
    return {**vs.get("defaults", {}), **row}


def validate_settings(key: str, st: dict) -> list[str]:
    """Structural errors in one page's video settings (empty = valid): known keys, a start_url, valid `before` actions."""
    err = [f"{key}: unknown video setting '{k}'" for k in st if k not in SETTING_KEYS]
    if not isinstance(st.get("start_url"), str) or not st["start_url"].strip():
        err.append(f"{key}: 'start_url' must be a non-empty string")
    probe = {"page_key": key, "title": key, "start_url": "/", "steps": [{"chapter": "x", "say": "x", "do": st.get("before", [])}]}
    err += [f"{key}: before {e.split(' ', 2)[-1]}" for e in validate_tour(probe)]
    return err


def from_guide(key: str, script: dict, st: dict) -> dict:
    """Guide me script (+ video settings) -> a tour of {chapter, say, do}. Cover = title + lede; each step
    presses `open` only when `target` is not on screen (as the kit does), then spotlights `target`.
    `before` (demo chart, demo files) runs at the very start, inside the first step."""
    product = str(st.get("product") or "AstroStage")
    sub = lambda t: str(t or "").replace("{product}", product)  # noqa: E731
    before = list(st.get("before", []))
    steps: list[dict] = []
    if script.get("lede"):
        steps.append({"chapter": sub(script.get("title") or key), "say": sub(script["lede"]), "do": before})
        before = []
    for s in script.get("steps") or []:
        if not isinstance(s, dict) or not str(s.get("say") or "").strip():
            continue
        do, before = before, []
        if s.get("open"):
            do.append({"click_target": s["open"], "unless": s.get("target", ""), "optional": True, "timeout": 5})
        if s.get("target"):
            do.append({"highlight_target": s["target"], "optional": True, "timeout": 5})
        steps.append({**({"chapter": sub(s["title"])} if s.get("title") else {}), "say": sub(s["say"]), "do": do})
    tour = {"page_key": key, "title": sub(script.get("title") or key), "start_url": st.get("start_url", ""), "steps": steps}
    for k in ("anonymous", "vars", "prod_base", "blur", "note", "rate", "voice", "viewport", "settle_ms"):
        if k in st:
            tour[k] = st[k]
    return tour


def load_path(ref: str) -> Path:
    return Path(ref) if ref.endswith(".json") else (guide_path(ref) or GUIDES / "astrostage" / f"{ref}.json")


def portal_product() -> str:
    """The product's one name as the portal's engine fills {product}: chip edition.settings of the repo this tool sits in
    (its PORTAL_EDITION, else default_edition). "" when the repo has no such chip."""
    try:
        c = json.loads((ROOT / "chips" / "edition.settings.json").read_text(encoding="utf-8"))
        d = {x["name"]: x["default"] for x in c["params"]}
        want = (os.getenv("PORTAL_EDITION") or d["default_edition"]).strip().lower()
        return next(str(r["product_name"]) for r in d["rows"] if r["id"] == want)
    except (OSError, ValueError, KeyError, TypeError, StopIteration):
        return ""


def named_tour(t: dict) -> dict:
    """2026-10-10: a raw tour (tours/<key>.json, made from a Guide me chip) says {product} - the voice read it out as "product"
    and the subtitles showed the braces. Its title, chapters and words get the portal's name (the tour's own `product`
    first); selectors and actions are left alone."""
    name = str(t.get("product") or portal_product() or video_settings().get("defaults", {}).get("product") or "")
    if not name:
        return t
    sub = lambda v: v.replace("{product}", name) if isinstance(v, str) else v  # noqa: E731
    out = dict(t, title=sub(t.get("title")))
    out["steps"] = [dict(s, **{k: sub(s[k]) for k in ("chapter", "say", "speak") if k in s}) for s in t.get("steps") or []]
    return out


def load_tour(ref: str, script: Path | None = None) -> dict:
    """A page key -> its Guide me script translated (`script` = another copy of it, e.g. the DB's).
    A path to a .json -> a raw {steps:[{say, do}]} tour, as-is (the tv portal's tv/docs/tour.json) - {product} filled."""
    if ref.endswith(".json"):
        return named_tour(json.loads(Path(ref).read_text(encoding="utf-8")))
    src = script or guide_path(ref)
    if not src or not src.is_file():
        raise SystemExit(f"no Guide me script for '{ref}' - write backend/data/guides/<portal>/{ref}.json (skill guide-me-script)")
    st = settings_for(ref)
    errs = validate_settings(ref, st)
    if errs:
        raise SystemExit("invalid video settings:\n  " + "\n  ".join(errs))
    return from_guide(ref, json.loads(src.read_text(encoding="utf-8")), st)


def validate_tour(t: dict) -> list[str]:
    """Structural errors in a tour (empty = valid). Shared with backend/tests/test_tour_coverage.py."""
    err = [f"unknown tour key '{k}'" for k in t if k not in TOUR_KEYS]
    for k in ("page_key", "title", "start_url"):
        if not isinstance(t.get(k), str) or not t[k].strip():
            err.append(f"'{k}' must be a non-empty string")
    steps = t.get("steps")
    if not isinstance(steps, list) or not steps:
        return err + ["'steps' must be a non-empty list"]
    # 2026-10-07 owner: every video carries several tags - the words people search a Watch section by (as the studio's make_tour)
    if "tags" in t and not (isinstance(t["tags"], list) and len({str(x).strip().lower() for x in t["tags"] if isinstance(x, str) and x.strip()}) >= 3):
        err.append("'tags' must list at least 3 different words people would search for")
    if "also" in t and not (isinstance(t["also"], list) and all(isinstance(x, str) for x in t["also"])):
        err.append("'also' must be a list of page keys this tour also covers")
    if "covers" in t and not (isinstance(t["covers"], list) and all(isinstance(x, str) and x.strip() for x in t["covers"])):
        err.append("'covers' must be a list of the module's features this video shows")
    if not steps[0].get("chapter"):
        err.append("step 1 needs a 'chapter' (YouTube chapters must start at 00:00)")
    for i, s in enumerate(steps, 1):
        err += [f"step {i}: unknown key '{k}'" for k in s if k not in STEP_KEYS]
        if not isinstance(s.get("say"), str) or not s["say"].strip():
            err.append(f"step {i}: 'say' is required")
        if "picture" in s and not (isinstance(s["picture"], str) and PICTURE.match(s["picture"]) and (DEMO / s["picture"]).is_file()):
            err.append(f"step {i}: picture must be an existing file under tools/tour_video/pictures/")
        for j, a in enumerate(s.get("do", []), 1):
            verbs = [k for k in a if k in ACTIONS]
            if len(verbs) != 1:
                err.append(f"step {i} action {j}: exactly one of {sorted(ACTIONS)} required, got {verbs}")
            err += [f"step {i} action {j}: unknown key '{k}'" for k in a if k not in ACTION_KEYS]
            if "fill" in a and "text" not in a:
                err.append(f"step {i} action {j}: 'fill' needs 'text'")
            if "select" in a and "value" not in a:
                err.append(f"step {i} action {j}: 'select' needs 'value'")
            if "upload" in a:
                files = a.get("files")
                if not (isinstance(files, list) and files and all(isinstance(f, str) for f in files)):
                    err.append(f"step {i} action {j}: 'upload' needs 'files', a list of paths under tools/tour_video/")
                elif any(".." in f or not upload_path(f).is_file() for f in files):
                    err.append(f"step {i} action {j}: upload file missing or outside tools/tour_video/: {files}")
    return err


def subst(obj, vars_: dict):
    if isinstance(obj, str):
        return re.sub(r"\$\{(\w+)\}", lambda m: str(vars_.get(m.group(1), m.group(0))), obj)
    if isinstance(obj, list):
        return [subst(x, vars_) for x in obj]
    if isinstance(obj, dict):
        return {k: subst(v, vars_) for k, v in obj.items()}
    return obj


def voice_ids() -> set[str]:
    return {v["id"] for v in json.loads((TOOL / "_voices.json").read_text(encoding="utf-8"))["voices"]}


def spoken(text: str) -> str:
    """Apply _lexicon.json so the voice says 'Ted Book', not 'tedbook'."""
    lex = json.loads((TOOL / "_lexicon.json").read_text(encoding="utf-8"))["say_as"]
    for word, say in lex.items():
        text = re.sub(rf"(?<!\w){re.escape(word)}(?!\w)", say, text)   # not \b: "139(5)" ends in ")"
    return text


def ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def duration(path: Path) -> float:
    r = subprocess.run([ffmpeg(), "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    if not m:
        raise RuntimeError(f"could not read duration of {path}")
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])


async def synth(tour: dict, out: Path) -> list[float]:
    import edge_tts
    (out / "audio").mkdir(parents=True, exist_ok=True)
    durs = []
    for i, s in enumerate(tour["steps"]):
        mp3 = out / "audio" / f"{i:02d}.mp3"
        await edge_tts.Communicate(spoken(s.get("speak") or s["say"]), tour.get("voice", "en-IN-NeerjaNeural"),
                                   rate=tour.get("rate", "+0%")).save(str(mp3))
        durs.append(duration(mp3))
    return durs


def target(page, a: dict):
    """Page or the first (possibly nested) frame whose URL contains a['frame']."""
    if not a.get("frame"):
        return page
    deadline = time.monotonic() + a.get("timeout", 15)
    while time.monotonic() < deadline:
        for f in page.frames:
            if a["frame"] in f.url:
                return f
        page.wait_for_timeout(250)
    raise RuntimeError(f"no frame with URL containing '{a['frame']}'")


# A Guide me `target` / `open`, found EXACTLY as the kit finds it (src/vendor/guideKit/guide-kit.js findTarget):
# `|` alternatives, the first on screen wins; `sel:has-text('X')` = the innermost `sel` whose text holds X
# (never <html> or a page-wide wrapper); inside an open dialog its own parts win. The hit is tagged so
# Playwright can hover, flash and click it. Change findTarget in the kit -> change this in the same change.
FIND_JS = """(alts) => {
  document.querySelectorAll('[data-tour-hit]').forEach((e) => e.removeAttribute('data-tour-hit'));
  const HAS = /^(.*?):has-text\\((['"])(.*?)\\2\\)\\s*$/;
  for (const sel of String(alts || '').split('|').map((x) => x.trim()).filter(Boolean)) {
    const m = HAS.exec(sel);
    let all = [];
    try { all = [...document.querySelectorAll(m ? (m[1] || '*') : sel)]; } catch (e) { continue; }
    if (m) {
      const hits = all.filter((el) => (el.textContent || '').includes(m[3]));
      all = hits.filter((el) => !hits.some((o) => o !== el && el.contains(o)));
    }
    const shown = all.filter((el) => el.getClientRects().length && !el.closest('.gd-card'));
    // a popup open over the page: its own parts win over look-alikes underneath (the topmost = the last open dialog)
    const dialogs = [...document.querySelectorAll('[role="dialog"],[aria-modal="true"],dialog[open]')]
      .filter((d) => !d.classList.contains('gd-card') && d.getClientRects().length);
    const top = dialogs[dialogs.length - 1];
    const el = (top && shown.find((x) => top.contains(x))) || shown[0];
    if (el) { el.setAttribute('data-tour-hit', '1'); return true; }
  }
  return false;
}"""


def find_target(t, alts: str, ms: float):
    """The element a Guide me selector list points at (polls up to ms), or None."""
    deadline = time.monotonic() + ms / 1000
    while True:
        if t.evaluate(FIND_JS, alts):
            return t.locator("[data-tour-hit]").first
        if time.monotonic() >= deadline:
            return None
        t.wait_for_timeout(200)


def run_action(page, base: str, a: dict) -> None:
    t = target(page, a)
    ms = a.get("timeout", 15) * 1000
    # Visible matches only: `.first` on a bare selector happily picks a hidden twin (a collapsed
    # header search, an off-screen form) and then waits 15 s for it to appear.
    loc = lambda sel: t.locator(f"{sel} >> visible=true").first  # noqa: E731
    if "goto" in a:
        page.goto(a["goto"] if a["goto"].startswith(("http", "data:")) else base + a["goto"], wait_until="domcontentloaded")
    elif "wait" in a:
        page.wait_for_timeout(float(a["wait"]) * 1000)
    elif "wait_for" in a:
        loc(a["wait_for"]).wait_for(state="visible", timeout=ms)
    elif "press" in a:
        page.keyboard.press(a["press"])
    elif "scroll" in a:
        # Wheel from the middle of the screen: the wheel scrolls whatever is under the pointer, and
        # after a click the pointer usually rests on a toolbar that does not scroll at all.
        vp = page.viewport_size or {"width": 1280, "height": 720}
        page.mouse.move(vp["width"] / 2, vp["height"] * 0.6)
        page.mouse.wheel(0, float(a["scroll"]))
    elif "pick_chart" in a:
        pick_chart(page, t, a["pick_chart"], int(a.get("nth", 0)), ms)
    elif "click_target" in a or "highlight_target" in a:
        verb = "click_target" if "click_target" in a else "highlight_target"
        if verb == "click_target" and a.get("unless") and find_target(t, a["unless"], 0):
            return                                   # the part is already on screen: nothing to open
        el = find_target(t, a[verb], ms)
        if el is None:
            raise RuntimeError(f"not on screen: {a[verb]}")
        el.scroll_into_view_if_needed(timeout=ms)
        el.hover(timeout=ms)
        el.evaluate("e => window.__tourFlash && window.__tourFlash(e)")
        page.wait_for_timeout(350)
        if verb == "click_target":
            el.click(timeout=ms)
    elif "upload" in a:   # demo birth files into a (usually hidden) <input type=file>: multi-chart screens
        t.locator(a["upload"]).first.set_input_files([str(upload_path(f)) for f in a["files"]], timeout=ms)
    else:
        verb = next(k for k in ("click", "fill", "select", "hover", "highlight", "scroll_to") if k in a)
        el = loc(a[verb])
        el.wait_for(state="visible", timeout=ms)
        el.scroll_into_view_if_needed(timeout=ms)
        el.hover(timeout=ms)                     # moves the drawn cursor there first
        el.evaluate("e => window.__tourFlash && window.__tourFlash(e)")
        page.wait_for_timeout(350)
        if verb == "click":
            el.click(timeout=ms)
        elif verb == "fill":
            if el.get_attribute("type") == "date":     # typed keys follow the browser's locale order; fill takes yyyy-mm-dd
                el.fill(a["text"])
                el.dispatch_event("change")
                return
            el.fill("")
            el.press_sequentially(a["text"], delay=45)   # visible typing, not a paste
        elif verb == "select":   # exact option value, else the first option whose text contains it
            v = el.evaluate("(e, v) => { const o = [...e.options]; const hit = o.find(x => x.value === v) || o.find(x => x.text.includes(v)); return hit ? hit.value : null; }", str(a["value"]))
            if v is None:
                raise RuntimeError(f"no option matching '{a['value']}'")
            el.select_option(v, timeout=ms)


_OPTION_JS = "(e, n) => { const o = [...e.options].find(x => x.text.toLowerCase().includes(n.toLowerCase())); return o ? o.value : null; }"


def pick_chart(page, t, name: str, nth: int, ms: float) -> None:
    """Choose a saved chart by name in whichever picker the screen uses (the nth one, for
    two-person screens): the shared SearchSelect, a native <select>, or a search box with a list."""
    def show(el):
        el.scroll_into_view_if_needed(timeout=ms)
        el.hover(timeout=ms)
        el.evaluate("e => window.__tourFlash && window.__tourFlash(e)")
        page.wait_for_timeout(350)

    deadline = time.monotonic() + ms / 1000
    while True:
        triggers = t.locator("button[data-search-select*='chart' i] >> visible=true")
        if triggers.count() > nth:                                          # SearchSelect
            trig = triggers.nth(nth)
            ph = trig.get_attribute("data-search-select") or ""
            show(trig)
            trig.click(timeout=ms)
            box = t.locator(f"input[placeholder={json.dumps(ph)}] >> visible=true").first
            box.press_sequentially(name, delay=45)
            opt = t.locator(f"button[title^={json.dumps(name)}] >> visible=true").first
            opt.wait_for(state="visible", timeout=ms)
            opt.click(timeout=ms)
            return
        selects = t.locator("select >> visible=true")
        hits = [selects.nth(i) for i in range(selects.count()) if selects.nth(i).evaluate(_OPTION_JS, name)]
        if len(hits) > nth:                                                # native <select>
            show(hits[nth])
            hits[nth].select_option(hits[nth].evaluate(_OPTION_JS, name), timeout=ms)
            return
        boxes = t.locator("input[placeholder*='chart' i] >> visible=true")
        if boxes.count() > nth:                                            # search box + list
            box = boxes.nth(nth)
            show(box)
            box.fill("")
            box.press_sequentially(name, delay=45)
            opt = t.locator(f"button:has-text({json.dumps(name)}), [role=option]:has-text({json.dumps(name)}), li:has-text({json.dumps(name)})").locator("visible=true").first
            opt.wait_for(state="visible", timeout=ms)
            opt.click(timeout=ms)
            return
        if time.monotonic() > deadline:
            raise RuntimeError(f"no chart picker offering '{name}' (is the demo chart saved on this account?)")
        page.wait_for_timeout(500)


def evidence(page, out: Path) -> None:
    """What the browser saw when a step failed: tmp/tour_video/<key>/failed.png plus every frame URL
    in the log, so a broken selector is diagnosed from the picture, not guessed."""
    try:
        out.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(out / "failed.png"))
        print(f"  screenshot: {out / 'failed.png'}")
        for f in page.frames[1:]:
            print(f"  frame: {f.url[:160]}")
    except Exception:  # noqa: BLE001 - evidence must never mask the real failure
        pass


def show_picture(page, path: Path) -> None:
    """A step's own picture, full screen over the page while its sentence plays (a pasted screenshot,
    a diagram, a step the script cannot click to)."""
    import base64
    mime = "image/png" if path.suffix == ".png" else "image/jpeg"
    data = f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()
    page.evaluate("""(src) => {
      document.getElementById('__tour_picture')?.remove();
      const d = document.createElement('div'); d.id = '__tour_picture';
      d.style.cssText = 'position:fixed;inset:0;z-index:2147483646;background:#0f172a;display:flex;align-items:center;justify-content:center';
      const img = document.createElement('img'); img.src = src; img.style.cssText = 'max-width:100%;max-height:100%;object-fit:contain';
      d.appendChild(img); document.body.appendChild(d);
    }""", data)


def blocked(page, tour: dict) -> None:
    """Refuse to record a page that is not the screen: a sign-in form, or an access guard."""
    if not tour.get("anonymous"):
        # The app drops an expired token and falls back to a public landing page that may have no
        # password box at all (the studio's individual page), so ask the page itself whether it holds a token.
        has_token = page.evaluate("() => { try { return Object.keys(localStorage).some(k => k.endsWith('_token') && localStorage.getItem(k)); } catch (e) { return true; } }")
        # A portal that keeps its session in an httpOnly cookie (the Training & Video Portal) has
        # nothing in localStorage to find, and JavaScript cannot see the cookie either - ask the
        # browser context, which can. Without this every such tour "failed" while signed in.
        has_cookie = any(c.get("name", "").endswith(("_session", "_token")) and c.get("value")
                         for c in page.context.cookies())
        # 2026-11-11: an EXPIRED session cookie still has a value, so the check above passed, the page fell back to the
        # signed-out landing and the run said done. Ask the server: a portal whose bootstrap answers {"user": null} is
        # signed out whatever the cookies say. A site with no such route (404, or no "user" key) is not asked.
        signed_out = page.evaluate("""async (p) => { try { const r = await fetch(p, {credentials: 'include'}); if (!r.ok) return false;
            const d = await r.json(); return d && typeof d === 'object' && 'user' in d && !d.user; } catch (e) { return false; } }""",
                                   tour.get("signed_in_probe", "/api/bootstrap"))
        if not (has_token or has_cookie) or signed_out or page.locator(PASS_BOX).count():
            raise SystemExit("FAILED not signed in on this site - press Sign in again (the session has expired or belongs to another site)")
    guard = page.locator("[data-access-denied], [data-screen-blocked]").locator("visible=true")
    if guard.count():
        raise SystemExit("FAILED this account cannot open the screen: " + " ".join(guard.first.inner_text().split())[:160])


def walk(tour: dict, base: str, out: Path, durs: list[float] | None, headed: bool) -> list[tuple[float, float]]:
    """Drive the tour. With durs: record video and return (start, dur) per step. Without: --check."""
    from playwright.sync_api import sync_playwright
    vp = tour.get("viewport", {"width": 1280, "height": 720})
    record = durs is not None
    times = []
    (out / "failed.png").unlink(missing_ok=True)   # never show an old failure next to a new run
    if not record:
        shutil.rmtree(out / "shots", ignore_errors=True)   # a storyboard is always one run's pictures
        (out / "shots").mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not (headed and has_screen()), args=launch_args())
        # anonymous: the page as a signed-out visitor sees it (a landing page, a public FYI link).
        ctx = browser.new_context(viewport=vp, locale=tour.get("locale"), storage_state=str(AUTH) if AUTH.exists() and not tour.get("anonymous") else None,
                                  **({"record_video_dir": str(out / "raw"), "record_video_size": vp} if record else {}))
        if AUTH.exists() and not tour.get("anonymous"):
            ctx.add_init_script(session_storage_js(json.loads(AUTH.read_text(encoding="utf-8"))))
        ctx.add_init_script(CURSOR_JS)
        if tour.get("type_emails"):
            ctx.add_init_script("window.__tourKeepInputs = 1")
        ctx.add_init_script(MASK_JS)      # no real email address is ever recorded
        if tour.get("blur"):              # names, titles: anything personal the tour lists stays unreadable
            ctx.add_init_script(blur_js(tour["blur"]))
        mask = mask_config(tour)          # 2026-10-13: a real record on screen - patterns, selectors and names blurred, a leak fails the run
        if mask:
            ctx.add_init_script(mask_js(mask))
        page = ctx.new_page()
        t0 = time.monotonic()
        su = tour["start_url"]
        # A signed-in page keeps polling (badges, inbox), so "networkidle" can never come: wait for the page to load,
        # then give it a short quiet spell at most (video_settings.json defaults.settle_ms) (FYI and Book timed out at 30 s on goto, 2026-10-02).
        page.goto(su if su.startswith(("http", "data:")) else base + su, wait_until="load")
        with contextlib.suppress(Exception):
            page.wait_for_load_state("networkidle", timeout=int(tour.get("settle_ms") or 8000))
        page.wait_for_timeout(800)
        lead = time.monotonic() - t0                 # blank/loading frames, trimmed off later
        for i, s in enumerate(tour["steps"]):
            start = time.monotonic() - t0 - lead
            if s.get("picture"):
                show_picture(page, DEMO / s["picture"])
            for j, a in enumerate(s.get("do", []), 1):
                try:
                    run_action(page, base, a)
                except Exception as e:  # noqa: BLE001 - report which step broke, in tour terms
                    msg = f"step {i + 1} ('{s['say'][:50]}...') action {j} {json.dumps(a)}: {str(e).splitlines()[0]}"
                    if a.get("optional"):
                        print("  skipped optional -", msg.encode("ascii", "replace").decode())   # ASCII only: a Windows console dies on "−"
                        continue
                    evidence(page, out)
                    ctx.close(); browser.close()
                    raise SystemExit("FAILED " + msg)
            if i == 0:
                blocked(page, tour)
            if mask:
                page.wait_for_timeout(350)
                leaks = page.evaluate("() => window.__tourAudit ? window.__tourAudit() : ['no mask']")
                if leaks:
                    evidence(page, out)
                    ctx.close(); browser.close()
                    raise SystemExit(f"PRIVACY: step {i + 1} shows {len(leaks)} readable private value(s) ({sorted(set(leaks))}) - nothing was kept")
            if s.get("picture") and not record:
                page.wait_for_timeout(400)
            if not record:
                # Storyboard: what the screen shows at the end of each step, beside its narration on the
                # Tour Video page. This is how a script is reviewed against the picture, not guessed.
                page.wait_for_timeout(600)
                page.screenshot(path=str(out / "shots" / f"{i + 1:02d}.png"))
            if record:
                left = durs[i] + float(s.get("hold", 0.6)) - (time.monotonic() - t0 - lead - start)
                page.wait_for_timeout(max(0.0, left) * 1000)
                times.append((start, durs[i]))
            if s.get("picture"):
                page.evaluate("() => document.getElementById('__tour_picture')?.remove()")
            print(f"  ok step {i + 1}/{len(tour['steps'])}")
        video = page.video.path() if record else None
        ctx.close(); browser.close()
    if record:
        (out / "raw.webm").unlink(missing_ok=True)
        Path(video).replace(out / "raw.webm")
        times.append((lead, 0.0))                   # carried to mux() as the trim
    return times


def stamp(sec: float, srt: bool) -> str:
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s % 1) * 1000):03d}" if srt else f"{int(h * 60 + m):02d}:{int(s):02d}"


def mux(tour: dict, out: Path, times: list[tuple[float, float]]) -> Path:
    lead = times.pop()[0]
    key = tour["page_key"]
    cmd = [ffmpeg(), "-y", "-ss", f"{lead:.3f}", "-i", str(out / "raw.webm")]
    parts = []
    for i, (start, _) in enumerate(times):
        cmd += ["-i", str(out / "audio" / f"{i:02d}.mp3")]
        ms = int(start * 1000)
        parts.append(f"[{i + 1}:a]adelay={ms}|{ms}[a{i}]")
    graph = ";".join(parts) + ";" + "".join(f"[a{i}]" for i in range(len(times))) + f"amix=inputs={len(times)}:normalize=0[aout]"
    mp4 = out / f"{key}.mp4"
    cmd += ["-filter_complex", graph, "-map", "0:v", "-map", "[aout]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-crf", "20", "-preset", "veryfast", "-c:a", "aac", "-b:a", "160k", str(mp4)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("ffmpeg failed:\n" + r.stderr[-1500:])

    srt = [f"{i}\n{stamp(st, True)} --> {stamp(st + d, True)}\n{s['say']}\n" for i, ((st, d), s) in enumerate(zip(times, tour["steps"]), 1)]
    (out / f"{key}.srt").write_text("\n".join(srt), encoding="utf-8")
    chapters = [f"{'00:00' if i == 0 else stamp(st, False)} {s['chapter']}" for i, ((st, _), s) in enumerate(zip(times, tour["steps"])) if s.get("chapter")]
    (out / "description.txt").write_text(f"{tour['title']}\n\n" + "\n".join(chapters) + "\n", encoding="utf-8")
    return mp4


def revoice(tour: dict, out: Path) -> None:
    """2026-10-08 (owner: every -Fy name said as one word, "Tradify"): voice the steps again and lay them over the video
    already made - each step starts where its subtitle starts. A step whose new voice outruns its slot (the next step's
    start) stops the run: that tour needs a real re-record."""
    key = tour["page_key"]
    mp4, srt = out / f"{key}.mp4", out / f"{key}.srt"
    if not mp4.exists() or not srt.exists():
        raise SystemExit(f"{key}: no recorded video to revoice - record it first")
    starts = [int(h) * 3600 + int(m) * 60 + float(s.replace(",", "."))
              for h, m, s in re.findall(r"^(\d+):(\d+):([\d,.]+) -->", srt.read_text(encoding="utf-8"), re.M)]
    if len(starts) != len(tour["steps"]):
        raise SystemExit(f"{key}: the tour has {len(tour['steps'])} steps, the video {len(starts)} - re-record it")
    total = duration(mp4)
    durs = asyncio.run(synth(tour, out))
    for i, d in enumerate(durs):
        room = (starts[i + 1] if i + 1 < len(starts) else total) - starts[i]
        if d > room + 0.3:
            raise SystemExit(f"{key}: step {i + 1} now speaks {d:.1f}s in a {room:.1f}s slot - re-record this tour")
    tmp = out / f"{key}.revoiced.mp4"
    cmd = [ffmpeg(), "-y", "-i", str(mp4)]
    parts = []
    for i, st in enumerate(starts):
        cmd += ["-i", str(out / "audio" / f"{i:02d}.mp3")]
        parts.append(f"[{i + 1}:a]adelay={int(st * 1000)}|{int(st * 1000)}[a{i}]")
    graph = ";".join(parts) + ";" + "".join(f"[a{i}]" for i in range(len(starts))) + f"amix=inputs={len(starts)}:normalize=0[aout]"
    cmd += ["-filter_complex", graph, "-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", str(tmp)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("ffmpeg failed:\n" + r.stderr[-1500:])
    tmp.replace(mp4)
    # 2026-10-10: the words changed, so the subtitles and chapters say the new ones (the same start times)
    srt.write_text("\n".join(f"{i}\n{stamp(st, True)} --> {stamp(st + d, True)}\n{s['say']}\n"
                             for i, (st, d, s) in enumerate(zip(starts, durs, tour["steps"]), 1)), encoding="utf-8")
    chapters = [f"{'00:00' if i == 0 else stamp(st, False)} {s['chapter']}" for i, (st, s) in enumerate(zip(starts, tour["steps"])) if s.get("chapter")]
    (out / "description.txt").write_text(f"{tour['title']}\n\n" + "\n".join(chapters) + "\n", encoding="utf-8")
    print(f"revoiced: {mp4}")


def has_screen() -> bool:
    return os.name == "nt" or sys.platform == "darwin" or bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def launch_args() -> list[str]:
    """Chromium on a Linux server: tiny /dev/shm crashes pages, and root refuses the sandbox."""
    if os.name == "nt":
        return []
    return ["--disable-dev-shm-usage"] + (["--no-sandbox"] if hasattr(os, "geteuid") and os.geteuid() == 0 else [])


def _token_origins(state: dict) -> list[str]:
    # ponytail: any '*_token' in localStorage = signed in (a studio token, a family token...).
    out = [o["origin"] for o in state.get("origins", [])
           if any(i["name"].endswith("_token") and i["value"] for i in o.get("localStorage", []))]
    # A portal that keeps its session in an httpOnly cookie writes nothing to localStorage (the
    # Training & Video Portal's `tv_session`). Without this, --login waits until it times out and
    # saves no session at all, so every tour of that portal records the sign-in screen.
    out += [c.get("domain", "") for c in state.get("cookies", [])
            if c.get("name", "").endswith(("_session", "_token")) and c.get("value")]
    return sorted({o for o in out if o})


def _save_session(state: dict) -> None:
    """Merge into auth.json per site, so signing in to one site keeps another site's session."""
    OUT.mkdir(parents=True, exist_ok=True)
    old = json.loads(AUTH.read_text(encoding="utf-8")) if AUTH.exists() else {"cookies": [], "origins": []}
    mine = {o["origin"] for o in state.get("origins", [])}
    old["origins"] = [o for o in old.get("origins", []) if o["origin"] not in mine] + state.get("origins", [])
    # 2026-10-03: was `domain in origin` - "localhost" is inside "http://door.localhost:8820", so signing in to a door
    # threw away the main site's session. Then (same day) every cookie of the HOST went: signing in to the studio on
    # localhost:5174 wiped the main site's session cookie on localhost:8820 - cookies have no port. A new sign-in now replaces
    # only the cookies it sets itself (same host, name and path); every other site's stays.
    key = lambda c: (c.get("domain", "").lstrip("."), c.get("name", ""), c.get("path", "/"))   # noqa: E731
    fresh = {key(c) for c in state.get("cookies", [])}
    old["cookies"] = [c for c in old.get("cookies", []) if key(c) not in fresh] + state.get("cookies", [])
    old["session_storage"] = {**old.get("session_storage", {}), **state.get("session_storage", {})}
    AUTH.write_text(json.dumps(old), encoding="utf-8")


def session_storage_js(state: dict) -> str:
    """Playwright's storage_state keeps localStorage only. The app treats a tab with no per-tab session mark as a
    fresh browser and signs out any account not on the remember list, so every recording opened signed out
    (2026-10-02). Put back the tab's sessionStorage from sign-in, per origin, before the page's own code runs."""
    saved = json.dumps(state.get("session_storage") or {})
    return ("(() => { try { const s = " + saved + "[location.origin] || {};"
            " for (const k in s) if (sessionStorage.getItem(k) === null) sessionStorage.setItem(k, s[k]); } catch (e) {} })();")


def login(base: str) -> None:
    """Username + password in TOUR_USER / TOUR_PASSWORD (env, never argv): fills the sign-in form
    headless, which is what works on a server. Otherwise opens a window for the owner to sign in."""
    from playwright.sync_api import sync_playwright
    user, password = os.environ.get("TOUR_USER", ""), os.environ.get("TOUR_PASSWORD", "")
    auto = bool(user and password)
    if not auto and not has_screen():
        raise SystemExit("no screen on this machine - enter the demo account's username and password to sign in")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=auto, args=launch_args())
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(base, wait_until="domcontentloaded")
        if auto:
            print("signing in with the given account...", flush=True)
            try:
                # Signed out, the studio shows the public front door; the form sits behind its
                # "Sign up / Sign in" button. Brand hosts (tedbook.in, familyos.in) show the form at once.
                pw_box = page.locator(PASS_BOX)
                entry = page.locator("button:has-text('Sign in') >> visible=true")
                for i in range(30):
                    if pw_box.count() or entry.count() or page.locator("button:text-is('Password') >> visible=true").count():
                        break
                    start = page.locator("a[href$='start'] >> visible=true")   # a portal's landing page: its Start here opens the sign-in
                    if i == 4 and start.count():
                        start.first.click()
                    page.wait_for_timeout(500)
                if not pw_box.count() and entry.count():
                    entry.first.click()
                    page.wait_for_timeout(1000)
                tab = page.locator("button:text-is('Password') >> visible=true").first
                if tab.count():
                    tab.click()
                page.locator(USER_BOX).first.fill(user, timeout=20000)
                page.locator(PASS_BOX).first.fill(password)
                page.locator(PASS_BOX).first.press("Enter")
            except Exception as e:  # noqa: BLE001
                browser.close()
                raise SystemExit(f"could not find the sign-in form: {str(e).splitlines()[0]}")
        else:
            print("Sign in in the browser window. It closes by itself once you are signed in.", flush=True)
        deadline = time.monotonic() + (45 if auto else 900)
        while time.monotonic() < deadline and not page.is_closed():
            try:
                state = ctx.storage_state()
            except Exception:  # noqa: BLE001 - the window was closed by hand between two looks
                break
            if _token_origins(state):
                time.sleep(1.5)
                done = ctx.storage_state()
                done["session_storage"] = {page.evaluate("location.origin"): page.evaluate("({...sessionStorage})")}
                _save_session(done)
                browser.close()
                return print(f"signed in - session saved for {', '.join(_token_origins(state))}")
            time.sleep(1)
        browser.close()
    raise SystemExit("sign-in did not complete (wrong password, or the window was closed) - session not saved")


def check_all(base: str, prod: bool) -> None:
    """Walk every tour with its default vars; one PASS/FAIL line each. Stops nothing on a failure."""
    keys = pages()
    failed = []
    for n, key in enumerate(keys, 1):
        print(f"tour: {key} ...", flush=True)
        try:
            raw = load_tour(key)
            tour = subst(raw, raw.get("vars", {}))
            site = raw.get("prod_base", PROD_BASE) if prod else base
            with contextlib.redirect_stdout(io.StringIO()):
                walk(tour, site, OUT / key, None, False)
            print(f"PASS {n}/{len(keys)} {key}", flush=True)
        except (SystemExit, Exception) as e:  # noqa: BLE001 - one broken tour must not stop the sweep
            failed.append(key)
            print(f"FAIL {n}/{len(keys)} {key}: {str(e).splitlines()[0] if str(e) else type(e).__name__}", flush=True)
    print(f"check-all: {len(keys) - len(failed)} passed, {len(failed)} failed" + (f" ({', '.join(failed)})" if failed else ""))
    if failed:
        raise SystemExit(1)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tour", nargs="?", help="page key (its Guide me script + video_settings.json row) or a path to a raw tour .json")
    ap.add_argument("--script", help="read the page's Guide me script from this file (the server passes the DB copy)")
    ap.add_argument("--base", default="http://localhost:5174")
    ap.add_argument("--login", action="store_true", help="sign in by hand once; saves tmp/tour_video/auth.json")
    ap.add_argument("--check", action="store_true", help="walk the steps without recording or narration")
    ap.add_argument("--headed", action="store_true", help="show the browser while it runs")
    ap.add_argument("--var", action="append", default=[], help="override a tour var: name=value")
    ap.add_argument("--voice", help="narrator voice id from _voices.json (overrides the tour's own)")
    ap.add_argument("--check-all", action="store_true", help="walk every tour with default vars, PASS/FAIL per tour")
    ap.add_argument("--revoice", action="store_true", help="new narration over the recorded picture (a lexicon or wording change); no browser")
    ap.add_argument("--prod", action="store_true", help="use each tour's production site instead of --base")
    args = ap.parse_args()
    base = args.base.rstrip("/")
    if args.login:
        return login(base)
    if args.check_all:
        return check_all(base, args.prod)
    if not args.tour:
        ap.error("tour is required")
    raw = load_tour(args.tour, Path(args.script) if args.script else None)
    errs = validate_tour(raw)
    if errs:
        raise SystemExit("invalid tour:\n  " + "\n  ".join(errs))
    tour = subst(raw, {**raw.get("vars", {}), **dict(v.split("=", 1) for v in args.var)})
    if args.prod:
        base = raw.get("prod_base", PROD_BASE)
    if args.voice:
        if args.voice not in voice_ids():
            raise SystemExit(f"unknown voice '{args.voice}' - pick one from _voices.json")
        tour["voice"] = args.voice
    out = OUT / tour["page_key"]
    out.mkdir(parents=True, exist_ok=True)
    # First log line names the script, so a pasted log always says which tour it came from.
    print(f"tour: {tour['page_key']} ({args.script or load_path(args.tour)}) | site: {base} | voice: {tour.get('voice', 'en-IN-NeerjaNeural')} | {'check' if args.check else 'record'}", flush=True)
    if args.check:
        walk(tour, base, out, None, args.headed)
        return print("check passed - every step ran")
    if args.revoice:
        return revoice(tour, out)
    print("narrating...")
    durs = asyncio.run(synth(tour, out))
    print(f"recording ({sum(durs):.0f}s of narration)...")
    times = walk(tour, base, out, durs, args.headed)
    print("combining voice and video...", flush=True)
    mp4 = mux(tour, out, times)
    print(f"done: {mp4}\n      {out / (tour['page_key'] + '.srt')}\n      {out / 'description.txt'}")


if __name__ == "__main__":
    sys.exit(main())
