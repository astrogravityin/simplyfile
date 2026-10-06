"""Tax rules (Fetch, Compare, Apply) end to end in a scratch data folder, with no AI call: a hand-made AY 2027-28 draft is
compared and applied, then the live chips, the CA portal's past-year slabs, My return's tax and the History are checked.
Run from the repo root (D:/Simplyfile):

    python tools/e2e_taxwatch.py
"""
import copy
import os
import sys
import tempfile

os.environ["PORTAL_DATA"] = tempfile.mkdtemp(prefix="tw-e2e-")
os.environ["TV_DATA"] = os.environ["PORTAL_DATA"]
sys.path.insert(0, ".")
import store  # noqa: E402,F401 - maps the portal's settings and registers its chips, as the app does
from core import builder, engine  # noqa: E402
from core import store as cstore  # noqa: E402
import taxwatch  # noqa: E402

fails = []


def ok(cond, what):
    print(("PASS " if cond else "FAIL ") + what)
    if not cond:
        fails.append(what)


u = {"id": "u-owner", "email": "owner@demo.example", "role": "owner"}
live = taxwatch.settings()["live_ay"]
ay = taxwatch._ay_next(live)  # noqa: SLF001
c = taxwatch.compare(ay)
ok(not c["fetched"] and all(r["state"] == "unknown" for r in c["rows"]), f"nothing fetched for {ay}: every figure not announced")

# a draft as Fetch would leave it: every figure the same, except three
vals = {r["id"]: copy.deepcopy(r["live"]) for r in c["rows"]}
vals["std_new"] = 100000
vals["slabs_new"]["below60"][0]["upto"] = 500000
for b in ("60to80", "80plus"):
    vals["slabs_new"][b][0]["upto"] = 500000
vals["slabs_new"]["below60"][1]["upto"] = max(vals["slabs_new"]["below60"][1]["upto"], 900000)
vals["due"] = 815
vals["cess"] = "4"          # the wrong shape - must not count as a change
cstore.write(f"taxwatch_{ay}", {"ay": ay, "live_ay": live, "at": cstore.now(), "by": "test", "model": "none", "pages": [],
                                "items": {k: {"value": v, "source": "https://example.invalid/", "note": ""} for k, v in vals.items()}})
c = taxwatch.compare(ay)
changed = sorted(r["id"] for r in c["rows"] if r["state"] == "changed")
ok(changed == ["due", "slabs_new", "std_new"], f"three changes found: {changed}")
ok(next(r for r in c["rows"] if r["id"] == "cess")["state"] == "unknown", "a value of the wrong shape is not a change")

old_regimes = copy.deepcopy(next(p for p in engine.chips()["compute.settings"]["params"] if p["name"] == "regimes")["default"])
tax_before = engine.run("myreturn.tax", {"normal": 1300000, "regime": "new", "band": "below60"})
r = taxwatch.apply(u, ay, changed + ["rate_111a"])
print(" ", r["done"], "|", r["rebased"][:300])
ok(taxwatch.settings()["live_ay"] == ay, f"live figures now AY {ay}")
rates = engine.run("myreturn.rates")
ok(rates["std_deduction"]["new"] == 100000 and rates["slabs"]["new"]["below60"][0]["upto"] == 500000, "My return's rates moved")
cs = {p["name"]: p["default"] for p in engine.chips()["compute.settings"]["params"]}
ok(cs["regimes"][0]["slabs"][0]["upto"] == 500000, "CA portal's live new-regime slabs moved")
ok(cs["regimes_by_ay"].get(live) == old_regimes, f"CA portal keeps AY {live}'s slabs for past years")
ok(engine.run("close.dates", {"ay_year": int(ay[:4])})["due"] == int(ay[:4]) * 10000 + 815, "due date moved to 15 August")
tax_after = engine.run("myreturn.tax", {"normal": 1300000, "regime": "new", "band": "below60"})
ok(tax_after["tax"] < tax_before["tax"], f"tax on 13 L under the new figures is lower: {tax_before['tax']} -> {tax_after['tax']}")
ok((builder.root() / "chips" / "myreturn.rates.json").exists() and builder.history("chips", "myreturn.rates"), "published in the builder layer, with History")
ok(not engine.certify(), "every chip still certifies after Apply")
c = taxwatch.compare(taxwatch._ay_next(ay))  # noqa: SLF001
ok(c["live_ay"] == ay and not c["fetched"], "the next Fetch is for the year after")
print("ALL PASS" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
