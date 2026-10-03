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
MODULES = ["clients", "intake", "recon", "edition", "tourvideo", "manuals", "projects", "scan", "source", "keyshare",
           "keysales", "wallet", "guideme"]
SCREENS = ["clients", "intake", "recon", "manuals", "howto", "guideme", "tourvideo", "setup", "keys", "buykey", "keysales"]


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
    print(f"  api: owner, menu, {sum(1 for r in app.app.routes if '/api/' in getattr(r, 'path', ''))} routes, clients -> intake -> reconcile OK")


if __name__ == "__main__":
    print("SimplyFile - self-check")
    module_checks()
    static_checks()
    api_check()
    print("All checks passed.")
