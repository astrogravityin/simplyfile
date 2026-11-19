"""python tools/e2e_wizard.py

New filing (the wizard) end to end through the API, on a throw-away data folder (2026-10-11). Run after
tools/showcase/make_myreturn_demo.py (it writes the demo documents to tools/tour_video/showcase/wizard-*/, gitignored):
  A  a CA firm files for Demo Verma HUF: 26AS names the HUF -> the client is made; the popup asks only the Karta; the AIS shows a
     fund sale -> "upload the CAMS statement", gone once it is in; ITR-2; a file it does not know says Not recognised.
  B  a salaried client with capital gains: Form 16 names a PAN but no name -> the popup asks name + date of birth; the AIS is
     locked until the date is given, then opens by itself; 26AS shows a second employer's TAN and 194IA -> prompts; the second
     Form 16 and the CAMS PDF answer them; My return opens at the right step with the documents in.
  C  the walls: another firm cannot see the filing (404), a self-filer is offered only Myself, a filing carried on later, Discard.
  D  2026-10-11 later, the firm flow: a trust says not yet (409, no dead end); a trading firm with GST and a tax audit - the GST
     certificate names it, the deed's partners fill the popup, the client is made (status, GSTIN, partners, ITR-5 with audit), the
     books go to Intake & map, 26AS to Reconcile, the GSTR-3B zip to the tax audit, last year's ITR-5 is kept; Review opens Intake & map.
  E  a manufacturing firm already in the register is found by its GST certificate; its partners come from the deed.
  F  an LLP: an LLP certificate on a partnership-firm card is asked about and switched; an AOP is made from its agreement and 26AS.
  G  a company (ITR-6): its certificate of incorporation is read, the popup takes the option (115BAA), the company is made with its
     CIN and directors, ITR-6 with the audit, its books into Intake & map.
Prints PASS / FAIL per step; exits 1 on any FAIL."""
import os
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
os.chdir(HERE)
os.environ["TV_DATA"] = tempfile.mkdtemp(prefix="sf-wizard-")
sys.stdout.reconfigure(encoding="utf-8")
from fastapi.testclient import TestClient  # noqa: E402

import app  # noqa: E402

DOCS = HERE / "tools" / "tour_video" / "showcase"
AY = "2026-27"
results, S = [], {}


def step(name):
    def wrap(fn):
        try:
            got = fn()
            results.append(("PASS", name, got or ""))
        except Exception as e:  # noqa: BLE001
            results.append(("FAIL", name, f"{type(e).__name__}: {e}"))
            traceback.print_exc()
        return fn
    return wrap


def session(email, pw):
    s = TestClient(app.app)
    r = s.post("/api/auth/signin", json={"identity": email, "password": pw})
    assert r.status_code == 200, r.text
    return s


def send(s, wid, path, password="", on_same="", as_name=""):
    f = DOCS / path
    r = s.post(f"/api/wizard/{wid}/files", files={"file": (as_name or f.name, f.read_bytes())}, data={"password": password, "on_same": on_same})
    assert r.status_code == 200, r.text
    return r.json()


def card(v, name):
    return next(c for c in v["cards"] if c["name"] == Path(name).name)


admin = TestClient(app.app)
assert admin.post("/api/auth/first-account", json={"setup_code": app.auth.setup_code(), "email": "admin@valuestream.test", "password": "Admin-pass-123"}).status_code == 200
admin.post("/api/users", json={"email": "ca@demo.example", "password": "Demo-pass-1234", "display_name": "Demo Partner"})
ca = session("ca@demo.example", "Demo-pass-1234")


