"""Import old returns (2026-10-04 owner): a client's past ITR, as filed (the CBDT JSON), brought into SimplyFile.

A wizard: 1 upload the JSON -> read() says what it is; 2 the client - the one with this PAN, another, or a new one made
from the return; 3 the acknowledgement no. and date filed -> commit() records the return as filed (its own figures,
"imported"), keeps the JSON, and can start this year for a client who has not come yet; 4 the statement as filed and
next year's statement to fill, both made from the return (statement_xlsx).

Facts only here. Chips: itr.read (where each fact sits), itr.codes_in (codes -> kind / status / AY), itr.import_ok
(refused or replacing), itr.statement (which lines), close.ack_ok. Words: ui.itrimport.
"""
from __future__ import annotations

import hashlib
import io
import json
import re

import openpyxl
from fastapi import HTTPException
from openpyxl.styles import Font

import clients
import compute
import store
from core import engine


def settings() -> dict:
    return engine.run("itr.read")


def say(key: str, **v) -> str:
    return str(engine.run("ui.itrimport").get(key, key)).format(**v)


def _bad(key: str, code: int = 400, **v):
    raise HTTPException(code, say(key, **v))


def _at(doc, path: str):
    for part in path.split("."):
        if not isinstance(doc, dict) or part not in doc:
            return None
        doc = doc[part]
    return doc


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def read(data: bytes) -> dict:
    """What a return says: its form, AY, kind, the person, the figures - nothing written."""
    k = settings()
    if len(data) > k["max_kb"] * 1024:
        _bad("imp_big", kb=k["max_kb"])
    try:
        doc = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        _bad("imp_bad_json", why=str(e)[:80])
    body = doc.get(k["wrap"]) if isinstance(doc, dict) and k["wrap"] in doc else doc
    code = next((f for f in k["forms"] if isinstance(body, dict) and f in body), None)
    if not code:
        _bad("imp_form")
    spec = k["forms"][code]
    f = {name: next((v for v in (_at(body, p) for p in paths) if v not in (None, "")), None) for name, paths in spec["facts"].items()}
    for m in k["money"]:
        f[m] = _num(f.get(m))
    for name, li in spec["lists"].items():
        rows = _at(body, li["path"]) or []
        f[name] = [{out: _at(r, src) for out, src in li["item"].items()} for r in rows if isinstance(r, dict)]
    codes = engine.run("itr.codes_in", {"form": spec["form"], "status": str(f.get("status") or ""), "substatus": str(f.get("substatus") or ""),
                                        "section": str(f.get("section") or ""), "residential": str(f.get("residential") or ""),
                                        "ay_code": str(f.get("ay_code") or "")})
    name = " ".join(str(f.get(x) or "").strip() for x in ("first", "middle", "surname") if str(f.get(x) or "").strip())
    address = ", ".join(str(f.get(x) or "").strip() for x in ("flat", "building", "road", "area", "city") if f.get(x))
    if f.get("pin"):
        address += f" {f['pin']}"
    return f | codes | {"form": spec["form"], "name": name, "pan": str(f.get("pan") or "").upper(), "address": address,
                        "digest": hashlib.sha1(json.dumps(doc, sort_keys=True).encode()).hexdigest()[:16]}


def preview(user: dict, data: bytes) -> dict:
    f = read(data)
    mine = [c for c in clients._mine(user) if not c.get("archived_at")]
    same = [c for c in mine if c["pan"] == f["pan"]]
    return {"facts": {x: f.get(x) for x in ("form", "ay", "kind", "name", "pan", "status", "nri", "dob", "email", "mobile", "address",
                                            "hp", "bp", "cg", "os", "sal", "gti", "deductions", "income", "tax_net", "tds", "advance", "sat",
                                            "paid", "refund", "payable", "interest", "receipt", "digest")},
            "match": [{"id": c["id"], "name": c["name"], "pan": c["pan"]} for c in same],
            "clients": [{"id": c["id"], "name": c["name"], "pan": c["pan"]} for c in mine],
            "current_ay": clients.settings()["current_ay"], "years": clients.settings()["years"]}


def _check(cid: str, f: dict) -> dict:
    c = clients.get(cid)
    y = (c.get("years") or {}).get(f["ay"]) or {}
    v = engine.run("itr.import_ok", {
        "known_year": f["ay"] in clients.settings()["years"], "form_ok": True, "pan_ok": c["pan"] == f["pan"],
        "duplicate": (y.get("imported") or {}).get("digest") == f["digest"] or any(x.get("digest") == f["digest"] for x in y.get("filings") or []),
        "has_current": bool(compute.current_filing(y)), "kind": f["kind"], "replaces": ["revised", "updated"]})
    if not v["ok"]:
        _bad(v["say"], 409, pan=f["pan"], name=c["name"], cpan=c["pan"], ay=f["ay"])
    return v


