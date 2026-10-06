"""My return's readers - one document in, what it says out (2026-10-06 owner: "Form 16 integration ... AI ok").

read(name, data, ...) -> {kind, method, facts, found, problems}. Kind is decided by what the file IS, never by its name:
  * pre-filled JSON (e-filing portal, camelCase keys: personalInfo, form24q, form26as, insights, bankAccountDtls)
  * AIS - its JSON is encrypted (IV + salt in hex, then base64; AES-256-CBC, key by PBKDF2-SHA256 from PAN + a fixed pepper
    + date of birth), its PDF is locked with pan + DDMMYYYY, its CSV is rows; every reported item has an information code
    (SFT-016(SB) savings interest, SFT-015 dividend, TDS-192 salary ...)
  * Form 16 - a PDF with a text layer: Part A (TRACES: TAN, the quarterly TDS) and Part B (the employer's annexure: salary,
    allowances exempt u/s 10, deductions u/s 16 and Chapter VI-A). Labels are found by chip myreturn.read's anchors, the figure
    is the last amount on that line. An unusual layout (or a scan) goes to AI when the person allowed it.
  * 26AS - the TRACES text export ('^' between fields; zipped with a password) or its PDF; read by recon.read_portal.
facts carry the keys myreturn.merged expects (person / employers / other / cg / via / tds / paid / banks). Every pattern, code,
label and limit is chip myreturn.read; every sentence is ui.myreturn.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import zipfile

from core import engine
from core.ops import template


def settings() -> dict:
    return engine.run("myreturn.read")


def say(key: str, **values) -> str:
    return template(engine.run("ui.myreturn")[key], values)


def _num(v) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    t = re.sub(r"[,\s₹]|Rs\.?|INR", "", str(v or ""))
    try:
        return float(t)
    except ValueError:
        return 0.0


def _inr(v: float) -> str:
    """12,34,567 - the Indian grouping (lakh, crore)."""
    n = str(abs(round(v)))
    head, tail = n[:-3], n[-3:]
    while len(head) > 2:
        tail = f"{head[-2:]},{tail}"
        head = head[:-2]
    return ("-" if v < 0 else "") + "₹" + (f"{head},{tail}" if head else tail)


def _ddmmyyyy(dob: str) -> str:
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", str(dob or ""))
    return f"{m[3]}{m[2]}{m[1]}" if m else ""


def _passwords(typed: str, pan: str, dob: str) -> list[str]:
    """What a locked file may open with: what the person typed, then the department's usual pan + DDMMYYYY."""
    d = _ddmmyyyy(dob)
    out = [typed] if typed else []
    if pan and d:
        out += [pan.lower() + d, pan.upper() + d]
    if d:
        out.append(d)
    if typed and re.fullmatch(r"\d{8}", typed) and pan:
        out += [pan.lower() + typed, pan.upper() + typed]
    return list(dict.fromkeys(out))


# --- the entry -----------------------------------------------------------------------------------------------------------

def read(name: str, data: bytes, password: str = "", user: dict | None = None, ay: str = "", pan: str = "", dob: str = "",
         ai_ok: bool = False) -> dict:
    k = settings()
    head = data[:4096]
    if head[:2] == b"PK":
        return _zip(data, password, pan, dob, ay)
    if head.lstrip()[:1] in (b"{", b"["):
        try:
            doc = json.loads(data.decode("utf-8-sig"))
        except (ValueError, UnicodeDecodeError):
            doc = None
        if isinstance(doc, dict) and isinstance(doc.get("ITR"), dict) and set(doc["ITR"]) & set(k["filed_roots"]):
            return filed(doc, pan, ay)
        if isinstance(doc, dict) and any(x in doc for x in k["prefill_keys"]):
            return prefill(doc, pan, ay)
        if isinstance(doc, dict) and ("partB" in doc or "PartB" in doc):
            return ais_json(doc)
        return _unknown()
    if re.fullmatch(rb"[0-9a-fA-F]{64}[A-Za-z0-9+/=\s]+", data.strip()[:4096]) and len(data) > 100:
        return _ais_encrypted(data, password, pan, dob)
    if head[:5] == b"%PDF-":
        return _pdf(data, password, pan, dob, ay, user, ai_ok)
    text = data.decode("utf-8-sig", errors="replace")
    low = text[:6000].lower()
    if any(w in low for w in k["words_26as"]):
        return form26as(data, ".txt" if "^" in text[:6000] else ".csv")
    if any(w in low for w in k["words_ais"]):
        return ais_rows(text)
    return _unknown()