@step("0 A CA firm signs up and is approved; New filing shut until then, then open")
def _():
    assert ca.get("/api/wizard").status_code == 403, "no firm yet - Filing (and New filing) is shut"
    S["fid"] = ca.post("/api/firm/start", json={"kind": "ca_firm"}).json()["id"]
    ca.put("/api/firm", json={"name": "Demo Wizard CA Firm", "pan": "AAFFZ1234C", "tan": "HYDZ12345E", "gstin": "36AAFFZ1234C1Z5", "frn": "012399S",
                              "membership_no": "212399", "owner_name": "Demo Partner", "aadhaar_last4": "4821", "phone": "+91 90000 00009",
                              "email": "ca@demo.example", "address": "Demo Road, Hyderabad", "consent": True})
    for k in ("owner_aadhaar", "pan_card", "tan_letter", "gst_cert"):
        ca.post(f"/api/firm/docs/{k}", files={"file": (f"{k}.pdf", b"%PDF-1.4 demo")})
    assert ca.post(f"/api/firm/{S['fid']}/move", json={"action": "submit"}).json()["state"] == "submitted"
    assert admin.post(f"/api/firm/{S['fid']}/move", json={"action": "approve"}).json()["state"] == "approved"
    h = ca.get("/api/wizard").json()
    assert [w["id"] for w in h["who"]] == ["individual", "huf", "firm", "llp", "aop", "company"], h["who"]
    assert [w["id"] for w in h["not_yet"]] == ["trust"] and h["not_yet"][0]["note"] == "ny_trust", h["not_yet"]
    assert "salary" not in h["offered"]["huf"] and "salary" in h["offered"]["individual"], h["offered"]
    acc = ca.get("/api/bootstrap").json()["access"]
    assert acc["wizard"]["allowed"], acc.get("wizard")
    st = ca.get("/api/start", params={"screen": "clients"}).json()
    first = next(x for x in st["steps"] if x["id"] == "client")
    assert first["href"] == "#/wizard", first
    return f"who: {[w['id'] for w in h['who']]}; Start here: {first['label']}"


@step("A1 HUF: who + what applies -> the documents needed, the likely form (ITR-2, why_huf / why_cg)")
def _():
    assert ca.post("/api/wizard", json={"who": "huf", "picked": ["salary"]}).status_code == 400, "an HUF has no salary"
    v = ca.post("/api/wizard", json={"who": "huf", "picked": ["interest", "shares"]}).json()
    S["huf"] = v["id"]
    need = {d["id"]: d["need"] for d in v["docs"]}
    assert need.get("ais") == "required" and need.get("26as") == "required" and need.get("cg") == "required" and "form16" not in need, need
    assert v["form"]["form"] == "ITR-2", v["form"]
    assert v["client"] is None and v["asks"] == [] and v["prompts"] == [], v
    return f"docs {need}; form {v['form']}"


@step("A2 HUF: 26AS names the HUF -> client made; popup asks only the Karta")
def _():
    v = send(ca, S["huf"], "wizard-huf/1 26AS - ZZDHW0046M - AY 2026-27.txt")
    c = card(v, "1 26AS - ZZDHW0046M - AY 2026-27.txt")
    assert c["kind"] == "26as" and c["who"]["pan"] == "ZZDHW0046M" and c["state"] == "in", c
    assert v["client"] and v["client"]["pan"] == "ZZDHW0046M" and v["client"]["status"] == "huf" and v["client"]["made"], v["client"]
    assert [a["id"] for a in v["asks"]] == ["karta_name", "karta_pan"], v["asks"]
    assert ca.put(f"/api/wizard/{S['huf']}", json={"answers": {"karta_pan": "ZZDHW"}}).status_code == 400, "a PAN that is not a PAN"
    v = ca.put(f"/api/wizard/{S['huf']}", json={"answers": {"karta_name": "Demo Ramesh Verma", "karta_pan": "ZZDPV0049E"}}).json()
    assert v["asks"] == [], v["asks"]
    mr = ca.get(f"/api/myreturn/{v['client']['id']}/{AY}").json()
    assert mr["answers"].get("karta_name") == "Demo Ramesh Verma" and mr["answers"].get("karta_pan") == "ZZDPV0049E", mr["answers"]
    S["huf_cid"] = v["client"]["id"]
    return f"client {v['client']['name']} ({v['client']['pan']}), Karta saved in the return"


@step("A3 HUF: the AIS shows a fund sale -> 'upload the CAMS statement'; the CAMS PDF answers it")
def _():
    v = send(ca, S["huf"], "wizard-huf/2 AIS - ZZDHW0046M - FY 2025-26.csv")
    assert card(v, "2 AIS - ZZDHW0046M - FY 2025-26.csv")["state"] == "in"
    pr = [p["id"] for p in v["prompts"]]
    assert pr == ["cams"] and v["prompts"][0]["amount"] == 320000 and v["prompts"][0]["kind"] == "cg", v["prompts"]
    v = send(ca, S["huf"], "wizard-huf/3 CAMS capital gains - ZZDHW0046M - FY 2025-26.pdf")
    assert card(v, "3 CAMS capital gains - ZZDHW0046M - FY 2025-26.pdf")["kind"] == "cg" and v["prompts"] == [], v["prompts"]
    return f"prompt {pr} answered"


