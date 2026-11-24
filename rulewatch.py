"""Rule watch - Fetch, Compare, Apply a domain's yearly figures (boilerplate; 2026-10-07, made from SimplyFile's Tax rules).

A watch is a name `<w>` (SimplyFile: "taxwatch") and three chips the domain writes:
  <w>.settings  live_ay (the period the portal runs on), ais, prompt, fence, ai_timeout, note_chars, new_most, sources_most, search
  <w>.items     items [{id, group, kind, label, targets: [{chip, path, archive?, pick?, extend?}]}], groups
  ui.<w>        every word (bad_ay, no_key, ai_none, ai_failed, ai_bad, unknown_item, bad_json, apply_failed, applied, rebased,
                ext_why, log_note, snapshot)
Fetch: an AI that searches the web (Gemini with Google Search, or OpenAI with web search) is asked for every item, for a period,
in the exact shape the portal keeps it. The answer is a draft (store <w>_<period>) - nothing changes.
Compare: each item as it is live beside the draft - changed, same or unknown (not announced, or the wrong shape) - with its source.
Apply: the ticked items are written into their chips and published through the Ops & chips builder layer (History, and a deploy
never undoes it). A target's `archive` param keeps the live period's old value before its first change; a target's `extend`
param (a map {period start year: {path: value, why, source}}) takes a re-check of the live period's value, for that period only.
Tests that held before and fail with the new figures are moved to the new answer, and listed.
Periods are "2026" or "2026-27". Who: the portal owner fetches, edits and applies; the routes guard it.
"""
from __future__ import annotations

from typing import Any
import copy
import json
import re
import threading

from fastapi import HTTPException

from core import builder, engine, store
from core.ops import json_in_text, template

_LOCK = threading.Lock()


def next_period(p: str, n: int = 1) -> str:
    y = int(p[:4]) + n
    return str(y) if len(p) == 4 else f"{y}-{str(y + 1)[2:]}"


# --- paths inside a chip's params: "slabs.new", "regimes[id=new].slabs" -----------------------------------------------

def _steps(path: str) -> list:
    out: list[Any] = []
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


