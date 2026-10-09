"""Chip Chat's question corpus - 10,000+ questions people will ask, each with the answer it must reach (2026-10-04 owner:
"let us have at least 10,000 questions").

The corpus is built here, deterministically, from the question families (an amount, a year, a date, an age, a role, a
PAN - answered by the portal's own rule chips) and from every prepared question asked in several ways. Running it asks
Chip Chat every one and counts what reached the right answer.

    python tools/chat_corpus.py            # all of them; fails under the bars below
    python tools/chat_corpus.py --sample 1500
"""
from __future__ import annotations

import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__":          # a test run asks 10,000 questions: they go to a throw-away store, never the portal's
    import tempfile
    os.environ["TV_DATA"] = tempfile.mkdtemp()
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import store  # noqa: E402,F401 - registers this portal's chips
from core import engine  # noqa: E402

BARS = {"family": 0.99, "faq": 0.95}       # share that must reach the right answer (a choice offered counts for prepared ones)


def lakh(n: float) -> list[str]:
    """The ways people write an amount: 12 lakh, 12,00,000, Rs 1200000, 1.2 crore."""
    out = [f"{n / 1e5:g} lakh", f"Rs {int(n):,}".replace(",", ""), _indian(int(n))]
    if n >= 1e7:
        out.append(f"{n / 1e7:g} crore")
    return out


def _indian(n: int) -> str:
    s = str(n)
    head, tail = s[:-3], s[-3:]
    while len(head) > 2:
        tail = head[-2:] + "," + tail
        head = head[:-2]
    return f"{head},{tail}" if head else tail


def build() -> list[dict]:
    """Every question with the answer it must reach. `clean` marks the plain way of asking each one - the only rows Chip Chat
    offers as a suggestion (2026-10-09, TradyFy: "who is in my desk? (TradyFy)" and "... - thanks" showed as suggestion chips)."""
    q: list[dict] = []
    add = lambda text, kind, want, clean=False, **blanks: q.append({"q": text, "kind": kind, "want": want, "clean": clean, "blanks": blanks})  # noqa: E731
    years = ["2023-24", "2024-25", "2025-26", "2026-27", "2027-28"]
    amounts = [x * 1e5 for x in (2.5, 3, 4, 5, 6, 7, 7.5, 8, 9, 10, 11, 12, 12.5, 13, 14, 15, 16, 18, 20, 22, 24, 25, 28, 30, 35, 40, 45, 50,
                                 55, 60, 75, 80, 90, 100, 120, 150, 200, 250, 300, 500)]
    statuses = [("individual", "an individual"), ("huf", "an HUF"), ("firm", "a partnership firm"), ("llp", "an LLP")]
    # tax: amount x status x year x regime, three ways of asking
    for i, a in enumerate(amounts):
        for st, sw in statuses:
            for ay in years:
                for reg in ("", "old", "new"):
                    if st in ("firm", "llp") and reg:
                        continue
                    r = f" under the {reg} regime" if reg else ""
                    w = lakh(a)[i % 3]
                    add(f"How much tax on {w} for {sw} for AY {ay}{r}?", "family", "tax", clean=True, amount=a, status=st, ay=ay, **({"regime": reg} if reg else {}))
                    add(f"tax payable on income of {w} - {sw}, assessment year {ay}{r}", "family", "tax", amount=a, status=st, ay=ay, **({"regime": reg} if reg else {}))
                    add(f"calculate tax for {sw} earning {lakh(a)[(i + 1) % 3]} in AY {ay}{r}", "family", "tax", amount=a, status=st, ay=ay, **({"regime": reg} if reg else {}))
    # due dates
    for ay in years:
        for form in ("ITR-3", "ITR-5"):
            for extra, flags in [("", {}), (" with tax audit", {"audit": True}), (" with Form 3CEB", {"tp": True})]:
                for n, t in enumerate(("What is the due date for {f}{x} for AY {ay}?", "last date to file {f}{x}, AY {ay}", "{f}{x} deadline for assessment year {ay}",
                                       "by when should I file {f}{x} for AY {ay}")):
                    add(t.format(f=form, x=extra, ay=ay), "family", "due", clean=n == 0, ay=ay, form=form, **flags)
    # what a return filed on a date would be
    import datetime as dt
    d0 = dt.date(2026, 7, 1)
    for i in range(0, 1800, 6):
        d = d0 + dt.timedelta(days=i)
        for form in ("ITR-3", "ITR-5"):
            for extra, flags in [("", {}), (" with tax audit", {"audit": True})]:
                fmt = [d.strftime("%d/%m/%Y"), d.isoformat(), f"{d.day} {d.strftime('%B')} {d.year}"][i % 3]
                add(f"If I file {form}{extra} for AY 2026-27 on {fmt}, what kind of return is it?", "family", "kind_on", clean=True, date=d.isoformat(), form=form, **flags)
                add(f"{form}{extra} filed on {fmt} for AY 2026-27 - original or belated?", "family", "kind_on", date=d.isoformat(), form=form, **flags)
    # ITR-U 140B
    for a in amounts[:24]:
        for m in range(1, 49, 2):
            add(f"ITR-U additional tax on extra tax of {lakh(a)[0]} filed {m} months after the year ended", "family", "itr_u", clean=True, amount=a, months=m)
    # 244A
    for a in amounts[:20]:
        for m in range(1, 25):
            add(f"244A interest on a refund of {lakh(a)[1]} for {m} months", "family", "refund", clean=True, amount=a, months=m)
    # 234F
    for a in amounts:
        add(f"What is the 234F late fee if total income is {lakh(a)[0]}?", "family", "fee", clean=True, amount=a)
        add(f"late fee for filing late with income {lakh(a)[2]}", "family", "fee", amount=a)
    # advance tax by age
    for age in range(18, 101):
        for nri, nw in [(False, ""), (True, " NRI")]:
            for biz, bw in [(False, ""), (True, " with business income")]:
                add(f"Does a {age} year old{nw}{bw} have to pay advance tax?", "family", "advance", clean=True, age=age, **({"nri": True} if nri else {}), **({"business": True} if biz else {}))
    # who may do what
    roles = {"firm_admin": "firm admin", "partner": "partner", "reviewer": "reviewer", "auditor": "auditor", "preparer": "tax preparer"}
    acts = {"compute.signoff": "sign off a computation", "compute.file": "mark a return filed", "compute.reopen": "reopen a filed year",
            "clients.create": "add a client", "clients.archive": "archive a client", "intake.delete": "delete an uploaded file",
            "intake": "upload statements", "recon": "reconcile", "itrimport": "import old returns", "analytics": "see firm analytics",
            "team": "add a team member", "firm": "edit the firm profile", "recon.delete": "delete a portal file"}
    for rid, rw in roles.items():
        for aid, aw in acts.items():
            for n, t in enumerate(("Can a {r} {a}?", "Is a {r} allowed to {a}?", "may the {r} {a}", "does a {r} have permission to {a}?")):
                add(t.format(r=rw, a=aw).replace(" a a", " an a"), "family", "role_can", clean=n == 0, role=rid, action=aid)
    # PANs
    rnd = random.Random(7)
    L = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for i in range(700):
        p = "".join(rnd.choice(L) for _ in range(3)) + "PCHFATBLJG"[i % 10] + rnd.choice(L) + f"{rnd.randint(0, 9999):04d}" + rnd.choice(L)
        add([f"Is {p} a valid PAN?", f"whose PAN is {p}", f"check PAN {p}"][i % 3], "family", "pan", clean=i % 3 == 0, pan=p)
    # every prepared question, asked several ways
    for e in engine.run("chat.faq", {})["rows"]:
        base = e["q"].rstrip("?")
        low = base[0].lower() + base[1:]
        for n, t in enumerate(("{b}?", "{l}", "Please tell me: {l}?", "Can you tell me {l}?", "Quick question - {l}", "I want to know {l}",
                               "{l}? (SimplyFile)", "Help: {l}", "{b}", "hi, {l}?", "could you explain {l}", "{l} - thanks")):
            add(t.format(b=base, l=low), "faq", e["id"], clean=n == 0)
    return q