@step("A4 HUF: a file it does not know says Not recognised and stays out of the return; Remove takes it off")
def _():
    v = send(ca, S["huf"], "wizard-misc/Family trip notes.txt")
    c = card(v, "Family trip notes.txt")
    assert c["state"] == "other" and c["kind"] == "other" and c["problems"], c
    mr = ca.get(f"/api/myreturn/{S['huf_cid']}/{AY}").json()
    assert "Family trip notes.txt" not in [d["name"] for d in mr["docs"]] and len(mr["docs"]) == 3, [d["name"] for d in mr["docs"]]
    v = ca.delete(f"/api/wizard/{S['huf']}/files/{c['id']}").json()
    assert "Family trip notes.txt" not in [x["name"] for x in v["cards"]]
    return f"{len(mr['docs'])} documents in the return"


@step("A5 HUF: Review - form from the return, nothing missing, opens My return; finished leaves the resume list")
def _():
    v = ca.put(f"/api/wizard/{S['huf']}", json={"step": "review"}).json()
    assert v["form"]["form"] == "ITR-2" and v["form"].get("from") == "return", v["form"]
    assert v["link"].startswith(f"#/myreturn?c={S['huf_cid']}&ay={AY}&step=") and v["next"] in ("check", "choose", "review"), v.get("link")
    f = ca.post(f"/api/wizard/{S['huf']}/finish").json()
    assert f["link"] == v["link"]
    assert S["huf"] not in [x["id"] for x in ca.get("/api/wizard").json()["sessions"]]
    return f"{v['link']}"


@step("B1 Salaried + capital gains: Form 16 names a PAN, no name -> popup asks name and date of birth")
def _():
    v = ca.post("/api/wizard", json={"who": "individual", "picked": ["employers", "shares"]}).json()
    S["sal"] = v["id"]
    assert v["picked"] == ["employers", "salary", "shares"], v["picked"]
    need = {d["id"]: d["need"] for d in v["docs"]}
    assert need["form16"] == "required" and need["cg"] == "required" and v["form"]["form"] == "ITR-2", (need, v["form"])
    v = send(ca, S["sal"], "wizard-sal/1 Form 16 - Demo Analytics - AY 2026-27.pdf")
    c = card(v, "1 Form 16 - Demo Analytics - AY 2026-27.pdf")
    assert c["kind"] == "form16" and c["who"]["pan"] == "ZZDPR0047N" and c["state"] == "held", c
    assert v["client"] is None and [a["id"] for a in v["asks"]] == ["name", "dob"], v["asks"]
    return f"asks {[a['id'] for a in v['asks']]}"


@step("B2 The AIS is locked (PAN + date of birth) until the popup's date is given - then it opens by itself")
def _():
    v = send(ca, S["sal"], "wizard-sal/2 AIS - ZZDPR0047N - FY 2025-26.pdf")
    c = card(v, "2 AIS - ZZDPR0047N - FY 2025-26.pdf")
    assert c["state"] == "locked", c
    assert ca.put(f"/api/wizard/{S['sal']}", json={"answers": {"dob": "11/02/1986"}}).status_code == 400, "a date as yyyy-mm-dd"
    v = ca.put(f"/api/wizard/{S['sal']}", json={"answers": {"name": "Ravi Demo Salaried", "dob": "1986-02-11"}}).json()
    assert v["client"] and v["client"]["pan"] == "ZZDPR0047N" and v["client"]["dob"] == "1986-02-11" and v["client"]["made"], v["client"]
    assert v["asks"] == [], v["asks"]
    assert card(v, "1 Form 16 - Demo Analytics - AY 2026-27.pdf")["state"] == "in"
    c = card(v, "2 AIS - ZZDPR0047N - FY 2025-26.pdf")
    assert c["state"] == "in" and c["kind"] == "ais", c
    assert [p["id"] for p in v["prompts"]] == ["cams"], v["prompts"]
    S["sal_cid"] = v["client"]["id"]
    return f"client {v['client']['name']}; AIS opened; prompts {[p['id'] for p in v['prompts']]}"