def _unknown() -> dict:
    return {"kind": "other", "method": "text", "facts": {}, "found": [], "problems": [say("unknown_doc")]}


def _zip(data: bytes, password: str, pan: str, dob: str, ay: str) -> dict:
    z = zipfile.ZipFile(io.BytesIO(data))
    inner = next((n for n in z.namelist() if n.lower().endswith((".txt", ".csv", ".pdf", ".json"))), None)
    if not inner:
        return _unknown()
    for pw in [None] + _passwords(password, pan, dob):
        try:
            raw = z.read(inner, pwd=pw.encode() if pw else None)
            return read(inner, raw, password, None, ay, pan, dob)
        except RuntimeError:                       # "Bad password" / "password required"
            continue
    return {"kind": "26as", "method": "text", "facts": {}, "found": [], "problems": [say("need_password" if not password else "bad_password")]}


# --- pre-filled JSON -----------------------------------------------------------------------------------------------------

def _at(doc, path: str):
    cur = doc
    for p in path.split("."):
        if isinstance(cur, list):
            cur = cur[0] if cur else None
        cur = cur.get(p) if isinstance(cur, dict) else None
    return cur


def _list(doc, path: str) -> list:
    v = _at(doc, path)
    return v if isinstance(v, list) else [v] if isinstance(v, dict) else []


