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
MODULES = ["firms", "itr_json", "analytics", "portal_stats", "server", "delegation", "chipchat", "chatfam", "notes", "dock_issues", "itr_import", "clients", "intake", "recon", "compute", "edition", "tourvideo", "manuals", "projects", "scan", "source", "keyshare",
           "keysales", "wallet", "guideme"]
SCREENS = ["firm", "analytics", "delegate", "clients", "itrimport", "intake", "recon", "compute", "manuals", "howto", "guideme", "tourvideo", "setup", "keys", "buykey", "keysales", "approvals", "portalstats", "server"]


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
        # 2026-10-04 owner: multi-select Archive; a client takes its filings with it; a filing alone leaves the client active
        ay_ = c.get("/api/clients/settings").json()["current_ay"]
        two = c.post("/api/clients", json={"name": "Sample Two", "status": "individual", "pan": "BBBPS1234K"}).json()
        for x in (cl, two):
            assert c.put(f"/api/clients/{x['id']}/years/{ay_}", json={}).status_code == 200
        yr = lambda cid: c.get(f"/api/clients/{cid}").json()["years"][ay_]  # noqa: E731
        got = c.post("/api/clients/archive", json={"ids": [cl["id"], two["id"]], "archived": True}).json()
        assert got["done"] == 2 and {cl["id"], two["id"]} <= set(ids("archived")) and yr(cl["id"]).get("archived_at"), "bulk archive takes every filing"
        assert c.post("/api/clients/archive", json={"ids": [cl["id"], two["id"]], "archived": False}).json()["done"] == 2
        assert not yr(cl["id"]).get("archived_at") and cl["id"] in ids(""), "Restore brings the client and its filings back"
        assert c.post(f"/api/clients/{two['id']}/years/{ay_}/archive", json={"archived": True}).status_code == 200
        assert two["id"] in ids("") and two["id"] in ids("archived") and yr(two["id"]).get("archived_at"), "a filing alone: the client stays active"
        c.post("/api/clients/archive", json={"ids": [two["id"]], "archived": True})
        assert c.post(f"/api/clients/{two['id']}/years/{ay_}/archive", json={"archived": False}).status_code == 400, "no filing back under an archived client"
        c.post("/api/clients/archive", json={"ids": [two["id"]], "archived": False})
        assert yr(two["id"]).get("archived_at"), "a filing archived on its own stays archived when its client comes back"
        assert c.post(f"/api/clients/{two['id']}/years/{ay_}/archive", json={"archived": False}).status_code == 200 and not yr(two["id"]).get("archived_at")
        big = c.post("/api/clients/archive", json={"ids": [f"x{i}" for i in range(c.get("/api/clients/settings").json().get("bulk_max", 500) + 1)], "archived": True})
        assert big.status_code == 400, "a bulk press over chip clients.settings bulk_max is refused"
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
        stage = lambda: next(r["stage"] for r in c.get("/api/lists/clients", params={"ay": "2026-27"}).json()["rows"] if r["id"] == cl["id"])  # noqa: E731
        assert stage() == "reconciling", "a red finding keeps the year in Reconciling - by itself"
        cb = f"/api/compute/{cl['id']}/2026-27"
        assert c.post(f"{cb}/signoff", json={"on": True}).status_code == 400, "no sign-off with a red finding"
        red = next(x for x in d["findings"] if x["severity"] == "red")
        c.put(f"{rb}/notes/{red['id']}", json={"note": "checked with the client"})
        assert stage() == "review", "explained -> Review, nobody moved it"
        # the same statement again: offered as a replacement, refs kept
        again = c.post(base, files={"file": ("books.xlsx", buf.getvalue())})
        assert again.status_code == 409 and again.json()["detail"]["replace"] == f["id"]
        assert c.post(f"{base}?replace={f['id']}", files={"file": ("books.xlsx", buf.getvalue())}).json()["counts"]["tagged"] >= 10
        assert c.post(rb, files={"file": ("26as-new.txt", recon.SAMPLE_26AS.encode() + b" ")}).status_code == 409, "one 26AS: replace, not add"
        # Compute & close: the computation, the three files, sign-off, filed = closed, every write refused
        cd = c.get(cb).json()
        assert cd["income"] > 0 and cd["tax"]["total"] > 0 and cd["tds_total"] > 0 and cd["balance"]["kind"] in ("payable", "refund", "nil"), cd
        assert "valid" in c.get(f"{cb}/itr-check").json() and c.get(f"{cb}/itr.json").json()["ITR"], "the ITR JSON is made and checked"
        assert "valid" in c.get(f"{cb}/3cd-check").json() and c.get(f"{cb}/3cd.json").json()["FORM3CB"], "the 3CD JSON is made and checked"
        for part in ("computation.xlsx", "utility.zip", "3cd.xlsx"):
            assert c.get(f"{cb}/{part}").status_code == 200, part
        assert c.post(f"{cb}/file", json={"ack_no": "998877665544332"}).status_code == 409, "filing needs a sign-off"
        assert c.post(f"{cb}/signoff", json={"on": True}).json()["signed"] and stage() == "signed"
        assert c.post(f"{cb}/file", json={"ack_no": "123"}).status_code == 409, "a 15-digit acknowledgement"
        assert c.post(f"{cb}/file", json={"ack_no": "998877665544332", "filed_on": "2099-01-01"}).status_code == 409, "not filed in the future"
        fl = c.post(f"{cb}/file", json={"ack_no": "998877665544332"}).json()          # filed today: original / belated by the dates
        assert fl["locked"] and fl["current"]["kind"] in ("original", "belated", "updated") and stage() == "filed", fl["current"]
        assert c.post(base, files={"file": ("more.csv", b"a,1")}).status_code == 409, "a filed year takes no new statement"
        assert c.put(cb, json={"interest": 10}).status_code == 409 and c.post(rb, files={"file": ("x.txt", b"x")}).status_code == 409
        # a revision: opened, discarded (closed again), opened, filed as revised - the original kept as superseded
        assert not c.post(f"{cb}/revise").json()["locked"]
        assert c.post(f"{cb}/discard").json()["locked"]
        rv = c.post(f"{cb}/revise").json()
        assert rv["revising"] and not rv["signed"], "a revision needs a fresh sign-off"
        c.post(f"{cb}/signoff", json={"on": True})
        fl = c.post(f"{cb}/file", json={"ack_no": "998877665544333"}).json()
        assert fl["current"]["kind"] in ("revised", "updated") and [x["status"] for x in fl["filings"]] == ["superseded", "current"], fl["filings"]
        # undo a wrong 'filed': a reason is needed, the record stays as withdrawn
        assert c.post(f"{cb}/withdraw", json={}).status_code == 409
        wd = c.post(f"{cb}/withdraw", json={"note": "wrong ack typed"}).json()
        assert not wd["locked"] and wd["revising"] and wd["filings"][-1]["status"] == "withdrawn" and wd["current"]["ack_no"] == "998877665544332",             "a revised return undone: the original stands again, the revision is open"
        # Firms (tenants): sign up -> papers -> wait -> the portal admin approves -> team; another firm's client is not there
        firm_check(app, c, cl["id"])
    print(f"  api: owner, menu, {sum(1 for r in app.app.routes if '/api/' in getattr(r, 'path', ''))} routes, clients -> intake -> reconcile -> compute -> filed -> revised -> withdrawn OK")


