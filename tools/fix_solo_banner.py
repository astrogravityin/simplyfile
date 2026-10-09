"""2026-10-09 owner (TradyFy, an Individual investor desk): the approved banner said "add your team below" on a desk that
has no team. Word st_approved_solo (chip ui.firm) is the approved line for a desk with no team card; page-firm.js picks it
when the server sends no team. Run from a portal's root (re-runnable): python tools/fix_solo_banner.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
SUFFIXES = ("; add your team below.", " add your team below.")

p = Path("chips/ui.firm.json")
c = json.loads(p.read_text(encoding="utf-8"))
names = [x["name"] for x in c["params"]]
if "st_approved_solo" not in names:
    base = next(x for x in c["params"] if x["name"] == "st_approved")
    solo = base["default"]
    for s in SUFFIXES:
        if solo.endswith(s):
            solo = solo[: -len(s)] + "."
    assert solo != base["default"], solo
    c["params"].insert(names.index("st_approved") + 1, {**base, "name": "st_approved_solo", "default": solo, "label": "st approved solo"})
    s = json.dumps(c["expr"], ensure_ascii=False)
    c["expr"] = json.loads(s.replace('"st_approved": "$st_approved"', '"st_approved": "$st_approved", "st_approved_solo": "$st_approved_solo"', 1))
    assert "st_approved_solo" in json.dumps(c["expr"])
    c["version"] = c.get("version", 1) + 1
    c["description_nl"] = c.get("description_nl", "") + " 2026-10-09: st_approved_solo - the approved line for a desk with no team (no 'add your team')."
    p.write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    import store  # noqa: E402,F401
    from core import engine  # noqa: E402
    engine._cache["at"] = 0.0
    c = json.loads(p.read_text(encoding="utf-8"))
    for t in c.get("test_cases", []):
        if "expect_value" in t:
            t["expect_value"] = engine.run("ui.firm", t.get("args") or {})
    p.write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("ui.firm st_approved_solo:", solo)

j = Path("static/page-firm.js")
s = j.read_text(encoding="utf-8")
a = "`st_${f.state}`, { hours"
b = "f.state === d.settings.working_state && !('team' in d) ? 'st_approved_solo' : `st_${f.state}`, { hours"
if b not in s:
    assert s.count(a) == 1
    j.write_text(s.replace(a, b), encoding="utf-8")
    print("page-firm.js")
