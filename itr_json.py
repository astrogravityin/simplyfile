"""ITR JSON - the return as the Income-tax Department's own JSON (2026-10-04 owner: "check if the Income tax portal has
something to import ... give it in that format"). The CBDT publishes, per AY and form, a JSON Schema (schemas/itr/,
downloaded from incometax.gov.in > Downloads). A JSON that fits it uploads on the e-filing portal (e-File > Income Tax
Return > offline) or opens in the department's offline utility, where the schedules SimplyFile does not hold yet
(balance sheet, P&L, ...) are completed.

How: the schema gives the skeleton (every required part, zeros and "N"s), chip itr.map puts SimplyFile's figures at their
paths, chip itr.codes turns our words into the schema's codes (194A -> 94A, original -> 11 ...), and the official schema
checks the result before it is offered - every problem is listed with its path, never hidden.
"""
from __future__ import annotations

import datetime
import json
import re
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException

import clients
import compute
import recon
from core import engine

HERE = Path(__file__).resolve().parent


def settings() -> dict:
    return engine.run("itr.settings")


def say(key: str, **values) -> str:
    return engine.say("ui.compute", key, **values)


@lru_cache(maxsize=8)
def schema_at(path: str) -> dict:
    return json.loads((HERE / path).read_text(encoding="utf-8"))


def schema(form: str) -> dict:
    f = settings()["forms"].get(form)
    if not f:
        raise HTTPException(409, say("itr_no_schema", form=form))
    return schema_at(f["schema"])


# --- the skeleton: every required part of the schema, filled with the quietest valid value --------------------------------

def _ref(s: dict, v: dict) -> dict:
    while "$ref" in v:
        v = s["definitions"][v["$ref"].split("/")[-1]]
    return v


def skeleton(s: dict, v: dict, depth: int = 0):
    v = _ref(s, v)
    t = v.get("type")
    if "enum" in v:
        e = v["enum"]
        return settings()["enum_default"] if settings()["enum_default"] in e else e[0]
    if t == "object" or "properties" in v:
        return {k: skeleton(s, v["properties"][k], depth + 1) for k in v.get("required", []) if k in v.get("properties", {})}
    if t == "array":
        return []
    if v.get("pattern") and re.fullmatch(v["pattern"], settings()["enum_default"]):
        return settings()["enum_default"]                       # a Y|N flag reads as N until a fact says Y
    if t in ("integer", "number"):
        return max(0, v.get("minimum", 0)) if v.get("minimum", 0) <= 0 else v["minimum"]
    return ""


# --- the facts SimplyFile holds ---------------------------------------------------------------------------------------------

def _iso(n) -> str:
    n = str(n or "").replace("-", "")
    return f"{n[:4]}-{n[4:6]}-{n[6:8]}" if len(n) >= 8 else ""


def _int(v) -> int:
    return int(round(float(v or 0)))


