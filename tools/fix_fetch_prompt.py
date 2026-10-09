"""2026-10-08: a live OpenAI fetch gave null for 24 of 41 figures because they were not restated for the year ("80C limit
not restated ... likely 1.5 lakh"). A figure the law did not change carries forward - the prompt now says so: give the
figure in force with note "unchanged", null only when the law changed it and the new value cannot be found. Run from
D:/Simplyfile (re-runnable)."""
import json
from pathlib import Path

ADD = (" A figure that no Finance Act, notification or circular has changed CARRIES FORWARD: give the value in force for"
       " AY {ay} (usually the one shown for AY {live_ay}) with note \"unchanged - <the provision, e.g. s.80C>\"; do not give"
       " null just because the figure is not restated for the year. Give null only when the law changed the figure and you"
       " cannot find the new value.")
p = Path("chips/taxwatch.settings.json")
c = json.loads(p.read_text(encoding="utf-8"))
pr = next(x for x in c["params"] if x["name"] == "prompt")
anchor = "If AY {ay} has not been announced yet, or you are not sure, give null and say why in note."
if "CARRIES FORWARD" not in pr["default"]:
    assert anchor in pr["default"]
    new = pr["default"].replace(anchor, anchor + ADD)
    s = json.dumps(c, ensure_ascii=False).replace(json.dumps(pr["default"], ensure_ascii=False)[1:-1], json.dumps(new, ensure_ascii=False)[1:-1])
    c = json.loads(s)
    c["version"] += 1
    c["description_nl"] += " 2026-10-08: prompt - unchanged figures carry forward (a live fetch gave null for 24 of 41)."
    p.write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("taxwatch.settings prompt")