@step("B3 26AS: a second employer's TAN and 194IA -> 'upload that Form 16', 'enter the property sale'")
def _():
    v = send(ca, S["sal"], "wizard-sal/3 26AS - ZZDPR0047N - AY 2026-27.txt")
    pr = {p["id"]: p for p in v["prompts"]}
    assert set(pr) == {"cams", "form16_more", "property"}, list(pr)
    assert pr["form16_more"]["tans"] == "HYDD00048H" and pr["property"]["amount"] == 6200000 and pr["property"]["step"] == "review", pr
    v = send(ca, S["sal"], "wizard-sal/4 Form 16 - Demo Cloud Services - AY 2026-27.pdf")
    v = send(ca, S["sal"], "wizard-sal/5 CAMS capital gains - ZZDPR0047N - FY 2025-26.pdf")
    assert [p["id"] for p in v["prompts"]] == ["property"], v["prompts"]
    return f"left: {[p['id'] for p in v['prompts']]}"


@step("B4 The same AIS again asks first (replace / keep), as My return does")
def _():
    again = "AIS downloaded again.pdf"
    v = send(ca, S["sal"], "wizard-sal/2 AIS - ZZDPR0047N - FY 2025-26.pdf", as_name=again)
    assert v.get("ask", {}).get("why") == "same" and again not in [c["name"] for c in v["cards"]], v.get("ask")
    v = send(ca, S["sal"], "wizard-sal/2 AIS - ZZDPR0047N - FY 2025-26.pdf", on_same="replace", as_name=again)
    assert not v.get("ask") and sum(1 for c in v["cards"] if c["kind"] == "ais" and c["state"] == "in") >= 1
    return "asked, then replaced"


@step("B5 Review: two employers in the return, the gains read; opens My return at Review (the property sale to type)")
def _():
    v = ca.put(f"/api/wizard/{S['sal']}", json={"step": "review"}).json()
    assert v["next"] == "review" and v["link"].endswith("&step=review"), (v["next"], v["link"])
    mr = ca.get(f"/api/myreturn/{S['sal_cid']}/{AY}").json()
    tans = sorted(e["tan"] for e in mr["return"]["employers"])
    assert tans == ["HYDD00047G", "HYDD00048H"], tans
    assert mr["form"]["form"] == "ITR-2" and v["form"]["form"] == "ITR-2", mr["form"]
    kinds = sorted(d["kind"] for d in mr["docs"])
    assert kinds.count("form16") == 2 and "cg" in kinds and "ais" in kinds and "26as" in kinds, kinds
    return f"{v['link']}; documents {kinds}"


@step("C1 Tenant wall: another firm's person never sees the filing (404), a self-filer is offered only Myself")
def _():
    admin.post("/api/users", json={"email": "self@demo.example", "password": "Self-pass-12345", "display_name": "Demo Self"})
    me = session("self@demo.example", "Self-pass-12345")
    fid = me.post("/api/firm/start", json={"kind": "self"}).json()["id"]
    me.put("/api/firm", json={"name": "Demo Self Filer", "pan": "ZZDPS0050F", "owner_name": "Demo Self Filer", "aadhaar_last4": "1111",
                              "phone": "9000000050", "email": "self@demo.example", "consent": True})
    assert me.post(f"/api/firm/{fid}/move", json={"action": "submit"}).json()["state"] == "approved"
    assert me.get(f"/api/wizard/{S['sal']}").status_code == 404
    assert me.put(f"/api/wizard/{S['sal']}", json={"step": "docs"}).status_code == 404
    assert me.delete(f"/api/wizard/{S['sal']}").status_code == 404
    h = me.get("/api/wizard").json()
    assert [w["id"] for w in h["who"]] == ["self"] and h["sessions"] == [], h
    assert me.post("/api/wizard", json={"who": "individual", "picked": []}).status_code == 400
    v = me.post("/api/wizard", json={"who": "self", "picked": ["salary"]}).json()
    assert v["client"] and v["client"]["pan"] == "ZZDPS0050F" and v["self"], v["client"]
    v = send(me, v["id"], "wizard-huf/1 26AS - ZZDHW0046M - AY 2026-27.txt")
    assert v["cards"][0]["state"] == "other_pan", v["cards"][0]
    return "404 x3; self-filer: Myself only, another PAN's 26AS kept out"