def facts(cid: str, ay: str) -> dict:
    """Everything the map can point at, as plain values. Python gathers; chips decide codes and places."""
    d = compute.compute(cid, ay)
    c = clients.get(cid)
    y = clients.year_of(cid, ay)
    codes = engine.run("itr.codes")
    st = clients.status_of(c["status"]) or {}
    form = y.get("form") or st.get("form", "")
    fc = codes["by_form"].get(form, {"statuses": {}, "capacity": {}, "substatus": {}})
    heads = {h["id"]: h["net"] for h in d["heads"]}
    person = c["status"] in codes["person_statuses"]                 # a person has a first name and signs for self
    yn = lambda v, kind="flags": codes[kind][str(bool(v)).lower()]  # noqa: E731
    words = c["name"].split()
    pin = (re.findall(r"\b[1-9][0-9]{5}\b", c.get("address") or "") or [""])[-1]
    parts = [p.strip() for p in re.split(r",", re.sub(r"\b[1-9][0-9]{5}\b", "", c.get("address") or "")) if p.strip()]
    cur = d["current"] if d["revising"] else None                   # a revision quotes the return that stands
    kind = d["dates"]["kind"] if not d["locked"] else (d["current"] or {}).get("kind", "original")
    tds_rows = []
    for e in d["tds"]:
        sec = re.sub(r"\s+", "", str(e["section"] or "")).upper()
        tds_rows.append({"tan": e["tan"], "section": codes["sections"].get(sec, codes["sections"].get(sec[:4], "")),
                         "gross": _int(e["gross"]), "tax": _int(e["tax"]),
                         "head": codes["heads"].get(engine.run("recon.groups", {"section": sec})["group"] or "", codes["default_head"])})
    adv = sum(x["amount"] for x in d["paid"] if engine.run("compute.paid_kind", {
        "minor": str(x.get("minor") or ""), "paid_on": compute._day(x["date"]), "fy_end": compute.year_day(ay, "end")}) == "advance")
    banks = [{"ifsc": b.get("ifsc", ""), "bank": b.get("bank", ""), "account": b.get("account", ""),
              "type": codes["account_types"].get(str(b.get("type") or "").strip().lower(), codes["default_account"]),
              "refund": "true" if i == 0 else "false"} for i, b in enumerate(c.get("banks") or [])]
    x = d["tax"]
    return {
        "today": datetime.date.today().isoformat(), "ay_code": ay[:4], "form": form,
        "sw_id": settings()["sw_id"], "sw_version": settings()["sw_version"],
        "client": {"name": c["name"], "first": " ".join(words[:-1]) if person else "",
                   "surname": words[-1] if person else c["name"], "pan": c["pan"],
                   "status": fc["statuses"].get(c["status"], ""), "substatus": fc["substatus"].get(c["status"], ""),
                   "dob": c.get("dob") or "", "verifier_pan": c.get("signer_pan") or next((p["pan"] for p in c.get("partners") or [] if p.get("pan")), "")
                   or (c["pan"] if person else ""),
                   "mobile": _int(re.sub(r"\D", "", c.get("phone") or "")[-10:]) or "", "email": c.get("email") or "",
                   "flat": (parts[0] if parts else "")[:50], "area": (parts[1] if len(parts) > 1 else "")[:50],
                   "city": (parts[-1] if len(parts) > 2 else "")[:50], "pin": _int(pin) or "", "state": (c.get("gst") or "")[:2],
                   "residential": yn(c.get("nri"), "residential"), "capacity": fc["capacity"].get(c["status"], ""),
                   "verifier": c.get("relation") or c["name"], "verifier_father": c.get("father") or ""},
        "filing": {"section": codes["return_sec"].get(kind, 11), "due": _iso(d["dates"]["due"]),
                   "orig_ack": (cur or {}).get("ack_no", ""), "orig_date": (cur or {}).get("filed_on", ""),
                   "business": yn(heads.get(codes["business_head"])), "audit": yn(y.get("audit")),
                   "books": yn(heads.get(codes["business_head"]))},
        "income": {"hp": _int(heads.get("HP")), "bp": _int(heads.get("BP")), "os": _int(heads.get("OS")),
                   "cg": _int(heads.get("CG")), "sal": _int(heads.get("SAL")), "gti": _int(d["gti"]),
                   "deductions": _int(d["deductions"]), "total": _int(d["income"])},
        "tax": {"normal": _int(x.get("tax")), "rebate": _int(x.get("rebate")), "after_rebate": _int(x.get("tax", 0) - x.get("rebate", 0)),
                "surcharge": _int(x.get("surcharge", 0) - x.get("relief", 0)), "surcharge_before": _int(x.get("surcharge")),
                "cess": _int(x.get("cess")), "gross": _int(x["total"]), "net": _int(x["total"]),
                "i234a": _int(d["interest_auto"]["a"]), "i234b": _int(d["interest_auto"]["b"]), "i234c": _int(d["interest_auto"]["c"]),
                "challans": _int(d["paid_total"]),
                "interest": _int(d["interest"]), "aggregate": _int(x["total"] + d["interest"]),
                "tds": _int(d["tds_total"]), "advance": _int(adv), "sat": _int(d["paid_total"] - adv),
                "paid": _int(d["tds_total"] + d["paid_total"]),
                "payable": _int(max(0, d["balance"]["net"])), "refund": _int(max(0, -d["balance"]["net"]))},
        "tds": tds_rows,
        "challans": [{"bsr": x["bsr"], "date": _iso(compute._day(x["date"])), "serial": _int(re.sub(r"\D", "", str(x["challan"]) or "0") or 0),
                      "amount": _int(x["amount"])} for x in d["paid"]],
        "banks": banks, "has_banks": yn(banks),
        "auditor": _auditor(c) if y.get("audit") else {},
    }


