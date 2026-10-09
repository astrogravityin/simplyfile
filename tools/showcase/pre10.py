"""Before part 10 (My return, the review) - Anil Kumar Demo's return gets what he would type on Review: a plot sold (cost from
2010, the cheaper of 12.5% and 20% with indexation; two exemptions on it - 54EC bonds and a new house under 54F, each inside its
time limit; the buyer's PAN as in the 26AS's Part IV), a co-owned flat let out, two gifts (an uncle's - a relative - and a friend's),
online-game winnings and a crypto sale, self-assessment tax paid, his son's interest clubbed, salary arrears for FY 2022-23 (s.89),
an account abroad he can sign for (Schedule FA table D), and an updated return (ITR-U) for AY 2024-25 - short-term gains at that
year's 15%, with 234C. The losses brought forward are not typed: the film fills them from last year's ITR-3 (dropped in part 9).
Run after part 9 (his documents are in). Data dir = argv[1]; --dump prints the body only. All made up.
"""
import pathlib as _pl; _R = str(_pl.Path(__file__).resolve().parents[2])  # the repo root
import json
import os
import sys

BODY = {
    "cg_rows": [{"asset": "land", "name": "Plot 42, Demo Layout, Shadnagar", "acquired": "2010-06-01", "sold": "2025-11-10", "sale": 4800000,
                 "cost": 1200000, "expenses": 48000, "stamp": 4600000, "buyer": "Demo Buyer", "buyer_pan": "ZZDPB0050B",
                 "address": "Plot 42, Demo Layout, Shadnagar", "pin": "509216", "other_houses": 1,
                 "ex_kind": "54EC", "ex_amount": 2000000, "ex_on": "2026-01-15",
                 "ex_kind_1": "54F", "ex_amount_1": 1500000, "ex_on_1": "2026-03-20"}],
    "houses": [{"kind": "let", "rent": 360000, "municipal_tax": 12000, "interest": 180000, "share": 50, "co_name": "Sunita Demo", "co_pan": "ZZDPS0043S"}],
    "gifts": [{"from": "Demo Uncle", "relation": "parent_sibling", "kind": "money", "value": 200000, "on": "2025-10-02"},
              {"from": "Demo Friend", "relation": "", "occasion": "", "kind": "money", "value": 75000, "on": "2025-12-25"}],
    "edits": {"other": {"online_games": 12000}},
    "answers": {"games_on": "2025-08-15", "father": "Demo Father", "state": "36", "foreign": True},
    "vda": [{"name": "Demo Coin", "acquired": "2024-05-01", "transferred": "2025-09-01", "cost": 50000, "sale": 65000}],
    "paid": [{"kind": "self", "date": "2026-07-10", "amount": 25000, "bsr": "0510002", "challan": "00042"}],
    "club_rows": [{"name": "Demo Son", "relation": "minor_child", "head": "interest", "amount": 30000}],
    "arrears": [{"fy": "2022-23", "amount": 120000, "income": 300000, "regime": ""}],
    "fa_rows": [{"kind": "signing", "country": "2", "name": "Demo Bank NA", "address": "1 Demo Plaza, Seattle", "zip": "98101",
                 "holder": "Demo Father", "account": "US4201", "peak": 600000, "income": 0}],
    "itru": {"ay": "2024-25", "filed": "original", "orig_income": 1500000, "add_111a": 200000, "tds": 150000, "advance": 0, "regime": "new",
             "reason": "2", "on": "2026-10-07"},
}
if "--dump" in sys.argv:
    print(json.dumps(BODY))
    sys.exit(0)
os.environ["TV_DATA"] = os.environ["PORTAL_DATA"] = sys.argv[1]
sys.path.insert(0, _R)
os.chdir(_R)
import app  # noqa: E402,F401 - registers chips and the catalog
import clients  # noqa: E402
import myreturn  # noqa: E402
from core import store  # noqa: E402

c = next(x for x in clients._all() if x["pan"] == "ZZDPK0042Q")  # noqa: SLF001
me = next(u for u in store.users() if u.get("firm_id") == c.get("firm_id"))
ay = clients.settings()["current_ay"]
w = myreturn.answer(me, c["id"], ay, BODY)
g = w["regimes"][w["regime"]]
print("pre10:", w["form"]["form"], w["regime"], "income", g["tax"]["total"], "balance", g["balance"], "| checks", [x["what"] for x in w["checks"] if x["level"] != "ok"])