def prefill(doc: dict, pan: str, ay: str) -> dict:
    """The department's own pre-filled data: who, salary per employer, TDS, taxes paid, interest, refund banks."""
    k = settings()["prefill"]
    pi = doc.get("personalInfo") or {}
    nm = pi.get("assesseeName") or {}
    ad = pi.get("address") or {}
    person = {"name": " ".join(x for x in (nm.get("firstName"), nm.get("middleName"), nm.get("surNameOrOrgName")) if x),
              "first": nm.get("firstName") or "", "middle": nm.get("middleName") or "", "surname": nm.get("surNameOrOrgName") or "",
              "pan": (pi.get("pan") or "").upper(), "dob": pi.get("dob") or "",
              "flat": ad.get("residenceNo") or "", "building": ad.get("residenceName") or "", "road": ad.get("roadOrStreet") or "",
              "area": ad.get("localityOrArea") or "", "city": ad.get("cityOrTownOrDistrict") or "", "state": str(ad.get("stateCode") or ""),
              "country": str(ad.get("countryCode") or "91"), "pin": str(ad.get("pinCode") or ""), "mobile": str(ad.get("mobileNo") or ""),
              "email": ad.get("emailAddress") or "",
              "residential": _at(doc, "personalInfo.filingStatus.residentialStatus") or _at(doc, "filingStatus.residentialStatus") or ""}
    emps = []
    for s in _list(doc, "form24q.salaries.salary"):
        sal = s.get("salarys") or s.get("salaries") or {}
        emps.append({"name": s.get("nameOfEmployer") or "", "tan": (s.get("tanOfEmployer") or "").upper(),
                     "gross_17_1": _num(sal.get("salary") or sal.get("grossSalary")), "perq_17_2": _num(sal.get("valueOfPerquisites")),
                     "profit_17_3": _num(sal.get("profitsinLieuOfSalary") or sal.get("profitsInLieuOfSalary"))})
    inc = _at(doc, "form24q.incomeDeductions") or {}
    if not emps and inc:
        emps.append({"name": "", "tan": "", "gross_17_1": _num(inc.get("salary")), "perq_17_2": _num(inc.get("perquisitesValue")),
                     "profit_17_3": _num(inc.get("profitsInSalary"))})
    if len(emps) == 1:
        ex = _list(doc, "form24q.allwncExemptUs10DtlsType") or _list(doc, "form24q.allwncExemptUs10.allwncExemptUs10Dtls")
        emps[0]["exempt_all"] = sum(_num(x.get("salOthAmount")) for x in ex)
        emps[0]["exempt_new"] = sum(_num(x.get("salOthAmount")) for x in ex if str(x.get("salNatureDesc") or "") in k["exempt_new_codes"])
        emps[0]["prof_tax"] = _num(inc.get("professionalTaxUs16Iii"))
        emps[0]["exempt_rows"] = [{"code": str(x.get("salNatureDesc") or ""), "amount": _num(x.get("salOthAmount"))} for x in ex if _num(x.get("salOthAmount"))]
    tds = []
    for t in _list(doc, "form26as.tdsOnSalaries.tdsOnSalary"):
        e = t.get("employerOrDeductorOrCollectDetl") or {}
        tds.append({"kind": "salary", "tan": (e.get("tan") or "").upper(), "name": e.get("employerOrDeductorOrCollecterName") or "",
                    "income": _num(t.get("incChrgSal")), "tds": _num(t.get("totalTDSSal")), "section": "192"})
    for t in _list(doc, "form26as.tdsOnOthThanSals.tdSonOthThanSal") + _list(doc, "form26as.tdsOnOthThanSals.tdsOnOthThanSal"):
        e = t.get("employerOrDeductorOrCollectDetl") or {}
        tds.append({"kind": "other", "tan": (e.get("tan") or t.get("tanOfDeductor") or "").upper(), "name": e.get("employerOrDeductorOrCollecterName") or "",
                    "income": _num(t.get("amtForTaxDeduct") or t.get("grossAmount")), "tds": _num(t.get("claimOutOfTotTDSOnAmtPaid") or t.get("totTDSOnAmtPaid") or t.get("tdsClaimed")),
                    "section": str(t.get("tdsSection") or t.get("section") or "")})
    for e in emps:                                          # an employer's TDS, by its TAN
        e["tds"] = sum(x["tds"] for x in tds if x["kind"] == "salary" and x["tan"] == e["tan"]) if e["tan"] else 0.0
    paid = [{"bsr": str(p.get("bsrCode") or ""), "date": str(p.get("dateDep") or ""), "challan": str(p.get("srlNoOfChaln") or ""),
             "amount": _num(p.get("amt"))} for p in _list(doc, "form26as.taxPayments.taxPayment")]
    oth = {"savings": _num(_at(doc, "insights.intrstFrmSavingBank") or _at(doc, "form24q.intrstFrmSavingBank")),
           "deposits": _num(_at(doc, "insights.intrstFrmTermDeposit") or _at(doc, "form26as.intrstFrmTermDeposit")),
           "dividend": _num(_at(doc, "insights.scheduleOS.incOthThanOwnRaceHorse.dividendGross") or _at(doc, "ais.scheduleOS.incOthThanOwnRaceHorse.dividendGross")),
           "refund_interest": sum(_num(x.get("othSrcOthAmount")) for x in _list(doc, "insights.incDeductionsOthIncCPC"))}
    banks = []
    for b in _list(doc, "bankAccountDtls"):
        for x in (b.get("addtnlBankDetails") or [b]) if isinstance(b, dict) else []:
            if x.get("bankAccountNo"):
                banks.append({"ifsc": x.get("ifsccode") or x.get("ifscCode") or "", "bank": x.get("bankName") or "",
                              "account": str(x.get("bankAccountNo")), "type": "SB", "refund": bool(x.get("useForRefund"))})
    banks.sort(key=lambda b: not b["refund"])
    via_src = _at(doc, "form24q.usrDeductUndChapVIAType") or {}
    via = {f: _num(via_src.get(src)) for f, src in k["via"].items() if via_src.get(src)}
    problems = []
    if pan and person["pan"] and person["pan"] != pan.upper():
        problems.append(say("pan_mismatch", theirs=person["pan"], ours=pan.upper()))
    facts = {"person": person, "employers": emps, "tds": tds, "paid": paid, "other": oth, "banks": banks, "via": via}
    found = [{"label": say("fd_name"), "value": person["name"]}] if person["name"] else []
    found += [{"label": say("fd_salary"), "value": _inr(sum(e["gross_17_1"] + e["perq_17_2"] + e["profit_17_3"] for e in emps))}] if emps else []
    found += [{"label": say("fd_tds"), "value": _inr(sum(x["tds"] for x in tds))}] if tds else []
    found += [{"label": say("fd_interest"), "value": _inr(oth["savings"] + oth["deposits"])}] if oth["savings"] + oth["deposits"] else []
    found += [{"label": say("fd_banks"), "value": str(len(banks))}] if banks else []
    return {"kind": "prefill", "method": "json", "facts": facts, "found": found, "problems": problems}


