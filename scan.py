"""Setup → Scan: find the screens of ANY project folder, whatever it is written in.

The portal cannot know your framework, so it does not try to parse one. It walks the folder and
scores files against patterns that mean "a human looks at this": component files under
pages/screens/views/routes, files named …Page/…Screen/…View, HTML and server templates, and any
file that registers a route. Everything it finds is a CANDIDATE — you tick, rename and delete in
the Setup grid, and what you save becomes the screen list the other three modules use.

A project can skip the guessing entirely by dropping a `screens.json` in its root:
    {"screens": [{"key": "my-screen", "label": "My Screen", "route": "/my"}]}
That file wins outright.

Every judgement lives in chips (tv/chips): `scan.settings` (which extensions, folders and limits count),
`scan.patterns` (route, name, skip and title patterns, in order), `scan.is_likely` (when a candidate is
ticked for you) and `scan.messages` (every reason and note shown). This file walks and reads; the chips
are fetched ONCE per scan, never per file.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from core import engine, ops

engine.register_dir(Path(__file__).resolve().parent / "chips")

_rx = lru_cache(maxsize=256)(re.compile)   # a pattern from a chip, compiled once


def _settings() -> dict:
    return engine.run("scan.settings")


def _patterns() -> dict:
    return engine.run("scan.patterns")


def _label_from(name: str, pats: dict | None = None) -> str:
    """`UserManualBuilder.tsx` → `User Manual Builder`. `sign-in.html` → `Sign In`."""
    pats = pats or _patterns()
    stem = _rx(pats["file_extension"]).sub("", name)          # one extension: Foo.aspx -> Foo
    stem = _rx(pats["role_suffix"]).sub("", stem)
    spaced = stem
    for sep in pats["word_separators"]:
        spaced = spaced.replace(sep, " ")
    words = _rx(pats["camel_boundary"]).sub(pats["camel_replacement"], spaced)
    words = re.sub(r"\s+", " ", words).strip()
    return " ".join(w if w.isupper() else w[:1].upper() + w[1:] for w in words.split()) or stem


def _key_from(label: str, taken: set[str], pats: dict | None = None, fallback: str | None = None) -> str:
    pats = pats or _patterns()
    fallback = fallback if fallback is not None else _settings()["default_key"]
    base = _rx(pats["key_unsafe"]).sub("-", label.lower()).strip("-") or fallback
    key = base
    n = 2
    while key in taken:
        key, n = f"{base}-{n}", n + 1
    taken.add(key)
    return key


def _title_in_html(text: str, pats: dict | None = None) -> str:
    pats = pats or _patterns()
    for pattern in pats["titles"]:
        m = _rx(pattern).search(text)
        if m:
            t = re.sub(r"\s+", " ", m.group(1)).strip()
            if t and not any(bad in t for bad in pats["title_rejects"]):
                return t
    return ""


def _routes_in(text: str, pats: dict | None = None, max_length: int | None = None) -> list[str]:
    pats = pats or _patterns()
    max_length = max_length if max_length is not None else _settings()["max_route_length"]
    api = _rx(pats["api_route"])
    out = []
    for row in pats["routes"]:
        for hit in _rx(row["pattern"]).findall(text):
            hit = hit.strip()
            if hit and not api.search(hit) and len(hit) < max_length and hit not in out:
                out.append(hit)
    return out


def _walk(root: Path, cfg: dict):
    skip, hidden = set(cfg["skip_dirs"]), bool(cfg["skip_hidden_dirs"])
    seen = 0
    for path in root.rglob("*"):
        if seen >= cfg["max_files"]:
            return
        if path.is_dir():
            continue
        if any(part in skip or hidden and part.startswith(".") and part not in {".", ".."}
               for part in path.relative_to(root).parts[:-1]):
            continue
        seen += 1
        yield path


def manifest(root: Path, cfg: dict | None = None) -> list[dict] | None:
    """A project that declares its own screens is believed without argument."""
    cfg = cfg or _settings()
    f = root / cfg["manifest_file"]
    if not f.exists():
        return None
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    rows = data.get("screens", data) if isinstance(data, dict) else data
    pats, said = _patterns(), engine.run("scan.messages")
    out, taken = [], set()
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        label = str(r.get("label") or r.get("name") or r.get("key") or "").strip()
        if not label:
            continue
        out.append({"key": str(r.get("key") or _key_from(label, taken, pats, cfg["default_key"])).strip(),
                    "label": label, "route": str(r.get("route") or "").strip(),
                    "file": str(r.get("file") or cfg["manifest_file"]),
                    "why": said["why_declared"], "confidence": cfg["confidence_declared"], "selected": True})
        taken.add(out[-1]["key"])
    return out or None


def scan(folder: str) -> dict:
    """Candidate screens for one project folder. Nothing is saved here — the Setup grid decides."""
    lib = engine.chips()                                    # one library for the whole walk
    cfg, pats = engine.run("scan.settings", lib=lib), engine.run("scan.patterns", lib=lib)
    said = engine.run("scan.messages", lib=lib)
    root = Path(folder).expanduser()
    if not root.is_dir():
        raise ValueError(ops.template(said["not_a_folder"], {"folder": folder}))

    declared = manifest(root, cfg)
    if declared:
        return {"root": str(root), "screens": declared, "files_read": 0, "note": said["note_declared"]}

    ui_ext, screen_dirs, code_ext = set(cfg["ui_ext"]), set(cfg["screen_dirs"]), set(cfg["screen_code_ext"])
    markup, layout_ext = set(cfg["markup_page"]), cfg["layout_ext"]
    compound = [s.lower() for s in cfg["compound_suffixes"]]
    generated = tuple(s.lower() for s in cfg["generated_suffixes"])
    screen_name, not_a_screen = _rx(pats["screen_name"]), _rx(pats["not_a_screen"])
    code_behind, layout_res = _rx(pats["code_behind"]), _rx(pats["resource_layout"])
    read_bytes, max_route = cfg["read_bytes"], cfg["max_route_length"]

    found: dict[str, dict] = {}
    taken: set[str] = set()
    files_read = 0
    for path in _walk(root, cfg):
        rel_posix = path.relative_to(root).as_posix()
        lower = path.name.lower()
        suffix = next((c for c in compound if lower.endswith(c)), path.suffix.lower())
        parts = {p.lower() for p in path.relative_to(root).parts[:-1]}
        in_screen_dir = bool(parts & screen_dirs)
        named_screen = bool(screen_name.search(path.stem))
        # An Android/resource layout is a screen even though .xml is not a UI extension anywhere else.
        in_layout_res = bool(layout_res.search(rel_posix)) and suffix == layout_ext
        # Foo.aspx.cs / Foo.xaml.cs is the class behind Foo.aspx — one screen, not two.
        if code_behind.search(path.name):
            continue
        # WinForms: Form1.Designer.cs is generated; Form1.cs is the screen.
        if lower.endswith(generated):
            continue
        if suffix not in ui_ext and not in_layout_res and not (in_screen_dir and suffix in code_ext):
            continue

        text = ""
        if path.stat().st_size <= read_bytes:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
                files_read += 1
            except OSError:
                text = ""
        routes = _routes_in(text, pats, max_route)

        reasons = []
        if in_screen_dir:
            reasons.append(ops.template(said["why_screen_dir"], {"dirs": "/".join(sorted(parts & screen_dirs))}))
        if named_screen:
            reasons.append(said["why_named"])
        if in_layout_res:
            reasons.append(said["why_layout"])
        if suffix in markup:
            reasons.append(said["why_template"])
        if routes:
            reasons.append(ops.template(said["why_route"], {"route": routes[0]}))
        if not reasons:
            continue
        # Index/layout/partial files are the frame around a screen, not a screen.
        framing = bool(not_a_screen.search(path.stem))
        if framing and not routes:
            continue

        # `Views/Orders/Index.cshtml`, `pages/billing/index.vue`: the FOLDER is the screen's name.
        named_by_folder = framing and path.parent != root
        label = ((_title_in_html(text, pats) if suffix in markup else "")
                 or (_label_from(path.parent.name, pats) if named_by_folder else "")
                 or _label_from(path.name, pats))
        key = _key_from(label, taken, pats, cfg["default_key"])
        strong = engine.run("scan.is_likely", {"in_screen_dir": in_screen_dir, "named_screen": named_screen,
                                               "declares_route": bool(routes), "android_layout": in_layout_res,
                                               "page_template": suffix in markup}, lib) is True
        found[rel_posix] = {"key": key, "label": label, "route": routes[0] if routes else "",
                            "file": rel_posix, "why": said["why_joiner"].join(reasons),
                            "confidence": cfg["confidence_likely"] if strong else cfg["confidence_maybe"],
                            "selected": strong}

    likely = cfg["confidence_likely"]
    screens = sorted(found.values(), key=lambda s: (s["confidence"] != likely, s["label"].lower()))
    return {"root": str(root), "screens": screens, "files_read": files_read,
            "note": "" if screens else said["note_none"]}


if __name__ == "__main__":  # ponytail: one runnable self-check
    import tempfile

    assert _label_from("UserManualBuilder.tsx") == "User Manual Builder"
    assert _label_from("sign-in.html") == "Sign In"
    assert _routes_in('<Route path="/billing" element={<B/>}/>') == ["/billing"]
    assert _routes_in('@app.route("/api/users")') == [], "API routes are not screens"
    assert _routes_in('@GetMapping("/orders")') == ["/orders"], "Spring MVC"
    assert _routes_in('[Route("customers/{id}")]') == ["customers/{id}"], "ASP.NET"
    assert _routes_in('@page "/counter"') == ["/counter"], "Blazor"
    assert _label_from("CustomerWindow.xaml") == "Customer Window"
    assert _label_from("activity_login.xml") == "Activity Login"
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "src" / "pages").mkdir(parents=True)
        (root / "node_modules" / "junk").mkdir(parents=True)
        (root / "src" / "pages" / "BillingPage.tsx").write_text("export default function BillingPage(){}")
        (root / "node_modules" / "junk" / "FakePage.tsx").write_text("x")
        (root / "src" / "pages" / "index.tsx").write_text("export default function Index(){}")
        # the same portal, pointed at Java, .NET and Android in one folder
        (root / "src" / "main" / "webapp").mkdir(parents=True)
        (root / "src" / "main" / "webapp" / "invoice.jsp").write_text("<html><title>Invoice</title></html>")
        (root / "Views" / "Orders").mkdir(parents=True)
        (root / "Views" / "Orders" / "Index.cshtml").write_text('@page "/orders"')
        (root / "Views" / "Orders" / "Index.cshtml.cs").write_text("class IndexModel {}")
        (root / "Wpf").mkdir()
        (root / "Wpf" / "CustomerWindow.xaml").write_text("<Window/>")
        (root / "Wpf" / "CustomerWindow.xaml.cs").write_text("class CustomerWindow {}")
        (root / "app" / "src" / "res" / "layout").mkdir(parents=True)
        (root / "app" / "src" / "res" / "layout" / "activity_login.xml").write_text("<LinearLayout/>")
        out = scan(str(root))
        keys = {s["key"] for s in out["screens"]}
        assert keys == {"billing-page", "invoice", "orders", "customer-window", "activity-login"}, keys
        by_file = {s["file"]: s for s in out["screens"]}
        assert not any(f.endswith(".cs") for f in by_file), "code-behind is not a second screen"
        assert by_file["src/main/webapp/invoice.jsp"]["label"] == "Invoice", "a JSP title beats its filename"
        assert by_file["Views/Orders/Index.cshtml"]["label"] == "Orders", "an index file is named by its folder"
        assert by_file["src/pages/BillingPage.tsx"]["why"] == "under pages/, named like a screen"
        (root / "screens.json").write_text('{"screens":[{"key":"k","label":"Declared"}]}')
        assert scan(str(root))["screens"][0]["label"] == "Declared"
    assert not engine.run("scan.is_likely", {"in_screen_dir": True}), "a folder alone is only a maybe"
    print("scan self-check OK")
