"""Guide Me Builder (SteadyMove, 2026-09-28): bring a Guide Me script, check it, preview it, export it for any site.

A Guide Me script (format guide-me/1, skill .agents/skills/guide-me-script) is a screen's live tour written as plain
JSON: its site, its page, a title and the steps (what each spotlights and what it says). This module only GATHERS
and asks chips:
- check(script) -> (clean, problems): the rules are chip guide.check (generic op doc_problems over an editable rules
  table), asked through core.guide.check(script=True) with the sites of chip guideme.portals; the answers are plain
  sentences (chip guide.messages). Fields not listed in chip guideme.settings are dropped first.
- one store file per account (`guideme-<user_id>`): a build = the clean script + its facts. Listing is chip
  guideme.list_view over the generic op rows_view.
- export: one zip with the portable kit (core/static guide-kit.js, guide-kit.css, icons.js), the script, a ready
  guide-me.<page>.js carrying the kit's words (chips ui.guide + ui.shell rd_*) and settings (chip guide.settings),
  and a README - their code and words are templates in chip guideme.export.
"""
from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path

from fastapi import HTTPException

import store
from core import engine, guide, ops

engine.register_dir(Path(__file__).resolve().parent / "chips")

KIT = Path(__file__).resolve().parent / "core" / "static"      # the portable Guide me kit this portal already serves


def say(key: str, **values) -> str:
    return engine.say("guideme.messages", key, **values)


def kit_words() -> dict:
    """The card's words as the kit takes them: chip ui.guide, plus the four roads' names from chip ui.shell."""
    return dict(engine.run("ui.guide")) | {k: v for k, v in engine.run("ui.shell").items() if k.startswith("rd_")}


# --- the check ------------------------------------------------------------------------------------

def _keep(d, keys: list) -> dict:
    return {k: d[k] for k in keys if isinstance(d, dict) and k in d}


def _clean(script: dict, cfg: dict) -> dict:
    """Only the fields a script may carry (lists in chip guideme.settings); everything else is dropped."""
    out = _keep(script, cfg["top_keys"])
    if isinstance(out.get("voice"), dict):
        out["voice"] = _keep(out["voice"], cfg["voice_keys"])
    if isinstance(out.get("steps"), list):
        out["steps"] = [(_keep(s, cfg["step_keys"]) | ({"art": _keep(s["art"], cfg["art_keys"])} if isinstance(s.get("art"), dict) else {}))
                        if isinstance(s, dict) else s for s in out["steps"]]
    return out


def check(script) -> tuple[dict | None, list[str]]:
    """A script (a dict, or its text) -> (the clean script, []) or (None, [every problem, in plain words])."""
    cfg = engine.run("guideme.settings")
    cap = int(cfg["max_kb"]) * 1024
    if isinstance(script, bytes):
        script = script.decode("utf-8", "replace")
    if isinstance(script, str):
        if len(script.encode("utf-8")) > cap:
            return None, [say("too_big", kb=cfg["max_kb"])]
        try:
            script = json.loads(script.lstrip("﻿"))
        except ValueError:
            return None, [say("not_script")]
    if not isinstance(script, dict):
        return None, [say("not_script")]
    if len(json.dumps(script, ensure_ascii=False).encode("utf-8")) > cap:
        return None, [say("too_big", kb=cfg["max_kb"])]
    clean = _clean(script, cfg)
    problems = guide.check(clean, script=True, sets={"portals": [r["id"] for r in engine.run("guideme.portals")["rows"]]})
    return (None, problems) if problems else (clean, [])


# --- the builds (one file per account) ------------------------------------------------------------

def _file(user_id: str) -> str:
    return f"guideme-{user_id}"


def _rows(user_id: str) -> list[dict]:
    return list((store.read(_file(user_id), {}) or {}).get("rows") or [])


def _save(user_id: str, rows: list[dict]) -> None:
    store.write(_file(user_id), {"rows": rows})