# --- a return already filed ----------------------------------------------------------------------------------------------

def filed(doc: dict, pan: str, ay: str) -> dict:
    """An ITR JSON as filed (ITR-1 / ITR-2, from the e-filing portal or the utility): kept whole, to compare with."""
    k = settings()
    root = next(r for r in doc["ITR"] if r in k["filed_roots"])
    form = k["filed_roots"][root]
    got = {}
    for row in k["filed_found"].get(form, []):
        cur = doc["ITR"]
        for part in row["path"].split("."):
            cur = cur.get(part) if isinstance(cur, dict) else None
        if cur not in (None, ""):
            got[row["word"]] = cur
    problems = []
    their_pan = str(got.get("fd_pan") or "")
    if pan and their_pan and their_pan.upper() != pan.upper():
        problems.append(say("pan_mismatch", theirs=their_pan, ours=pan.upper()))
    if got.get("fd_ay") and ay and str(got["fd_ay"]) != ay[:4]:
        problems.append(say("ay_mismatch", theirs=got["fd_ay"], ours=ay))
    found = [{"label": say("fd_form"), "value": form}] + [{"label": say(w), "value": _inr(_num(v)) if isinstance(v, (int, float)) else str(v)}
                                                         for w, v in got.items() if w not in ("fd_ay",)]
    return {"kind": "filed", "method": "json", "facts": {"filed_json": doc, "form": form}, "found": found, "problems": problems}


# --- AIS -----------------------------------------------------------------------------------------------------------------

def _ais_encrypted(data: bytes, password: str, pan: str, dob: str) -> dict:
    from cryptography.hazmat.primitives import padding  # noqa: PLC0415
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes  # noqa: PLC0415
    k = settings()["ais_crypt"]
    raw = data.strip()
    iv, salt, body = bytes.fromhex(raw[:32].decode()), bytes.fromhex(raw[32:64].decode()), base64.b64decode(re.sub(rb"\s", b"", raw[64:]))
    d = _ddmmyyyy(dob) or (password if re.fullmatch(r"\d{8}", password or "") else "")
    tries = []
    for p in ([pan.upper(), pan.lower()] if pan else []):
        tries += [p + k["pepper"] + d, p + d]
    if password:
        tries.insert(0, password)
    for pw in dict.fromkeys(tries):
        key = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, int(k["iterations"]), 32)
        try:
            dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
            plain = dec.update(body) + dec.finalize()
            un = padding.PKCS7(128).unpadder()
            plain = un.update(plain) + un.finalize()
            return ais_json(json.loads(plain.decode("utf-8")))
        except (ValueError, UnicodeDecodeError):
            continue
    return {"kind": "ais", "method": "json", "facts": {}, "found": [], "problems": [say("bad_password" if password or d else "need_password")]}


