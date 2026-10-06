"""Tax rules - Fetch, Compare, Apply (2026-10-06 owner: "what changed this year as compared to last year, and another button
to apply ... for all tax, individual and the CA portal").

Fetch: Gemini, with Google Search, is asked for every figure chip taxwatch.items watches, for a new AY, in the exact shape the
portal keeps it (official sources only). The answer is a draft (store taxwatch_<ay>) - nothing changes.
Compare: each figure as it is live (taxwatch.settings live_ay) beside the draft, changed or not, with its source.
Apply: the ticked figures are written into their chips and published through the Ops & chips builder layer
(data/builder/chips - a deploy never undoes it, and each chip's History can restore the one before). Before a chip's first
change its old param is kept under the param `archive` names (compute.settings regimes_by_ay: past years keep their slabs).
A chip's own tests that expected last year's figure are moved to the new one, and that list is shown.

Who: the portal owner only. Words: chip ui.taxwatch.
"""
from __future__ import annotations

import copy
import json
import re
import threading

from fastapi import HTTPException

from core import builder, engine, store
from core.ops import json_in_text, template

_LOCK = threading.Lock()


def settings() -> dict:
    return engine.run("taxwatch.settings")


def say(key: str, **values) -> str:
    return template(engine.run("ui.taxwatch")[key], values)


def items() -> list[dict]:
    return engine.run("taxwatch.items")["items"]


def _ay_next(ay: str, n: int = 1) -> str:
    y = int(ay[:4]) + n
    return f"{y}-{str(y + 1)[2:]}"


# --- paths inside a chip's params: "slabs.new", "regimes[id=new].slabs" -----------------------------------------------

def _steps(path: str) -> list:
    out = []
    for part in path.split("."):
        m = re.fullmatch(r"(\w+)\[(\w+)=([\w-]+)\]", part)
        out += [m[1], (m[2], m[3])] if m else [part]
    return out


def _params(cid: str) -> dict:
    return {p["name"]: p.get("default") for p in engine.chips()[cid]["params"]}


def _get(root, path: str):
    cur = root
    for s in _steps(path):
        cur = next((x for x in cur if x.get(s[0]) == s[1]), None) if isinstance(s, tuple) else (cur or {}).get(s)
        if cur is None:
            return None
    return cur


def _set(root: dict, path: str, value) -> None:
    st = _steps(path)
    cur = root
    for s in st[:-1]:
        cur = next(x for x in cur if x.get(s[0]) == s[1]) if isinstance(s, tuple) else cur.setdefault(s, {})
    cur[st[-1]] = value


def live_value(it: dict):
    """An item's value as the portal holds it - its first target, the one whose shape the AI is asked for."""
    t = it["targets"][0]
    return _get(_params(t["chip"]), t["path"])


# --- fetch ----------------------------------------------------------------------------------------------------------

def _key(ay: str) -> str:
    return f"taxwatch_{ay}"


def draft(ay: str) -> dict:
    return store.read(_key(ay), {}) or {}


def fetch(u: dict, ay: str) -> dict:
    import providers  # noqa: PLC0415
    k = settings()
    if not (re.fullmatch(r"\d{4}-\d{2}", ay or "") and ay > k["live_ay"]):
        raise HTTPException(400, say("bad_ay", ay=k["live_ay"]))
    if not providers.have_key(u["id"], k["provider"]):
        raise HTTPException(400, say("no_key"))
    lines = "\n".join(f"- {it['id']}: {it['label']}. AY {k['live_ay']}: {json.dumps(live_value(it))}" for it in items())
    prompt = template(k["prompt"], {"ay": ay, "fy": f"{int(ay[:4]) - 1}-{ay[2:4]}", "live_ay": k["live_ay"], "items": lines})

    def call(secret: str):
        from google import genai  # noqa: PLC0415
        from google.genai import types  # noqa: PLC0415
        cfg = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())] if k["search"] else None)
        resp = genai.Client(api_key=secret).models.generate_content(model=k["model"], contents=prompt, config=cfg)
        pages = []
        for c in getattr(resp, "candidates", None) or []:
            for ch in getattr(getattr(c, "grounding_metadata", None), "grounding_chunks", None) or []:
                web = getattr(ch, "web", None)
                if web and getattr(web, "uri", ""):
                    pages.append({"title": getattr(web, "title", "") or "", "uri": web.uri})
        return getattr(resp, "text", "") or "", pages

    try:
        (text, pages), _row = providers.call_with_keys(u["id"], k["provider"], call, model=k["model"])
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001 - the owner is told; nothing changed
        raise HTTPException(502, say("ai_failed", why=str(e)[:160])) from e
    got = json_in_text(text, k["fence"])
    if not isinstance(got, dict):
        raise HTTPException(502, say("ai_bad"))
    known = {it["id"] for it in items()}
    rows = {i: {"value": (v or {}).get("value"), "source": str((v or {}).get("source") or "")[:300],
                "note": str((v or {}).get("note") or "")[: k["note_chars"]]} for i, v in got.items() if i in known and isinstance(v, dict)}
    d = {"ay": ay, "live_ay": k["live_ay"], "at": store.now(), "by": u.get("email", ""), "model": k["model"], "items": rows,
         "pages": pages[: k["sources_most"]]}
    store.write(_key(ay), d)
    return compare(ay)