def _summary(r: dict) -> dict:
    return {k: r.get(k) for k in ("id", "portal", "page", "title", "lede", "steps", "created_at", "updated_at")}


def find(user_id: str, q: str = "", page: int = 1) -> dict:
    view = engine.run("guideme.list_view")
    rows = [_summary(r) for r in _rows(user_id)]
    out = ops.rows_view(rows, str(q or "")[:200], view["search_keys"], view["sort_key"], view["sort_desc"], page,
                        view["page_size"], view["max_page_size"])
    return out | {"total_all": len(rows)}


def _opened(row: dict) -> dict:
    """A build as the page opens it: plus what Preview hands the kit (its words and settings - the kit carries none)."""
    return row | {"kit": {"words": kit_words(), "settings": engine.run("guide.settings")}}


def get(user_id: str, build_id: str) -> dict:
    row = next((r for r in _rows(user_id) if r["id"] == build_id), None)
    if not row:
        raise HTTPException(404, say("no_build"))          # someone else's id is simply not there
    return _opened(row)


def save(user_id: str, script, build_id: str = "") -> dict:
    """Check a script and keep it: a new build, or (build_id) this build's script replaced. Problems -> 422, nothing kept."""
    clean, problems = check(script)
    if problems:
        raise HTTPException(422, {"message": say("has_problems", n=len(problems)), "problems": problems})
    facts = {"portal": clean.get("portal", ""), "page": clean.get("page", ""), "title": clean.get("title", ""),
             "lede": clean.get("lede", ""), "steps": len(clean.get("steps") or []), "script": clean, "updated_at": store.now()}
    with store._LOCK:                                     # noqa: SLF001 - this portal's own store
        rows = _rows(user_id)
        if build_id:
            row = next((r for r in rows if r["id"] == build_id), None)
            if not row:
                raise HTTPException(404, say("no_build"))
            row.update(facts)
            word = "replaced"
        else:
            row = {"id": store.new_id(), "created_at": facts["updated_at"]} | facts
            rows.append(row)
            word = "created"
        _save(user_id, rows)
    return _opened(row) | {"message": say(word, title=row["title"])}


def delete(user_id: str, build_id: str) -> dict:
    get(user_id, build_id)
    with store._LOCK:                                     # noqa: SLF001
        _save(user_id, [r for r in _rows(user_id) if r["id"] != build_id])
    return {"ok": True, "message": say("deleted")}


# --- export ---------------------------------------------------------------------------------------