def _code_field(code: str, title: str) -> str:
    """An AIS information code (or, without one, its title) -> the return's field (chip myreturn.read ais_codes)."""
    for row in settings()["ais_codes"]:
        if (row.get("code") and re.fullmatch(row["code"], code or "", re.I)) or (row.get("title") and re.search(row["title"], title or "", re.I)):
            return row["field"]
    return ""


def _ais_add(facts: dict, field: str, amount: float, src: str = "", tds: float = 0.0) -> None:
    if field == "salary":
        facts.setdefault("salary", {"gross": 0.0})["gross"] += amount
        if tds:
            facts.setdefault("tds", []).append({"kind": "salary", "tan": src, "name": "", "income": amount, "tds": tds, "section": "192"})
    elif field in ("savings", "deposits", "dividend", "refund_interest", "other"):
        facts.setdefault("other", {}).setdefault(field, 0.0)
        facts["other"][field] += amount
    elif field == "sales":
        facts.setdefault("sales", 0.0)
        facts["sales"] = facts["sales"] + amount


def ais_json(doc: dict) -> dict:
    """The AIS as its utility holds it: partB.sections[].elements[] - each element an information item with a title, a
    source and a table (l1: columnLabel / columnData)."""
    facts: dict = {}
    for sec in (doc.get("partB") or doc.get("PartB") or {}).get("sections") or []:
        for el in sec.get("elements") or []:
            l1 = el.get("l1") or {}
            labels = [str(x).lower() for x in l1.get("columnLabel") or []]
            col = lambda *ws: next((i for i, c in enumerate(labels) if any(w in c for w in ws)), None)  # noqa: E731
            ci, ca, cs, ct = col("information code"), col("amount", "value"), col("status"), col("tds", "tax deducted")
            for row in l1.get("columnData") or []:
                if cs is not None and cs < len(row) and str(row[cs]).strip().lower() not in ("active", ""):
                    continue
                code = str(row[ci]) if ci is not None and ci < len(row) else str(el.get("infoCode") or "")
                f = _code_field(code, el.get("title") or "")
                if f:
                    _ais_add(facts, f, _num(row[ca]) if ca is not None and ca < len(row) else 0.0, str(el.get("infoSrcId") or ""),
                             _num(row[ct]) if ct is not None and ct < len(row) and ct != ca else 0.0)
    return _ais_result(facts, "json")


def ais_rows(text: str) -> dict:
    """AIS as CSV or as the text of its PDF: each line with an information code and amounts."""
    facts: dict = {}
    k = settings()
    for line in text.splitlines():
        m = re.search(k["ais_code_pattern"], line)
        if not m:
            continue
        nums = [_num(x) for x in re.findall(k["amount_pattern"], line[m.end():])]
        nums = [n for n in nums if n >= 1]
        if not nums:
            continue
        f = _code_field(m.group(0), line)
        if f:
            _ais_add(facts, f, nums[-1])
    return _ais_result(facts, "text")


def _ais_result(facts: dict, method: str) -> dict:
    o = facts.get("other") or {}
    found = [{"label": say(f"f_{f}"), "value": _inr(v)} for f, v in o.items() if v]
    if (facts.get("salary") or {}).get("gross"):
        found.insert(0, {"label": say("fd_salary"), "value": _inr(facts["salary"]["gross"])})
    problems = [say("rv_cg_p")] if facts.get("sales") else []
    return {"kind": "ais", "method": method, "facts": facts, "found": found, "problems": problems}


# --- 26AS ----------------------------------------------------------------------------------------------------------------

