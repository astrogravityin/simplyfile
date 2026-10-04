"""Chip Chat question families - one question with blanks, answered by the portal's own rule chips (2026-10-04 owner: "at
least 10,000 questions").

Facts only: blanks() reads an amount, an assessment year, a date, months, an age, a status, a regime, a form, audit / 3CEB,
a role, an action and a PAN out of the question; match() finds the family whose words it carries and whose blanks are
filled (chip chat.families); answer() calls the chip that already decides it - compute.tax (with compute.regime and the
AY's slabs), chat.fee_234f, close.itr_u, compute.refund_interest, close.dates, compute.no_advance, firm.roles,
chat.pan_kind - and words the result with chip ui.chatfam.
"""
from __future__ import annotations

import datetime
import re

import clients
import compute
import firms
from core import access, engine

def fam() -> dict:
    return engine.run("chat.families", {})


def say(key: str, **v) -> str:
    s = str(engine.run("ui.chatfam", {}).get(key, key))
    for k, x in v.items():
        s = s.replace("{" + k + "}", str(x))
    return s


def rupees(n: float) -> str:
    """Indian grouping: 12,34,567."""
    n = round(float(n or 0))
    s, neg = str(abs(int(n))), n < 0
    head, tail = s[:-3], s[-3:]
    head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", head) if head else ""
    return f"{'-' if neg else ''}Rs {head + ',' if head else ''}{tail}"


def _dmy(n: int) -> str:
    s = str(n)
    return f"{s[6:8]}/{s[4:6]}/{s[:4]}" if len(s) == 8 else ""


