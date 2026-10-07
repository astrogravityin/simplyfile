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
    if head[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":     # an old .xls
        return cg_book(data, ".xls") or bank_book(data, ".xls")
    text = data.decode("utf-8-sig", errors="replace")
    low = text[:6000].lower()
    if any(w in low for w in k["words_26as"]):
        return form26as(data, ".txt" if "^" in text[:6000] else ".csv")
    if any(w in low for w in k["words_ais"]):
        return ais_rows(text)
    if any(w in low for w in k["cg_statement"]["words"]) and (got := cg_book(data, ".csv")):
        return got
    if any(w in low for w in k["words_bank"]) or any(w in low[:3000] for w in k["bank"]["credit_words"][:2]):
        return bank_book(data, ".csv")
    return _unknown()


def _unknown() -> dict:
    return {"kind": "other", "method": "text", "facts": {}, "found": [], "problems": [say("unknown_doc")]}


def _zip(data: bytes, password: str, pan: str, dob: str, ay: str) -> dict:
    z = zipfile.ZipFile(io.BytesIO(data))
    if "xl/workbook.xml" in z.namelist():              # an Excel workbook is a zip too - a capital-gains statement or a bank statement
        return cg_book(data, ".xlsx") or bank_book(data, ".xlsx")
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
    # 2026-10-07: last year's return (its AY the year before this one) is kept for what it carries forward - its losses (Schedule CFL)
    prev = bool(got.get("fd_ay") and ay and str(got["fd_ay"]) == str(int(ay[:4]) - 1))
    if got.get("fd_ay") and ay and str(got["fd_ay"]) != ay[:4] and not prev:
        problems.append(say("ay_mismatch", theirs=got["fd_ay"], ours=ay))
    found = [{"label": say("fd_form"), "value": form}] + [{"label": say(w), "value": _inr(_num(v)) if isinstance(v, (int, float)) else str(v)}
                                                         for w, v in got.items() if w not in ("fd_ay",)]
    return {"kind": "filed_prev" if prev else "filed", "method": "json", "facts": {"filed_json": doc, "form": form}, "found": found, "problems": problems}


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
    elif field in ("savings", "deposits", "dividend", "refund_interest", "other", "lottery", "online_games"):
        facts.setdefault("other", {}).setdefault(field, 0.0)
        facts["other"][field] += amount
    elif field == "vda_sale":                                # 194S: what a virtual digital asset sold for - the gain is typed
        facts["vda_seen"] = facts.get("vda_seen", 0.0) + amount
    elif field == "property_tds":                            # 2026-10-07: 194IA - the buyer's TDS on a property sold (Form 26QB)
        pan = src if re.fullmatch(settings()["pan_pattern"].replace(r"\b", ""), src or "") else ""
        facts.setdefault("tds_194ia", []).append({"pan": pan, "name": "", "income": amount, "tds": tds, "section": "194IA"})
        facts["property_seen"] = facts.get("property_seen", 0.0) + amount
    elif field == "property_sft":                            # SFT-012: the sub-registrar's report of a property sold
        facts["property_sft"] = facts.get("property_sft", 0.0) + amount
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
    k = settings()["ais_header"]["json"]
    part_a = doc.get("partA") or doc.get("PartA") or {}
    flat = {str(x).lower(): v for d in [part_a] + [v for v in part_a.values() if isinstance(v, dict)] if isinstance(d, dict) for x, v in d.items()}
    got = {f: next((str(flat[n.lower()]) for n in names if flat.get(n.lower()) not in (None, "") and not isinstance(flat[n.lower()], dict)), "")
           for f, names in k.items()}
    if person := _person(got.get("address", ""), got.get("email", ""), got.get("mobile", "")):
        facts["person"] = person
    return _ais_result(facts, "json")


# --- bank statement ------------------------------------------------------------------------------------------------------

def bank_book(data: bytes, ext: str) -> dict:
    import intake  # noqa: PLC0415
    try:
        return bank(intake.read_book(data, ext))
    except Exception:  # noqa: BLE001 - a file that is not a readable statement is one answer
        return _unknown()


def bank_pdf_rows(text: str) -> list[list]:
    """A statement PDF's layout text -> rows [date, narration, debit, credit, balance]: each amount goes to the column whose
    heading it sits nearest under (the page keeps its columns as character positions), so an empty debit never shifts a credit."""
    import intake  # noqa: PLC0415
    k, ik = settings()["bank"], intake.settings()
    num = re.compile(r"-?\d[\d,]*\.\d{2}(?:\s?(?:cr|dr)\b)?", re.I)

    def at(line: str, words: list) -> float | None:
        for w in sorted(words, key=len, reverse=True):
            if m := re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", line):
                return (m.start() + m.end()) / 2
        return None
    head, out = None, [["Date", "Narration", "Debit", "Credit", "Balance"]]
    for ln in text.splitlines():
        lw = ln.lower()
        if head is None:
            if at(lw, k["date_words"]) is not None and at(lw, k["credit_words"]) is not None:
                head = {c: v for c, v in (("dr", at(lw, k["debit_words"])), ("cr", at(lw, k["credit_words"])), ("bal", at(lw, k["balance_words"]))) if v is not None}
            continue
        if not (d := re.match(k["date_pattern"], ln)):
            continue
        row = {"dr": None, "cr": None, "bal": None}
        for m in num.finditer(ln):
            mid = (m.start() + m.end()) / 2
            row[min(head, key=lambda c: abs(head[c] - mid))] = intake.text_amount(m.group(0), ik)
        out.append([d.group(0).strip(), re.sub(r"\s+", " ", num.sub(" ", ln[d.end():])).strip(), row["dr"], row["cr"], row["bal"]])
    return out if head else []


def bank(book: dict) -> dict:
    """A bank statement's credits for the year, each sorted by what it is (chip myreturn.read bank): receipts, cash, interest,
    tax refunds, salary, reversals, own transfers. Columns by their heading words; where a row's cells ran together (a PDF),
    the change in the running balance says what came in."""
    k = settings()["bank"]
    low = lambda c: re.sub(r"\s+", " ", c).strip().lower() if isinstance(c, str) else ""  # noqa: E731
    col = lambda cells, words: next((i for i, c in enumerate(cells) if c and any(c == w or c.startswith(w + " ") or c.startswith(w + "(") for w in words)), None)  # noqa: E731
    is_date = lambda c: isinstance(c, str) and re.match(k["date_pattern"], c) is not None or hasattr(c, "year")  # noqa: E731
    sums: dict = {}
    top: list = []
    n, first, last = 0, "", ""
    for rows in book.values():
        head = None
        prev_bal = None
        for r in rows:
            cells = [low(c) for c in r]
            if head is None:
                cr, amt, typ = col(cells, k["credit_words"]), col(cells, k["amount_words"]), col(cells, k["type_words"])
                if col(cells, k["date_words"]) is not None and (cr is not None or (amt is not None and typ is not None)):
                    head = {"cr": cr, "dr": col(cells, k["debit_words"]), "nar": col(cells, k["narration_words"]),
                            "bal": col(cells, k["balance_words"]), "amt": amt, "typ": typ, "width": len(r)}
                continue
            if not r or not any(is_date(c) for c in r[:2]):
                continue
            nums = [c for c in r if isinstance(c, (int, float)) and not isinstance(c, bool)]
            bal = nums[-1] if nums and head["bal"] is not None else None
            amount = None
            if len(r) == head["width"] and head["cr"] is not None and head["cr"] < len(r):
                v = r[head["cr"]]
                amount = float(v) if isinstance(v, (int, float)) and v > 0 else 0.0
            elif len(r) == head["width"] and head["cr"] is None and head["amt"] is not None:      # one Amount column, a Dr / Cr beside it
                v, t = r[head["amt"]], low(r[head["typ"]])
                amount = abs(float(v)) if isinstance(v, (int, float)) and t in k["credit_marks"] else 0.0
            elif bal is not None and prev_bal is not None:
                amount = max(round(bal - prev_bal, 2), 0.0)
            prev_bal = bal if bal is not None else prev_bal
            if not amount:
                continue
            text = " ".join(c for c in (low(x) for x in r) if c and not re.fullmatch(r"[\d,./:-]+", c))
            nar = low(r[head["nar"]]) if head["nar"] is not None and head["nar"] < len(r) and isinstance(r[head["nar"]], str) else text
            kind = next((x["kind"] for x in k["kinds"] if any(w in f" {nar} " for w in x["words"])), k["receipt_kind"])
            sums[kind] = sums.get(kind, 0.0) + amount
            n += 1
            d = next((c for c in r[:2] if is_date(c)), "")
            first, last = first or str(d)[:10], str(d)[:10]
            if kind == k["receipt_kind"]:
                top.append({"name": nar[:60], "amount": amount})
    if not n:
        return {"kind": "bank", "method": "text", "facts": {}, "found": [], "problems": [say("no_bank_table")]}
    total = sum(sums.values())
    facts = {"bank": {"credits": round(total, 2), "receipts": round(sums.get(k["receipt_kind"], 0.0), 2), "cash": round(sums.get("cash", 0.0), 2),
                      "interest": round(sums.get("interest", 0.0), 2), "by_kind": {x: round(v, 2) for x, v in sums.items()}, "rows": n,
                      "from": first, "to": last, "top": sorted(top, key=lambda x: -x["amount"])[: int(k["top_most"])]}}
    b = facts["bank"]
    found = [{"label": say("fd_bank_period"), "value": f"{first} - {last}"}, {"label": say("fd_bank_credits"), "value": _inr(total)},
             {"label": say("fd_bank_receipts"), "value": _inr(b["receipts"])}]
    found += [{"label": say("fd_bank_cash"), "value": _inr(b["cash"])}] if b["cash"] else []
    found += [{"label": say("fd_bank_interest"), "value": _inr(b["interest"])}] if b["interest"] else []
    return {"kind": "bank", "method": "text", "facts": facts, "found": found, "problems": []}


# --- capital-gains statement (2026-10-07) --------------------------------------------------------------------------------

def cg_book(data: bytes, ext: str) -> dict | None:
    """A broker's / registrar's capital-gains statement (CSV, Excel) - None when the book holds no such table."""
    import intake  # noqa: PLC0415
    try:
        return cg_statement(intake.read_book(data, ext))
    except Exception:  # noqa: BLE001 - not a readable book: let the next reader try
        return None


def cg_day(v) -> str:
    """A statement's date -> YYYY-MM-DD: 15/06/2025, 15-06-2025, 15.06.25 (Excel, as intake reads it), 15-Jun-2025, 2025-06-15."""
    k = settings()["cg_statement"]
    s = str(v or "").strip()
    if m := re.fullmatch(r"(\d{4})-(\d{2})-(\d{2}).*", s):
        return f"{m[1]}-{m[2]}-{m[3]}"
    if m := re.fullmatch(r"(\d{1,2})[/.\-]([A-Za-z]{3}|\d{1,2})[/.\-](\d{2}|\d{4})", s):
        mon = m[2] if m[2].isdigit() else str(k["months"].get(m[2][:3].title(), 0))
        y = int(m[3]) if len(m[3]) == 4 else int(m[3]) + (k["two_digit_base"] if int(m[3]) < k["two_digit_pivot"] else k["two_digit_base"] - 100)
        return f"{y:04d}-{int(mon):02d}-{int(m[1]):02d}" if 1 <= int(mon) <= 12 else ""
    return ""


def cg_statement(book: dict) -> dict | None:
    """One row per sale from a CAMS / KFintech consolidated capital-gains statement or a broker's tax P&L: the table is found by
    its heading words (chip myreturn.read cg_statement cols - the first row holding the needed columns), each later row with a
    sale value is a sale. A scheme or category naming debt (liquid, gilt ...) is a debt fund; the rest is the statement's default
    (listed equity / equity funds). FMV on 31-01-2018 given per unit (a NAV, a price) is made the total. None = no such table."""
    k = settings()["cg_statement"]
    low = lambda c: re.sub(r"\s+", " ", c).strip().lower() if isinstance(c, str) else ""  # noqa: E731
    num = lambda c: float(c) if isinstance(c, (int, float)) and not isinstance(c, bool) else _num(c) if isinstance(c, str) and re.fullmatch(r"[\d,.\s-]+", c) else 0.0  # noqa: E731
    out, heads = [], 0
    for rows in book.values():
        head = None
        for r in rows:
            cells = [low(c) for c in r]
            if head is None:
                cols: dict = {}
                for field, words in k["cols"].items():
                    i = next((i for i, c in enumerate(cells) if i not in cols.values() and any(w in c for w in words)), None)
                    if i is not None:
                        cols[field] = i
                if all(f in cols for f in k["need"]) and any(f in cols for f in k["need_one"]):
                    head, heads = cols, heads + 1
                    per_unit = "fmv" in cols and any(w in cells[cols["fmv"]] for w in k["per_unit_words"])
                continue
            at = lambda f: r[head[f]] if f in head and head[f] < len(r) else None  # noqa: E731
            text = " ".join(c for c in cells if c)
            if not num(at("sale")) or any(text.startswith(w) for w in k["skip_words"]):
                continue
            isin = str(at("isin") or "").strip().upper() or next((m.group(0) for c in r if isinstance(c, str) for m in [re.search(k["isin_pattern"], c.upper())] if m), "")
            name = str(at("name") or "").strip()
            kind = low(at("category") or "") + " " + name.lower()
            asset = next((a for a, words in k["asset_words"].items() if any(w in kind for w in words)), k["default_asset"])
            units = num(at("units"))
            fmv = num(at("fmv"))
            out.append({"asset": asset, "name": name[:125], "isin": isin if re.fullmatch(k["isin_pattern"], isin) else "", "units": units,
                        "acquired": cg_day(at("acquired")), "sold": cg_day(at("sold")), "sale": round(num(at("sale")), 2), "cost": round(num(at("cost")), 2),
                        "fmv": round(fmv * units if per_unit else fmv, 2), "expenses": round(num(at("expenses")), 2)})
    if not heads:
        return None
    sale = sum(x["sale"] for x in out)
    found = [{"label": say("fd_cg_rows"), "value": str(len(out))}, {"label": say("fd_cg_sale"), "value": _inr(sale)}]
    return {"kind": "cg", "method": "text", "facts": {"cg_rows": out}, "found": found, "problems": [] if out else [say("no_cg_rows")]}


def ais_paid(text: str, ay: str = "") -> list[dict]:
    """AIS Part B3: tax the person paid - advance or self-assessment - with its BSR, date and challan (chip myreturn.read
    ais_paid). Only the return's own financial year counts: a payment for an earlier year (paid this year) is not this return's."""
    k = settings()["ais_paid"]
    if k["start"] not in text:
        return []
    part = re.sub(r"\s+", " ", text.split(k["start"], 1)[1].split(k["end"], 1)[0])
    fy = f"{int(ay[:4]) - 1}-{ay[2:4]}" if ay else ""
    out = []
    for m in re.finditer(k["row"], part):
        words = m.group(2).lower()
        minor = next((v for w, v in k["minor"].items() if w in words), "")
        if fy and m.group(1) != fy:
            continue
        out.append({"bsr": m.group(8), "date": f"{m.group(11)}-{m.group(10)}-{m.group(9)}", "challan": m.group(12),
                    "amount": _num(m.group(7)), "minor": minor, "fy": m.group(1)})
    return out


def ais_rows(text: str, ay: str = "") -> dict:
    """AIS as CSV or as the text of its PDF: each line with an information code and amounts; Part B3, the tax paid."""
    facts: dict = {}
    if paid := ais_paid(text, ay):
        facts["paid"] = paid
    k = settings()
    h = k["ais_header"]
    head = re.sub(r"\s+", " ", re.split(h["end"], text, maxsplit=1)[0])
    if any(w in head.lower() for w in h["start_words"]):
        grab = lambda pat: (m.group(1).strip() if (m := re.search(pat, head)) else "")  # noqa: E731
        if person := _person(grab(h["address"]), grab(h["email"]), grab(h["mobile"])):
            facts["person"] = person
    for line in text.splitlines():
        m = re.search(k["ais_code_pattern"], line)
        if not m:
            continue
        nums = [_num(x) for x in re.findall(k["amount_pattern"], line[m.end():])]
        if not nums and (t := re.search(k["ais_amount_tail"], line[m.end():])):   # a small amount has no comma (654)
            nums = [_num(t.group(1))]
        nums = [n for n in nums if n >= 1]
        if not nums:
            continue
        f = _code_field(m.group(0), line)
        if f == "property_tds":                              # 194IA: the amount, then the tax deducted when the line has it; the buyer's PAN
            pan = re.search(k["pan_pattern"], line[m.end():])
            _ais_add(facts, f, nums[0], pan.group(0) if pan else "", nums[1] if len(nums) > 1 else 0.0)
        elif f:
            _ais_add(facts, f, nums[-1])
    return _ais_result(facts, "text")


def tis_rows(text: str) -> dict:
    """The TIS PDF: its first table, a line per category with the amount processed and the one accepted (the last) - read as the AIS."""
    k = settings()["tis"]
    facts: dict = {}
    for ln in text.split(k["start"], 1)[-1].split(k["end"], 1)[0].splitlines():
        if (m := re.match(k["row"], re.sub(r"\s+", " ", ln).strip())) and (f := _code_field("", m.group(1))):
            _ais_add(facts, f, _num(m.group(3)))
    return _ais_result(facts, "tis")


def _address(text: str) -> dict:
    """An address line -> {address, city, pin, state}: the PIN, the state it names (chip myreturn.read state_names) or, failing
    that, the state its PIN belongs to (pin_states), and the city - the last part before the PIN that is not the state."""
    from core import ops  # noqa: PLC0415
    k = settings()
    text = re.sub(r"\s+", " ", text or "").strip(" ,-")
    if not text:
        return {}
    pins = list(re.finditer(k["employer_block"]["pin"], text))
    pin = pins[-1].group(0) if pins else ""
    state = ops.first_matching(text, k["state_names"], "pattern", "code", "") or (ops.first_matching(pin, k["pin_states"], "pattern", "code", "") if pin else "")
    before = text[: pins[-1].start()] if pins else text
    chunks = [x.strip(" -") for x in before.split(",") if x.strip(" -")]
    city, at = "", len(chunks)
    for n in range(len(chunks) - 1, -1, -1):
        left = chunks[n]
        for row in k["state_names"]:
            left = re.sub(row["pattern"], "", left)
        if left.strip(" -"):
            city, at = left.strip(" -"), n
            break
    return {"address": ", ".join(chunks[:at]) or text, "city": city, "pin": pin, "state": state}


def _person(address: str, email: str, mobile: str) -> dict:
    a = _address(address)
    lines = [x.strip() for x in a.get("address", "").split(",") if x.strip()]
    out = {"flat": lines[0] if lines else "", "area": ", ".join(lines[1:]), "city": a["city"], "pin": a["pin"], "state": a["state"]} if a else {}
    return {f: v for f, v in (out | {"email": email.strip(), "mobile": re.sub(r"\D", "", mobile)[-10:]}).items() if v}


def employer_block(text: str) -> dict:
    """Form 16 Part A: the lines under "Name and address of the Employer" - the employer's address (its left column when the
    page is laid out in two), its e-mail; the state from the address (chip myreturn.read employer_block, state_names, pin_states)."""
    k, kb = settings(), settings()["employer_block"]
    raw = text.splitlines()
    at = next((n for n, ln in enumerate(raw) if re.search(k["employer_anchor"], ln, re.I)), None)
    if at is None:
        return {}
    col = re.search(kb["employee_anchor"], raw[at], re.I)
    cut = col.start() if col and col.start() > 0 else None
    lines = []
    for ln in raw[at + 1: at + 1 + int(kb["lines_max"])]:
        if re.search(kb["stop"], ln):
            break
        left = (ln[:cut] if cut else ln).strip()
        left = re.split(kb["column_gap"], left)[0].strip() if cut else left
        if left:
            lines.append(left)
    email = next((m.group(0) for ln in lines if (m := re.search(kb["email"], ln))), "")
    body = [ln for ln in lines if not re.search(kb["email"], ln) and not re.fullmatch(kb["phone"], ln)]
    if not body:
        return {}
    first = body[0].split(",", 1)                         # the name, then (on the same line) the address
    addr = ", ".join(([first[1]] if len(first) > 1 else []) + body[1:])
    a = _address(addr)
    return {"address": a.get("address", ""), "city": a.get("city", ""), "pin": a.get("pin", ""), "state": a.get("state", ""), "email": email} if a else {}


def _ais_result(facts: dict, method: str) -> dict:
    o = facts.get("other") or {}
    found = [{"label": say(f"f_{f}"), "value": _inr(v)} for f, v in o.items() if v]
    found += [{"label": say("fd_vda_seen"), "value": _inr(facts["vda_seen"])}] if facts.get("vda_seen") else []
    found += [{"label": say("fd_property_seen"), "value": _inr(facts["property_seen"])}] if facts.get("property_seen") else []
    found += [{"label": say("fd_tds_194ia"), "value": _inr(sum(x["tds"] for x in facts["tds_194ia"]))}] if any(x["tds"] for x in facts.get("tds_194ia") or []) else []
    found += [{"label": say("fd_property_sft"), "value": _inr(facts["property_sft"])}] if facts.get("property_sft") else []
    found += [{"label": say("fd_address"), "value": ", ".join(x for x in (facts["person"].get("city"), facts["person"].get("pin")) if x) or facts["person"].get("email", "")}] if facts.get("person") else []
    if (facts.get("salary") or {}).get("gross"):
        found.insert(0, {"label": say("fd_salary"), "value": _inr(facts["salary"]["gross"])})
    found += [{"label": say("fd_paid"), "value": _inr(sum(p["amount"] for p in facts["paid"]))}] if facts.get("paid") else []
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
    return {"kind": "26as", "method": "text", "facts": {"tds": rows, "paid": paid, "other": _income_of(rows)}, "found": found,
            "problems": [] if rows or paid else [say("unknown_doc")]}


def form26as_pdf(text: str) -> dict:
    """The TRACES Annual Tax Statement PDF, Part I: a deductor's total line, then its entries (whose section says salary or not)."""
    k = settings()["pdf26as"]
    part = text.split(k["start"], 1)[-1].split(k["end"], 1)[0]
    rows = []
    for ln in (re.sub(r"\s+", " ", x).strip() for x in part.splitlines()):
        if m := re.match(k["deductor"], ln):
            rows.append({"kind": "other", "tan": m.group(2), "name": m.group(1), "income": _num(m.group(3)), "tds": _num(m.group(5)), "section": ""})
        elif rows and not rows[-1]["section"] and (m := re.match(k["entry"], ln)):
            rows[-1]["section"] = m.group(1)
            rows[-1]["kind"] = "salary" if m.group(1).startswith("192") else "other"
    found = [{"label": r["name"] or r["tan"], "value": _inr(r["tds"])} for r in rows]
    return {"kind": "26as", "method": "text", "facts": {"tds": rows, "paid": [], "other": _income_of(rows)}, "found": found,
            "problems": [] if rows else [say("unknown_doc")]}


def _income_of(rows: list[dict]) -> dict:
    """Other income a 26AS shows as paid to the person (chip myreturn.read income_of: 194A interest, 194 dividend)."""
    out: dict = {}
    for r in rows:
        if f := settings()["income_of"].get(str(r["section"])):
            out[f] = out.get(f, 0.0) + r["income"]
    return out


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
        laid = "\n".join((p.extract_text(extraction_mode="layout") or "") for p in r.pages[: int(k["pdf_pages_max"])])
        got = form16(laid, data, None, False, pan, ay, layout=True)       # columns kept in rows: a label beside its amount
        return got if got["facts"]["employers"][0]["gross_17_1"] else form16(text, data, user, ai_ok, pan, ay)
    if any(w in low for w in k["words_ais"]):
        return ais_rows(text, ay)
    if any(w in low for w in k["tis"]["words"]):
        return tis_rows(text)
    if any(w in low for w in k["words_bank"]):
        laid = "\n".join((p.extract_text(extraction_mode="layout") or "") for p in r.pages)
        return bank({"PDF": bank_pdf_rows(laid)})
    if any(w in low for w in k["words_26as"]):
        got =form26as(text.replace("\t", "^").encode(), ".txt")
        return got if got["facts"]["tds"] or got["facts"]["paid"] else form26as_pdf(text)
    if len(text.strip()) < int(k["scan_chars"]):
        if ai_ok and user:
            return form16("", data, user, True, pan, ay)
        return {"kind": "other", "method": "text", "facts": {}, "found": [], "problems": [say("scanned")]}
    return _unknown()


def _amounts(line: str) -> list[float]:
    k = settings()
    return [_num(x) for x in re.findall(k["amount_pattern"], re.sub(k["glued_split"], lambda m: m.group(1) + " ", line))]


def form16(text: str, data: bytes, user: dict | None, ai_ok: bool, pan: str, ay: str, layout: bool = False) -> dict:
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
    if not e.get("employee_pan") and (m := re.search(k["employee_pan_pattern"], text, re.I)):
        e["employee_pan"] = m.group(1).upper()
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
                if not a and layout and i > 0:                      # a wrapped label: its amount sits on the row above
                    a = _amounts(lines[i - 1])
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
    blk = employer_block(text)                                # 2026-10-07: the employer's address, city, PIN and state (Schedule S)
    emp |= {f: blk[f] for f in ("address", "city", "state", "pin") if blk.get(f)}
    via = {f: got[f] for f in ("c80c", "c80ccc", "c80ccd1", "c80ccd1b", "c80ccd2", "c80d_self", "c80d_parents", "c80e", "c80g") if got.get(f)}
    tds = [{"kind": "salary", "tan": e["tan"], "name": e["name"], "income": emp["gross_17_1"] + emp["perq_17_2"] + emp["profit_17_3"],
            "tds": emp["tds"], "section": "192"}] if emp["tds"] else []
    found = [x for x in (
        {"label": say("fd_employer"), "value": e["name"]} if e["name"] else None,
        {"label": say("fd_tan"), "value": e["tan"]} if e["tan"] else None,
        {"label": say("fd_employer_at"), "value": ", ".join(x for x in (blk.get("city"), blk.get("pin")) if x)} if blk.get("city") or blk.get("pin") else None,
        {"label": say("fd_salary"), "value": _inr(emp["gross_17_1"] + emp["perq_17_2"] + emp["profit_17_3"])} if emp["gross_17_1"] else None,
        {"label": say("fd_tds"), "value": _inr(emp["tds"])} if emp["tds"] else None,
        {"label": say("fd_via"), "value": _inr(sum(via.values()))} if via else None,
        {"label": say("fd_regime"), "value": say(f"r_{regime}")} if regime else None) if x]
    person = {"person": {"pan": e["employee_pan"], "name": "", "dob": ""}} if e.get("employee_pan") else {}  # lets a return start from it
    return {"kind": "form16", "method": method, "facts": {"employers": [emp], "via": via, "tds": tds} | person, "found": found, "problems": problems}


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
                            "3 TDS-194A Interest 1 62,000", "4 SFT-015 Dividend DEMO TWO LTD (ZZZZZ0000Z.AZ1) 1 654"]))
    assert a["facts"]["other"] == {"savings": 18400.0, "dividend": 10154.0}, a
    b3 = "Part B3-Information relating to payment of taxes\n1 2025-26 Income Tax \n(Other than \nCompanies)\nAdvance \nTax\n50,000 0 0 0 50,000 0510002 14/03/2026 11 2603\n2 2024-25 Income Tax \n(Other than \nCompanies)\nSelf \nAssessment\n9,000 0 0 0 9,000 0510002 30/08/2025 12 2508\nPart B4"
    assert ais_paid(b3, "2026-27") == [{"bsr": "0510002", "date": "2026-03-14", "challan": "11", "amount": 50000.0, "minor": "100", "fy": "2025-26"}], ais_paid(b3, "2026-27")
    st = bank({"CSV": [["Date", "Narration", "Chq/Ref No", "Withdrawal Amt", "Deposit Amt", "Closing Balance"],
                       ["01/04/2025", "NEFT CR-DEMO CLIENT ONE-INV 101", "N1", None, 150000.0, 150000.0],
                       ["15/04/2025", "UPI-DEMO GROCER", "U1", 2000.0, None, 148000.0],
                       ["30/06/2025", "INT.PD:0000000000:01-04-2025 TO 30-06-2025", "", None, 812.0, 148812.0],
                       ["05/07/2025", "BY CASH DEPOSIT CDM", "", None, 20000.0, 168812.0],
                       ["10/07/2025", "TRF FROM SELF A/C DEMO", "", None, 50000.0, 218812.0]]})["facts"]["bank"]
    assert (st["receipts"], st["cash"], st["interest"], st["by_kind"]["own"]) == (150000.0, 20000.0, 812.0, 50000.0), st
    one = bank({"CSV": [["Tran Date", "Particulars", "Amount", "Dr/Cr", "Balance"], ["02-04-2025", "NEFT DEMO CLIENT", 25000.0, "CR", 25000.0],
                        ["03-04-2025", "ATM WDL", 5000.0, "DR", 20000.0]]})["facts"]["bank"]
    assert one["receipts"] == 25000.0 and one["rows"] == 1, one
    pdf_like = bank({"Page 1": [["Txn Date", "Description", "Debit", "Credit", "Balance"],
                                ["01-Apr-2025", "Opening", 10000.0], ["02-Apr-2025", "IMPS DEMO CLIENT TWO", 70000.0, 80000.0],
                                ["03-Apr-2025", "POS DEMO SHOP", 5000.0, 75000.0]]})["facts"]["bank"]
    assert pdf_like["receipts"] == 70000.0 and pdf_like["rows"] == 1, pdf_like     # cells ran together: the balance says 70,000 came in
    ti = tis_rows("\n".join(["Taxpayer Information Summary (TIS)", "SR. NO. INFORMATION CATEGORY PROCESSED BY", "1 Salary 9,00,000 9,00,000",
                             "2 Dividend 4,540 4,000", "3 Interest from savings bank 398 398", "The information details under each category"]))
    assert ti["facts"]["other"] == {"dividend": 4000.0, "savings": 398.0} and ti["facts"]["salary"]["gross"] == 900000, ti
    t26 = form26as_pdf("\n".join([
        "PART-I - Details of Tax Deducted at Source", "1 DEMO BANK LIMITED ZZZZ12345Z 1126456.00 112645.60 112645.60",
        "1 194A 31-Mar-2026 F 10-May-2026 - 224428.00 22442.80 22442.80", "2 DEMO EMPLOYER ZZZZ54321Z 900.00 90.00 90.00",
        "1 192 31-Mar-2026 F 01-Jun-2026 - 900.00 90.00 90.00", "PART-II"]))["facts"]["tds"]
    assert [(r["kind"], r["section"], r["tds"]) for r in t26] == [("other", "194A", 112645.6), ("salary", "192", 90.0)], t26
    assert _income_of(t26) == {"deposits": 1126456.0}, _income_of(t26)
    pf = prefill({"personalInfo": {"pan": "ABCPD1234F", "dob": "1990-01-31", "assesseeName": {"surNameOrOrgName": "Demo"}},
                  "insights": {"intrstFrmSavingBank": 500}}, "ABCPD1234F", "2026-27")
    assert pf["kind"] == "prefill" and pf["facts"]["other"]["savings"] == 500 and not pf["problems"], pf
    assert read("x.txt", b"hello there")["kind"] == "other"
    print("myreturn_read self-check OK")

