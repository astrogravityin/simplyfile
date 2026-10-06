"""Real returns, checked (2026-10-06 owner): every person's documents run through My return and compared, figure by figure,
with the return their CA actually filed. Run from D:/Simplyfile:

    python tools/realcheck.py "D:/My Thoughts/Returns AY 2026-27"            one folder per person inside it
    python tools/realcheck.py "D:/.../Returns" --ay 2026-27 --out report.md  the report also as a file (beside the folders)

A person's folder holds what they gave the CA - Form 16, 26AS, AIS / TIS, pre-filled JSON, bank statements - and the return
the CA filed (its JSON, as downloaded from the portal, ideally named by its acknowledgement number). The run works in a
scratch data folder - your portal's data is never touched - starts the return from the documents, takes the filing date and
each challan from the filed return (myreturn.from_filed), uses the regime the CA used, and for presumptive income (ITR-4)
the business figures the CA declared (no document holds those). Prints each figure as matched, or the gap; never a PAN.
Real files stay where they are: nothing is copied into the repository."""
import argparse
import os
import sys
import tempfile
from pathlib import Path

os.environ["PORTAL_DATA"] = os.environ["TV_DATA"] = tempfile.mkdtemp(prefix="realcheck-")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import store  # noqa: E402,F401 - maps the portal's settings and registers its chips, as the app does
import clients  # noqa: E402
import itr_json  # noqa: E402
import myreturn  # noqa: E402
import myreturn_read  # noqa: E402

U = {"id": "u-check", "firm_id": "", "role": "owner", "name": "Real-return check"}
EXTS = {".pdf", ".json", ".csv", ".txt", ".xlsx", ".xls", ".zip"}


def first_who(files: list[Path], ay: str) -> Path | None:
    """The file that names the person: a filed return or the pre-filled JSON first, then a Form 16."""
    ranked = sorted(files, key=lambda f: (f.suffix.lower() != ".json", "16" not in f.name))
    for f in ranked:
        try:
            if myreturn.who(myreturn_read.read(f.name, f.read_bytes(), ay=ay)):
                return f
        except Exception:  # noqa: BLE001 - an unreadable file is reported later, when it is added
            continue
    return None


def business_from_filed(cid: str, ay: str) -> dict | None:
    """ITR-4 / ITR-3 presumptive figures as the CA declared them: kind, nature, receipts by mode."""
    st = myreturn.state(cid, ay)
    d = next((x for x in reversed(st.get("docs") or []) if x["kind"] == "filed"), None)
    body = next(iter(((d or {}).get("facts", {}).get("filed_json") or {}).get("ITR", {}).values()), {})
    bp = body.get("ScheduleBP") or {}
    ada, ad = bp.get("PersumptiveInc44ADA") or {}, bp.get("PersumptiveInc44AD") or {}
    if ada.get("GrsReceipt"):
        nat = (bp.get("NatOfBus44ADA") or [{}])[0]
        return {"kind": "44ADA", "code": nat.get("CodeADA", ""), "name": nat.get("NameOfBusiness", ""),
                "digital": ada.get("GrsTrnOverBank44ADA", 0) + ada.get("GrsTrnOverAnyOthMode44ADA", 0), "cash": ada.get("GrsTotalTrnOverInCash44ADA", 0),
                "declared": ada.get("TotPersumptiveInc44ADA", 0)}
    if ad.get("GrsTotalTrnOver"):
        nat = (bp.get("NatOfBus44AD") or [{}])[0]
        return {"kind": "44AD", "code": nat.get("CodeAD", ""), "name": nat.get("NameOfBusiness", ""),
                "digital": ad.get("GrsTrnOverBank", 0) + ad.get("GrsTrnOverAnyOthMode", 0), "cash": ad.get("GrsTotalTrnOverInCash", 0),
                "declared": ad.get("TotPersumptiveInc44AD", 0)}
    return None