class Watch:
    def __init__(self, name: str):
        self.name = name

    def settings(self) -> dict:
        return engine.run(f"{self.name}.settings")

    def say(self, key: str, **values) -> str:
        return template(engine.run(f"ui.{self.name}")[key], values)

    def items(self) -> list[dict]:
        return engine.run(f"{self.name}.items")["items"]

    def live_value(self, it: dict):
        """An item's value as the portal holds it - its first target, the one whose shape the AI is asked for; a value the
        live period was given by a re-check (the target's `extend` param) is the value that period has."""
        t = it["targets"][0]
        if t.get("extend"):
            ext = (_params(t["chip"]).get(t["extend"]) or {}).get(self.settings()["live_ay"][:4]) or {}
            if t["path"] in ext:
                return ext[t["path"]]
        return _get(_params(t["chip"]), t["path"])

    def _key(self, ay: str) -> str:
        return f"{self.name}_{ay}"

    def draft(self, ay: str) -> dict:
        return store.read(self._key(ay), {}) or {}

    # --- fetch ------------------------------------------------------------------------------------------------------

    def ai_choices(self, u: dict) -> list[dict]:
        """The AIs Fetch may ask (settings ais), each with whether this person has a key that works now."""
        import providers  # noqa: PLC0415
        return [a | {"ready": bool(providers.candidates(u["id"], a["provider"])), "why": "" if providers.candidates(u["id"], a["provider"])
                     else providers.no_key_text(u["id"], a["provider"])} for a in self.settings()["ais"]]

    def fetch(self, u: dict, ay: str, provider: str = "") -> dict:
        import providers  # noqa: PLC0415
        k = self.settings()
        if not (re.fullmatch(r"\d{4}(-\d{2})?", ay or "") and len(ay) == len(k["live_ay"]) and ay >= k["live_ay"]):  # the live period too
            raise HTTPException(400, self.say("bad_ay", ay=k["live_ay"]))
        choices = self.ai_choices(u)
        pick = next((a for a in choices if a["provider"] == provider), None) if provider else next((a for a in choices if a["ready"]), None)
        if not pick or not pick["ready"]:
            why = (pick or choices[0])["why"] if choices else self.say("no_key")
            raise HTTPException(400, self.say("ai_none", why=why))
        k = k | {"provider": pick["provider"], "model": pick["model"]}
        lines = "\n".join(f"- {it['id']}: {it['label']}. {k['live_ay']}: {json.dumps(self.live_value(it))}" for it in self.items())
        prompt = template(k["prompt"], {"ay": ay, "y": ay[:4], "fy": f"{int(ay[:4]) - 1}-{ay[2:4]}", "live_ay": k["live_ay"], "items": lines})

        def call_openai(secret: str):
            """OpenAI's Responses API with its web_search tool, over plain HTTPS (no SDK: the portal's own client)."""
            base = (providers.row("openai") or {}).get("base_url") or "https://api.openai.com/v1"
            resp = providers._post_json(f"{base.rstrip('/')}/responses", secret,  # noqa: SLF001
                                        {"model": k["model"], "input": prompt, "tools": [{"type": pick.get("tool") or "web_search"}]}, float(k["ai_timeout"]))
            text, pages = [], []
            for out in resp.get("output") or []:
                for part in out.get("content") or []:
                    if part.get("type") == "output_text":
                        text.append(part.get("text") or "")
                        pages += [{"title": a.get("title") or "", "uri": a["url"]} for a in part.get("annotations") or [] if a.get("url")]
            return "".join(text), pages

        def call(secret: str):
            if k["provider"] == "openai":
                return call_openai(secret)
            from google import genai  # noqa: PLC0415
            from google.genai import types  # noqa: PLC0415
            cfg = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())] if k["search"] else None)
            client = genai.Client(api_key=secret)        # held: a temporary client closes before its call answers
            resp = client.models.generate_content(model=k["model"], contents=prompt, config=cfg)
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
            raise HTTPException(502, self.say("ai_failed", why=str(e)[:160])) from e
        got = json_in_text(text, k["fence"])
        if not isinstance(got, dict):
            raise HTTPException(502, self.say("ai_bad"))
        known = {it["id"] for it in self.items()}
        rows = {i: {"value": (v or {}).get("value"), "source": str((v or {}).get("source") or "")[:300],
                    "note": str((v or {}).get("note") or "")[: k["note_chars"]]} for i, v in got.items() if i in known and isinstance(v, dict)}
        new_rules = [{f: str(x.get(f) or "")[: k["note_chars"]] for f in ("what", "who", "source")}   # what is not a figure: needs building
                     for x in (got.get("_new") or []) if isinstance(x, dict) and x.get("what")][: int(k["new_most"])]
        d = {"ay": ay, "live_ay": k["live_ay"], "at": store.now(), "by": u.get("email", ""), "model": k["model"], "items": rows,
             "pages": pages[: k["sources_most"]], "new_rules": new_rules}
        store.write(self._key(ay), d)
        return self.compare(ay)

    def edit(self, u: dict, ay: str, iid: str, value) -> dict:
        """The owner's own value over the AI's (a figure it could not find, or got wrong)."""
        if iid not in {it["id"] for it in self.items()}:
            raise HTTPException(400, self.say("unknown_item", id=iid))
        with _LOCK:
            d = self.draft(ay) or {"ay": ay, "live_ay": self.settings()["live_ay"], "at": store.now(), "items": {}, "pages": []}
            row = d["items"].setdefault(iid, {"source": "", "note": ""})
            if not _same_shape(self.live_value(next(it for it in self.items() if it["id"] == iid)), value):
                raise HTTPException(400, self.say("bad_json"))
            row.update(value=value, edited_by=u.get("email", ""), edited_at=store.now())
            store.write(self._key(ay), d)
        return self.compare(ay)

    # --- compare ----------------------------------------------------------------------------------------------------

    def compare(self, ay: str) -> dict:
        k = self.settings()
        d = self.draft(ay)
        rows = []
        for it in self.items():
            now = self.live_value(it)
            got = (d.get("items") or {}).get(it["id"]) or {}
            new = got.get("value")
            state = "unknown" if new is None or not _same_shape(now, new) else ("same" if new == now else "changed")
            rows.append({"id": it["id"], "group": it["group"], "kind": it["kind"], "label": it["label"], "live": now, "new": new,
                         "state": state, "source": got.get("source", ""), "note": got.get("note", ""), "edited": bool(got.get("edited_by")),
                         "where": [f"{t['chip']} · {t['path']}" for t in it["targets"]]})
        count = {s: sum(r["state"] == s for r in rows) for s in ("changed", "same", "unknown")}
        return {"live_ay": k["live_ay"], "ay": ay, "fetched": bool(d), "at": d.get("at"), "by": d.get("by", ""), "model": d.get("model", ""),
                "pages": d.get("pages", []), "new_rules": d.get("new_rules", []), "rows": rows, "count": count,
                "groups": engine.run(f"{self.name}.items")["groups"], "next": next_period(k["live_ay"]),
                "years": [next_period(k["live_ay"], n) for n in range(4)]} | self._last_check(k)   # the live period first: check it again

    def _last_check(self, k: dict) -> dict:
        """When the live period or the next was last fetched, and whether a re-check is due (settings check_every_days) - the
        department publishes circulars all year; Fetch costs the owner's AI key and its answer needs a person, so nothing runs
        by itself: the page says so."""
        import datetime  # noqa: PLC0415
        at = max((self.draft(p).get("at") or "" for p in (k["live_ay"], next_period(k["live_ay"]))), default="")
        days = (datetime.date.today() - datetime.date.fromisoformat(at[:10])).days if at else None
        every = int(k.get("check_every_days") or 0)
        return {"last_check": at, "check_due": bool(every) and (days is None or days >= every), "check_every_days": every}

    # --- apply ------------------------------------------------------------------------------------------------------

    def apply(self, u: dict, ay: str, ids: list[str]) -> dict:
        with _LOCK:
            c = self.compare(ay)
            k = self.settings()
            pick = [r for r in c["rows"] if r["id"] in set(ids) and r["state"] == "changed"]
            by_id = {it["id"]: it for it in self.items()}
            chips: dict[str, dict] = {}
            for r in pick:
                for t in by_id[r["id"]]["targets"]:
                    ch = chips.setdefault(t["chip"], copy.deepcopy(builder._clean(engine.chips()[t["chip"]])))   # noqa: SLF001
                    params = {p["name"]: p for p in ch["params"]}
                    head = _steps(t["path"])[0]
                    if t.get("archive") and k["live_ay"] not in (params[t["archive"]]["default"] or {}):
                        params[t["archive"]]["default"] = dict(params[t["archive"]]["default"] or {}) | {k["live_ay"]: copy.deepcopy(params[head]["default"])}
                    new = r["new"][t["pick"]] if t.get("pick") else r["new"]
                    if ay == k["live_ay"] and t.get("extend"):
                        # the live period's value as published since (a circular): that period only, the rule stays for the others
                        ext = copy.deepcopy(params[t["extend"]]["default"] or {})
                        e = ext.setdefault(ay[:4], {})
                        e[t["path"]] = new
                        e["why"] = r.get("note") or e.get("why") or self.say("ext_why", ay=ay)
                        e["source"] = r.get("source") or e.get("source", "")
                        params[t["extend"]]["default"] = ext
                        continue
                    vals = {n: p["default"] for n, p in params.items()}
                    _set(vals, t["path"], new)
                    params[head]["default"] = vals[head]
            if ay > k["live_ay"]:                   # a new period: the settings chip moves on to it; a re-check of the live one stays
                tw = copy.deepcopy(builder._clean(engine.chips()[f"{self.name}.settings"]))  # noqa: SLF001
                next(p for p in tw["params"] if p["name"] == "live_ay")["default"] = ay
                chips[f"{self.name}.settings"] = tw
            note = " " + self.say("log_note", day=store.now()[:10], ay=ay, ids=", ".join(r["id"] for r in pick), who=u.get("email", ""))
            # every test that held before and fails with the new figures (the chips changed, and the chips that use them) now
            # expects the new answer - listed for the owner, so a surprise shows
            figured = len(chips) - (1 if f"{self.name}.settings" in chips else 0)
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
                    raise HTTPException(422, {"message": self.say("apply_failed", chip=ch["chip_id"]), "chip": ch["chip_id"], **res})
            for cid, ch in chips.items():
                out = ch | {"version": int(ch.get("version") or 0) + 1, "status": "published", "updated_by": u.get("email", ""), "updated_at": store.now()}
                builder._write(builder.root() / "chips" / f"{cid}.json", out)       # noqa: SLF001
                builder._snapshot("chips", out, u, self.say("snapshot", ay=ay))    # noqa: SLF001
            builder.refresh("chips")
            d = self.draft(ay)
            d["applied"] = {"at": store.now(), "by": u.get("email", ""), "ids": [r["id"] for r in pick], "rebased": rebased}
            store.write(self._key(ay), d)
        return self.compare(ay) | {"done": self.say("applied", n=len(pick), chips=figured, ay=ay),
                                   "rebased": self.say("rebased", list=", ".join(rebased)) if rebased else ""}

    def check(self) -> int:
        """Self-check of a domain's items: every item and target resolves on the shipped chips."""
        for it in self.items():
            v = self.live_value(it)
            assert v is not None, it["id"]
            for t in it["targets"][1:]:
                assert _get(_params(t["chip"]), t["path"]) is not None, (it["id"], t)
                if t.get("pick"):
                    assert t["pick"] in v, (it["id"], t)
            for t in it["targets"]:
                assert not t.get("extend") or t["extend"] in _params(t["chip"]), (it["id"], t)
        return len(self.items())


if __name__ == "__main__":  # ponytail: paths, shapes and periods; a domain's items are checked by its own module (Watch.check)
    p = {"regimes": [{"id": "new", "slabs": [1]}, {"id": "old", "slabs": [2]}], "slabs": {"new": {"below60": 3}}}
    assert _get(p, "regimes[id=old].slabs") == [2] and _get(p, "slabs.new.below60") == 3
    _set(p, "regimes[id=new].slabs", [9])
    assert p["regimes"][0]["slabs"] == [9]
    assert _same_shape({"a": [{"upto": 1, "rate": 0}]}, {"a": [{"upto": 2, "rate": 5}, {"upto": None, "rate": 30}]}) is False  # upto None vs int
    assert _same_shape([{"above": 1, "rate": 10}], [{"above": 5, "rate": 15}]) and not _same_shape(731, "731")
    assert next_period("2026-27") == "2027-28" and next_period("2026") == "2027" and next_period("2099-00") == "2100-01"
    print("rulewatch self-check OK")