def commit(user: dict, data: bytes, body: dict) -> dict:
    """Record the return: the client (chosen or made from the return), the year, the filing as imported, the JSON kept."""
    f = read(data)
    ack = re.sub(r"\s+", "", str(body.get("ack_no") or ""))
    if engine.run("close.ack_ok", {"ack": ack}) is not True:
        _bad("imp_ack")
    filed_on = str(body.get("filed_on") or "")[:10]
    cid = str(body.get("cid") or "")
    if f["ay"] not in clients.settings()["years"]:
        _bad("imp_year", ay=f["ay"])
    if cid == "new":
        banks = [{"bank": b.get("bank") or "", "account": str(b.get("account") or ""), "ifsc": b.get("ifsc") or "", "type": b.get("type") or ""}
                 for b in f.get("banks") or []]
        cid = clients.save(user, {"name": body.get("name") or f["name"], "status": f["status"], "pan": f["pan"], "dob": f.get("dob") or "",
                                  "email": body.get("email") or f.get("email") or "", "phone": body.get("phone") or str(f.get("mobile") or ""),
                                  "address": f["address"], "father": f.get("father") or "", "nri": f["nri"],
                                  "signer_pan": f.get("signer_pan") or "",
                                  "banks": banks, "partners": [], "ay": f["ay"]})["id"]
    v = _check(cid, f)
    who, now = user.get("email") or user["id"], store.now()
    figures = {x: f.get(x) for x in ("hp", "bp", "cg", "os", "sal", "gti", "deductions", "income", "tax_net", "tds", "advance", "sat",
                                     "paid", "refund", "payable", "interest", "i234a", "i234b", "i234c")}

    def change(y: dict) -> None:
        fl = y.setdefault("filings", [])
        cur = compute.current_filing(y)
        if v["replace"] and cur:
            cur["status"], cur["superseded_at"] = "superseded", now
        fl.append({"n": len(fl) + 1, "kind": f["kind"], "ack_no": ack, "filed_on": filed_on or now[:10], "by": who, "at": now,
                   "figures": {"income": f["income"], "tax": f["tax_net"], "net": f["payable"] - f["refund"]}, "status": "current",
                   "revises": (cur or {}).get("ack_no", "") if v["replace"] else "", "itr_u": None, "imported": True,
                   "digest": f["digest"], "note": say("imported_tag")})
        y["form"] = f["form"]
        y["ack_no"], y["revising"] = ack, False
        y["imported"] = {"form": f["form"], "kind": f["kind"], "digest": f["digest"], "figures": figures}
    clients.change_year(cid, f["ay"], change)
    folder = store.DATA / "sf_files" / cid / f["ay"]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"itr-{f['digest']}.json").write_bytes(data)
    now_ay = clients.settings()["current_ay"]
    if body.get("also_now") and now_ay not in (clients.get(cid).get("years") or {}):
        clients.change_year(cid, now_ay, lambda y: None)
    compute.refresh(cid, f["ay"])
    c = clients.get(cid)
    return {"client": {"id": cid, "name": c["name"], "pan": c["pan"]}, "ay": f["ay"], "kind": f["kind"], "filed_on": filed_on or now[:10],
            "replaced": v["replace"], "next_ay": _next(f["ay"]), "started_now": now_ay in (c.get("years") or {})}


def _next(ay: str) -> str:
    a = int(ay[:4]) + 1
    return f"{a}-{str(a + 1)[2:]}"


def statement_xlsx(cid: str, ay: str, which: str = "filed") -> tuple[str, bytes]:
    """The return's lines as a statement SimplyFile reads: 'filed' with its amounts, 'next' for the following year to fill."""
    c = clients.get(cid)
    imp = ((c.get("years") or {}).get(ay) or {}).get("imported")
    if not imp:
        raise HTTPException(404, say("imp_form"))
    k = engine.run("itr.statement")
    code = k["form_code"][imp["form"]]
    fig = imp["figures"]
    wb = openpyxl.Workbook()
    ws = wb.active
    target = ay if which == "filed" else _next(ay)
    ws.title = "IT Statement"
    ws.append([c["name"].upper()])
    ws.append([f"PAN : {c['pan']}      Assessment Year {target}"])
    ws.append([])
    if which == "filed":
        ws.append(["", f"STATEMENT AS FILED - {imp['form']} AY {ay}", "", "Amount (Rs)", "SF Ref"])
        for ln in k["lines"]:
            if fig.get(ln["fact"]):
                ws.append(["", ln["label"], "", fig[ln["fact"]], ln["ref"].replace("{itr}", code)])
    else:
        ws.append(["", f"TOTAL INCOME STATEMENT - AY {target} (fill this year's figures)", "", "Amount (Rs)", "SF Ref", f"Last year AY {ay} (Rs)"])
        for ln in k["lines"]:
            if ln["fact"] in k["next_lines"] and fig.get(ln["fact"]):
                ws.append(["", ln["label"].replace(" (as per ITR, net)", "").replace(" (as per ITR)", ""), "", None,
                           ln["ref"].replace("{itr}", code), f"{fig[ln['fact']]:,.0f}"])
    for r in ws.iter_rows(min_row=1, max_row=4):
        for cell in r:
            cell.font = Font(bold=True)
    ws.column_dimensions["B"].width = 62
    for col in "DEF":
        ws.column_dimensions[col].width = 18
    buf = io.BytesIO()
    wb.save(buf)
    label = "as filed" if which == "filed" else "to fill"
    return f"{c['name']} - Statement {label} AY {target}.xlsx", buf.getvalue()