@step("C2 Carry on later: the open filing is listed with its step; Discard drops it, the client and return stay")
def _():
    h = ca.get("/api/wizard").json()
    row = next((x for x in h["sessions"] if x["id"] == S["sal"]), h["sessions"])
    assert row["step"] == "review" and row["files"] >= 5 and row["client"] == "Ravi Demo Salaried", row
    assert ca.get(f"/api/wizard/{S['sal']}").json()["step"] == "review"
    h = ca.delete(f"/api/wizard/{S['sal']}").json()
    assert S["sal"] not in [x["id"] for x in h["sessions"]]
    assert ca.get(f"/api/wizard/{S['sal']}").status_code == 404
    assert ca.get(f"/api/myreturn/{S['sal_cid']}/{AY}").json()["docs"], "the return stays"
    return "listed, discarded, return kept"


FT = "case-firm-trading/"


@step("D0 A trust (ITR-7) says not yet - starting one is refused with its words; a firm's cards are its own")
def _():
    r = ca.post("/api/wizard", json={"who": "trust", "picked": []})
    assert r.status_code == 409 and "not in" in r.json()["detail"], r.text
    h = ca.get("/api/wizard").json()
    off = h["offered"]["firm"]
    assert "salary" not in off and "house" not in off and "partners_pay" in off and "presumptive" in off and "trading" in off, off
    assert "presumptive" not in h["offered"]["llp"] and "partners_pay" not in h["offered"]["aop"] and "presumptive" not in h["offered"]["company"]
    ny = next(x for x in h["not_yet"] if x["id"] == "trust")
    assert ny["instead"] == "individual" and ny["form"] == "ITR-7" and ny["flow"] == "firm", ny
    return "trust: 409 not yet; the card offers an individual's return instead"


@step("D1 Trading firm: what kind of work -> ITR-5 with a tax audit; the firm's documents listed (no Form 16)")
def _():
    v = ca.post("/api/wizard", json={"who": "firm", "picked": ["trading", "gst", "audit", "partners_pay", "stock", "depreciation"]}).json()
    S["ft"] = v["id"]
    assert v["flow"] == "firm" and v["work_open"] and "books" in v["picked"] and "business" not in v["picked"], v["picked"]
    assert v["form"] == {"form": "ITR-5", "why": "why_e_audit", "from": "wizard"}, v["form"]
    need = {d["id"]: d["need"] for d in v["docs"]}
    for d in ("gst_cert", "deed", "books", "26as", "stock_list", "asset_register"):
        assert need.get(d) == "required", (d, need)
    assert "form16" not in need and "prefill" not in need and need.get("gst_json") == "optional", need
    return f"picked {v['picked']}; docs {sorted(need)}"


@step("D2 The GST certificate and the deed are told apart; the popup shows the deed's partners before the client is made")
def _():
    v = send(ca, S["ft"], FT + "1 GST certificate - Demo Balaji Traders.pdf")
    c = card(v, "1 GST certificate - Demo Balaji Traders.pdf")
    assert c["kind"] == "gst_cert" and c["who"]["pan"] == "ZZDFB0057J" and c["who"]["gstin"] == "36ZZDFB0057J1Z3" and c["who"]["status"] == "firm", c
    assert v["client"] is None and [a["id"] for a in v["asks"]] == ["partners"], v["asks"]
    v = send(ca, S["ft"], FT + "2 Partnership deed - Demo Balaji Traders.pdf")
    c = card(v, "2 Partnership deed - Demo Balaji Traders.pdf")
    assert c["kind"] == "deed" and len(c["who"]["partners"]) == 3, c
    a = v["asks"][0]
    assert a["id"] == "partners" and [p["pan"] for p in a["partners"]] == ["ZZDPR0071A", "ZZDPR0072B", "ZZDPR0073C"], a
    assert ca.put(f"/api/wizard/{S['ft']}", json={"answers": {"partners": [{"name": "X", "pan": "BAD"}]}}).status_code == 400
    return f"partners from the deed: {[p['name'] for p in a['partners']]}"