def one(folder: Path, ay: str) -> dict:
    files = sorted(f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in EXTS)
    out = {"who": folder.name, "docs": [], "rows": [], "notes": []}
    start = first_who(files, ay)
    if not start:
        out["notes"].append("no file names the person (needs a filed return, the pre-filled JSON or a Form 16)")
        return out
    s = myreturn.start(U, ay, start.name, start.read_bytes(), on_old="continue")
    cid = s["cid"]
    out["docs"].append((start.name, s["added"]["kind"], s["added"]["problems"]))
    for f in files:
        if f == start:
            continue
        a = myreturn.add_doc(U, cid, ay, f.name, f.read_bytes(), on_same="keep")
        a = a.get("added") or {"kind": "asked", "problems": [str(a.get("ask"))]}
        out["docs"].append((f.name, a["kind"], a["problems"]))
    if not any(k == "filed" for _, k, _ in out["docs"]):
        out["notes"].append("no filed return in the folder - nothing to compare with")
        return out
    myreturn.from_filed(U, cid, ay)
    if biz := business_from_filed(cid, ay):
        myreturn.answer(U, cid, ay, {"business": biz})
        out["notes"].append(f"business figures ({biz['kind']}) taken from the filed return - no document holds them")
    c = myreturn.compare(cid, ay)
    w = myreturn.work(cid, ay)
    if c["regime_filed"] != w["regime"]:
        try:
            myreturn.answer(U, cid, ay, {"regime": c["regime_filed"]})
            out["notes"].append(f"regime set to the one filed ({c['regime_filed']})")
        except Exception as x:  # noqa: BLE001
            out["notes"].append(f"the filed regime ({c['regime_filed']}) could not be used: {getattr(x, 'detail', x)}")
        c = myreturn.compare(cid, ay)
    out["form"] = (c["form_filed"], c["form_ours"])
    out["rows"] = [(r["word"], r["ours"], r["theirs"], r["level"]) for r in c["rows"]]
    doc, rep = itr_json.assemble(myreturn.facts(cid, ay), c["form_ours"])
    out["schema_ok"] = rep["valid"]
    out["schema_missing"] = sorted({x["path"].split(".")[-1] if not x["path"].split(".")[-1].isdigit() else x["path"].split(".")[-2]
                                    for x in rep["errors"]})[:12]           # field names only, never their values
    return out


PAN = __import__("re").compile(r"[A-Z]{5}[0-9]{4}[A-Z]")


def nopan(s: str) -> str:
    """A file name often carries the PAN - the report never does."""
    return PAN.sub("XXXXX0000X", s)


def money(v) -> str:
    return "-" if v is None else f"{round(v):,}"


def report(results: list[dict]) -> str:
    lines = ["# Real returns checked", ""]
    tot = sum(len(r["rows"]) for r in results)
    ok = sum(1 for r in results for x in r["rows"] if x[3] == "ok")
    lines.append(f"{len(results)} returns, {ok} of {tot} figures matched the filed return.")
    for r in results:
        bad = [x for x in r["rows"] if x[3] != "ok"]
        lines += ["", f"## {r['who']}" + (f" - filed {r['form'][0]}, ours {r['form'][1]}" if r.get("form") else ""),
                  "Documents: " + "; ".join(f"{nopan(n)} ({k}{', ' + p[0] if p else ''})" for n, k, p in r["docs"])]
        lines += [f"- {nopan(n)}" for n in r["notes"]]
        if r["rows"]:
            lines.append(f"{len(r['rows']) - len(bad)} of {len(r['rows'])} figures match. JSON fits the schema: "
                         + ("yes." if r.get("schema_ok") else "not yet - still needs: " + ", ".join(r.get("schema_missing") or []) + "."))
            if bad:
                lines += ["", "| Figure | SimplyFile | Filed | Gap |", "|---|---:|---:|---:|"]
                lines += [f"| {w} | {money(a)} | {money(b)} | {money((a or 0) - (b or 0))} |" for w, a, b, _ in bad]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Check My return against returns a CA filed.")
    ap.add_argument("folder", help="a folder with one folder per person")
    ap.add_argument("--ay", default=clients.settings()["current_ay"])
    ap.add_argument("--out", default="", help="also write the report to this file (keep it out of the repository)")
    a = ap.parse_args()
    root = Path(a.folder)
    people = sorted(p for p in root.iterdir() if p.is_dir()) or [root]
    res = []
    for p in people:
        try:
            res.append(one(p, a.ay))
        except Exception as x:  # noqa: BLE001 - one person's failure never stops the others
            res.append({"who": p.name, "docs": [], "rows": [], "notes": [f"stopped: {getattr(x, 'detail', x)}"]})
    text = report(res)
    print(text)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