def export_files(script: dict) -> tuple[str, dict[str, bytes]]:
    """(the zip's name, {file name: bytes}) for one clean script - every name and the generated code from chip guideme.export."""
    ex = engine.run("guideme.export")
    words = kit_words()
    slug = re.sub(r"[^a-z0-9_-]+", "-", str(script.get("portal", "")).lower()).strip("-")
    names = {"portal": slug, "page": script.get("page", "")}
    module_file = ops.template(ex["module_file"], names)
    script_file = ops.template(ex["script_file"], names)
    fill = {"page": script.get("page", ""), "portal": script.get("portal", ""), "title": script.get("title", ""),
            "format": script.get("format", ""), "module_file": module_file, "script_file": script_file,
            "page_json": json.dumps(script.get("page", "")), "script_json": json.dumps(script, indent=2, ensure_ascii=False),
            "words_json": json.dumps(words, indent=2, ensure_ascii=False),
            "settings_json": json.dumps(engine.run("guide.settings"), indent=2, ensure_ascii=False),
            "button_label_json": json.dumps(words.get("guide_me", ""), ensure_ascii=False), "button_style_json": json.dumps(ex["button_style"])}
    files = {name: (KIT / name).read_bytes() for name in ex["kit_files"]}
    files[script_file] = (json.dumps(script, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    files[module_file] = ops.template(ex["module_js"], fill).encode("utf-8")
    files[ex["readme_file"]] = ops.template(ex["readme"], fill).encode("utf-8")
    return ops.template(ex["zip_name"], names), files


def export(user_id: str, build_id: str) -> tuple[str, bytes]:
    """(the zip's name, the zip) - small enough to build in memory: the kit is three text files."""
    name, files = export_files(get(user_id, build_id)["script"])
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for fname, data in files.items():
            z.writestr(f"{name}/{fname}", data)
    return name, buf.getvalue()


if __name__ == "__main__":  # ponytail: one runnable self-check - bad scripts refused in words, a good one kept and exported
    import tempfile

    import core.store as cs
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        cs.DATA = Path(tmp)
        good = {"format": "guide-me/1", "portal": "sm", "page": "comics", "title": "Comic Book Studio", "lede": "L", "icon": "image",
                "voice": {"rate": 1.1, "speak_by_default": False, "secret": 1}, "extra": "dropped",
                "steps": [{"title": f"S{i}", "say": "Words.", "target": "#x", "art": {"kind": "flow", "items": ["A", "B"], "at": 0, "junk": 1}, "zzz": 1}
                          for i in range(3)]}
        clean, bad = check(json.dumps(good))
        assert not bad and "extra" not in clean and "secret" not in clean["voice"] and "zzz" not in clean["steps"][0], bad
        assert "junk" not in clean["steps"][0]["art"], clean
        assert check({**good, "portal": "workspace:astrogaami"})[0], "any institute workspace is a site"
        _, bad = check({**good, "format": "x", "portal": "nope", "page": "Bad Page", "icon": "no-such-icon",
                        "steps": [{"title": "", "say": "", "art": {"kind": "movie"}, "place": "middle"}]})
        assert len(bad) >= 6 and all(not b.startswith("[") and "{" not in b for b in bad), bad
        assert check("{not json")[1] == [say("not_script")] and check([1])[1] == [say("not_script")]
        assert check({**good, "voice": {"rate": 9}})[1], "a voice speed out of range is a problem"
        row = save("u1", good)
        assert row["steps"] == 3 and row["kit"]["words"]["step_of"] and find("u1")["total"] == 1 and find("u2")["total"] == 0, "a build is its owner's alone"
        try:
            save("u1", {**good, "steps": []}, row["id"])
            raise AssertionError("a bad replacement must be refused")
        except HTTPException as e:
            assert e.status_code == 422 and e.detail["problems"], e.detail
        assert get("u1", row["id"])["steps"] == 3, "a refused replacement changes nothing"
        name, data = export("u1", row["id"])
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            got = {Path(n).name: z.read(n).decode("utf-8") for n in z.namelist()}
        assert name == "guide-me-sm-comics" and set(got) == {"guide-kit.js", "guide-kit.css", "icons.js", "comics.guide.json", "guide-me.comics.js", "README.md"}, got.keys()
        mod = got["guide-me.comics.js"]
        assert "import { openTour } from './guide-kit.js'" in mod and "export function mountGuideMe(where = document.body)" in mod, mod[:400]
        assert '"page": "comics"' in mod and '"step_of"' in mod and '"art_kinds"' in mod, "the module carries the script, the words and the settings"
        slots_ = set(re.findall(r"\{([a-z_]+)\}", engine.run("guideme.export")["module_js"]))
        assert slots_ and not any("{" + s_ + "}" in mod for s_ in slots_ - {"n", "total", "why", "product"}), "every slot of the template is filled"
        assert "mountGuideMe" in got["README.md"] and "guide-me.comics.js" in got["README.md"]
        assert export_files({**clean, "portal": "workspace:astrogaami"})[0] == "guide-me-workspace-astrogaami-comics", "a zip name never carries a colon"
        try:
            get("u2", row["id"])
            raise AssertionError("another account never sees a build")
        except HTTPException as e:
            assert e.status_code == 404
        delete("u1", row["id"])
        assert find("u1")["total"] == 0
    print("guideme self-check OK")