@step("D3 Partners confirmed -> the client is made (partnership firm, GSTIN, 3 partners), its year ITR-5 with the audit")
def _():
    v = ca.get(f"/api/wizard/{S['ft']}").json()
    v = ca.put(f"/api/wizard/{S['ft']}", json={"answers": {"partners": v["asks"][0]["partners"]}}).json()
    c = v["client"]
    assert c and c["status"] == "firm" and c["made"] and c["gst"] == "36ZZDFB0057J1Z3" and c["partners"] == 3 and c["name"] == "DEMO BALAJI TRADERS", c
    assert v["asks"] == [], v["asks"]
    full = ca.get(f"/api/clients/{c['id']}").json()
    y = full["years"][AY]
    assert y["form"] == "ITR-5" and y["audit"] is True and not y.get("presumptive"), y
    assert all(x["state"] == "in" and x["dest"] == "client" for x in v["cards"]), [(x["kind"], x["state"], x.get("dest")) for x in v["cards"]]
    S["ft_cid"] = c["id"]
    return f"{c['name']} {c['pan']} {c['gst']}; {AY}: ITR-5, audit"


@step("D4 Each document into its screen: books -> Intake & map, 26AS -> Reconcile, GSTR-3B zip -> tax audit, ITR-5 kept")
def _():
    for f in ("3 26AS - ZZDFB0057J - AY 2026-27.txt", "4 Demo Balaji Traders - Trading, P&L and Balance Sheet AY 2026-27.xlsx",
              "5 Demo Balaji Traders - IT Stmt, Dep, Loans AY 2026-27.xlsx", "6 GSTR-3B - 36ZZDFB0057J1Z3 - FY 2025-26.zip",
              "7 ITR-5 AY 2025-26 - Demo Balaji Traders - ZZDFB0057J.json"):
        v = send(ca, S["ft"], FT + f)
    dest = {x["kind"]: (x["state"], x["dest"]) for x in v["cards"]}
    assert dest["26as"] == ("in", "recon") and dest["books"] == ("in", "intake") and dest["gst_json"] == ("in", "gst") and dest["itr_prev"] == ("kept", "keep"), dest
    cid = S["ft_cid"]
    assert len(ca.get(f"/api/intake/{cid}/{AY}").json()["files"]) == 2
    assert len(ca.get(f"/api/recon/{cid}/{AY}").json()["files"]) == 1
    au = ca.get(f"/api/audit/{cid}/{AY}").json()
    assert len(au["gst"]["files"]) == 12, au["gst"].get("files")
    assert [p["id"] for p in v["prompts"]] == ["stock", "dep", "itr_prev", "audit_3cd"], v["prompts"]
    v = send(ca, S["ft"], FT + "3 26AS - ZZDFB0057J - AY 2026-27.txt", as_name="26AS again.txt")
    assert card(v, "26AS again.txt")["already"] is True and len(ca.get(f"/api/recon/{cid}/{AY}").json()["files"]) == 1
    return f"{dest}; hints {[p['id'] for p in v['prompts']]}"


@step("D5 Review -> the next firm screen (the books carry their SF Refs and 26AS is in: Tax audit); Remove takes a book out of Intake & map too")
def _():
    v = ca.put(f"/api/wizard/{S['ft']}", json={"step": "review"}).json()
    assert v["next"] == "audit" and v["link"] == f"#/audit?c={S['ft_cid']}&ay={AY}", (v["next"], v["link"])
    b = next(x for x in v["cards"] if x["name"].startswith("5 Demo"))
    v = ca.delete(f"/api/wizard/{S['ft']}/files/{b['id']}").json()
    assert len(ca.get(f"/api/intake/{S['ft_cid']}/{AY}").json()["files"]) == 1
    f = ca.post(f"/api/wizard/{S['ft']}/finish").json()
    assert f["link"] == v["link"]
    return v["link"]


