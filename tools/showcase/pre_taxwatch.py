"""Before part 12 (Tax rules) - a Fetch's answer for the next AY, saved as Fetch would leave it, with NO AI call: every figure as it
is today except four made-up changes (the new regime's standard deduction, its first slab, the 80C cap and the ITR-1/ITR-2 due
date), three figures not announced yet, and one change that is not a figure. Sources point at demo.example - nothing here is a
real announcement. Dated 40 days ago, so the "check again" reminder shows. Data dir = argv[1].
"""
import pathlib as _pl; _R = str(_pl.Path(__file__).resolve().parents[2])  # the repo root
import copy
import datetime
import os
import sys

os.environ["TV_DATA"] = os.environ["PORTAL_DATA"] = sys.argv[1]
sys.path.insert(0, _R)
os.chdir(_R)
import store as _portal_store  # noqa: E402,F401 - registers the portal's chips, as the app does
import taxwatch  # noqa: E402
from core import store  # noqa: E402

live = taxwatch.settings()["live_ay"]
ay = taxwatch._ay_next(live)  # noqa: SLF001
rows = taxwatch.compare(ay)["rows"]
vals = {r["id"]: copy.deepcopy(r["live"]) for r in rows}
SRC = "https://demo.example/made-up-finance-bill"
vals["std_new"] = 100000
for band in vals["slabs_new"]:
    vals["slabs_new"][band][0]["upto"] = 500000
vals["cap_80c"] = 200000
vals["due"] = 815
note = {"std_new": "Made up for the film: standard deduction raised.", "slabs_new": "Made up for the film: nil slab up to 5 lakh.",
        "cap_80c": "Made up for the film: 80C cap raised.", "due": "Made up for the film: ITR-1 / ITR-2 due 15 August."}
for gone in ("surcharge_new", "surcharge_old", "updated_years"):      # not announced yet
    vals.pop(gone)
at = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=40)).isoformat(timespec="seconds")
store.write(f"taxwatch_{ay}", {
    "ay": ay, "live_ay": live, "at": at, "by": "owner", "model": "made-up draft (no AI)",
    "items": {k: {"value": v, "source": SRC if k in note else "", "note": note.get(k, "")} for k, v in vals.items()},
    "pages": [{"title": "A made-up finance bill (demo only)", "uri": SRC}, {"title": "A made-up circular (demo only)", "uri": "https://demo.example/made-up-circular"}],
    "new_rules": [{"what": "Made up for the film: a new fee on a return revised after 31 December", "who": "Anyone revising late", "source": SRC}]})
c = taxwatch.compare(ay)
print("pre_taxwatch:", ay, c["count"], "check due", c["check_due"])
