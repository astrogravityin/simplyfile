"""SimplyFile self-check - proves the whole portal works, with no paid call and nothing kept afterwards.

    python selfcheck.py

1. every module's own self-check (the framework's core/*.py and SimplyFile's *.py that carry one)
2. every chip certified (core/chips + chips): references resolve, every test case holds
3. the browser side: every page module the shell imports exists, and no page imports one that is not here
4. the API, on a throw-away data folder: the owner's first account, the menu is SimplyFile's eleven screens, every
   screen's GET routes answer without a server error, and Clients -> Intake & map -> Reconcile end to end
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable
MODULES = ["clients", "intake", "recon", "compute", "edition", "tourvideo", "manuals", "projects", "scan", "source", "keyshare",
           "keysales", "wallet", "guideme"]
SCREENS = ["clients", "intake", "recon", "compute", "manuals", "howto", "guideme", "tourvideo", "setup", "keys", "buykey", "keysales"]


def run(args: list[str], what: str) -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        env = os.environ | {"TV_DATA": str(Path(tmp) / "data"), "PYTHONIOENCODING": "utf-8"}
        r = subprocess.run([PY, *args], cwd=HERE, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise SystemExit(f"FAILED {what}:\n{(r.stdout + r.stderr)[-2000:]}")
    print(f"  {what} OK")


def module_checks() -> None:
    for p in sorted((HERE / "core").glob("*.py")):
        if "__main__" in p.read_text(encoding="utf-8") and p.stem != "__init__":
            run(["-m", f"core.{p.stem}"], f"core.{p.stem}")
    for m in MODULES:
        if "__main__" in (HERE / f"{m}.py").read_text(encoding="utf-8"):
            run([f"{m}.py"], m)
    run(["-m", "core.engine", "chips"], "chips certified")


def static_checks() -> None:
    app_js = (HERE / "static" / "app.js").read_text(encoding="utf-8")
    for f in sorted((HERE / "static").glob("*.js")) + sorted((HERE / "core" / "static").glob("*.js")):
        for imp in re.findall(r"""^\s*import\s[^'"]*?from\s*['"]([^'"]+)['"]""", f.read_text(encoding="utf-8"), re.M):
            target = (f.parent / imp).resolve() if not imp.startswith("../core-static/") else HERE / "core" / "static" / imp.split("/", 2)[2]
            assert target.exists(), f"{f.name} imports {imp}, which is not here"
    views = re.search(r"views: \{([^}]*)\}", app_js).group(1)
    assert sorted(x.split(":")[0].strip() for x in views.split(",") if x.strip()) == sorted(SCREENS), views
    print("  static: every import resolves, one page per screen OK")


def api_check() -> None:
    from fastapi.testclient import TestClient
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        os.environ["TV_DATA"] = str(Path(tmp) / "data")
        os.environ.pop("PORTAL_EDITION", None)
        sys.path.insert(0, str(HERE))
        import app  # noqa: PLC0415 - after TV_DATA
        import recon  # noqa: PLC0415
        c = TestClient(app.app)
        boot = c.get("/api/bootstrap").json()
        assert boot["needs_first_account"] is True
        assert "<title>SimplyFile" in c.get("/").text
        assert c.get("/health").text == "ok"
        assert c.get("/api/clients/settings").status_code == 401, "signed-out callers get nothing"
        r = c.post("/api/auth/first-account", json={"email": "owner@example.com", "password": "a-good-password"})
        assert r.status_code == 200, r.text
        boot = c.get("/api/bootstrap").json()
        menu = [s["id"] for s in boot["catalog"] if s["id"] in SCREENS]
        assert menu == SCREENS, menu
        words = c.get(f"/api/core/words?screens={','.join(SCREENS + ['app', 'shell'])}").json()["words"]
        assert all(words.get(s) for s in ("clients", "intake", "recon", "app")), "a screen has no words"
        bad = []
        for route in app.app.routes:
            path, methods = getattr(route, "path", ""), getattr(route, "methods", set()) or set()
            if "GET" in methods and "{" not in path and path.startswith("/api/"):
                code = c.get(path).status_code
                if code >= 500:
                    bad.append(f"{path} {code}")
        assert not bad, f"server errors: {bad}"
        # Clients -> Intake & map -> Reconcile
        cl = c.post("/api/clients", json={"name": "Sample HUF", "status": "huf", "pan": "AAAHS1234K"}).json()
        assert c.post("/api/clients", json={"name": "X", "status": "individual", "pan": "AAAHS1234K"}).status_code == 400
        ids = lambda view: [r["id"] for r in c.get("/api/lists/clients", params={"view": view}).json()["rows"]]  # noqa: E731
        assert c.post(f"/api/clients/{cl['id']}/archive", json={"archived": True}).status_code == 200
        assert cl["id"] not in ids("") and cl["id"] in ids("archived"), "an archived client moves to the Archived tab"
        assert c.post(f"/api/clients/{cl['id']}/archive", json={"archived": False}).status_code == 200
        assert cl["id"] in ids("") and cl["id"] not in ids("archived"), "Restore brings it back"
        import openpyxl  # noqa: PLC0415
        wb = openpyxl.Workbook()
        ws = wb.active
        for row in [["", "TOTAL INCOME STATEMENT"], ["", "Rent received from the premises", "", 3202838],
                    ["", "Interest on SB a/c", "", 2700], ["", "Interest from Acme Traders Pvt Ltd", "", 460000],
                    ["", "Less: TDS as per certificates from"], ["", "HDFC Bank Ltd", "", 26793],
                    ["", "Acme Traders Pvt Ltd", "", 46000], ["", "Yes Bank", "", 320284],
                    ["", "Advance tax paid on", "13.06.25", 450000], ["", "", "14.09.25", 4000000],
                    ["", "", "13.12.25", 5000000], ["", "", "13.03.26", 1500000]]:
            ws.append(row)
        buf = io.BytesIO()
        wb.save(buf)
        base = f"/api/intake/{cl['id']}/2026-27"
        f = c.post(base, files={"file": ("books.xlsx", buf.getvalue())}).json()
        assert f["counts"]["suggested"] >= 10, f
        assert c.post(f"{base}/{f['id']}/accept").json()["counts"]["tagged"] >= 10
        assert c.get(f"{base}/{f['id']}/download").status_code == 200
        rb = f"/api/recon/{cl['id']}/2026-27"
        assert c.post(rb, files={"file": ("26as.txt", recon.SAMPLE_26AS.encode())}).status_code == 200
        d = c.get(rb).json()
        assert d["summary"]["red"] == 1 and d["open_red"] == 1, d["summary"]
        assert c.put(f"/api/clients/{cl['id']}/years/2026-27", json={"stage": "review"}).status_code == 400, "red blocks review"
        red = next(x for x in d["findings"] if x["severity"] == "red")
        c.put(f"{rb}/notes/{red['id']}", json={"note": "checked with the client"})
        assert c.put(f"/api/clients/{cl['id']}/years/2026-27", json={"stage": "review"}).status_code == 200
        # Compute & close: the computation, the three files, sign-off, filed = closed, every write refused, reopen
        cb = f"/api/compute/{cl['id']}/2026-27"
        cd = c.get(cb).json()
        assert cd["income"] > 0 and cd["tax"]["total"] > 0 and cd["tds_total"] > 0 and cd["balance"]["kind"] in ("payable", "refund", "nil"), cd
        for part in ("computation.xlsx", "utility.zip", "3cd.xlsx"):
            assert c.get(f"{cb}/{part}").status_code == 200, part
        assert c.post(f"{cb}/file", json={"ack_no": "123"}).status_code == 409, "filing needs a sign-off"
        assert c.post(f"{cb}/signoff", json={"on": True}).json()["signed"]
        assert c.post(f"{cb}/file", json={"ack_no": ""}).status_code == 409, "filing needs the acknowledgement"
        assert c.post(f"{cb}/file", json={"ack_no": "998877665544332"}).json()["locked"]
        assert c.post(base, files={"file": ("more.csv", b"a,1")}).status_code == 409, "a filed year takes no new statement"
        assert c.put(cb, json={"interest": 10}).status_code == 409 and c.post(rb, files={"file": ("x.txt", b"x")}).status_code == 409
        assert not c.post(f"{cb}/reopen").json()["locked"]
    print(f"  api: owner, menu, {sum(1 for r in app.app.routes if '/api/' in getattr(r, 'path', ''))} routes, clients -> intake -> reconcile -> compute -> filed -> reopen OK")


# Chips-first guard (2026-10-04 audit). Every rate, threshold and decision of the Filing screens is a chip; these are the
# shapes they had when they slipped into code once. A match means a decision came back - put it in its chip instead.
LEAKS = {
    "compute.py": [
        ("r[\"statuses\"]", "which regime a status may use -> chip compute.regime / compute.settings status_regimes"),
        ("max(gti", "deductions capped at gross total income -> chip compute.total_income"),
        ("min(sum(", "deductions capped at gross total income -> chip compute.total_income"),
        ("* k[\"hp_std_pct\"]", "the 30% of house property -> chip compute.hp"),
        ("-k[\"hp_loss_cap\"]", "the house-property loss cap -> chip compute.hp"),
        ("if on and d[\"open_red\"]", "sign-off with red findings -> chip close.signoff"),
        ("== \"26as\"] or portal", "where the credit is read from -> compute.settings credit_sources"),
        (", \"OS\")", "the default head in the utility CSV -> compute.settings csv_head_default"),
        ("2400000", "a slab edge -> compute.settings regimes"),
        ("20000000", "a surcharge band -> compute.settings regimes"),
        ("cess_pct = 4", "the cess rate -> compute.settings cess_pct"),
    ],
    "recon.py": [
        ("e[\"kind\"] in (\"tds\", \"income\") and e[\"gross\"]:\n            g = ", "income from every source at once -> recon.settings income_sources"),
    ],
    "static/page-compute.js": [
        ("s_recon:", "which steps are done -> chip close.steps (the page only draws d.steps)"),
        ("d.has_26as && !d.open_red", "which steps are done -> chip close.steps"),
        ("open_red ?", "the verdict is the server's open_red count, not a rule in the page"),
    ],
    "static/page-recon.js": [
        ("['tds', 'tds_claim']", "which findings belong to which check -> chip page.recon checks"),
    ],
}
REQUIRED_CHIPS = ["compute.settings", "compute.tax", "compute.tax_parts", "compute.balance", "compute.regime", "compute.total_income",
                  "compute.hp", "close.move", "close.settings", "close.signoff", "close.steps", "recon.settings", "page.recon",
                  "page.intake", "ui.compute"]


def leaks_in(text: str, rules: list) -> list[str]:
    return [why for needle, why in rules if needle in text]


def chips_first_check() -> None:
    # the guard itself first: it must catch a planted leak, and pass clean code
    assert leaks_in("x = min(sum(a), max(gti, 0))", LEAKS["compute.py"]), "the guard no longer sees a planted leak"
    assert not leaks_in("x = 1", LEAKS["compute.py"])
    found = [f"{name}: {why}" for name, rules in LEAKS.items()
             for why in leaks_in((HERE / name).read_text(encoding="utf-8"), rules)]
    assert not found, "decisions are back in code:\n  " + "\n  ".join(found)
    missing = [c for c in REQUIRED_CHIPS if not (HERE / "chips" / f"{c}.json").exists()]
    assert not missing, f"chips missing: {missing}"
    print(f"  chips first: no decision in code ({sum(len(r) for r in LEAKS.values())} shapes watched), {len(REQUIRED_CHIPS)} chips present OK")


if __name__ == "__main__":
    print("SimplyFile - self-check")
    module_checks()
    static_checks()
    chips_first_check()
    api_check()
    print("All checks passed.")
