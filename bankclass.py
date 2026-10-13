"""2026-10-13 SimplyFy, "Small business - only a bank statement": what each credit and debit of a bank statement is.

The statement's rows (myreturn_read.bank_pdf_serial: date, narration, ref, debit, credit, balance) are cut into groups by who the
money came from / went to (the counterparty of the narration), each group is given a suggested class by the rules of chip
bank.classify (own money - the account holder's own name read from the statement -, loans from lender names, refunds, interest,
cash deposits, customer receipts), and the person's own taps (stored by myreturn as bank_class) win over the suggestion.
Turnover for the presumptive tax (s.44AD) is the customer receipts - never loans, own money, refunds or interest.
No sentence and no word list lives here: every pattern, word and threshold is chip bank.classify."""
from __future__ import annotations

import datetime
import difflib
import re

from core import engine


def settings() -> dict:
    return engine.run("bank.classify")


def _name(s: str, k: dict) -> str:
    """A counterparty text -> its comparable form: lower-case letters and single spaces only."""
    return re.sub(r"\s+", " ", re.sub(k["name_noise"], " ", (s or "").lower())).strip()


def counterparty(narration: str, k: dict | None = None) -> str:
    """Who the money is with: the first pattern of chip bank.classify counterparty that names someone, else the narration's own
    first words (references and numbers dropped)."""
    k = k or settings()
    for pat in k["counterparty"]:
        if (m := re.match(pat, narration or "", re.I)) and len(_name(m.group(1), k).replace(" ", "")) >= int(k["name_min_letters"]):
            return _name(m.group(1), k)[: int(k["name_max"])]
    return _name(narration, k)[: int(k["name_max"])] or "?"


def is_holder(name: str, holder: str, k: dict) -> bool:
    """Loosely the account holder's own name: one is the start of the other (a narration cuts a long name), every word of it is a
    word of the holder's, or they are nearly the same letters (chip bank.classify own_min_letters / own_ratio)."""
    a, b = _name(holder, k), _name(name, k)
    ja, jb = a.replace(" ", ""), b.replace(" ", "")
    if not ja or len(jb) < int(k["own_min_letters"]):
        return False
    words = [w for w in b.split() if len(w) >= 2]
    return (ja.startswith(jb) or jb.startswith(ja) or (len(words) >= 2 and all(w in a.split() for w in words))
            or difflib.SequenceMatcher(None, ja, jb).ratio() >= float(k["own_ratio"]))


def kind_of(narration: str, name: str, direction: str, holder: str, k: dict | None = None) -> str:
    """What a credit ("cr") or debit ("dr") is, by the chip's rules in order (first match wins); the default is a customer's
    receipt for a credit and a personal spend for a debit."""
    k = k or settings()
    low = f" {(narration or '').lower()} "
    for rule in k["credit_rules" if direction == "cr" else "debit_rules"]:
        if rule.get("by") == "holder":
            if holder and is_holder(name, holder, k):
                return rule["kind"]
        elif rule.get("by") == "own_words":
            if any(w in low for w in k["own_words"]):
                return rule["kind"]
        elif any(w in low for w in rule.get("words") or []):
            return rule["kind"]
    return k["default_credit" if direction == "cr" else "default_debit"]


def _day(s: str):
    try:
        return datetime.date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def passthrough(txns: list[dict], k: dict) -> set[int]:
    """Serials of credits an equal debit follows within a few days (chip bank.classify passthrough) - money that only passed
    through the account: a loan or a transfer moved on, not a customer's payment."""
    p = k["passthrough"]
    debits = [(d, x["debit"], x["n"]) for x in txns if x["debit"] and (d := _day(x["date"]))]
    out = set()
    for x in txns:
        if not x["credit"] or x["credit"] < float(p["min_amount"]) or not (d := _day(x["date"])):
            continue
        if any(0 <= (dd - d).days <= int(p["days"]) and abs(v - x["credit"]) <= float(p["tolerance"]) for dd, v, _n in debits):
            out.add(x["n"])
    return out


