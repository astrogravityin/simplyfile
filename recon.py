"""Reconcile - SimplyFile phase 3 (2026-10-03 client voice note: "we need to correlate the income statements from our
Tally with 26AS, AIS and TIS ... that is done manually").

Two sides, one client and assessment year:
  books   the statements uploaded in Intake & map, ONLY rows whose SF Ref is saved or comes from the file (a suggestion
          is not a mapping until accepted). TDS rows (ITR TDS1/2/3), tax-paid rows (ITR IT), income rows (HP, OS ...).
  portal  files downloaded from the Income-tax portal: 26AS (TRACES text export, '^' between fields), and AIS / TIS
          exported as CSV or Excel. One reader for all: it finds each part by its title (chip recon.read parts) and each
          column by its header words (chip recon.read columns), so a new layout is a chip edit, not code.
Checks (every threshold chip recon.settings, every head chip recon.groups, every sentence chip ui.recon):
  tds      tax deducted per deductor, 26AS against the books (names matched on their significant words)
  income   amount paid/credited per head (194A -> OS, 194-I -> HP ...) against the books' income rows of that head
  paid     each challan of tax paid against the books' tax-paid rows (by amount)
A finding is red (must be cleared), amber (look at it) or ok. A person may explain a red or amber one with a note;
the year cannot move to a stage in chip recon.blocks while a red one is unexplained. Every verdict is chip recon.verdict.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
import threading
from pathlib import Path

from fastapi import HTTPException

import clients
import intake
from core import engine, store

_LOCK = threading.Lock()


def settings() -> dict:
    return engine.run("recon.settings")


def say(key: str, **values) -> str:
    return engine.run("ui.recon")[key].format(**values)


def _bad(key: str, code: int = 400, **values):
    raise HTTPException(code, say(key, **values))


def _meta_name(cid: str, ay: str) -> str:
    return f"sf_portal/{cid}/{ay}/files.json"


def _notes_name(cid: str, ay: str) -> str:
    return f"sf_portal/{cid}/{ay}/notes.json"


def _money(v) -> float | None:
    if isinstance(v, (int, float)):
        return float(v)
    t = re.sub(r"[,\s₹]|Rs\.?", "", str(v or ""))
    return float(t) if re.fullmatch(r"-?\d+(\.\d+)?", t) else None


# --- reading a portal file ----------------------------------------------------------------------------------------------

def _rows_of(data: bytes, ext: str) -> list[list]:
    if ext == ".txt":
        text = data.decode("utf-8-sig", errors="replace")
        return [[c.strip() for c in line.split("^")] for line in text.splitlines()]
    if ext == ".csv":
        text = data.decode("utf-8-sig", errors="replace")
        return [[c.strip() for c in r] for r in csv.reader(io.StringIO(text))]
    book = intake.read_book(data, ext)
    return [["" if v is None else (f"{v:.2f}" if isinstance(v, float) else str(v)) for v in r] for rows in book.values() for r in rows]


def _header(cells: list[str], k: dict) -> dict:
    """{field: column} when this row is a header (2+ known column titles, no figures), else {}. Earlier words win."""
    if any(_money(c) is not None and not re.fullmatch(r"\d{1,3}", c) for c in cells if c):
        return {}
    found, taken = {}, set()
    for col in k["columns"]:
        for w in col["words"]:
            i = next((i for i, c in enumerate(cells) if i not in taken and w in c.lower()), None)
            if i is not None:
                found[col["field"]] = i
                taken.add(i)
                break
    return found if len(found) >= 2 else {}


def read_portal(data: bytes, ext: str) -> dict:
    """{source, entries: [{kind, party, tan, section, category, gross, tax, date, bsr, challan}]}; kind = tds|tcs|paid|income."""
    k = engine.run("recon.read")
    rows = _rows_of(data, ext)
    flat = " ".join(" ".join(r) for r in rows[: settings()["sniff_lines"]]).lower()
    source = next((s["id"] for s in k["sources"] if any(w in flat for w in s["words"])), "other")
    out, part, cols, party, tan = [], None, {}, "", ""
    for cells in rows:
        line = " ".join(c for c in cells if c).lower()
        if not line:
            continue
        hit = next((p for p in k["parts"] if any(w in line for w in p["words"])), None)
        if hit and len([c for c in cells if c]) <= 3:                       # a part's title line
            part, cols, party, tan = hit["kind"], {}, "", ""
            continue
        h = _header(cells, k)
        if h:
            cols = h
            continue
        if not cols:
            continue
        get = lambda f: cells[cols[f]] if f in cols and cols[f] < len(cells) else ""   # noqa: E731
        kind = part or ("income" if source in ("ais", "tis") else "tds")
        t = next((i for i, c in enumerate(cells) if re.fullmatch(k["tan_pattern"], c)), None)
        if t is not None and kind in ("tds", "tcs") and not re.match(k["section_pattern"], get("section").upper()):
            party = next((c for c in reversed(cells[:t]) if c and not re.fullmatch(r"\d{1,4}", c)), "")
            tan = cells[t]                                                    # 26AS: the deductor's summary line
            continue
        gross, tax = _money(get("gross")), _money(get("tax"))
        if not gross and not tax:
            continue
        out.append({"kind": kind, "party": get("party") or party, "tan": get("tan") or tan, "section": get("section").upper(),
                    "category": get("category"), "gross": gross or 0.0, "tax": tax or 0.0, "date": get("date"),
                    "bsr": get("bsr"), "challan": get("challan")})
    return {"source": source, "entries": out}


# --- files --------------------------------------------------------------------------------------------------------------

def _dir(cid: str, ay: str) -> Path:
    intake._dir(cid, ay)                                     # same year and client checks as intake
    return store.DATA / "sf_portal" / cid / ay


def files(cid: str, ay: str) -> list[dict]:
    _dir(cid, ay)
    return store.read(_meta_name(cid, ay), [])


def add(user: dict, cid: str, ay: str, name: str, data: bytes) -> dict:
    k = settings()
    ext = Path(name).suffix.lower()
    if ext not in k["exts"]:
        _bad("bad_type", exts=" ".join(k["exts"]))
    if len(data) > k["max_mb"] * 1024 * 1024:
        _bad("too_big", mb=k["max_mb"])
    d = _dir(cid, ay)
    try:
        got = read_portal(data, ext)
    except Exception:                                         # noqa: BLE001 - any unreadable file is one answer
        _bad("unreadable", name=name)
    if not got["entries"]:
        _bad("nothing_read", name=name)
    with _LOCK:
        metas = store.read(_meta_name(cid, ay), [])
        sha = hashlib.sha256(data).hexdigest()
        if any(m["sha256"] == sha for m in metas):
            _bad("same_file", name=name)
        fid = store.new_id()
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{fid}{ext}").write_bytes(data)
        store.write(f"sf_portal/{cid}/{ay}/{fid}.entries.json", got["entries"])
        c = clients.get(cid)
        meta = {"id": fid, "name": Path(name).name[: k["file_name_max"]], "ext": ext, "size": len(data), "sha256": sha, "source": got["source"],
                "entries": len(got["entries"]), "pan_seen": c["pan"] in data.decode("latin-1").upper().replace(" ", ""),
                "uploaded_at": store.now(), "uploaded_by": user["id"]}
        store.write(_meta_name(cid, ay), metas + [meta])
        return meta


def delete(cid: str, ay: str, fid: str) -> None:
    with _LOCK:
        metas = files(cid, ay)
        m = next((m for m in metas if m["id"] == fid), None)
        if not m:
            _bad("no_file", 404)
        store.write(_meta_name(cid, ay), [x for x in metas if x["id"] != fid])
        (_dir(cid, ay) / f"{fid}{m['ext']}").unlink(missing_ok=True)
        store.path_of(f"sf_portal/{cid}/{ay}/{fid}.entries.json").unlink(missing_ok=True)


def portal_entries(cid: str, ay: str) -> list[dict]:
    return [e | {"source": m["source"]} for m in files(cid, ay)
            for e in store.read(f"sf_portal/{cid}/{ay}/{m['id']}.entries.json", [])]


# --- the books side -----------------------------------------------------------------------------------------------------

def book_rows(cid: str, ay: str) -> list[dict]:
    """Every intake row with a mapping a person stands behind (saved or from the file), one row per ref part."""
    out = []
    for m in intake.files(cid, ay)["files"]:
        for x in intake.view(cid, ay, m["id"])["rows"]:
            if x["state"] != "tagged":
                continue
            for p in intake.parse_ref(x["ref"]) or []:
                out.append({"table": p["table"], "form": p["form"], "label": x["label"], "text": x["text"],
                            "amount": x["numbers"][0] if x["numbers"] else 0.0, "key": x["key"], "file": m["name"]})
    return out


# --- matching ----------------------------------------------------------------------------------------------------------

def _words(name: str) -> set[str]:
    k = settings()
    stop = set(k["name_stop_words"])
    return {w for w in re.findall(r"[a-z0-9]+", str(name).lower()) if len(w) >= k["min_word_len"] and w not in stop}


def same_party(a: str, b: str) -> bool:
    """Python counts the words; chip recon.same_party decides."""
    wa, wb = _words(a), _words(b)
    return engine.run("recon.same_party", {"shared": len(wa & wb), "a_words": len(wa), "b_words": len(wb)}) is True


def agrees(books: float, portal: float) -> bool:
    return engine.run("recon.agrees", {"books": books, "portal": portal}) is True


def group_of(section: str = "", text: str = "") -> str:
    return engine.run("recon.groups", {"section": section, "text": text})["group"]


def is_income(label: str) -> bool:
    return engine.run("recon.groups", {"label": label})["is_income"] is True


def _fid(*parts) -> str:
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:12]


def _inr(v: float) -> str:
    """Indian grouping: 32724463 -> 3,27,24,463."""
    s = str(int(round(abs(v))))
    if len(s) > 3:
        s = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", s[:-3]) + "," + s[-3:]
    return ("-" if v < 0 else "") + "₹" + s


def findings(cid: str, ay: str) -> dict:
    k = settings()
    books, portal = book_rows(cid, ay), portal_entries(cid, ay)
    notes = store.read(_notes_name(cid, ay), {})
    out = []

    def add(kind, key, facts, amounts=None, **v):
        sev = engine.run("recon.verdict", {"kind": kind, **facts})
        fid = _fid(kind, key)
        out.append({"id": fid, "kind": kind, "severity": sev, "title": say(f"{kind}_{sev}", **v),
                    "note": notes.get(fid), "amounts": amounts or {}})   # books / portal figures, for the screen's bars

    if not portal:
        return {"findings": [], "books": len(books), "portal": 0, "open_red": 0, "summary": {}}

    # 1. TDS per deductor
    tds_tables = set(k["tds_tables"])
    b_tds = [r for r in books if r["table"] in tds_tables]
    p_tds: dict[str, dict] = {}
    for e in portal:
        if e["kind"] == "tds" and e["tax"]:
            key = e["tan"] or e["party"]
            p = p_tds.setdefault(key, {"party": e["party"], "tax": 0.0, "gross": 0.0})
            p["tax"] += e["tax"]
            p["gross"] += e["gross"]
    used = set()
    for key, p in p_tds.items():
        mine = [r for r in b_tds if same_party(r["label"], p["party"])]
        used.update(r["key"] for r in mine)
        got = sum(r["amount"] for r in mine)
        add("tds", key, {"found": bool(mine), "books": got, "portal": p["tax"]}, {"books": got, "portal": p["tax"]},
            party=p["party"], portal=_inr(p["tax"]), books=_inr(got))
    for r in b_tds:
        if r["key"] not in used:
            add("tds_claim", r["key"], {}, {"books": r["amount"], "portal": 0}, party=r["label"], books=_inr(r["amount"]))

    # 2. income per head
    p_inc: dict[str, float] = {}
    for e in portal:
        g = group_of(e["section"], e["category"] or e["party"])
        if g and e["kind"] in ("tds", "income") and e["gross"]:
            p_inc[g] = p_inc.get(g, 0.0) + e["gross"]
    for g, amount in p_inc.items():
        if g not in k["compare_groups"]:
            continue
        got = sum(r["amount"] for r in books if r["table"] == g and is_income(r["label"]))
        add("income", g, {"books": got, "portal": amount}, {"books": got, "portal": amount}, head=say(f"head_{g}"), portal=_inr(amount), books=_inr(got),
            gap=_inr(amount - got))

    # 3. tax paid (challans)
    b_paid = [r for r in books if r["table"] in set(k["paid_tables"])]
    free = list(b_paid)
    for e in [e for e in portal if e["kind"] == "paid"]:
        amt = e["tax"] or e["gross"]
        hit = next((r for r in free if agrees(r["amount"], amt)), None)
        if hit:
            free.remove(hit)
        add("paid", e["challan"] or e["date"] or amt, {"found": bool(hit)}, {"books": hit["amount"] if hit else 0, "portal": amt},
            amount=_inr(amt), date=e["date"] or "-")
    for r in free:
        add("paid_claim", r["key"], {}, {"books": r["amount"], "portal": 0}, amount=_inr(r["amount"]), label=r["label"])

    order = {s: i for i, s in enumerate(k["severity_order"])}
    out.sort(key=lambda f: (order.get(f["severity"], len(order)), f["kind"]))
    summary = {s: sum(1 for f in out if f["severity"] == s) for s in order}
    open_red = sum(1 for f in out if f["severity"] == "red" and not f["note"])
    return {"findings": out, "books": len(books), "portal": len(portal), "open_red": open_red, "summary": summary}


def explain(user: dict, cid: str, ay: str, fid: str, note: str) -> dict:
    f = findings(cid, ay)
    if not any(x["id"] == fid for x in f["findings"]):
        _bad("no_finding", 404)
    note = re.sub(r"\s+", " ", str(note or "")).strip()[: settings()["note_max"]]
    with _LOCK:
        notes = store.read(_notes_name(cid, ay), {})
        if note:
            notes[fid] = {"text": note, "by": user.get("name") or user["email"], "at": store.now()}
        else:
            notes.pop(fid, None)
        store.write(_notes_name(cid, ay), notes)
    return findings(cid, ay)


def gate(cid: str, ay: str, stage: str) -> None:
    """Refuse a year's move to a blocked stage while a red finding is unexplained."""
    n = findings(cid, ay)["open_red"]
    if engine.run("recon.blocks", {"stage": stage, "open_red": n}) is True:
        _bad("blocked", n=n, stage=stage)