def _auditor(c: dict) -> dict:
    """The tax auditor is the CA firm whose client this is (firms.py) - its PAN and name, from its approved application."""
    import firms  # noqa: PLC0415
    f = next((x for x in firms._all() if x["id"] == c.get("firm_id")), None)  # noqa: SLF001
    return {"pan": (f or {}).get("pan", ""), "name": (f or {}).get("name", "")}


# --- putting the facts at their paths ---------------------------------------------------------------------------------------

def _get(f: dict, key: str):
    if isinstance(key, str) and key.startswith("="):
        return key[1:]
    if isinstance(key, str) and key.startswith("#"):
        return int(key[1:])
    cur = f
    for p in str(key).split("."):
        cur = cur.get(p) if isinstance(cur, dict) else None
    return cur


def _put(doc: dict, path: str, value) -> None:
    keys = path.split(".")
    for k in keys[:-1]:
        doc = doc.setdefault(k, {})
    doc[keys[-1]] = value


def _seed(s: dict, root: str, doc: dict, path: str) -> None:
    """Before a value lands inside a part the skeleton left out (it is optional), give that part its own required fields."""
    v, cur = s["definitions"][root], doc
    for k in path.split(".")[:-1]:
        v = _ref(s, v)["properties"][k]
        if k not in cur:
            cur[k] = skeleton(s, v)
        cur = cur[k]


def _has(s: dict, root: str, path: str) -> bool:
    v = s["definitions"][root]
    for k in path.split("."):
        v = _ref(s, v)
        if k not in v.get("properties", {}):
            return False
        v = v["properties"][k]
    return True


def _val(doc: dict, path: str) -> float:
    cur = doc
    for k in path.split("."):
        cur = cur.get(k) if isinstance(cur, dict) else None
    return float(cur or 0) if isinstance(cur, (int, float)) else 0.0


def books(cid: str, ay: str, form_doc: dict, s: dict, root: str) -> dict:
    """Balance sheet, trading account and P&L from rows whose SF Ref names a BS / PL item (chip itr.books)."""
    k = engine.run("itr.books")
    form = next((f for f, v in settings()["forms"].items() if v["root"] == root), "")
    rw = k["rewrites"].get(form, [])

    def at(path: str) -> str:
        for a, b in rw:
            path = path.replace(a, b)
        return path
    rows = recon.book_rows(cid, ay)
    sums: dict[str, float] = {}
    unknown, skipped = set(), set()
    for r in rows:
        if r["table"] not in k["tables"]:
            continue
        item = str(r.get("serial") or "").lower()
        if item not in k["items"]:
            unknown.add(f"{r['table']} {item or '-'}")
            continue
        sums[item] = sums.get(item, 0.0) + float(r["amount"] or 0)
    for item, amt in sums.items():
        path = at(k["items"][item])
        if _has(s, root, path):
            _seed(s, root, form_doc, path)
            _put(form_doc, path, _int(amt))
        else:
            skipped.add(item)
    if sums:
        for t in k["extra_totals"].get(form, []) + k["totals"]:
            tp = at(t["path"])
            if _has(s, root, tp):
                _seed(s, root, form_doc, tp)
                _put(form_doc, tp, _int(sum(_val(form_doc, at(p)) for p in t.get("plus", [])) - sum(_val(form_doc, at(p)) for p in t.get("minus", []))))
    ch = k["checks"]
    bp = next((r["amount"] for r in rows if r["table"] in k["profit_tables"] and re.search(k["profit_pattern"], r["label"] or "")), None)
    pbt = _val(form_doc, at(ch["pl_profit"]))
    return {"items": len(sums), "rows": sum(1 for r in rows if r["table"] in k["tables"]), "unknown": sorted(unknown), "skipped": sorted(skipped),
            "bs_sources": _val(form_doc, at(ch["bs_sources"])), "bs_applied": _val(form_doc, at(ch["bs_applied"])),
            "bs_diff": _val(form_doc, at(ch["bs_sources"])) - _val(form_doc, at(ch["bs_applied"])),
            "pl_profit": pbt, "bp_profit": bp, "pl_diff": None if bp is None or not sums else pbt - bp}