def form26as(data: bytes, ext: str) -> dict:
    import recon  # noqa: PLC0415 - the same 26AS reader Reconcile uses
    got = recon.read_portal(data, ext)
    tds, paid = {}, []
    for e in got["entries"]:
        if e["kind"] in ("tds", "tcs") and e["tax"]:
            key = (e["tan"], "salary" if str(e["section"]).startswith("192") else "other")
            r = tds.setdefault(key, {"kind": key[1], "tan": e["tan"], "name": e["party"], "income": 0.0, "tds": 0.0, "section": e["section"]})
            r["income"] += e["gross"]
            r["tds"] += e["tax"]
        elif e["kind"] == "paid":
            paid.append({"bsr": e["bsr"], "date": e["date"], "challan": e["challan"], "amount": e["tax"] or e["gross"], "minor": e.get("minor", "")})
    rows = list(tds.values())
    found = [{"label": f"{r['name'] or r['tan']}", "value": _inr(r["tds"])} for r in rows]
    found += [{"label": say("fd_paid"), "value": _inr(sum(p["amount"] for p in paid))}] if paid else []
    return {"kind": "26as", "method": "text", "facts": {"tds": rows, "paid": paid}, "found": found,
            "problems": [] if rows or paid else [say("unknown_doc")]}


# --- PDFs: Form 16, AIS, 26AS ----------------------------------------------------------------------------------------------

def _pdf(data: bytes, password: str, pan: str, dob: str, ay: str, user: dict | None, ai_ok: bool) -> dict:
    import pypdf  # noqa: PLC0415
    r = pypdf.PdfReader(io.BytesIO(data))
    if r.is_encrypted:
        if not any(r.decrypt(pw) for pw in _passwords(password, pan, dob)):
            return {"kind": "other", "method": "text", "facts": {}, "found": [], "problems": [say("bad_password" if password else "need_password")]}
    text = "\n".join((p.extract_text() or "") for p in r.pages[: int(settings()["pdf_pages_max"])])
    low = text.lower()
    k = settings()
    if any(w in low for w in k["words_form16"]):
        return form16(text, data, user, ai_ok, pan, ay)
    if any(w in low for w in k["words_ais"]):
        return ais_rows(text)
    if any(w in low for w in k["words_26as"]):
        return form26as(text.replace("\t", "^").encode(), ".txt")
    if len(text.strip()) < int(k["scan_chars"]):
        if ai_ok and user:
            return form16("", data, user, True, pan, ay)
        return {"kind": "other", "method": "text", "facts": {}, "found": [], "problems": [say("scanned")]}
    return _unknown()


def _amounts(line: str) -> list[float]:
    k = settings()
    return [_num(x) for x in re.findall(k["amount_pattern"], re.sub(k["glued_split"], lambda m: m.group(1) + " ", line))]