def run(sample: int = 0) -> dict:
    import chipchat
    rows = build()
    if sample:
        rows = random.Random(1).sample(rows, min(sample, len(rows)))
    u = {"id": "corpus", "role": "owner", "email": "corpus@x.test"}
    tally = {"family": [0, 0], "faq": [0, 0]}
    fails = []
    for r in rows:
        a = chipchat.ask(u, r["q"])
        tally[r["kind"]][1] += 1
        if r["kind"] == "family":
            got = a.get("family") == r["want"] and a["route"] == "answer"
            if got:
                import chatfam
                b = chatfam.blanks(r["q"])
                got = all(b.get(k) == v for k, v in r["blanks"].items())
        else:
            got = (a.get("answer") or {}).get("id") == r["want"] or r["want"] in [o["id"] for o in a.get("options", [])]
        tally[r["kind"]][0] += got
        if not got and len(fails) < 25:
            fails.append((r["q"], r["want"], a.get("family") or (a.get("answer") or {}).get("id") or a["route"]))
    return {"total": len(rows), "tally": tally, "fails": fails}


if __name__ == "__main__":
    n = int(sys.argv[sys.argv.index("--sample") + 1]) if "--sample" in sys.argv else 0
    out = run(n)
    print(f"questions: {out['total']}")
    ok = True
    for k, (good, all_) in out["tally"].items():
        share = good / all_ if all_ else 1
        ok &= share >= BARS[k]
        print(f"  {k}: {good}/{all_} = {share:.1%} (bar {BARS[k]:.0%})")
    for f in out["fails"]:
        print("  MISS", f)
    sys.exit(0 if ok else 1)