def classify(txns: list[dict], holder: str, saved: dict | None = None) -> dict:
    """The statement's groups and totals. Each group: {key, dir, name, kind, suggest, class, chosen, count, total, first, last,
    flags}. totals: per class, for credits ("cr") and debits ("dr"); turnover figures (digital = receipts, cash), interest and
    salary seen, the credits still to be decided (class "ask")."""
    k = settings()
    saved = saved or {}
    pt = passthrough(txns, k)
    fr = k["fee_rule"]
    same = {}                                                     # how often each plain credit amount occurs
    for x in txns:
        if x["credit"] and kind_of(x["narration"], counterparty(x["narration"], k), "cr", holder, k) == k["default_credit"]:
            same[x["credit"]] = same.get(x["credit"], 0) + 1
    groups: dict[str, dict] = {}
    for x in txns:
        direction = "cr" if x["credit"] else "dr" if x["debit"] else ""
        if not direction:
            continue
        name = counterparty(x["narration"], k)
        kind = kind_of(x["narration"], name, direction, holder, k)
        if direction == "cr" and kind == k["default_credit"] and fr["on"]:     # the same amount again and again is a fee, the rest family and friends
            kind = fr["fee_kind"] if same[x["credit"]] >= int(fr["min_count"]) and x["credit"] >= float(fr["min_amount"]) else fr["other_kind"]
        key = f"{direction}|{kind}|{name}"
        amount = x["credit"] or x["debit"]
        g = groups.setdefault(key, {"key": key, "dir": direction, "name": name, "kind": kind, "count": 0, "total": 0.0, "first": x["date"],
                                    "last": x["date"], "through": 0, "round": 0, "biggest": 0.0})
        g["count"] += 1
        g["total"] = round(g["total"] + amount, 2)
        g["last"] = x["date"]
        g["biggest"] = max(g["biggest"], amount)
        g["through"] += 1 if direction == "cr" and x["n"] in pt else 0
        w = k["watch"]
        g["round"] += 1 if direction == "cr" and amount >= float(w["min_amount"]) and amount % float(w["round_to"]) == 0 else 0
    out, totals = [], {"cr": {}, "dr": {}}
    for g in groups.values():
        flags = []
        if g["dir"] == "cr" and g["kind"] in k["receipt_kinds"] and g["through"] and g["through"] >= g["count"] * float(k["passthrough"]["share"]):
            flags.append("through")
        if g["kind"] in k["receipt_kinds"] and g["dir"] == "cr" and g["round"] and g["round"] >= g["count"] * float(k["watch"]["share"]):
            flags.append("round")
        suggest = k["kind_class"].get(g["kind"], "other")
        if "through" in flags and g["kind"] in k["receipt_kinds"]:
            suggest = "ask"
        chosen = saved.get(g["key"])
        cls = chosen if chosen else suggest
        g |= {"suggest": suggest, "class": cls, "chosen": bool(chosen), "flags": flags}
        g.pop("through"), g.pop("round")
        out.append(g)
        totals[g["dir"]][cls] = round(totals[g["dir"]].get(cls, 0.0) + g["total"], 2)
    out.sort(key=lambda g: -g["total"])
    cr = totals["cr"]
    inc, sal = set(k["income_kinds"]), set(k["salary_kinds"])
    return {"groups": out, "totals": totals,
            "digital": cr.get("receipt", 0.0), "cash": cr.get("cash", 0.0),
            "interest": round(sum(g["total"] for g in out if g["dir"] == "cr" and g["kind"] in inc and g["class"] == "other"), 2),
            "salary": round(sum(g["total"] for g in out if g["dir"] == "cr" and g["kind"] in sal and g["class"] == "other"), 2),
            "undecided": sum(1 for g in out if g["dir"] == "cr" and g["class"] == "ask"),
            "undecided_total": cr.get("ask", 0.0),
            "credits": sum(cr.values()), "debits": sum(totals["dr"].values())}


def of_docs(docs: list[dict], saved: dict | None) -> dict | None:
    """The classification of every serial-numbered bank statement among a return's documents (their rows put together), or None."""
    rows, holder = [], ""
    for d in docs:
        b = (d.get("facts") or {}).get("bank") or {}
        if d.get("kind") == "bank" and b.get("txns"):
            rows += b["txns"]
            holder = holder or b.get("holder", "")
    return classify(rows, holder, saved) if rows else None


if __name__ == "__main__":  # ponytail: one runnable self-check - made-up rows through the chips
    import store  # noqa: F401 - registers this portal's chips, as the app does
    t = lambda n, d, nar, cr=0.0, dr=0.0: {"n": n, "date": d, "narration": nar, "credit": cr, "debit": dr}  # noqa: E731
    rows = [t(1, "2025-04-01", "UPI/ASHA DEMO MEMBER/500000000001/Payment from Ph", 1500),
            t(2, "2025-04-01", "UPI/ZZ RAVI DEMO KUMAR/500000000002/UPI", 20000),
            t(3, "2025-04-01", "UPI/ZZ RAVI DEMO KUMAR/500000000003/UPI", dr=20000),
            t(4, "2025-04-02", "UPI/KREDITBEE DEMO/500000000004/Loan", 30000),
            t(5, "2025-04-03", "UPI/BLINKIT/500000000005/Refund", 250)]
    c = classify(rows, "RAVI DEMO KUMAR ZZ")
    cls = {g["name"]: g["class"] for g in c["groups"] if g["dir"] == "cr"}
    rows += [t(6, "2025-05-01", "UPI/MEERA DEMO MEMBER/500000000006/Payment from Ph", 1500),
             t(7, "2025-06-01", "UPI/ZZ SUNIL DEMO FRIEND/500000000007/Payment from Ph", 1500),
             t(8, "2025-06-02", "UPI/ZZ SUNIL DEMO FRIEND/500000000008/Payment from Ph", 7300)]
    c = classify(rows, "RAVI DEMO KUMAR ZZ")
    cls = {g["key"]: g["class"] for g in c["groups"] if g["dir"] == "cr"}
    assert cls["cr|fee|asha demo member"] == "receipt" and cls["cr|friend|zz sunil demo friend"] == "friend", cls   # 1500 three times = fee; 7300 once = friend
    assert cls["cr|loan|kreditbee demo"] == "loan" and cls["cr|own|zz ravi demo kumar"] == "own" and cls["cr|refund|blinkit"] == "other", cls
    assert c["digital"] == 4500 and c["credits"] == 62050, c
    print("bankclass self-check OK")
