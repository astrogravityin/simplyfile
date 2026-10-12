"""New filing's worked examples in the demo (2026-10-11 owner: "every demo use case must have demo data refreshed nightly"): each row
of chip wizard.cases is played through the wizard on a data dir - its who-card, its picks, its documents batch by batch, the popup's
answers (a firm's partners as its deed gives them) - and left at Review, so a visitor opens New filing and finds every path under
"Carry on where you left off", each with its client and documents in place (and carries it on into My return or Intake & map).
The documents: tools/showcase/make_myreturn_demo.py (tools/tour_video/showcase/<folder>/, made up). Run on a data dir after the
showcase parts (record_all.sh does): python pre_cases.py <data dir>. Re-runnable: a case whose filing is there already is skipped."""
import pathlib as _pl; _R = str(_pl.Path(__file__).resolve().parents[2])  # the repo root
import os
import sys

os.environ["TV_DATA"] = os.environ["PORTAL_DATA"] = sys.argv[1]
sys.path.insert(0, _R)
os.chdir(_R)
import app  # noqa: E402,F401 - registers chips and the catalog
import clients  # noqa: E402
import wizard  # noqa: E402
from core import engine, store  # noqa: E402

K = engine.run("wizard.cases")
ROOT = _pl.Path(_R) / K["folder_root"]
firm_admin = next(u for u in store.users() if u.get("firm_role") == "firm_admin" and u.get("firm_id"))
have = {(s.get("case") or "") for s in wizard._index(firm_admin)}  # noqa: SLF001
done = []
for c in K["rows"]:
    if c["id"] in have:
        continue
    v = wizard.start(firm_admin, {"who": c["who"], "ay": c["ay"], "picked": c["picks"], "step": "upload"})
    wid = v["id"]
    for batch in c["batches"]:
        for f in batch:
            v = wizard.upload(firm_admin, wid, f, (ROOT / c["folder"] / f).read_bytes())
        ans = {a: x for a, x in c["answers"].items() if a in [q["id"] for q in v["asks"]]}
        for q in v["asks"]:
            if q["id"] == "partners":
                ans["partners"] = q["partners"]
            if q["id"] == "company":                        # what the certificate said, with the case's option and manufacturing
                want = c["answers"].get("company") or {}
                ans["company"] = q["company"] | {"option": want.get("option", "normal"), "manufacturing": want.get("manufacturing") == "yes"}
        if ans:
            v = wizard.update(firm_admin, wid, {"answers": ans})
    v = wizard.update(firm_admin, wid, {"step": "review"})
    s = store.read(wizard._name(firm_admin, wid), {})  # noqa: SLF001
    s["case"] = c["id"]
    store.write(wizard._name(firm_admin, wid), s)  # noqa: SLF001
    cl = v["client"] or {}
    assert cl, f"{c['id']}: no client made - {v['asks']}"
    done.append(f"{c['id']}: {cl.get('name')} {v['form']['form']} -> {v.get('next')} ({sum(1 for x in v['cards'] if x['state'] in ('in', 'kept'))} docs)")
print("pre_cases:", len(done), "worked examples left at Review |", " | ".join(done) or "all there already")