SAMPLE_26AS = """^Annual Tax Statement^
^Permanent Account Number (PAN)^AAAHS1234K^Assessment Year^2026-27^
^PART-I - Details of Tax Deducted at Source^
^Sr. No.^Name of Deductor^TAN of Deductor^^^^^Total Amount Paid / Credited(Rs.)^Total Tax Deducted #(Rs.)^Total TDS Deposited(Rs.)
^1^HDFC BANK LIMITED^MUMH00001A^^^^^267930.00^26793.00^26793.00
^^Sr. No.^Section^Transaction Date^Status of Booking*^Date of Booking^Remarks**^Amount Paid / Credited(Rs.)^Tax Deducted ##(Rs.)^TDS Deposited(Rs.)
^^1^194A^31-Mar-2026^F^15-May-2026^-^267930.00^26793.00^26793.00
^2^ACME TRADERS PRIVATE LIMITED^HYDA00002B^^^^^460000.00^46000.00^46000.00
^^Sr. No.^Section^Transaction Date^Status of Booking*^Date of Booking^Remarks**^Amount Paid / Credited(Rs.)^Tax Deducted ##(Rs.)^TDS Deposited(Rs.)
^^1^194A^31-Mar-2026^F^15-May-2026^-^460000.00^46000.00^46000.00
^3^YES BANK LIMITED^MUMY00003C^^^^^3202838.00^320284.00^320284.00
^^Sr. No.^Section^Transaction Date^Status of Booking*^Date of Booking^Remarks**^Amount Paid / Credited(Rs.)^Tax Deducted ##(Rs.)^TDS Deposited(Rs.)
^^1^194I(b)^31-Mar-2026^F^15-May-2026^-^3202838.00^320284.00^320284.00
^PART-III - Details of Tax Paid (other than TDS or TCS)^
^Sr. No.^Major Head^Minor Head^Tax (Rs.)^Surcharge (Rs.)^Education Cess (Rs.)^Others (Rs.)^Total Tax (Rs.)^BSR Code^Date of Deposit^Challan Serial Number^Remarks**
^1^0021^100^450000.00^0.00^0.00^0.00^450000.00^0000001^13-Jun-2025^10001^
^2^0021^100^4000000.00^0.00^0.00^0.00^4000000.00^0000001^14-Sep-2025^10002^
^3^0021^100^5000000.00^0.00^0.00^0.00^5000000.00^0000001^13-Dec-2025^10003^
^4^0021^100^1500000.00^0.00^0.00^0.00^1500000.00^0000001^13-Mar-2026^10004^
"""  # a FIXTURE in TRACES' text layout, with made-up names and figures - not a real 26AS