def form16(text: str, data: bytes, user: dict | None, ai_ok: bool, pan: str, ay: str) -> dict:
    """Part A: the employer, its TAN, the AY and the quarters' TDS. Part B: each line found by its anchor (chip myreturn.read
    form16_anchors), its figure the last amount on the line (or the next line when the line has none)."""
    k = settings()
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines() if ln.strip()]
    e: dict = {"name": "", "tan": ""}
    tan_re, pan_re = re.compile(k["tan_pattern"]), re.compile(k["pan_pattern"])
    for i, ln in enumerate(lines):
        if not e["tan"] and (t := tan_re.search(ln)) and not pan_re.fullmatch(t.group(0)):
            e["tan"] = t.group(0)
            pans = [p for p in pan_re.findall(ln) if p != t.group(0)]
            if pans:
                e["employee_pan"] = pans[-1]
        if not e["name"] and re.search(k["employer_anchor"], ln, re.I) and i + 1 < len(lines):
            e["name"] = re.split(r",|\s{2,}|\s(?=Name and address)", lines[i + 1])[0].strip()[:120]
    if m := re.search(r"Assessment Year\D{0,20}(20\d\d-\d\d)", text, re.I):
        e["ay"] = m.group(1)
    for ln in lines:
        if re.search(k["parta_total_anchor"], ln, re.I):
            a = _amounts(ln)
            if len(a) >= 2:
                e["tds"] = a[1] if len(a) >= 3 else a[-1]
                e["parta_paid"] = a[0]
                break
    got = {}
    for row in k["form16_anchors"]:
        for i, ln in enumerate(lines):
            if re.search(row["pattern"], ln, re.I):
                a = _amounts(re.sub(row["pattern"], " ", ln, flags=re.I))
                if not a and i + 1 < len(lines):
                    a = _amounts(lines[i + 1])
                if a:
                    got[row["field"]] = got.get(row["field"], 0.0) + a[-1] if row.get("add") else a[-1]
                    if not row.get("add"):
                        break
    regime = ""
    if m := re.search(k["regime_out_pattern"], text, re.I):
        regime = "old" if m.group(1).lower().startswith("y") else "new"
    elif m := re.search(k["regime_in_pattern"], text, re.I):
        regime = "new" if m.group(1).lower().startswith("y") else "old"
    method = "text"
    problems = []
    if not got.get("gross_17_1") and not got.get("gross_total"):
        if ai_ok and user:
            ai = _ai_form16(data, user)
            if ai.get("ok"):
                got, method = ai["fields"], "ai"
                e["name"] = e["name"] or ai["fields"].get("employer", "")
                e["tan"] = e["tan"] or ai["fields"].get("tan", "")
                if not e.get("tds") and ai["fields"].get("tds"):
                    e["tds"] = ai["fields"]["tds"]
            else:
                problems.append(ai["why"])
        else:
            problems.append(say("scanned") if not text.strip() else say("ai_ok"))
    if not got.get("gross_17_1") and got.get("gross_total"):
        got["gross_17_1"] = got["gross_total"] - got.get("perq_17_2", 0) - got.get("profit_17_3", 0)
    if e.get("ay") and ay and e["ay"] != ay:
        problems.append(say("ay_mismatch", theirs=e["ay"], ours=ay))
    if pan and e.get("employee_pan") and e["employee_pan"] != pan.upper():
        problems.append(say("pan_mismatch", theirs=e["employee_pan"], ours=pan.upper()))
    exempt_new = sum(got.get(f, 0.0) for f in k["exempt_new_fields"])
    emp = {"name": e["name"], "tan": e["tan"], "gross_17_1": got.get("gross_17_1", 0.0), "perq_17_2": got.get("perq_17_2", 0.0),
           "profit_17_3": got.get("profit_17_3", 0.0), "exempt_all": got.get("exempt_total", 0.0) or sum(got.get(f, 0.0) for f in k["exempt_fields"]),
           "exempt_new": exempt_new, "hra": got.get("hra", 0.0), "prof_tax": got.get("prof_tax", 0.0), "tds": e.get("tds", got.get("tds", 0.0)),
           "regime_used": regime, "exempt_rows": [{"code": k["exempt_codes"][f], "amount": got[f]} for f in k["exempt_fields"] if got.get(f)]}
    via = {f: got[f] for f in ("c80c", "c80ccc", "c80ccd1", "c80ccd1b", "c80ccd2", "c80d_self", "c80d_parents", "c80e", "c80g") if got.get(f)}
    tds = [{"kind": "salary", "tan": e["tan"], "name": e["name"], "income": emp["gross_17_1"] + emp["perq_17_2"] + emp["profit_17_3"],
            "tds": emp["tds"], "section": "192"}] if emp["tds"] else []
    found = [x for x in (
        {"label": say("fd_employer"), "value": e["name"]} if e["name"] else None,
        {"label": say("fd_tan"), "value": e["tan"]} if e["tan"] else None,
        {"label": say("fd_salary"), "value": _inr(emp["gross_17_1"] + emp["perq_17_2"] + emp["profit_17_3"])} if emp["gross_17_1"] else None,
        {"label": say("fd_tds"), "value": _inr(emp["tds"])} if emp["tds"] else None,
        {"label": say("fd_via"), "value": _inr(sum(via.values()))} if via else None,
        {"label": say("fd_regime"), "value": say(f"r_{regime}")} if regime else None) if x]
    return {"kind": "form16", "method": method, "facts": {"employers": [emp], "via": via, "tds": tds}, "found": found, "problems": problems}


