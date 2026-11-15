"""SimplyFy self-check - proves the whole portal works, with no paid call and nothing kept afterwards.

    python selfcheck.py

1. every module's own self-check (the framework's core/*.py and SimplyFy's *.py that carry one)
2. every chip certified (core/chips + chips): references resolve, every test case holds
3. the browser side: every page module the shell imports exists, and no page imports one that is not here
4. the API, on a throw-away data folder: the owner's first account, the menu is SimplyFy's eleven screens, every
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
MODULES = ["firms", "itr_json", "myreturn", "myreturn_read", "wizard", "wizard_firm", "rulewatch", "taxwatch", "rulebook", "analytics", "portal_stats", "server", "delegation", "chipchat", "chatfam", "notes", "dock_issues", "itr_import", "clients", "intake", "recon", "compute", "company", "audit", "changelog", "edition", "tourvideo", "manuals", "projects", "scan", "source", "keyshare",
           "keysales", "wallet", "guideme"]
SCREENS = ["firm", "analytics", "delegate", "wizard", "clients", "myreturn", "itrimport", "intake", "recon", "compute", "audit", "manuals", "howto", "guideme", "tourvideo", "setup", "keys", "buykey", "keysales", "approvals", "portalstats", "server", "taxwatch"]


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
    # 2026-11-15 owner (Tour Video Record did nothing on every portal): a confirmDialog callback runs after the click is
    # over, when e.currentTarget is null and busy(null) quietly returns - hold the button first, never pass the event on
    _late = [f"{f.relative_to(HERE)}:{n}" for f in sorted((HERE / "static").glob("*.js")) + sorted((HERE / "core" / "static").glob("*.js"))
             for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1)
             if re.search(r"confirmDialog\(.*=>[^;]*\(e\)", line)]
    assert not _late, f"a confirmDialog callback reuses the click event (busy(null) does nothing): {_late}"
    # 2026-11-15 owner (live tf, 800 px): People & access scrolled sideways - its six columns are cards up to tablet width
    _pcss = (HERE / "core" / "static" / "portal.css").read_text(encoding="utf-8")
    _card = re.search(r"@media \(max-width:(\d+)px\)\{#acc-people thead\{display:none\}", _pcss)
    assert _card and int(_card.group(1)) >= 1024, "People & access: the people table must turn into cards up to 1024 px (portal.css people-phone-card)"
    assert "const choose = (r) => { clearTimeout(st.timer);" in (HERE / "core" / "static" / "ui.js").read_text(encoding="utf-8"), \
        "pickList: a pick must drop the pending search, or the list reopens over the page (2026-11-09)"
    # 2026-11-08 VUI go-live: DEPLOY.md's unit had no Environment=PORT=, so deploy.sh (which reads it) stopped every update
    unit = (HERE / "DEPLOY.md").read_text(encoding="utf-8") if (HERE / "DEPLOY.md").is_file() else ""
    if "--port " in unit:   # a hand-written unit (VPS Console's New site writes its own, with the line)
        unit_port = re.search(r"^Environment=PORT=(\S+)$", unit, re.M)
        assert unit_port and f"--port {unit_port.group(1)}" in unit, "DEPLOY.md's unit needs Environment=PORT=<its --port> (deploy.sh reads it)"
    app_js = (HERE / "static" / "app.js").read_text(encoding="utf-8")
    for f in sorted((HERE / "static").glob("*.js")) + sorted((HERE / "core" / "static").glob("*.js")):
        for imp in re.findall(r"""^\s*import\s[^'"]*?from\s*['"]([^'"]+)['"]""", f.read_text(encoding="utf-8"), re.M):
            target = (f.parent / imp).resolve() if not imp.startswith("../core-static/") else HERE / "core" / "static" / imp.split("/", 2)[2]
            assert target.exists(), f"{f.name} imports {imp}, which is not here"
    views = re.search(r"views: \{([^}]*)\}", app_js).group(1)
    assert sorted(x.split(":")[0].strip() for x in views.split(",") if x.strip()) == sorted(SCREENS), views
    # 2026-10-06 the marketing film (chip promo.film, tools/showcase/promo_film.py) plays on the login pitch (edition.settings
    # tour): the pitch never points at a missing file, and the film's chip never names footage that is not here (from JustyFy)
    ed = json.loads((HERE / "chips" / "edition.settings.json").read_text(encoding="utf-8"))["test_cases"][0]["expect_value"]
    for row in ed["rows"]:
        for k in ("video", "captions", "poster") if row.get("tour") else ():
            assert (HERE / "static" / "tour" / row["tour"][k]).exists(), f"edition {row['id']}: tour {k} {row['tour'][k]} is not in static/tour"
    promo = HERE / "chips" / "promo.film.json"
    if promo.exists():
        pf = json.loads(promo.read_text(encoding="utf-8"))["test_cases"][0]["expect_value"]
        for sc in pf["scenes"]:
            assert sc["kind"] == "card" or (HERE / pf["sources_dir"] / sc["source"]).exists(), f"promo.film: {sc.get('source')} is not in {pf['sources_dir']}"
        assert (HERE / pf["out_dir"] / f"{pf['out']}.mp4").exists(), "promo.film is not built - python tools/showcase/promo_film.py"
    # 2026-10-05 owner: "Copy the prompt" barely visible on white - controls were drawn with --line-2 (1.4:1). A control's
    # edge is --edge (>= 3:1) and quiet text --muted (>= 4.5:1) on every surface, light and dark (same guard as tv).
    css = (HERE / "core" / "static" / "portal.css").read_text(encoding="utf-8")
    # 2026-11-13 owner (phone app): "Add your AI key" wrapped to four lines in the top bar - a top-bar chip never wraps and on
    # a phone shows its icon only (the word is its title)
    _app = (HERE / "static" / "app.js").read_text(encoding="utf-8")
    assert ".chipbtn{white-space:nowrap}" in css and ".topbar .tb-lbl{display:none}" in css and "<span class=\"tb-lbl\">${w('add_key')}</span>" in _app, "top bar: the AI key chip wraps on a phone (portal.css .chipbtn nowrap + .tb-lbl, static/app.js tb-lbl)"
    def lum(h: str) -> float:
        c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    light = dict(re.findall(r"--([\w-]+):(#[0-9a-f]{6})", css[:css.index("@media (prefers-color-scheme: dark)")]))
    dark = light | dict(re.findall(r"--([\w-]+):(#[0-9a-f]{6})", css[css.index(':root[data-theme="dark"]'):][:2000]))
    for name, t in (("light", light), ("dark", dark)):
        for sf in ("panel", "panel-2", "bg", "bg-2"):
            for tok, need in (("edge", 3), ("muted", 4.5)):
                r = (max(lum(t[tok]), lum(t[sf])) + 0.05) / (min(lum(t[tok]), lum(t[sf])) + 0.05)
                assert r >= need, f"{name}: --{tok} on --{sf} is {r:.2f}:1, needs {need}:1"
    for rule in ("input,select,textarea{", "button{"):
        assert "border:1px solid var(--edge)" in css[css.index("\n" + rule):].split("}")[0], f"the shared {rule} rule must draw its border with --edge"
    # 2026-11-11 owner (XForm Contact requests): a screen's news count comes from the server (bootstrap menu_badges) and is the
    # RED balloon, like Code Editor's - it had shown as a pale number nobody noticed. setBadge updates it in place, no reload.
    _sh = (HERE / "core" / "static" / "shell.js").read_text(encoding="utf-8")
    assert "d.menu_badges" in _sh and "export function setBadge(" in _sh and "badge news" in _sh and ".badge.news{background:var(--bad)" in css,         "a screen's news count is no longer the red menu balloon (core shell.js menu_badges / setBadge, portal.css .badge.news)"
    print("  static: every import resolves, one page per screen, controls stand out OK")


def api_check() -> None:
    from fastapi.testclient import TestClient
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        os.environ["TV_DATA"] = str(Path(tmp) / "data")
        os.environ.pop("PORTAL_EDITION", None)
        sys.path.insert(0, str(HERE))
        import app  # noqa: PLC0415 - after TV_DATA
        import recon  # noqa: PLC0415
        c = TestClient(app.app)
        # 2026-11-02 link card: WhatsApp asks HEAD first - 405 there meant a pasted link showed no card
        hd = TestClient(app.app).head("/")
        assert hd.status_code == 200 and not hd.content and "text/html" in hd.headers.get("content-type", ""), ("HEAD /", hd.status_code)
        boot = c.get("/api/bootstrap").json()
        assert boot["needs_first_account"] is True
        assert f"<title>{product()}" in c.get("/").text
        # 2026-10-05 owner: the public showcase is the landing for a visitor (chip showcase.page); Start here -> /start
        assert "showcase.js" in c.get("/").text and "showcase.js" not in c.get("/start").text, "a visitor lands on the showcase; /start is the portal"
        sc_ = c.get("/api/showcase").json()
        for ch_ in sc_["chapters"]:
            for ext_ in ("mp4", "jpg", "vtt"):
                assert (HERE / "static" / "showcase" / f"{ch_['key']}.{ext_}").is_file(), f"showcase {ch_['key']}.{ext_} is missing"
        assert c.get(f"/showcase/media/{sc_['chapters'][0]['key']}.mp4", headers={"Range": "bytes=0-9"}).status_code == 206, "showcase films seek"
        assert c.get("/showcase/media/nope.mp4").status_code == 404, "only the chip's chapters are served"
        # 2026-10-05 owner: a browser that has signed in here before skips the landing (landing.py, chip showcase.settings
        # returning_skip); the landing stays at /showcase and the sign-in pitch links to it (bootstrap showcase)
        r_ = TestClient(app.app)
        r_.cookies.set(app.auth.KNOWN, "1")
        assert "showcase.js" not in r_.get("/").text and "showcase.js" in r_.get("/showcase").text, "a returning visitor opens on sign-in"
        assert boot.get("showcase") is True, "the sign-in pitch knows this site has a showcase"
        assert "Make anything" not in (HERE / "static" / "showcase.js").read_text(encoding="utf-8"), "the showcase page holds no words of its own"
        # 2026-10-05 owner "more commercial": skin "ledger", how it works, who it's for, questions. SimplyFy fills the utility;
        # the CA uploads it - the pitch (showcase + sign-in words) must never promise a filed return
        js_, css_ = ((HERE / "static" / f"showcase.{x}").read_text(encoding="utf-8") for x in ("js", "css"))
        for k_ in ("trust", "steps", "desks", "faq", "pillars", "checks", "modules", "features", "play"):
            assert k_ not in sc_ or f"d.{k_}" in js_, f"showcase chip has {k_} but showcase.js never draws it"
        assert not sc_.get("skin") or f'[data-skin="{sc_["skin"]}"]' in css_, f"showcase skin {sc_.get('skin')} has no styles"
        # 2026-10-07 owner: "people want to find" a film - every film carries several tags, the theatre has its find words and
        # topics (each topic a tag some film carries), and the find forgives a typo (same guard as the studio tv/selfcheck.py)
        th_ = sc_["theatre"]
        assert all(th_.get(k_) for k_ in ("search", "found", "none", "topics")), "Watch has no find words (chip showcase.page theatre search/found/none/topics)"
        for ch_ in sc_["chapters"]:
            assert len(set(ch_.get("tags") or [])) >= 3, f"film {ch_['key']} needs several tags - the words people search for"
        tags_ = {t_.lower() for ch_ in sc_["chapters"] for t_ in ch_["tags"]}
        assert not [t_ for t_ in th_["topics"] if t_.lower() not in tags_], "Watch offers a topic no film carries"
        assert "findsFilm(hay[i], text)" in js_ and "stepFrom(" in js_, "Watch find: the list, Next and play-the-next follow what the find left"
        import shutil as _shutil  # noqa: PLC0415
        import subprocess as _sp  # noqa: PLC0415
        if _shutil.which("node"):
            find_js_ = js_[js_.index("const norm ="):js_.index("function wirePlayer")]
            find_t_ = """
const film = {title: 'Importing old returns', line: 'Past ITR JSON becomes history', module: 'Part 3', tags: ['import', 'PAN'], marks: [{t: 1, title: 'A belated return'}]};
const w = filmWords(film, {title: 'Filing'});
const ok = [findsFilm(w, 'imprting'), findsFilm(w, 'part 3'), findsFilm(w, 'returns'), findsFilm(w, 'belated pan'), findsFilm(w, ''),
            !findsFilm(w, 'gst'), !findsFilm(w, 'import gst'), !findsFilm(w, 'zz')];
if (ok.some((x) => !x)) { console.log(JSON.stringify(ok)); process.exit(1); }"""
            r_ = _sp.run(["node", "-e", find_js_ + find_t_], capture_output=True, text=True)
            assert r_.returncode == 0, f"Watch find: a typo, a plural or a half word must still find the film; others must not ({r_.stdout or r_.stderr})"
        said_ = (json.dumps(sc_) + (HERE / "chips" / "ui.app.json").read_text(encoding="utf-8")).lower()
        for over_ in ("filed return", "click to file", "files the return for you"):
            assert over_ not in said_, f"the pitch promises '{over_}' - SimplyFy fills the utility, the CA files"
        assert c.get("/health").text == "ok"
        assert c.get("/api/clients/settings").status_code == 401, "signed-out callers get nothing"
        r = c.post("/api/auth/first-account", json={"email": "owner@example.com", "password": "a-good-password"})
        assert r.status_code == 200, r.text
        boot = c.get("/api/bootstrap").json()
        menu = [s["id"] for s in boot["catalog"] if s["id"] in SCREENS]
        assert menu == SCREENS, menu
        asked = SCREENS + ["app", "shell"]   # the route answers at most 20 screens a call (core/words.py)
        words = {k: v for i in range(0, len(asked), 20) for k, v in c.get(f"/api/core/words?screens={','.join(asked[i:i + 20])}").json()["words"].items()}
        assert all(words.get(s) for s in ("clients", "intake", "recon", "app")), "a screen has no words"
        bad = []
        for route in app.app.routes:
            path, methods = getattr(route, "path", ""), getattr(route, "methods", None) or set[str]()
            # 2026-11-12: the push stream (core/events, /api/core/events) never ends by design - a GET of it here hung the
            # whole selfcheck; selfcheck_push walks it with a real disconnect
            if "GET" in methods and "{" not in path and path.startswith("/api/") and path != "/api/core/events":
                code = c.get(path).status_code
                if code >= 500:
                    bad.append(f"{path} {code}")
        assert not bad, f"server errors: {bad}"
        # 2026-10-06 owner "Can we have this process of trouble shooting in UI" (from the studio: a reset code that "never
        # came" took an SSH session - it had been sent, Gmail filed it under a label). Every code / notice attempt is on
        # People & access -> Email (SMTP) -> Recent mail with what became of it (core/auth.py _mail, chip mail.outcomes).
        st_, au_ = app.auth.store, app.auth
        kept_smtp_, kept_log_, sent_ = st_.read("smtp", {}), st_.read("code_log", []), []
        au_.mailer.save({"host": "smtp.example.com", "from_email": "portal@example.com"})
        real_send_ = au_.mailer.send
        def refuse_(*_a, **_k):
            raise RuntimeError("the mail server said no")
        au_.mailer.send = refuse_
        c.post("/api/auth/code/send", json={"purpose": "reset", "identity": "owner@example.com"})
        au_.mailer.send = lambda to, subject, text: sent_.append(to)   # noqa: ARG005
        for _ in range(au_.limits()["sends_per_hour"]):
            c.post("/api/auth/code/send", json={"purpose": "reset", "identity": "owner@example.com"})
        c.post("/api/auth/code/send", json={"purpose": "reset", "identity": "ghost@nowhere.com"})
        ml_ = c.get("/api/smtp/log").json()
        got_ = {(r["purpose"], r["to"], r["outcome"]) for r in ml_["rows"]}
        assert {("reset", "owner@example.com", "failed"), ("reset", "owner@example.com", "sent"),
                ("reset", "owner@example.com", "throttled"), ("reset", "ghost@nowhere.com", "no_account")} <= got_, got_
        assert "the mail server said no" in next(r for r in ml_["rows"] if r["outcome"] == "failed")["error"]
        assert all(r.get("next_at") for r in ml_["rows"] if r["outcome"] == "throttled"), "a held send says when the next may go"
        assert set(ml_["tones"]) >= {r["outcome"] for r in ml_["rows"]}, "an outcome with no tone in chip mail.outcomes"
        assert all("code" not in r for r in ml_["rows"]) and ml_["rows"][0]["to"] == "ghost@nowhere.com", "no codes kept; newest first"
        assert TestClient(app.app).get("/api/smtp/log").status_code in (401, 403), "Recent mail is the owner's alone"
        au_.mailer.send = real_send_
        st_.write("smtp", kept_smtp_)
        st_.write("code_log", kept_log_)
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
        ic = c.get(f"{cb}/itr-check").json()
        assert "valid" in ic and c.get(f"{cb}/itr.json").json()["ITR"], "the ITR JSON is made and checked"
        # 2026-10-19 owner: the rules and assumptions beside the JSON - said, and every one reads a real fact (chip itr.assumptions)
        assert ic["rules"]["count"] >= 10 and not ic["rules"]["missing"], ("rules beside the ITR JSON", ic["rules"]["missing"])
        assert "valid" in c.get(f"{cb}/3cd-check").json() and c.get(f"{cb}/3cd.json").json()["FORM3CB"], "the 3CD JSON is made and checked"
        # 2026-10-05 owner (3CD from a party master): a loans statement as CAs write it - name, then address and PAN on the
        # lines below - gives 31(a) / 31(c) and 23 their address and PAN; the client's party master fills what a statement leaves out
        wb = openpyxl.Workbook()
        ws = wb.active
        for row in [["", "Statement regarding payments to relatives u/s 40A(2)(b)"], ["Sl.No.", "Name and address", "Amount", "Nature", "Relationship"],
                    [1, "Smt Asha Test", 120000, "Interest", "Mother"], ["", "Testpur"], ["", "AAAPT1234A"],
                    ["", "Statement regarding loans u/s 269SS"], ["Sl", "Name & address of the lender", "Amount accepted", "Amount repaid",
                                                              "Whether squared up", "Maximum outstanding", "Whether accepted otherwise than account payee cheque"],
                    [1, "Ravi Test Kumar", 500000, 0, "No", 800000, "No"], ["", "Testpur"], ["", "BBBPT 5678 B"],
                    [2, "Mohan Test", 300000, 100000, "Yes", 300000, "No"], ["", "Sample Nagar, Testpur"]]:
            ws.append(row)
        buf = io.BytesIO()
        wb.save(buf)
        lf = c.post(base, files={"file": ("loans.xlsx", buf.getvalue())}).json()
        rows_ = {x["label"]: x["key"] for x in c.get(f"{base}/{lf['id']}").json()["rows"]}
        tag = {rows_["Smt Asha Test"]: "3CD 23", rows_["Ravi Test Kumar"]: "3CD 31(a)", rows_["Mohan Test"]: "3CD 31(a)"}
        assert c.put(f"{base}/{lf['id']}/tags", json={"tags": tag}).status_code == 200
        learned = c.post(f"/api/clients/{cl['id']}/parties/learn", params={"ay": "2026-27"}).json()
        assert learned["added"] == 3, learned
        mohan = next(p for p in learned["client"]["parties"] if p["name"] == "Mohan Test")
        assert mohan["address"] == "Sample Nagar, Testpur" and not mohan["pan"], mohan
        mine = c.get(f"/api/clients/{cl['id']}").json()
        for p_ in mine["parties"]:
            if p_["name"] == "Mohan Test":
                p_["pan"] = "CCCPT9012C"                            # the CA types the PAN once ...
        assert c.put(f"/api/clients/{cl['id']}", json=mine).status_code == 200
        f3 = c.get(f"{cb}/3cd.json").json()["FORM3CB"]["F3CB"]
        loans = {x["LenderName"]: x for x in f3["Form3cdAmtSec269ssDetail"]}
        assert loans["Ravi Test Kumar"]["PanNoLender"] == "BBBPT5678B" and loans["Ravi Test Kumar"]["LenderAddress"] == "Testpur", loans
        assert loans["Ravi Test Kumar"]["MaxAmtOsAccPy"] == 800000 and loans["Ravi Test Kumar"]["LoanDepSqrdPyFlag"] == "N"
        assert loans["Ravi Test Kumar"]["LoanDepChqDrftFlag"] == "Y", "otherwise than account payee: No -> by account payee cheque"
        assert loans["Mohan Test"]["PanNoLender"] == "CCCPT9012C" and loans["Mohan Test"]["LoanDepSqrdPyFlag"] == "Y", "... and every year after"
        assert [x["PayeeName"] for x in f3["Form3cdAmtSec269tDetail"]] == ["Mohan Test"], "a loan repaid in the year is a repayment too"
        rel = f3["Form3cdPymtSec40a2bDetail"][0]
        assert rel["RelatedPAN"] == "AAAPT1234A" and rel["NatureOfTrnsc"] == "Interest" and rel["Amount"] == 120000, rel
        bad = [e for e in c.get(f"{cb}/3cd-check").json()["errors"] if re.search("269ss|269t|40a2b", e["path"], re.I)]
        assert not bad, bad
        assert c.put(f"/api/clients/{cl['id']}", json={k: v for k, v in mine.items() if k != "parties"}).status_code == 200
        assert len(c.get(f"/api/clients/{cl['id']}").json()["parties"]) == 3, "a save without the party master keeps it"
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
        # 2026-10-24 Connect your AI (the SteadyMove / AstroStage door, core/mcp.py): the Portal Admin's key, the tools only, a
        # person's step said never run, the portal's own routes as the owner (selfcheck_mcp.py, boilerplate)
        import selfcheck_mcp  # noqa: PLC0415
        selfcheck_mcp.static_check(app)
        mem = selfcheck_mcp.member(app, c)
        selfcheck_mcp.door_walk(app, c, mem, None)
        # 2026-10-24 Agents (the SteadyMove / AstroStage runtime, core/agents.py): recipes complete, the Daily health check, the owners' bar
        import selfcheck_agents  # noqa: PLC0415
        selfcheck_agents.static_check(app)
        selfcheck_agents.walk(app, c, mem)
    print(f"  api: owner, menu, {sum(1 for r in app.app.routes if '/api/' in getattr(r, 'path', ''))} routes, clients -> intake -> reconcile -> compute -> filed -> revised -> withdrawn OK")


def firm_check(app, owner, house_cid: str) -> None:
    from fastapi.testclient import TestClient
    assert owner.post("/api/firm/start", json={"kind": "ca_firm"}).status_code == 409, "the portal admin keeps the house register"
    r = owner.post("/api/users", json={"email": "ca@demo.example", "password": "a-good-password-1", "display_name": "Demo Partner"})
    assert r.status_code == 200, r.text
    ca = TestClient(app.app)
    assert ca.post("/api/auth/signin", json={"identity": "ca@demo.example", "password": "a-good-password-1"}).status_code == 200
    assert ca.get("/api/clients/settings").status_code == 403, "no firm, no Filing"
    assert ca.get("/api/firm").json()["firm"] is None
    f = ca.post("/api/firm/start", json={"kind": "ca_firm"}).json()
    good = {"name": "Demo CA Filing Firm", "pan": "AAFFP1234C", "tan": "HYDP12345E", "gstin": "36AAFFP1234C1Z5", "frn": "012345S",
            "owner_name": "Demo Partner", "aadhaar_last4": "4821", "phone": "+91 90000 00001", "email": "ca@demo.example", "consent": True}
    assert ca.put("/api/firm", json=good | {"aadhaar_last4": "1234 5678 9012"}).status_code == 400, "a full Aadhaar is refused, never kept"
    assert ca.put("/api/firm", json=good | {"tan": "BAD"}).json()["ready"]["say"] == "bad_tan", "a draft keeps a half-typed field"
    me = ca.put("/api/firm", json=good).json()
    assert me["phone"] == "9000000001" and me["ready"]["say"] == "need_docs"
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
    p = ca.post("/api/firm/team", json={"name": "Ravi", "email": "ravi@demo.example", "role": "preparer"}).json()
    assert p["password"] and p["member"]["role"] == "preparer"
    prep = TestClient(app.app)
    assert prep.post("/api/auth/signin", json={"identity": "ravi@demo.example", "password": p["password"]}).status_code == 200
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
    home = me2.get("/api/myreturn").json()           # 2026-10-06: a self-filer works in My return, not a client register
    assert home["self"] and [x["pan"] for x in home["clients"]] == ["AAAHG4321K"], home
    assert me2.get(f"/api/myreturn/{home['clients'][0]['id']}/{home['current_ay']}").status_code == 200
    assert me2.post("/api/clients", json={"name": "X", "status": "individual", "pan": "ABCPX1234K"}).status_code == 403


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
    "company.py": [                                   # 2026-10-11 ITR-6: the rates and limits stay in chips company.*
        ("4000000000", "the 400 crore turnover limit -> chip company.settings rates_by_ay"),
        ("* 0.22", "the 115BAA rate -> chip company.settings rates_by_ay options"),
        ("* 0.15", "MAT or 115BAB -> chip company.settings rates_by_ay"),
        ("200000)", "the house-property set-off cap -> chip company.settings hp_setoff_cap"),
        ("age > 8", "the 8-year carry forward -> chip company.loss_ok"),
        ('== "115BAA"', "what an option means -> chip company.rate"),
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
REQUIRED_CHIPS = ["mcp.tools", "guide.connect_ai", "demo.host", "start.steps", "wizard.settings", "wizard.scenarios", "wizard.docs", "wizard.doc_need", "wizard.offered", "wizard.form", "wizard.pan_kind", "wizard.asks", "wizard.prompts", "wizard.next_step", "wizard.who_state", "wizard.work_open", "wizard.firm_next", "wizard.entity_sniff", "wizard.constitution", "wizard.route", "wizard.biz_kind", "wizard.cases", "showcase.case_films", "myreturn.sniff", "ui.wizard", "guide.wizard", "rulebook.sections", "myreturn.business", "taxwatch.settings", "taxwatch.items", "ui.taxwatch", "guide.taxwatch", "myreturn.cyla", "myreturn.rates", "myreturn.age_band", "myreturn.hra", "myreturn.salary", "myreturn.house", "myreturn.hp_total", "myreturn.family_pension", "myreturn.deductions", "myreturn.tax", "myreturn.better", "myreturn.form", "myreturn.settings", "myreturn.sources", "myreturn.checks", "myreturn.steps", "myreturn.read", "myreturn.json", "ui.myreturn", "guide.myreturn", "audit.settings", "audit.applicable", "audit.trend", "audit.checklist", "audit.pattern", "audit.risk", "audit.risk_level", "audit.gst_read", "audit.gst", "audit.gst_month", "audit.llp_audit", "audit.as_level", "audit.as_list", "ui.audit", "page.audit", "list.delegations", "list.firm_team", "list.due_radar", "list.firm_requests", "list.portal_firms", "list.chat_turns", "chat.examples", "chat.surprise", "chat.next", "chat.train", "notes.settings", "notes.list_view", "issues.mine_view", "chat.families", "chat.fee_234f", "chat.pan_kind", "chat.pick", "ui.chatfam", "chat.settings", "chat.faq", "chat.route", "ui.chipchat", "page.dock", "ui.dock", "delegation.settings", "delegation.check", "delegation.covers", "ui.delegate", "server.settings", "server.disk", "server.backup", "server.site", "server.trend", "ui.server", "page.server", "portalstats.settings", "portalstats.firm", "portalstats.rollup", "ui.portalstats", "itr.read", "itr.codes_in", "itr.import_ok", "itr.statement", "ui.itrimport", "analytics.settings", "analytics.client", "analytics.rollup", "ui.analytics", "page.analytics", "compute.settings", "compute.tax", "compute.tax_parts", "compute.balance", "compute.regime", "compute.total_income",
                  "compute.hp", "close.move", "close.settings", "close.signoff", "close.steps", "recon.settings", "page.recon",
                  "page.intake", "ui.compute",
                  "firm.settings", "firm.roles", "firm.problem", "firm.ready", "firm.move", "firm.may", "firm.sla", "firm.steps",
                  "firm.client_room", "firm.team_ok", "ui.firm", "page.firm",
                  "close.stage", "close.dates", "close.ack_ok", "close.itr_u", "compute.interest", "compute.paid_kind", "compute.no_advance",
                  "compute.refund_interest", "itr.settings", "itr.codes", "itr.map", "itr.books", "intake.suggest", "intake.row_sign", "intake.amount_col",
                  "tar.settings", "tar.columns", "tar.codes", "tar.map",
                  # 2026-10-11 ITR-6 (a company's return): company.py asks these; tools/make_itr6_chips.py writes them
                  "company.settings", "company.problem", "company.rate", "company.tax", "company.tax_s1", "company.tax_s2", "company.mat",
                  "company.dep_block", "company.setoff", "company.loss_ok", "company.d80g", "company.d80m", "rulebook.sections",
                  # 2026-10-13 "Small business - only a bank statement": tools/make_bankonly_chips.py (+ part2, part3) writes these
                  "bank.statement", "bank.classify", "bank.gst_gap", "bank.check", "bank.upload", "bank.special_states", "ui.bankonly", "tour.mask"]


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


GUIDED = ["firm", "analytics", "delegate", "wizard", "clients", "myreturn", "itrimport", "intake", "recon", "compute", "audit", "approvals", "portalstats", "server", "taxwatch",
          "keys", "connect-ai", "agents", "issues"]   # 2026-10-10: Account & key - its tour rebuilt from its Guide me (the old hand-made one said "draws stills"); 2026-10-25 Reported issues + Push to


def guides_tours_check() -> None:
    """Every Firm / Filing screen has its Guide me (chip guide.<screen>) and its Tour Video script (tours/sf-<screen>.json),
    and the video says what the walk says - the tour is made from the guide, so a new step in one shows up in the other."""
    import json  # noqa: PLC0415
    for sc in GUIDED:
        gp = HERE / "chips" / f"guide.{sc.replace('-', '_')}.json"   # core screen connect-ai -> guide.connect_ai
        g = json.loads((gp if gp.exists() else HERE / "core" / "chips" / gp.name).read_text(encoding="utf-8"))   # a core walk (Agents) when the portal has none
        d = {p["name"]: p["default"] for p in g["params"]}
        t = json.loads((HERE / "tours" / f"sf-{sc}.json").read_text(encoding="utf-8"))
        says = [x["say"].replace("{product}", product()) for x in t["steps"]]
        want = [d["lede"].replace("{product}", product())] + [x["say"].replace("{product}", product()) for x in d["steps"]]
        assert says == want, f"tours/sf-{sc}.json is not the Guide me walk of {sc} - rebuild it from chip guide.{sc}"
    print(f"  guides and tours: {len(GUIDED)} screens, each tour = its Guide me OK")


def product() -> str:
    """The product's one name (2026-10-08 owner: "the name should be chip/ops - one place change, everywhere changed")."""
    d = {p["name"]: p["default"] for p in json.loads((HERE / "chips" / "edition.settings.json").read_text(encoding="utf-8"))["params"]}
    return next(r["product_name"] for r in d["rows"] if r["id"] == d["default_edition"])


def name_once_check() -> None:
    """No chip or tour spells the product's name: they say {product}, which the engine fills from edition.settings.
    Left out: the chip that holds it, test_cases (answers as a person sees them), and the boilerplate chips that list
    every ValueStream product by name (server.settings, tourvideo.settings, changes.settings)."""
    name, keep = product(), {"edition.settings", "server.settings", "tourvideo.settings", "changes.settings"}
    bad = []
    for f in sorted((HERE / "chips").glob("*.json")) + sorted((HERE / "tours").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if f.stem in keep:
            continue
        d.pop("test_cases", None)
        if re.search(rf"\b{re.escape(name)}\b", json.dumps(d, ensure_ascii=False)):
            bad.append(f.name)
    assert not bad, f"these spell '{name}' - write {{product}} instead: {bad}"
    print(f"  product name: one place (chip edition.settings = {name}) OK")


BAD_VERBS = re.compile(r"^(Take\b.*\b(out|off|away)\b|Throw away|Purge\b|Wipe\b|Erase\b)", re.I)


def verbs_check() -> None:
    """One verb set on every portal (2026-10-08 owner, the MS Office rule): Delete = gone, Remove = out of a list or group,
    Archive = hidden and restorable, Discard = unsaved work dropped. No ui.* word says "Take out", "Throw away", "Purge"..."""
    bad = []
    for f in sorted((HERE / "chips").glob("ui.*.json")) + sorted((HERE / "core" / "chips").glob("ui.*.json")):
        for p in json.loads(f.read_text(encoding="utf-8")).get("params", []):
            v = p.get("default")
            if isinstance(v, str) and BAD_VERBS.match(v):
                bad.append(f"{f.stem}.{p['name']}: {v}")
    assert not bad, "say Delete / Remove / Archive / Discard: " + "; ".join(bad)
    print("  verbs: Delete / Remove / Archive / Discard on every button OK")


AI_CALL = re.compile(r"call_with_keys\(|\bWatch\(\s*[\"']")   # a model call, or a rulewatch.Watch (its Fetch calls one)


def ai_check() -> None:
    """2026-10-09 owner: no AI-key menu, button or link where the portal uses no AI; the portal admin's alone where it does.
    Chip ai.features lists the AI features (edition.catalog hides or locks the key screens from it). A module of this portal
    that calls a model while the chip is empty would leave its admin no way to add a key - so it fails here."""
    feats = json.loads((HERE / "chips" / "ai.features.json").read_text(encoding="utf-8"))["params"][0]["default"]
    skip = {"providers.py", "rulewatch.py", "keyshare.py", "narrator.py", "selfcheck.py", "edition.py"}   # the key machinery itself
    calls = sorted(f.name for f in HERE.glob("*.py") if f.name not in skip and AI_CALL.search(f.read_text(encoding="utf-8", errors="replace")))
    assert not calls or feats, f"{', '.join(calls)} call an AI model but chip ai.features lists no feature - add its row"
    shown = {s["id"] for s in json.loads((HERE / "catalog.json").read_text(encoding="utf-8"))}
    bad = [f["id"] for f in feats if f.get("screen") not in shown or f.get("who") not in ("owner", "anyone")]
    assert not bad, f"ai.features rows need a catalog screen and who = owner or anyone: {bad}"
    print(f"  ai: {len(feats)} AI feature(s) - key screens {'for the portal admin only' if feats else 'hidden everywhere'} OK")


SITE_FILE = "valuestream.site.json"   # ValueStream CC finds each portal by this file (CC chips cc.site_manifests, cc.site_schema)


def site_manifest_check() -> None:
    """2026-10-15 owner: "wherever we create a new Fy domain, one file which ValueStream picks up". Every domain keeps
    valuestream.site.json (format valuestream-site/1) at its root - CC lists it on Apps, Server & sites, VPS Console and
    Demo visitors from it, and no CC chip is edited. Its full schema is CC's chip cc.site_schema; here: it is there, it
    is this portal's own (not SimplyFile's copy left unedited), and it agrees with start.cmd."""
    f = HERE / SITE_FILE
    assert f.is_file(), f"{SITE_FILE} is missing - write it (skill domain-portal: format valuestream-site/1), or CC never sees this portal"
    m = json.loads(f.read_text(encoding="utf-8"))
    need = ["format", "id", "label", "host", "repo", "prod.dir", "prod.service", "prod.port", "prod.health_path",
            "local.dir", "local.port", "local.data", "local.health_path"]
    def get(path: str):
        cur = m
        for k in path.split("."):
            cur = cur.get(k) if isinstance(cur, dict) else None
        return cur

    missing = [k for k in need if get(k) in (None, "")]
    assert not missing and m["format"] == "valuestream-site/1", f"{SITE_FILE}: format valuestream-site/1 with {missing or need}"
    assert isinstance(m["prod"]["port"], int) and isinstance(m["local"]["port"], int), f"{SITE_FILE}: ports are numbers"
    for part in ("demo", "backup"):
        assert m.get(part) is None or isinstance(m[part], dict), f"{SITE_FILE}: {part} is an object or null"
    assert m["label"] == product(), f"{SITE_FILE} label {m['label']!r} is not this portal's name {product()!r} - a copied file?"
    port = re.search(r"set TV_PORT=(\d+)", (HERE / "start.cmd").read_text(encoding="utf-8")) if (HERE / "start.cmd").is_file() else None
    assert not port or int(port.group(1)) == m["local"]["port"], f"{SITE_FILE} local.port {m['local']['port']} but start.cmd serves {port.group(1)}"
    print(f"  site file: {SITE_FILE} ({m['id']}, {m['host']}) for ValueStream CC OK")


# 2026-11-12 owner ("Yes, A and B" on the VS standards review): one naming standard for tables, documents, exceptions and settings -
# every rule in chip standards.naming, the reading in core/standards.py; names made before the rule wait in db_known (only shrinks).
def standards_check() -> None:
    sk = json.loads((HERE / "core" / "chips" / "standards.naming.json").read_text(encoding="utf-8"))
    sk = {p["name"]: p["default"] for p in sk["params"]}   # read from the file: a selfcheck part never imports store in-process
    w = sk["check_words"]
    dk = {p["name"]: p["default"] for p in json.loads((HERE / "core" / "chips" / "deps.lock.json").read_text(encoding="utf-8"))["params"]}
    r = subprocess.run([sys.executable, "-m", "core.standards"], cwd=HERE, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, w["selftest_failed"] + "\n" + (r.stdout + r.stderr)[-2000:]
    code = ("import json, sys; from pathlib import Path; from core import standards as s\n"
            "H = Path('.'); k = s.K(); skip = set(k['scan_skip'])\n"
            "fs = [f for f in [*H.glob('*.py'), *(H / 'core').glob('*.py'), *(H / 'tools').rglob('*.py')] if f.name not in skip and not f.name.startswith('selfcheck')]\n"
            "txt = {f: f.read_text(encoding='utf-8', errors='replace') for f in fs}\n"
            "db = [p for f, t in txt.items() for p in s.db_problems(f.stem, t, k)]\n"
            "docs = [p for d in k['doc_folders'] if (H / d).is_dir() for p in s.doc_problems(sorted(x.name for x in (H / d).glob('*.md')), k)]\n"
            "exc = [p for n in k['exception_files'] if (H / n).is_file() for p in s.exception_problems((H / n).read_text(encoding='utf-8'), k)]\n"
            "env = s.env_problems(set().union(*[s.env_read(t) for t in txt.values()]), (H / k['env_file']).read_text(encoding='utf-8') if (H / k['env_file']).is_file() else '', k)\n"
            "print(json.dumps({'db': db, 'known': k['db_known'], 'docs': docs, 'exc': exc, 'env': env, 'env_file': k['env_file']}))\n")
    r = subprocess.run([sys.executable, "-c", code], cwd=HERE, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, w["scan_failed"] + "\n" + (r.stdout + r.stderr)[-2000:]
    got = json.loads(r.stdout.strip().splitlines()[-1])
    new = [p for p in got["db"] if p not in got["known"]]
    gone = [p for p in got["known"] if p not in got["db"]]
    for key, bad in (("db_new", new), ("db_gone", gone), ("docs", got["docs"]), ("exc", got["exc"]), ("env", got["env"])):
        assert not bad, w[key] + "\n  " + "\n  ".join(bad)
    # pinned packages: the lock (when the portal has one) names everything requirements.txt asks for, each line exact and hashed;
    # deploy.sh installs from it with --require-hashes
    r = subprocess.run([sys.executable, "tools/lock_deps.py", "--check"], cwd=HERE, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, w["lock_behind"] + "\n" + (r.stdout + r.stderr)[-1500:]
    dep_ = (HERE / "deploy.sh").read_text(encoding="utf-8")
    assert dk["install_line"] in dep_, w["deploy_unhashed"]
    print("  " + w["ok"].format(known=len(got["known"]), env_file=got["env_file"]))


if __name__ == "__main__":
    print("SimplyFy - self-check")
    only = sys.argv[1:]
    for name, fn in {"modules": module_checks, "statics": static_checks, "chips": chips_first_check, "guides": guides_tours_check, "name": name_once_check, "verbs": verbs_check, "ai": ai_check, "site": site_manifest_check, "standards": standards_check, "api": api_check, "push": lambda: __import__("selfcheck_push").main()}.items():
        if not only or name in only:
            fn()
    import selfcheck_quality  # W1.3 quality gate: lint/types, shape walk, word drift, clones, deps (+ coverage when named)
    selfcheck_quality.main(only)
    print("All checks passed." if not only else f"Checked: {', '.join(only)}.")