@step("E1 Manufacturing firm already in the register: its GST certificate finds it; the deed's partners are added")
def _():
    c0 = ca.post("/api/clients", json={"name": "Lakshmi Narayana Textiles", "pan": "AAGFL5512K", "status": "firm", "ay": AY}).json()
    v = ca.post("/api/wizard", json={"who": "firm", "picked": ["manufacturing", "gst", "audit", "stock", "depreciation"]}).json()
    S["fm"] = v["id"]
    for f in ("1 GST certificate - Lakshmi Narayana Textiles.pdf", "2 Partnership deed - Lakshmi Narayana Textiles.pdf"):
        v = send(ca, S["fm"], "case-firm-mfg/" + f)
    assert [a["id"] for a in v["asks"]] == ["partners"] and len(v["asks"][0]["partners"]) == 2, v["asks"]
    v = ca.put(f"/api/wizard/{S['fm']}", json={"answers": {"partners": v["asks"][0]["partners"]}}).json()
    assert v["client"]["id"] == c0["id"] and not v["client"]["made"] and v["client"]["partners"] == 2 and v["client"]["gst"] == "36AAGFL5512K1Z2", v["client"]
    v = send(ca, S["fm"], "case-firm-mfg/4 Lakshmi Narayana Textiles - Manufacturing, P&L and Balance Sheet AY 2026-27.xlsx")
    assert card(v, "4 Lakshmi Narayana Textiles - Manufacturing, P&L and Balance Sheet AY 2026-27.xlsx")["dest"] == "intake"
    assert ca.get(f"/api/clients/{c0['id']}").json()["years"][AY]["audit"] is True
    return f"found {v['client']['name']}; partners {v['client']['partners']}"


@step("F1 LLP: an LLP certificate on a partnership-firm card is asked about and switched; then made as an LLP")
def _():
    v = ca.post("/api/wizard", json={"who": "firm", "picked": ["services", "books"]}).json()
    S["llp"] = v["id"]
    v = send(ca, S["llp"], "case-llp/1 GST certificate - Demo Pixel Works LLP.pdf")
    assert "status" in [a["id"] for a in v["asks"]] and v["asks"][0]["kind"] == "llp", v["asks"]
    v = ca.put(f"/api/wizard/{S['llp']}", json={"answers": {"status": "switch"}}).json()
    assert v["who"] == "llp" and "status" not in [a["id"] for a in v["asks"]], (v["who"], v["asks"])
    v = send(ca, S["llp"], "case-llp/2 LLP agreement - Demo Pixel Works LLP.pdf")
    v = ca.put(f"/api/wizard/{S['llp']}", json={"answers": {"partners": v["asks"][0]["partners"]}}).json()
    assert v["client"]["status"] == "llp" and v["client"]["partners"] == 2, v["client"]
    v = send(ca, S["llp"], "case-llp/3 26AS - ZZDFP0058K - AY 2026-27.txt")
    v = send(ca, S["llp"], "case-llp/4 Demo Pixel Works LLP - Income statement AY 2026-27.xlsx")
    assert v["form"]["form"] == "ITR-5" and v["form"]["why"] == "why_e_books", v["form"]
    return f"{v['client']['name']} as LLP"


@step("F2 AOP: made from its agreement and 26AS (PAN letter A), the members in the popup")
def _():
    v = ca.post("/api/wizard", json={"who": "aop", "picked": ["services", "books"]}).json()
    S["aop"] = v["id"]
    v = send(ca, S["aop"], "case-aop/1 Agreement of association - Demo Residents Welfare Association.pdf")
    v = send(ca, S["aop"], "case-aop/2 26AS - ZZDAR0059L - AY 2026-27.txt")
    assert [a["id"] for a in v["asks"]] == ["partners"] and len(v["asks"][0]["partners"]) == 3, v["asks"]
    v = ca.put(f"/api/wizard/{S['aop']}", json={"answers": {"partners": v["asks"][0]["partners"]}}).json()
    assert v["client"]["status"] == "aop" and v["client"]["pan"] == "ZZDAR0059L", v["client"]
    v = send(ca, S["aop"], "case-aop/3 Demo Residents Welfare Association - Income statement AY 2026-27.xlsx")
    assert card(v, "3 Demo Residents Welfare Association - Income statement AY 2026-27.xlsx")["dest"] == "intake"
    return f"{v['client']['name']} (AOP)"


CO = "case-company-trading/"