def edit(u: dict, ay: str, iid: str, value) -> dict:
    """The owner's own value over the AI's (a figure it could not find, or got wrong)."""
    if iid not in {it["id"] for it in items()}:
        raise HTTPException(400, say("unknown_item", id=iid))
    with _LOCK:
        d = draft(ay) or {"ay": ay, "live_ay": settings()["live_ay"], "at": store.now(), "items": {}, "pages": []}
        row = d["items"].setdefault(iid, {"source": "", "note": ""})
        if not _same_shape(live_value(next(it for it in items() if it["id"] == iid)), value):
            raise HTTPException(400, say("bad_json"))
        row.update(value=value, edited_by=u.get("email", ""), edited_at=store.now())
        store.write(_key(ay), d)
    return compare(ay)


def _same_shape(a, b) -> bool:
    if isinstance(a, dict):
        return isinstance(b, dict) and set(a) == set(b) and all(_same_shape(a[x], b[x]) for x in a)
    if isinstance(a, list):
        return isinstance(b, list) and bool(b) and all(any(_same_shape(y, x) for y in a) for x in b) if a else isinstance(b, list)
    if isinstance(a, bool) or a is None:
        return type(a) is type(b) or a is None
    if isinstance(a, (int, float)):
        return isinstance(b, (int, float)) and not isinstance(b, bool)
    return isinstance(b, type(a))


# --- compare --------------------------------------------------------------------------------------------------------

def compare(ay: str) -> dict:
    k = settings()
    d = draft(ay)
    rows = []
    for it in items():
        now = live_value(it)
        got = (d.get("items") or {}).get(it["id"]) or {}
        new = got.get("value")
        state = "unknown" if new is None or not _same_shape(now, new) else ("same" if new == now else "changed")
        rows.append({"id": it["id"], "group": it["group"], "kind": it["kind"], "label": it["label"], "live": now, "new": new,
                     "state": state, "source": got.get("source", ""), "note": got.get("note", ""), "edited": bool(got.get("edited_by")),
                     "where": [f"{t['chip']} · {t['path']}" for t in it["targets"]]})
    count = {s: sum(r["state"] == s for r in rows) for s in ("changed", "same", "unknown")}
    return {"live_ay": k["live_ay"], "ay": ay, "fetched": bool(d), "at": d.get("at"), "by": d.get("by", ""), "model": d.get("model", ""),
            "pages": d.get("pages", []), "rows": rows, "count": count, "groups": engine.run("taxwatch.items")["groups"],
            "next": _ay_next(k["live_ay"])}


# --- apply ----------------------------------------------------------------------------------------------------------