def blanks(q: str) -> dict:
    """Every blank the question fills. Dates, years, sections, ages and months are read (and taken out) before amounts."""
    t = " " + q.lower().replace("₹", " rs ").replace("–", "-") + " "
    k = fam()
    MON = {m: i for i, m in enumerate(k["months"], 1)}
    UNIT = {x: float(v) for x, v in k["units"].items()}
    b: dict = {}
    m = re.search(r"\b([a-z]{3}[pchfatbljg][a-z]\d{4}[a-z])\b", t)
    if m:
        b["pan"] = m.group(1).upper()
        t = t.replace(m.group(1), " ")
    for pat, order in [(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](20\d\d)\b", "dmy"), (r"\b(20\d\d)-(\d{1,2})-(\d{1,2})\b", "ymd"),
                       (r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([a-z]{3})[a-z]*,?\s+(20\d\d)\b", "dMy"),
                       (r"\b([a-z]{3})[a-z]*\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(20\d\d)\b", "Mdy")]:
        m = re.search(pat, t)
        if m:
            g = m.groups()
            try:
                y, mo, d = {"dmy": (g[2], g[1], g[0]), "ymd": g, "dMy": (g[2], MON.get(g[1]), g[0]), "Mdy": (g[2], MON.get(g[0]), g[1])}[order]
                b["date"] = datetime.date(int(y), int(mo), int(d)).isoformat()
                t = t.replace(m.group(0), " ")
                break
            except (TypeError, ValueError):
                pass
    m = re.search(r"\b(?:(fy|f\.y\.|financial year|previous year)\s*)?(20\d\d)\s*-\s*(?:20)?(\d\d)\b", t)
    if m:
        a = int(m.group(2)) + (1 if m.group(1) else 0)
        b["ay"] = f"{a}-{str(a + 1)[2:]}"
        t = t.replace(m.group(0), " ")
    m = re.search(r"\b(\d+(?:\.\d+)?)\s*(months?|years?)\b(?!\s*old)", t)
    if m:
        b["months"] = float(m.group(1)) * (12 if m.group(2).startswith("year") else 1)
        t = t.replace(m.group(0), " ")
    m = re.search(r"\b(\d{2,3})\s*(?:-\s*)?(?:years?|yrs?|year-old|yr)\s*-?\s*old\b|\baged?\s*(\d{2,3})\b|\bage\s*(?:of\s*)?(\d{2,3})\b", t)
    if m:
        b["age"] = int(next(x for x in m.groups() if x))
        t = t.replace(m.group(0), " ")
    if re.search(k["senior"], t) and "age" not in b:
        b["age"] = k["ages"][1] if re.search(k["super_senior"], t) else k["ages"][0]
    units = "|".join(sorted((re.escape(x) for x in UNIT), key=len, reverse=True))
    # section numbers are not amounts: 234A, 87A, 44AD, 80CCD(1B), 139(4), section 44
    t = re.sub(rf"\b(?:u/s|sec(?:tion)?\.?|s\.)?\s*\d{{2,3}}(?!(?:{units})\b)[a-z]{{1,4}}(?:\(\w+\))?(?=\W)|\b\d{{3}}\(\w+\)|\b(?:u/s|sec(?:tion)?)\s*\d{{2,3}}\b", " ", t)
    for m in re.finditer(rf"(?:\brs\.?\s*|\binr\s*)?\b(\d[\d,]*(?:\.\d+)?)\s*({units})?\b", t):
        v = float(m.group(1).replace(",", "")) * UNIT.get(m.group(2) or "", 1)
        if m.group(2) or v >= k["min_amount"]:
            b["amount"] = v
            break
    for sid, words in k["status_words"].items():
        if any(re.search(rf"\b{re.escape(w)}\b", t) for w in words):
            b["status"] = sid
            break
    for flag, pat in k["flags"].items():           # nri, audit, 3CEB, business - each a pattern in chip chat.families
        if re.search(pat, t):
            b[flag] = True
    for rid, pat in k["regimes"].items():
        if re.search(pat, t):
            b["regime"] = rid
            break
    m = re.search(r"\bitr\s*-?\s*([35])\b", t)
    if m:
        b["form"] = f"ITR-{m.group(1)}"
    for rid, words in k["role_words"].items():
        if any(re.search(rf"\b{re.escape(w)}s?\b", t) for w in words):
            b["role"] = rid
            break
    best = None
    for aid, words in k["action_words"].items():
        for w in words:
            if re.search(rf"\b{re.escape(w)}\b", t) and (best is None or len(w) > best[1]):
                best = (aid, len(w))
    if best:
        b["action"] = best[0]
    return b


def _stems(text: str) -> set[str]:
    return {w[:5] for w in re.findall(r"[a-z0-9-]+", text.lower()) if len(w) > 2}


def match(q: str) -> dict:
    """{id, hits, ready, missing, blanks}: the family whose words the question carries most, among those it fills."""
    b = blanks(q)
    want = _stems(q)
    best = {"id": "", "hits": 0, "ready": False, "missing": [], "blanks": b}
    for f in fam()["rows"]:
        hits = len(want & _stems(f["words"]))
        missing = [x for x in f["need"] if x not in b]
        if f["need_any"] and not any(x in b for x in f["need_any"]):
            missing.append(f["need_any"][0])
        ready = hits >= 1 and not missing
        key = (ready, hits - len(missing))
        if hits and (not best["id"] or key > (best["ready"], best["hits"] - len(best["missing"]))):
            best = {"id": f["id"], "hits": hits, "ready": ready, "missing": missing, "blanks": b}
    return best


def answer(u: dict, f: dict) -> dict:
    b, fid = f["blanks"], f["id"]
    d = fam()["defaults"]
    cs = clients.settings()
    ay = b.get("ay") if b.get("ay") in cs["years"] else cs["current_ay"]
    if fid == "tax":
        k = engine.run("compute.settings", {})
        st = b.get("status", d["status"])
        reg = compute.regime_of(k, st, b.get("regime", ""), ay)
        x = engine.run("compute.tax", {"income": b["amount"], "status": st, "slabs": reg["slabs"], "steps": reg["surcharge"], "cess_pct": k["cess_pct"],
                                       "round_to": k["round_to"], "rebate_statuses": reg["rebate_statuses"], "resident": not b.get("nri"),
                                       "rebate_upto": reg["rebate_upto"], "rebate_most": reg["rebate_most"]})
        status = next((s["label"] for s in cs["statuses"] if s["id"] == st), st)
        return {"q": say("q_tax", amount=rupees(b["amount"]), status=status, nri=say("nri_word") if b.get("nri") else "", ay=ay),
                "text": say("a_tax", regime=say(f"regime_{reg['id']}"), tax=rupees(x["tax"]), rebate=say("a_tax_rebate", rebate=rupees(x["rebate"])) if x["rebate"] else "",
                            surcharge=say("a_tax_sur", surcharge=rupees(x["surcharge"])) if x["surcharge"] else "", cess=rupees(x["cess"]), total=rupees(x["total"])),
                "go": "#/compute"}
    if fid == "fee":
        return {"q": say("q_fee", amount=rupees(b["amount"])), "text": say("a_fee", fee=rupees(engine.run("chat.fee_234f", {"income": b["amount"]})))}
    if fid == "itr_u":
        x = engine.run("close.itr_u", {"net_now": b["amount"], "net_before": 0, "months": b["months"]})
        q = say("q_itr_u", amount=rupees(b["amount"]), months=f"{b['months']:g}")
        return {"q": q, "text": say("a_itr_u", pct=x["pct"], amount=rupees(b["amount"]), additional=rupees(x["additional"])) if x.get("ok") else say("a_itr_u_no")}
    if fid == "refund":
        x = engine.run("compute.refund_interest", {"refund": b["amount"], "tax_determined": b["amount"], "months": b["months"]})
        q = say("q_refund", amount=rupees(b["amount"]), months=f"{b['months']:g}")
        return {"q": q, "text": say("a_refund", interest=rupees(x["interest"])) if x.get("eligible") else say("a_refund_no")}
    if fid in ("kind_on", "due"):
        form = b.get("form", d["form"])
        on = int(b.get("date", "1900-01-01").replace("-", ""))
        x = engine.run("close.dates", {"ay_year": int(ay[:4]), "audit": bool(b.get("audit")), "tp": bool(b.get("tp")), "form": form,
                                       "filed_on": on, "today": on, "has_current": fid == "kind_on" and "revis" in "".join(f.get("words", "")), "has_updated": False})
        audit = say("with_tp") if b.get("tp") else say("with_audit") if b.get("audit") else ""
        dates = {"due": _dmy(x["due"]), "revise_by": _dmy(x["revise_by"]), "updated_by": _dmy(x["updated_by"])}
        if fid == "due":
            return {"q": say("q_due", form=form, audit=audit, ay=ay), "text": say("a_due", **dates)}
        return {"q": say("q_kind_on", date=_dmy(on), form=form, audit=audit, ay=ay), "text": say("a_kind_on", kind=say(f"kind_{x['kind'] or 'late'}"), **dates)}
    if fid == "advance":
        fy_end = int(f"{int(ay[:4])}0331")
        born = int(f"{int(ay[:4]) - b['age']}0331")
        free = engine.run("compute.no_advance", {"status": b.get("status", "individual"), "nri": bool(b.get("nri")), "born": born, "fy_end": fy_end,
                                                 "has_business": bool(b.get("business"))}) is True
        q = say("q_advance", age=b["age"], nri=say("nri_word") if b.get("nri") else "", business=say("biz_word") if b.get("business") else "")
        return {"q": q, "text": say("a_advance_no") if free else say("a_advance_yes")}
    if fid == "role_can":
        r = firms.role_of(b["role"])
        s, _, fn = b["action"].partition(".")
        what = access.label_of(s, fn)
        return {"q": say("q_role_can", role=r["label"], action=what), "go": "#/firm",
                "text": say("a_role_yes" if b["action"] in r["grants"] else "a_role_no", role=r["label"], action=what)}
    if fid == "pan":
        ok = clients.shape_ok("pan", b["pan"])
        return {"q": say("q_pan", pan=b["pan"]), "text": say("a_pan", pan=b["pan"], kind=engine.run("chat.pan_kind", {"letter": b["pan"][3]})) if ok else say("a_pan_bad", pan=b["pan"])}
    return {"q": "", "text": ""}


def ask_for(missing: list[str]) -> str:
    return say(f"ask_{missing[0]}")


if __name__ == "__main__":  # ponytail: the blanks read right
    import store  # noqa: F401 - registers this portal's chips
    b = blanks("tax on 12.5 lakh for an HUF under the old regime for AY 2025-26")
    assert b["amount"] == 1250000 and b["status"] == "huf" and b["regime"] == "old" and b["ay"] == "2025-26", b
    assert blanks("if I file ITR-3 on 15/11/2026 with tax audit")["date"] == "2026-11-15"
    assert blanks("244A on refund of Rs 2,50,000 for 7 months") | {} == {**blanks("244A on refund of Rs 2,50,000 for 7 months")}
    assert blanks("244A on refund of Rs 2,50,000 for 7 months")["amount"] == 250000
    assert blanks("does a 72 year old pay advance tax")["age"] == 72 and blanks("FY 2024-25 due date")["ay"] == "2025-26"
    assert blanks("can a tax preparer sign off")["action"] == "compute.signoff" and blanks("is ABCPA1234D valid")["pan"] == "ABCPA1234D"
    assert blanks("tax on 12lakh")["amount"] == 1200000 and blanks("tax on 50k")["amount"] == 50000 and blanks("234A on 3 lakh")["amount"] == 300000
    assert "audit" not in blanks("can an auditor delete an uploaded file") and blanks("ITR-5 with tax audit")["audit"]
    print("chatfam OK")