def tar_facts(cid: str, ay: str) -> dict:
    """The tax audit report's own facts: Part A, the CA (from the CA firm's approved application), and the clause rows -
    each row's figures by column (chip tar.columns), its PAN and payment mode (chip tar.codes)."""
    import intake  # noqa: PLC0415
    from core import ops  # noqa: PLC0415
    ts, tc, tm = engine.run("tar.settings"), engine.run("tar.codes"), engine.run("tar.map")
    cols = engine.run("tar.columns")["clauses"]
    c = clients.get(cid)
    yn = lambda v: tc["flags"][str(bool(v)).lower()]  # noqa: E731
    lists: dict[str, list] = {v: [] for v in tm["clause_lists"].values()}
    for m in intake.files(cid, ay)["files"]:
        for x in intake.view(cid, ay, m["id"])["rows"]:
            if x["state"] != "tagged":
                continue
            for p in intake.parse_ref(x["ref"]) or []:
                if p["form"] != "3CD" or p["table"] not in tm["clause_lists"]:
                    continue
                titles, vals = [t for t, _ in x.get("by_col") or []], [v for _, v in x.get("by_col") or []]
                party = row_party(c, x, ts)
                it = {"label": party["name"], "address": party["address"] or ts["address_blank"], "pan": party["pan"]}
                for name, pat in cols.get(p["table"], {}).items():
                    i = ops.first_index_matching(titles, pat)
                    it[name] = vals[i] if i is not None else 0
                if not it.get(tm["main_amount"].get(p["table"], ""), 1):            # one amount, under a title we cannot read
                    it[tm["main_amount"][p["table"]]] = x["amount"]
                said = {name: next((v for t, v in x.get("texts") or [] if ops.search(t, pat)), "")
                        for name, pat in tm["text_columns"].get(p["table"], {}).items()}
                yes = lambda name: bool(said.get(name)) and ops.search(said[name], tc["yes_pattern"])  # noqa: E731
                mode = ops.first_matching(x["text"] or "", tc["modes"], "pattern", "code", "") or party["mode"]
                payee = (not yes("otherwise")) if said.get("otherwise") else (mode in tc["account_payee_modes"]) if mode else True
                it |= {"mode": mode or tc["mode_default"][str(payee).lower()], "account_payee": yn(payee),
                       "squared": yn(yes("squared")), "relation": party["relation"] or said.get("relation") or tc["relation_default"],
                       "nature": ops.first_matching(x["text"] or "", tc["natures"], "pattern", "word", tc["nature_default"])}
                if not it.get("max"):
                    it["max"] = max(_int(it.get("accepted")), _int(x["amount"]))   # no maximum column: at least what was taken
                if "rate" in it:
                    blk = next((b for b in tc["blocks"] if ops.search(x["label"] or "", b["pattern"])), {"by_rate": {}})
                    it["block"] = blk["by_rate"].get(str(int(float(it["rate"] or 0))), "")
                one = {k: (_int(v) if isinstance(v, float) and k != "rate" else v) for k, v in it.items()}
                lists[tm["clause_lists"][p["table"]]].append(one)
                own = {tm["clause_lists"].get(q["table"]) for q in intake.parse_ref(x["ref"]) or [] if q["form"] == "3CD"}
                for also in tm["also"].get(p["table"], []):                   # a loan repaid in the year is a repayment too
                    if one.get(also["when"]) and also["list"] not in own:     # ... unless the row is tagged there itself
                        lists[also["list"]].append(one)
    for lst, field in tm["skip_zero"].items():
        lists[lst] = [x for x in lists[lst] if x.get(field)]
    import firms  # noqa: PLC0415
    fm = next((x for x in firms._all() if x["id"] == c.get("firm_id")), None) or {}  # noqa: SLF001
    owner = (fm.get("owner_name") or "").split()
    apin = (re.findall(r"[1-9][0-9]{5}", fm.get("address") or "") or [""])[-1]
    aparts = [q.strip() for q in re.sub(r"[1-9][0-9]{5}", "", fm.get("address") or "").split(",") if q.strip()]
    form = ts["form_by_status"].get(c["status"], ts["default_form"])
    return lists | {
        "tar": {"form": form, "form_name": ts["forms"][form]["wrap"], "status": tc["statuses"].get(c["status"]), "ay": ay,
                "pin": (re.findall(r"[1-9][0-9]{5}", c.get("address") or "") or [""])[-1], "gst_flag": yn(c.get("gst")),
                "start": _iso(compute.year_day(ay, "start", -1)), "end": _iso(compute.year_day(ay, "end")),
                "year": int(str(compute.year_day(ay, "end"))[:4]), "year_text": str(compute.year_day(ay, "end"))[:4],
                "type_of_account": tc["type_of_account"],
                "plsd": tc["plsd"][str(compute.compute(cid, ay)["has_books"] and _book_profit(cid, ay) >= 0).lower()]},
        "auditor": {"first": " ".join(owner[:-1]), "last": owner[-1] if owner else "", "membership_no": fm.get("membership_no", ""),
                    "frn": fm.get("frn", ""), "flat": (aparts[0] if aparts else "")[:100], "city": (aparts[-1] if len(aparts) > 1 else "")[:50],
                    "state": (fm.get("gstin") or "")[:2], "pin": apin, "voice": tc["voice"][str(bool(fm.get("frn"))).lower()]}}


