"""2026-10-07: s.234A when CBDT extends a due date by circular (s.119). Circular 07/2026 is silent on interest; CBDT's earlier
extension orders (e.g. 9/2021, 17/2021) kept 234A running from the original due date where the tax owed (after advance tax,
TDS/TCS and reliefs) is over Rs 1 lakh (Explanation 1 to s.234A). The conservative reading is taken: an extended year charges
234A from the rule's own date when the owed tax is over the chip's limit. close.dates gives due_rule (the date without the
extension); chip compute.due_234a picks the date 234A counts from. Run from D:/Simplyfile."""
import json
from pathlib import Path

p = Path("chips/close.dates.json")
c = json.loads(p.read_text(encoding="utf-8"))
F = c["expr"]["fields"]


def unext(n):              # the extension lookups taken out: the rule's own date
    if isinstance(n, dict) and n.get("vop") == "coalesce" and len(n.get("values", [])) == 2 \
            and isinstance(n["values"][1], str) and n["values"][1].startswith("$due_") and n["values"][0].get("value") == "$extensions":
        return n["values"][1]
    if isinstance(n, dict):
        return {k: unext(v) for k, v in n.items()}
    if isinstance(n, list):
        return [unext(x) for x in n]
    return n


if "due_rule" not in F:
    F["due_rule"] = unext(F["due"])
    for t in c["test_cases"]:
        t["expect_value"] = None
    c["version"] += 1
    c["description_nl"] += " 2026-10-07: due_rule - the due date without a circular's extension (s.234A counts from it when the owed tax is over 1 lakh: compute.due_234a)."
    p.write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("close.dates due_rule")

chip = {"chip_id": "compute.due_234a", "kind": "accessor", "set": "compute", "label": "Compute: the date s.234A interest counts from",
        "aliases": ["234a due date", "extended due date interest"],
        "params": [{"name": "due", "type": "number", "default": 0, "label": "the due date as extended (YYYYMMDD)"},
                   {"name": "due_rule", "type": "number", "default": 0, "label": "the due date without the extension (YYYYMMDD)"},
                   {"name": "owed", "type": "number", "default": 0, "label": "tax on total income less advance tax, TDS/TCS and reliefs"},
                   {"name": "above", "type": "number", "default": 100000, "label": "over this, 234A runs from the rule's own date (Explanation 1 to s.234A, as CBDT's extension orders say)"}],
        "expr": {"vop": "choose", "cases": [{"when": {"op": "all", "items": [{"op": "gt", "left": "$due", "right": "$due_rule"},
                                                                              {"op": "gt", "left": "$due_rule", "right": 0},
                                                                              {"op": "gt", "left": "$owed", "right": "$above"}]}, "then": "$due_rule"}],
                 "else": "$due"},
        "returns": "number", "version": 1, "status": "published",
        "description_nl": ("2026-10-07: when CBDT extends a due date by circular, s.234A interest still runs from the original date if the "
                           "tax owed (after advance tax, TDS/TCS, reliefs) is over 1 lakh - as CBDT's extension orders (9/2021, 17/2021) "
                           "say; Circular 07/2026 is silent, so the safer reading is kept. Otherwise from the extended date."),
        "test_cases": [{"args": {"due": 20261121, "due_rule": 20261031, "owed": 250000}, "expect_value": 20261031},
                       {"args": {"due": 20261121, "due_rule": 20261031, "owed": 90000}, "expect_value": 20261121},
                       {"args": {"due": 20260731, "due_rule": 20260731, "owed": 900000}, "expect_value": 20260731}]}
Path("chips/compute.due_234a.json").write_text(json.dumps(chip, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("compute.due_234a")