if __name__ == "__main__":  # ponytail: one runnable self-check - the reader and the three checks on the fixture
    import store as _portal_store  # noqa: F401 - registers this portal's chips, as the app does
    got = read_portal(SAMPLE_26AS.encode(), ".txt")
    assert got["source"] == "26as", got["source"]
    tds = [e for e in got["entries"] if e["kind"] == "tds"]
    paid = [e for e in got["entries"] if e["kind"] == "paid"]
    assert len(tds) == 3 and {e["section"] for e in tds} == {"194A", "194I(B)"}, tds
    assert tds[0]["party"] == "HDFC BANK LIMITED" and tds[0]["tax"] == 26793 and tds[0]["gross"] == 267930
    assert [e["tax"] for e in paid] == [450000, 4000000, 5000000, 1500000] and paid[0]["bsr"] == "0000001", paid
    assert same_party("HDFC Bank Ltd", "HDFC BANK LIMITED") and same_party("Yes Bank", "YES BANK LIMITED")
    assert not same_party("HDFC Bank Ltd", "YES BANK LIMITED")
    assert group_of("194I(B)") == "HP" and group_of("194A") == "OS" and group_of("", "Interest from deposit") == "OS"
    assert agrees(26793, 26793) and not agrees(2700, 26793) and not is_income("Less: Repairs @ 30%")
    assert _inr(32724463) == "₹3,27,24,463" and _inr(2700) == "₹2,700"
    print("recon self-check OK")
