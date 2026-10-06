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
                                "items": {k: {"value": v, "source": "https://example.invalid/", "note": ""} for k, v in vals.items()},
                                "new_rules": [{"what": "A new fee on a revised return after 31 December", "who": "everyone revising", "source": "https://example.invalid/"}]})
c = taxwatch.compare(ay)
ok(c["new_rules"] and c["new_rules"][0]["what"].startswith("A new fee"), "a change that is not a figure is shown as needs building")
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
ch = taxwatch.ai_choices(u)
ok([a["provider"] for a in ch] == ["gemini", "openai"] and not any(a["ready"] for a in ch), f"Gemini and OpenAI offered, neither ready without a key: {ch}")
try:
    taxwatch.fetch(u, taxwatch._ay_next(taxwatch.settings()["live_ay"]), "openai")  # noqa: SLF001
    ok(False, "Fetch with no working key is refused")
except Exception as x:  # noqa: BLE001
    ok(getattr(x, "status_code", 0) == 400 and "No AI key that works" in str(getattr(x, "detail", "")), f"Fetch says why no AI can be asked: {getattr(x, 'detail', x)}")
# the live year checked again (2026-10-06): a circular extends the audit cases' date - this year only, the live year stays
live2 = taxwatch.settings()["live_ay"]
c2 = taxwatch.compare(live2)
vals2 = {r["id"]: copy.deepcopy(r["live"]) for r in c2["rows"]}
vals2["due_audit"] = 1215
cstore.write(f"taxwatch_{live2}", {"ay": live2, "live_ay": live2, "at": cstore.now(), "by": "test", "model": "none", "pages": [], "new_rules": [],
                                   "items": {k: {"value": v, "source": "https://example.invalid/circular", "note": "Circular 99/2099 (test)"} for k, v in vals2.items()}})
c2 = taxwatch.compare(live2)
ok([r["id"] for r in c2["rows"] if r["state"] == "changed"] == ["due_audit"], f"the live year checked again: one change {[r['id'] for r in c2['rows'] if r['state'] == 'changed']}")
taxwatch.apply(u, live2, ["due_audit"])
from core import engine as _e  # noqa: E402
cd = {p["name"]: p["default"] for p in _e.chips()["close.dates"]["params"]}
ok(cd["extensions"].get(live2[:4], {}).get("due_audit_mmdd") == 1215 and cd["due_audit_mmdd"] != 1215 and taxwatch.settings()["live_ay"] == live2,
   f"an extended date goes to that year only; the rule and the live year stay: {cd['extensions'].get(live2[:4])}, rule {cd['due_audit_mmdd']}")
ok(_e.run("close.dates", {"ay_year": int(live2[:4]), "audit": True})["due"] == int(live2[:4]) * 10000 + 1215, "the engine's due date is the extended one for that year")
# a Fetch on OpenAI end to end (2026-10-06 - the server's own environment has no openai package: plain HTTPS), OpenAI's reply stood in
import json as _json  # noqa: E402
import providers  # noqa: E402
store.save_keys_for(u["id"], {"openai_api_key": "sk-test-000000000000"})
live3 = taxwatch.settings()["live_ay"]
same = {r["id"]: {"value": r["live"], "source": "https://www.incometax.gov.in/", "note": ""} for r in taxwatch.compare(live3)["rows"]}
same["_new"] = [{"what": "Test: a new schedule", "who": "test", "source": "https://www.incometax.gov.in/"}]
seen = {}
providers._post_json = lambda url, key, body, t, extra_headers=None: (seen.update(url=url, tools=body.get("tools")) or {"output": [  # noqa: SLF001
    {"type": "web_search_call"}, {"type": "message", "content": [{"type": "output_text", "text": "```json\n" + _json.dumps(same) + "\n```",
                                                                  "annotations": [{"type": "url_citation", "url": "https://www.incometax.gov.in/x", "title": "ITD"}]}]}]})
got = taxwatch.fetch(u, live3, "openai")
ok(seen.get("url", "").endswith("/responses") and seen.get("tools") == [{"type": "web_search"}], f"OpenAI asked through its Responses API with web search: {seen}")
ok(got["fetched"] and got["count"]["changed"] == 0 and got["pages"] and got["new_rules"], f"its answer read: {got['count']}, {len(got['pages'])} source(s), {len(got['new_rules'])} new rule(s)")
print("ALL PASS" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