def _ai_form16(data: bytes, user: dict) -> dict:
    """An unusual Form 16 (or a scan) read by Gemini on the portal's or the person's key: the PDF goes inline, the answer is
    JSON with chip myreturn.read's field names. Nothing is kept with the provider."""
    import providers  # noqa: PLC0415
    k = settings()
    if not providers.have_key(user["id"], k["ai_provider"]):
        return {"ok": False, "why": say("no_ai_key")}

    def call(key: str):
        from google import genai  # noqa: PLC0415
        from google.genai import types  # noqa: PLC0415
        client = genai.Client(api_key=key)
        resp = client.models.generate_content(model=k["ai_model"], contents=[types.Part.from_bytes(data=data, mime_type="application/pdf"), k["ai_prompt"]],
                                              config=types.GenerateContentConfig(response_mime_type="application/json"))
        return getattr(resp, "text", "") or "{}"
    try:
        out, _key = providers.call_with_keys(user["id"], k["ai_provider"], call, model=k["ai_model"])
        j = json.loads(out)
    except Exception as e:  # noqa: BLE001 - the person is told and types the figures
        return {"ok": False, "why": say("ai_failed", why=str(e)[:120])}
    fields = {f: (_num(j.get(f)) if f not in ("employer", "tan") else str(j.get(f) or "")) for f in k["ai_fields"]}
    return {"ok": True, "fields": fields}


if __name__ == "__main__":  # ponytail: each reader on a few hand-made lines
    import store as _st  # noqa: F401
    assert _amounts("Total (Rs.) 5489709.00 1311485.001311485.00") == [5489709.0, 1311485.0, 1311485.0], _amounts("Total (Rs.) 5489709.00 1311485.001311485.00")
    import store as _portal_store  # noqa: F401 - registers this portal's chips, as the app does
    assert _inr(1234567) == "₹12,34,567" and _inr(999) == "₹999" and _inr(-150000) == "-₹1,50,000"
    assert _passwords("", "ABCDE1234F", "1990-01-31")[:2] == ["abcde1234f31011990", "ABCDE1234F31011990"]
    sample = "\n".join([
        "FORM NO. 16", "TAN of the Deductor", "AAACD0042C HYDD00042E ABCPD1234F", "Assessment Year 2026-27",
        "Total (Rs.) 14,40,000.00 1,32,000.00 1,32,000.00", "(a) Salary as per provisions contained in section 17(1) 14,40,000.00",
        "(e) House rent allowance under section 10(13A) 1,20,000.00", "(a) Standard deduction under section 16(ia) 75,000.00",
        "(a) ... under section 80C 1,72,800.00 1,50,000.00", "Whether opting out of taxation u/s 115BAC(1A)? Yes"])
    f = form16(sample, b"", None, False, "ABCPD1234F", "2026-27")
    e = f["facts"]["employers"][0]
    assert e["tan"] == "HYDD00042E" and e["gross_17_1"] == 1440000 and e["tds"] == 132000 and e["hra"] == 120000, e
    assert e["exempt_rows"] == [{"code": "10(13A)", "amount": 120000.0}] and e["regime_used"] == "old" and f["facts"]["via"]["c80c"] == 150000, f
    a = ais_rows("\n".join(["1 SFT-016(SB) Interest income Savings bank DEMO BANK 1 18,400", "2 SFT-015 Dividend DEMO LTD 1 9,500",
                            "3 TDS-194A Interest 1 62,000"]))
    assert a["facts"]["other"] == {"savings": 18400.0, "dividend": 9500.0}, a
    pf = prefill({"personalInfo": {"pan": "ABCPD1234F", "dob": "1990-01-31", "assesseeName": {"surNameOrOrgName": "Demo"}},
                  "insights": {"intrstFrmSavingBank": 500}}, "ABCPD1234F", "2026-27")
    assert pf["kind"] == "prefill" and pf["facts"]["other"]["savings"] == 500 and not pf["problems"], pf
    assert read("x.txt", b"hello there")["kind"] == "other"
    print("myreturn_read self-check OK")