def firm_check(app, owner, house_cid: str) -> None:
    from fastapi.testclient import TestClient
    assert owner.post("/api/firm/start", json={"kind": "ca_firm"}).status_code == 409, "the portal admin keeps the house register"
    r = owner.post("/api/users", json={"email": "ca@pvr.example", "password": "a-good-password-1", "display_name": "P V Rao"})
    assert r.status_code == 200, r.text
    ca = TestClient(app.app)
    assert ca.post("/api/auth/signin", json={"identity": "ca@pvr.example", "password": "a-good-password-1"}).status_code == 200
    assert ca.get("/api/clients/settings").status_code == 403, "no firm, no Filing"
    assert ca.get("/api/firm").json()["firm"] is None
    f = ca.post("/api/firm/start", json={"kind": "ca_firm"}).json()
    good = {"name": "Prabhakar PVR & Co", "pan": "AAFFP1234C", "tan": "HYDP12345E", "gstin": "36AAFFP1234C1Z5", "frn": "012345S",
            "owner_name": "P V Rao", "aadhaar_last4": "4821", "phone": "+91 98490 12345", "email": "ca@pvr.example", "consent": True}
    assert ca.put("/api/firm", json=good | {"aadhaar_last4": "1234 5678 9012"}).status_code == 400, "a full Aadhaar is refused, never kept"
    assert ca.put("/api/firm", json=good | {"tan": "BAD"}).json()["ready"]["say"] == "bad_tan", "a draft keeps a half-typed field"
    me = ca.put("/api/firm", json=good).json()
    assert me["phone"] == "9849012345" and me["ready"]["say"] == "need_docs"
    assert ca.post(f"/api/firm/{f['id']}/move", json={"action": "submit"}).status_code == 400, "papers first"
    assert ca.post("/api/firm/docs/pan_card", files={"file": ("pan.exe", b"x")}).status_code == 400
    for k in ("owner_aadhaar", "pan_card", "tan_letter", "gst_cert"):
        assert ca.post(f"/api/firm/docs/{k}", files={"file": (f"{k}.pdf", b"%PDF-1.4 x")}).status_code == 200, k
    assert ca.post(f"/api/firm/{f['id']}/move", json={"action": "approve"}).status_code == 409, "a firm cannot approve itself"
    assert ca.post(f"/api/firm/{f['id']}/move", json={"action": "submit"}).json()["state"] == "submitted"
    assert ca.put("/api/firm", json=good).status_code == 409, "frozen while it waits"
    assert ca.get("/api/clients/settings").status_code == 403, "not approved yet"
    q = owner.get("/api/lists/firm_requests?state=submitted").json()
    assert [x["id"] for x in q["rows"]] == [f["id"]] and q["rows"][0]["sla"] == "on_time"
    doc = q["rows"][0]["docs"][0]
    assert owner.get(f"/api/firm/{f['id']}/docs/{doc['id']}").status_code == 200, "the portal admin reads the papers"
    assert ca.get("/api/approvals").status_code == 403
    assert ca.get("/api/lists/firm_requests").status_code == 403, "the queue is the portal admin's"
    assert owner.post(f"/api/firm/{f['id']}/move", json={"action": "return"}).status_code == 400, "a return needs a note"
    assert owner.post(f"/api/firm/{f['id']}/move", json={"action": "approve"}).json()["state"] == "approved"
    # the firm works in its own register; the portal admin's house client does not exist for it, nor its for the admin
    assert ca.get(f"/api/clients/{house_cid}").status_code == 404 and ca.get(f"/api/intake/{house_cid}/2026-27").status_code == 404
    mine = ca.post("/api/clients", json={"name": "Shree Ganesh Agarwal HUF", "status": "huf", "pan": "AAAHG4321K"}).json()
    assert owner.get(f"/api/clients/{mine['id']}").status_code == 404, "a firm's client is the firm's"
    assert [x["id"] for x in ca.get("/api/lists/clients").json()["rows"]] == [mine["id"]]
    # the team: a preparer works, but does not sign off
    p = ca.post("/api/firm/team", json={"name": "Ravi", "email": "ravi@pvr.example", "role": "preparer"}).json()
    assert p["password"] and p["member"]["role"] == "preparer"
    prep = TestClient(app.app)
    assert prep.post("/api/auth/signin", json={"identity": "ravi@pvr.example", "password": p["password"]}).status_code == 200
    assert prep.post("/api/auth/password", json={"current": p["password"], "password": "ravi-own-password-2", "confirm": "ravi-own-password-2"}).status_code == 200
    assert prep.get(f"/api/compute/{mine['id']}/2026-27").status_code == 200
    assert prep.post(f"/api/compute/{mine['id']}/2026-27/signoff", json={"on": True}).status_code == 403, "a preparer does not sign off"
    assert not prep.get("/api/bootstrap").json()["access"]["compute"]["functions"]["signoff"], "nor sees the button"
    assert ca.put(f"/api/firm/team/{me['created_by']}", json={"role": "partner"}).status_code == 400, "the last firm admin stays"
    owner.post(f"/api/firm/{f['id']}/move", json={"action": "suspend", "note": "papers expired"})
    assert ca.get("/api/clients/settings").status_code == 403, "suspended = Filing shut"
    # an individual / HUF files their own return: approved -> their one client is themselves, and no second one
    owner.post("/api/users", json={"email": "ganesh@huf.example", "password": "a-good-password-3", "display_name": "Ganesh"})
    me2 = TestClient(app.app)
    me2.post("/api/auth/signin", json={"identity": "ganesh@huf.example", "password": "a-good-password-3"})
    f2 = me2.post("/api/firm/start", json={"kind": "self"}).json()
    me2.put("/api/firm", json={"name": "Shree Ganesh Agarwal HUF", "pan": "AAAHG4321K", "owner_name": "Ganesh Agarwal",
                               "aadhaar_last4": "1111", "phone": "9000000001", "email": "ganesh@huf.example", "consent": True})
    for k in ("owner_aadhaar", "pan_card"):
        me2.post(f"/api/firm/docs/{k}", files={"file": (f"{k}.jpg", b"jpg")})
    assert me2.post(f"/api/firm/{f2['id']}/move", json={"action": "submit"}).status_code == 200
    owner.post(f"/api/firm/{f2['id']}/move", json={"action": "approve"})
    own = me2.get("/api/lists/clients").json()["rows"]
    assert [x["pan"] for x in own] == ["AAAHG4321K"], own
    assert me2.post("/api/clients", json={"name": "X", "status": "individual", "pan": "ABCPX1234K"}).status_code == 409


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
        ("* 10000 + 401", "the AY's start -> chip compute.settings year_start_mmdd (year_day)"),
        ("* 10000 + 331", "the year's end -> chip compute.settings year_end_mmdd (year_day)"),
        ('in ("revise", "withdraw")', "which moves clear the sign-off -> chip close.settings clear_signoff_on"),
    ],
    "recon.py": [
        ("e[\"kind\"] in (\"tds\", \"income\") and e[\"gross\"]:\n            g = ", "income from every source at once -> recon.settings income_sources"),
    ],
    "static/page-compute.js": [
        ("s_recon:", "which steps are done -> chip close.steps (the page only draws d.steps)"),
        ("d.has_26as && !d.open_red", "which steps are done -> chip close.steps"),
        ("open_red ?", "the verdict is the server's open_red count, not a rule in the page"),
    ],
    "firms.py": [
        ('"approved"', "the working state -> chip firm.settings working_state"),
        ('"submitted"', "the waiting state -> chip firm.settings waiting_state"),
        ('"ca_firm"', "a kind of account -> chip firm.settings kinds"),
        ('("pan", "tan"', "which fields are codes -> chip firm.settings code_fields"),
        ('in ("return", "reject")', "which moves need a note -> chip firm.settings needs_note"),
    ],
    "itr_json.py": [
        ('"94A"', "a TDS section code -> chip itr.codes sections"),
        ('== "individual"', "who is a person -> chip itr.codes person_statuses"),
        ('"NRI" if', "residential codes -> chip itr.codes residential"),
        ('"Y" if', "Y/N flags -> chip itr.codes flags"),
        ("* 10000 + 331", "the year's end -> chip compute.settings year_end_mmdd (compute.year_day)"),
        ('== "3CA"', "which audit form -> chip tar.settings form_by_status"),
        ('"We" if', "the report's voice -> chip tar.codes voice"),
        ('"NEFT"', "a payment mode code -> chip tar.codes modes"),
    ],
    "static/page-firm.js": [
        ("f.state === 'approved'", "the state's look -> chip page.firm"),
        ("['returned', 'rejected'", "which states show the note -> chip page.firm note_states"),
    ],
    "static/page-recon.js": [
        ("['tds', 'tds_claim']", "which findings belong to which check -> chip page.recon checks"),
    ],
}
REQUIRED_CHIPS = ["chat.examples", "chat.surprise", "chat.next", "chat.train", "notes.settings", "notes.list_view", "issues.mine_view", "chat.families", "chat.fee_234f", "chat.pan_kind", "chat.pick", "ui.chatfam", "chat.settings", "chat.faq", "chat.route", "ui.chipchat", "page.dock", "ui.dock", "delegation.settings", "delegation.check", "delegation.covers", "ui.delegate", "server.settings", "server.disk", "server.backup", "server.site", "server.trend", "ui.server", "page.server", "portalstats.settings", "portalstats.firm", "portalstats.rollup", "ui.portalstats", "itr.read", "itr.codes_in", "itr.import_ok", "itr.statement", "ui.itrimport", "analytics.settings", "analytics.client", "analytics.rollup", "ui.analytics", "page.analytics", "compute.settings", "compute.tax", "compute.tax_parts", "compute.balance", "compute.regime", "compute.total_income",
                  "compute.hp", "close.move", "close.settings", "close.signoff", "close.steps", "recon.settings", "page.recon",
                  "page.intake", "ui.compute",
                  "firm.settings", "firm.roles", "firm.problem", "firm.ready", "firm.move", "firm.may", "firm.sla", "firm.steps",
                  "firm.client_room", "firm.team_ok", "ui.firm", "page.firm",
                  "close.stage", "close.dates", "close.ack_ok", "close.itr_u", "compute.interest", "compute.paid_kind", "compute.no_advance",
                  "compute.refund_interest", "itr.settings", "itr.codes", "itr.map", "itr.books", "intake.suggest", "intake.row_sign", "intake.amount_col",
                  "tar.settings", "tar.columns", "tar.codes", "tar.map"]