def row_party(c: dict, x: dict, ts: dict) -> dict:
    """The party a 3CD row names - its name, and the lines under it (address, PAN) - with the client's party master filling
    in, and correcting, what the statement says (a name that wraps onto the next line, a PAN with spaces)."""
    more = [m for m in x.get("more") or [] if re.search(r"\w", m)]
    pan = next((re.sub(r"\s", "", m.group(0)) for ln in [x["text"] or ""] + more for m in [re.search(ts["pan_loose"], ln.upper())] if m), "")
    addr = [re.sub(ts["pan_loose"], "", ln, flags=re.I).strip(ts["address_trim"]) for ln in more]
    got = {"name": x["label"], "address": ts["address_join"].join(a for a in addr if a)[: ts["address_max"]], "pan": pan, "relation": "", "mode": ""}
    have = clients.party_of(c, got["name"], pan) or {}
    return {k: have.get(k) or got[k] for k in got}


def statement_parties(cid: str, ay: str) -> list[dict]:
    """Every party the year's 3CD-tagged rows name, read from the statements (for Fill the party master)."""
    import intake  # noqa: PLC0415
    tm, ts, c = engine.run("tar.map"), engine.run("tar.settings"), clients.get(cid)
    seen, out = set(), []
    for m in intake.files(cid, ay)["files"]:
        for x in intake.view(cid, ay, m["id"])["rows"]:
            if x["state"] == "tagged" and any(p["form"] == "3CD" and p["table"] in tm["party_clauses"] for p in intake.parse_ref(x["ref"]) or []):
                got = row_party({"parties": []}, x, ts)
                got["relation"] = next((v for t, v in x.get("texts") or [] if re.search(tm["relation_title"], t)), "")
                k = clients.party_key(got["name"], got["pan"])
                if got["name"] and k not in seen:
                    seen.add(k)
                    out.append(got)
    return out


def _book_profit(cid: str, ay: str) -> float:
    """The P&L's profit before tax, from the rows mapped to it (chip itr.books) - nil when there is no P&L."""
    k = engine.run("itr.books")
    return sum(r["amount"] for r in recon.book_rows(cid, ay) if r["table"] in k["profit_tables"] and re.search(k["profit_pattern"], r["label"] or ""))


