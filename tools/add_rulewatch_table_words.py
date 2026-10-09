"""2026-10-09 owner: Law updates showed court calendars (holidays, vacations) and court-fee slab tables as raw JSON - the
shared rule-watch page (static/page-rulewatch.js) now draws any list of rows as a compact table and a list of values as
chips, with added / changed (old -> new) / removed on Compare. Its words go into the domain's ui.<name> chip.

    python tools/add_rulewatch_table_words.py                       # chips/ui.taxwatch.json (SimplyFile)
    python tools/add_rulewatch_table_words.py D:/Justify/chips/ui.lawwatch.json

Re-runnable: the chip is written (and its version moves on) only when a word is missing or different."""
import json
import sys
from pathlib import Path

WORDS = {
    "t_yes": "Yes",
    "t_no": "No",
    "t_add": "added",
    "t_chg": "changed",
    "t_del": "removed",
    "t_add_n": "{n} added",
    "t_chg_n": "{n} changed",
    "t_del_n": "{n} removed",
    "t_gone": "Not in the fetched figures",
    "t_empty": "None",
    "c_id": "Id",
    "c_date": "Date",
    "c_name": "Name",
    "c_label": "What",
    "c_from": "From",
    "c_to": "To",
    "c_upto": "Up to",
    "c_per": "For every",
    "c_fee": "Fee",
    "c_fee_text": "Fee",
    "c_rate": "Rate",
    "c_where": "Where",
    "c_closed": "Closed for filing",
    "c_applies": "Applies to",
    "c_holidays": "Holidays",
    "c_vacations": "Vacations",
}
NOTE = ("2026-10-09: t_* / c_* - lists of rows (calendars, fee slabs) drawn as a table: column names c_<field>, "
        "added / changed / removed on Compare.")


def add(path: Path) -> bool:
    c = json.loads(path.read_text(encoding="utf-8"))
    names = {p["name"]: p for p in c["params"]}
    test = c["test_cases"][0]["expect_value"] if c.get("test_cases") and isinstance(c["test_cases"][0].get("expect_value"), dict) else None
    changed = False
    for k, v in WORDS.items():
        if k in names and names[k]["default"] == v and c["expr"]["fields"].get(k) == f"${k}" and (test is None or test.get(k) == v):
            continue
        changed = True
        if k in names:
            names[k]["default"] = v
        else:
            c["params"].append({"name": k, "type": "text", "default": v, "label": k.replace("_", " ")})
        c["expr"]["fields"][k] = f"${k}"
        if test is not None:
            test[k] = v
    if not changed:
        return False
    c["version"] = int(c.get("version") or 1) + 1
    if NOTE not in c.get("description_nl", ""):
        c["description_nl"] = (c.get("description_nl", "") + " " + NOTE).strip()
    path.write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return True


if __name__ == "__main__":
    p = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "chips" / "ui.taxwatch.json")
    print(p, "updated" if add(p) else "already has the words")