MAIN = '\nif __name__ == "__main__":'


def leaks_in(text: str, rules: list) -> list[str]:
    return [why for needle, why in rules if needle in text]


def chips_first_check() -> None:
    # the guard itself first: it must catch a planted leak, and pass clean code
    assert leaks_in("x = min(sum(a), max(gti, 0))", LEAKS["compute.py"]), "the guard no longer sees a planted leak"
    assert not leaks_in("x = 1", LEAKS["compute.py"])
    found = [f"{name}: {why}" for name, rules in LEAKS.items()
             for why in leaks_in((HERE / name).read_text(encoding="utf-8").split(MAIN)[0], rules)]  # a self-test may name things
    assert not found, "decisions are back in code:\n  " + "\n  ".join(found)
    missing = [c for c in REQUIRED_CHIPS if not (HERE / "chips" / f"{c}.json").exists()]
    assert not missing, f"chips missing: {missing}"
    print(f"  chips first: no decision in code ({sum(len(r) for r in LEAKS.values())} shapes watched), {len(REQUIRED_CHIPS)} chips present OK")


GUIDED = ["firm", "analytics", "clients", "itrimport", "intake", "recon", "compute", "approvals"]


def guides_tours_check() -> None:
    """Every Firm / Filing screen has its Guide me (chip guide.<screen>) and its Tour Video script (tours/sf-<screen>.json),
    and the video says what the walk says - the tour is made from the guide, so a new step in one shows up in the other."""
    import json  # noqa: PLC0415
    for sc in GUIDED:
        g = json.loads((HERE / "chips" / f"guide.{sc}.json").read_text(encoding="utf-8"))
        d = {p["name"]: p["default"] for p in g["params"]}
        t = json.loads((HERE / "tours" / f"sf-{sc}.json").read_text(encoding="utf-8"))
        says = [x["say"] for x in t["steps"]]
        want = [d["lede"].replace("{product}", "SimplyFile")] + [x["say"].replace("{product}", "SimplyFile") for x in d["steps"]]
        assert says == want, f"tours/sf-{sc}.json is not the Guide me walk of {sc} - rebuild it from chip guide.{sc}"
    print(f"  guides and tours: {len(GUIDED)} screens, each tour = its Guide me OK")


if __name__ == "__main__":
    print("SimplyFile - self-check")
    module_checks()
    static_checks()
    chips_first_check()
    guides_tours_check()
    api_check()
    print("All checks passed.")