def apply(u: dict, ay: str, ids: list[str]) -> dict:
    with _LOCK:
        c = compare(ay)
        k = settings()
        pick = [r for r in c["rows"] if r["id"] in set(ids) and r["state"] == "changed"]
        by_id = {it["id"]: it for it in items()}
        chips: dict[str, dict] = {}
        for r in pick:
            for t in by_id[r["id"]]["targets"]:
                ch = chips.setdefault(t["chip"], copy.deepcopy(builder._clean(engine.chips()[t["chip"]])))   # noqa: SLF001
                params = {p["name"]: p for p in ch["params"]}
                head = _steps(t["path"])[0]
                if t.get("archive") and k["live_ay"] not in (params[t["archive"]]["default"] or {}):
                    params[t["archive"]]["default"] = dict(params[t["archive"]]["default"] or {}) | {k["live_ay"]: copy.deepcopy(params[head]["default"])}
                vals = {n: p["default"] for n, p in params.items()}
                _set(vals, t["path"], r["new"][t["pick"]] if t.get("pick") else r["new"])
                params[head]["default"] = vals[head]
        # the settings chip moves on to the new year with them
        tw = copy.deepcopy(builder._clean(engine.chips()["taxwatch.settings"]))  # noqa: SLF001
        next(p for p in tw["params"] if p["name"] == "live_ay")["default"] = ay
        chips["taxwatch.settings"] = tw
        note = f" {store.now()[:10]}: AY {ay} figures applied from Tax rules ({', '.join(r['id'] for r in pick)}) by {u.get('email', '')}."
        # every test that held before and fails with the new figures (the chips changed, and the chips that use them) now
        # expects the new answer - listed for the owner, so a surprise shows
        figured = len(chips) - 1
        rebased = []
        lib = engine.with_drafts(list(chips.values()))
        was = engine.chips()
        for cid, ch in lib.items():
            if ch.get("status") == "inactive":
                continue
            now = [t for t in engine.run_tests(ch, lib) if not t["ok"] and t.get("error") is None]
            held = {t["n"] for t in engine.run_tests(was[cid], was) if t["ok"]} if now and cid in was else set()
            for t in now:
                if t["n"] in held or cid in chips:
                    ch = chips.setdefault(cid, copy.deepcopy(builder._clean(ch)))  # noqa: SLF001
                    case = ch["test_cases"][t["n"] - 1]
                    case["expect_value" if "expect_value" in case else "expect"] = t["got"]
                    rebased.append(f"{cid} #{t['n']}")
        lib_drafts = list(chips.values())
        for ch in lib_drafts:
            ch["description_nl"] = (ch.get("description_nl") or "") + note
            res = builder.check("chips", ch, [x for x in lib_drafts if x is not ch])
            if res["problems"] or not all(t["ok"] for t in res["tests"]):
                raise HTTPException(422, {"message": say("apply_failed", chip=ch["chip_id"]), "chip": ch["chip_id"], **res})
        for cid, ch in chips.items():
            out = ch | {"version": int(ch.get("version") or 0) + 1, "status": "published", "updated_by": u.get("email", ""), "updated_at": store.now()}
            builder._write(builder.root() / "chips" / f"{cid}.json", out)       # noqa: SLF001
            builder._snapshot("chips", out, u, f"Tax rules: AY {ay}")           # noqa: SLF001
        builder.refresh("chips")
        d = draft(ay)
        d["applied"] = {"at": store.now(), "by": u.get("email", ""), "ids": [r["id"] for r in pick], "rebased": rebased}
        store.write(_key(ay), d)
    return compare(ay) | {"done": say("applied", n=len(pick), chips=figured, ay=ay),
                          "rebased": say("rebased", list=", ".join(rebased)) if rebased else ""}


if __name__ == "__main__":  # ponytail: paths, shapes and the compare of a hand-made draft, on the shipped chips
    import store as _portal_store  # noqa: F401 - registers this portal's chips, as the app does
    p = {"regimes": [{"id": "new", "slabs": [1]}, {"id": "old", "slabs": [2]}], "slabs": {"new": {"below60": 3}}}
    assert _get(p, "regimes[id=old].slabs") == [2] and _get(p, "slabs.new.below60") == 3
    _set(p, "regimes[id=new].slabs", [9])
    assert p["regimes"][0]["slabs"] == [9]
    assert _same_shape({"a": [{"upto": 1, "rate": 0}]}, {"a": [{"upto": 2, "rate": 5}, {"upto": None, "rate": 30}]}) is False  # upto None vs int
    assert _same_shape([{"above": 1, "rate": 10}], [{"above": 5, "rate": 15}]) and not _same_shape(731, "731")
    slabs = live_value(next(it for it in items() if it["id"] == "slabs_new"))
    assert _same_shape(slabs, copy.deepcopy(slabs) | {"below60": slabs["below60"][:2] + slabs["below60"][-1:]})   # fewer slabs, same shape
    for it in items():
        assert live_value(it) is not None, it["id"]
        for t in it["targets"][1:]:
            v = live_value(it)
            assert _get(_params(t["chip"]), t["path"]) is not None, (it["id"], t)
            if t.get("pick"):
                assert t["pick"] in v, (it["id"], t)
    assert _ay_next("2026-27") == "2027-28"
    print("taxwatch self-check OK", len(items()), "figures")