@step("G1 Company (ITR-6): the certificate of incorporation is read (CIN, date, directors); the popup asks the option before the client")
def _():
    v = ca.post("/api/wizard", json={"who": "company", "picked": ["trading", "gst", "audit"]}).json()
    S["co"] = v["id"]
    assert v["flow"] == "firm" and v["form"]["form"] == "ITR-6" and v["form"]["why"] == "why_e_audit", v["form"]
    need = {d["id"]: d["need"] for d in v["docs"]}
    assert need.get("coi") == "required" and need.get("books") == "required" and need.get("comp_income") == "required" and "deed" not in need, need
    v = send(ca, S["co"], CO + "00 Certificate of incorporation - Zenith Demo Traders.pdf")
    c = card(v, "00 Certificate of incorporation - Zenith Demo Traders.pdf")
    assert c["kind"] == "coi" and c["who"]["pan"] == "ZZDCZ0061K" and c["who"]["company"]["cin"] == "U51909TG2018PTC000061", c
    assert len(c["who"]["company"]["directors"]) == 2 and c["who"]["company"]["incorporated"] == "2018-06-14", c["who"]["company"]
    a = next(x for x in v["asks"] if x["id"] == "company")
    assert v["client"] is None and a["company"]["cin"] == "U51909TG2018PTC000061" and "115BAA" in [o["id"] for o in a["co_options"]], a
    return f"asks {[x['id'] for x in v['asks']]}; options {[o['id'] for o in a['co_options']]}"


@step("G2 Company: option 115BAA confirmed -> the company is made (status company, CIN, directors), ITR-6 with the audit; books into Intake & map")
def _():
    v = ca.get(f"/api/wizard/{S['co']}").json()
    co = next(x for x in v["asks"] if x["id"] == "company")["company"] | {"option": "115BAA", "manufacturing": "no"}
    assert ca.put(f"/api/wizard/{S['co']}", json={"answers": {"company": "x"}}).status_code == 400
    v = ca.put(f"/api/wizard/{S['co']}", json={"answers": {"company": co}}).json()
    c = v["client"]
    assert c and c["status"] == "company" and c["made"] and c["pan"] == "ZZDCZ0061K", c
    full = ca.get(f"/api/clients/{c['id']}").json()
    assert full["company"]["cin"] == "U51909TG2018PTC000061" and full["company"]["option"] == "115BAA" and len(full["company"]["directors"]) == 2, full["company"]
    assert full["years"][AY]["form"] == "ITR-6" and full["years"][AY]["audit"] is True, full["years"][AY]
    for f in ("00 GST certificate - Zenith Demo Traders.pdf", "01 Final accounts - Zenith Demo Traders FY 2025-26.xlsx", "04 26AS - ZZDCZ0061K - AY 2026-27.txt"):
        v = send(ca, S["co"], CO + f)
    dest = {x["kind"]: x["dest"] for x in v["cards"]}
    assert dest["coi"] == "client" and dest["gst_cert"] == "client" and dest["books"] == "intake" and dest["26as"] == "recon", dest
    assert ca.get(f"/api/clients/{c['id']}").json()["gst"] == "36ZZDCZ0061K1Z5"
    v = ca.put(f"/api/wizard/{S['co']}", json={"step": "review"}).json()
    assert v["link"].startswith(f"#/") and v["next"] in ("intake", "audit", "recon", "compute"), v.get("link")
    return f"{c['name']} - ITR-6, 115BAA; opens {v['next']}"


@step("G3 A trust still says not yet")
def _():
    r = ca.post("/api/wizard", json={"who": "trust"})
    assert r.status_code == 409, r.text
    assert "company" in [w["id"] for w in ca.get("/api/wizard").json()["who"]]


@step("C3 Every /api/wizard route is guarded")
def _():
    anon = TestClient(app.app)
    for m, p in (("get", "/api/wizard"), ("post", "/api/wizard"), ("get", "/api/wizard/abc123"), ("put", "/api/wizard/abc123"),
                 ("delete", "/api/wizard/abc123"), ("post", "/api/wizard/abc123/finish"), ("delete", "/api/wizard/abc123/files/abc")):
        r = getattr(anon, m)(p, **({"json": {}} if m in ("post", "put") else {}))
        assert r.status_code in (401, 403), (m, p, r.status_code)


for st, name, got in results:
    print(f"{st} {name}" + (f"  - {got}" if got else ""))
bad = [r for r in results if r[0] == "FAIL"]
print(f"\n{len(results) - len(bad)}/{len(results)} PASS")
sys.exit(1 if bad else 0)