def build(cid: str, ay: str, kind: str = "itr") -> tuple[dict, dict]:
    """(the JSON, a report {form, valid, errors[], filled}) - kind itr (ITR-3 / ITR-5) or tar (Form 3CA/3CB-3CD)."""
    import jsonschema  # noqa: PLC0415
    f = facts(cid, ay)
    if kind == "tar":
        f |= tar_facts(cid, ay)
        form = f["tar"]["form"]
        spec = engine.run("tar.settings")["forms"][form]
        m = engine.run("tar.map")["forms"].get(form) or []
    else:
        form = f["form"]
        spec = settings()["forms"].get(form)
        if not spec:
            raise HTTPException(409, say("itr_no_schema", form=form))
        m = engine.run("itr.map")["forms"].get(form) or []
    s, root, wrap = schema_at(spec["schema"]), spec["root"], spec.get("wrap", "ITR")
    doc = {wrap: {root: skeleton(s, {"$ref": f"#/definitions/{root}"})}}
    filled = 0
    for row in m:
        if "each" in row:
            items = []
            for it in f.get(row["each"]) or []:
                one = {}
                for p, key in row["item"].items():
                    v = _get(it, key)
                    if v not in (None, ""):
                        _put(one, p, v)
                items.append(one)
            if items or row.get("always"):
                _put(doc[wrap], row["path"], items)
                filled += len(items)
            continue
        v = _get(f, row["from"])
        if v in (None, "") and row.get("skip_blank", True):
            continue
        _put(doc[wrap], row["path"], v)
        filled += 1
    bk = books(cid, ay, doc[wrap][root], s, root) if kind == "itr" else None
    errors = sorted(jsonschema.Draft4Validator(s).iter_errors(doc), key=lambda e: list(e.absolute_path))
    out = [{"path": ".".join(str(p) for p in e.absolute_path), "message": e.message[: settings()["error_chars"]],
            "field": _field(e), "what": say("itr_err_missing" if e.validator == "required" or e.instance in ("", 0, None) else "itr_err_bad")}
           for e in errors]
    return doc, {"form": form, "valid": not out, "books": bk, "errors": out[: settings()["errors_shown"]], "error_count": len(out), "filled": filled,
                 "schema": spec["schema"].split("/")[-1], "kind": kind}


def _field(e) -> str:
    """A schema error's field in words: PartA_GEN1.PersonalInfo.Address.PinCode -> "Address: Pin Code"."""
    path = [str(p) for p in e.absolute_path if not str(p).isdigit()]
    if e.validator == "required":
        path.append(re.findall(r"'([^']+)'", e.message)[0] if "'" in e.message else "")
    words = [re.sub(r"(?<=[a-z])(?=[A-Z])|_", " ", p).strip() for p in path[2:] if p]
    return " · ".join(words[-2:])


def report(cid: str, ay: str, kind: str = "itr") -> dict:
    return build(cid, ay, kind)[1]


def export(cid: str, ay: str, kind: str = "itr") -> tuple[str, bytes]:
    doc, rep = build(cid, ay, kind)
    c = clients.get(cid)
    return f"{rep['form']} {c['pan']} AY {ay}.json", json.dumps(doc, indent=1, ensure_ascii=False).encode("utf-8")


if __name__ == "__main__":  # ponytail: the schema loads, the skeleton is shaped like it, and codes resolve
    import store as _portal_store  # noqa: F401 - registers this portal's chips, as the app does
    import jsonschema
    for form in settings()["forms"]:
        s = schema(form)
        root = settings()["forms"][form]["root"]
        sk = skeleton(s, {"$ref": f"#/definitions/{root}"})
        assert set(s["definitions"][root]["required"]) <= set(sk), form
        jsonschema.Draft4Validator.check_schema(s)
    assert engine.run("itr.codes")["sections"]["194A"] == "94A"
    print("itr_json self-check OK")
