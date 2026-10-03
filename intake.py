"""Intake & map - SimplyFile phase 2 (2026-10-03 client: "insert in one column in all excel sheets the table and serial
number of the relevant statement in 3CD or in ITR 3 or ITR 5").

A client's statements (.xls / .xlsx / .csv - a Tally export saved as Excel is the same thing) are uploaded per client
and assessment year, kept as uploaded and never overwritten. Each file is read into rows: the sheet, the row, the
cells, the label (first words), the numbers, and the heading the row sits under. Every row that carries a number needs
an SF Ref - `<form> <table> [#serial]`, several joined with ";" - and gets one from, in this order:
    1. a ref saved here by a person, 2. the file's own SF Ref column (chip intake.settings ref_headers), 3. a suggestion
    from chip intake.suggest (first rule whose words are in the row's label or heading; "{itr}" = the year's form).
A suggestion is never a mapping until a person accepts it. Refs are checked against chip intake.ref (forms, tables).
Download writes the workbook back with the SF Ref column filled - the client's idea, so next year's file comes tagged.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
import threading
from datetime import date, datetime
from pathlib import Path

from fastapi import HTTPException

import clients
from core import engine, store

_LOCK = threading.Lock()  # ponytail: one lock for every client's tags; per-file locks if staff collide


def settings() -> dict:
    return engine.run("intake.settings")


def say(key: str, **values) -> str:
    return engine.run("ui.intake")[key].format(**values)


def _bad(key: str, code: int = 400, **values):
    raise HTTPException(code, say(key, **values))


def _dir(cid: str, ay: str) -> Path:
    if ay not in clients.settings()["years"]:
        _bad("bad_ay", ay=ay)
    clients.get(cid)                                             # 404 for a client that is not in the register
    return store.DATA / "sf_files" / cid / ay


def _meta_name(cid: str, ay: str) -> str:
    return f"sf_files/{cid}/{ay}/files.json"


def _tags_name(cid: str, ay: str, fid: str) -> str:
    return f"sf_files/{cid}/{ay}/{fid}.tags.json"


# --- reading a workbook -------------------------------------------------------------------------------------------------

def _cell(v) -> str | float | None:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, (datetime, date)):
        return v.strftime("%d.%m.%y")
    s = re.sub(r"\s+", " ", str(v)).strip()
    return s or None


def read_book(data: bytes, ext: str) -> dict[str, list[list]]:
    """{sheet: [row cells]} with cells as str, float or None. Raises ValueError on a file that cannot be read."""
    if ext == ".csv":
        text = data.decode("utf-8-sig", errors="replace")
        return {"CSV": [[_cell(_num(c)) for c in r] for r in csv.reader(io.StringIO(text))]}
    if ext == ".xls":
        import xlrd  # noqa: PLC0415
        b = xlrd.open_workbook(file_contents=data)
        out = {}
        for s in b.sheets():
            rows = []
            for r in range(s.nrows):
                cells = []
                for c in s.row(r):
                    v = c.value
                    if c.ctype == xlrd.XL_CELL_DATE:
                        v = xlrd.xldate.xldate_as_datetime(v, b.datemode)
                    cells.append(_cell(v))
                rows.append(cells)
            out[s.name] = rows
        return out
    import openpyxl  # noqa: PLC0415
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    return {ws.title: [[_cell(v) for v in r] for r in ws.iter_rows(values_only=True)] for ws in wb.worksheets}


def _num(s: str):
    t = s.replace(",", "").strip()
    try:
        return float(t) if re.fullmatch(r"-?\d+(\.\d+)?", t) else s
    except ValueError:
        return s


def ref_column(rows: list[list], k: dict) -> tuple[int, int] | None:
    """(header row, column) of the file's own SF Ref column, if it has one."""
    want = {h.lower() for h in k["ref_headers"]}
    for r, cells in enumerate(rows[: k["header_scan_rows"]]):
        for c, v in enumerate(cells):
            if isinstance(v, str) and v.lower() in want:
                return r, c
    return None


def parse(book: dict[str, list[list]]) -> list[dict]:
    """Every row with words or numbers: label, numbers, heading, and the file's own ref."""
    k = settings()
    head_re = re.compile(k["heading_words"], re.I)
    out = []
    for sheet, rows in book.items():
        rc = ref_column(rows, k)
        heading, colhead = "", {}
        for r, cells in enumerate(rows):
            if rc and r == rc[0]:
                continue
            own = cells[rc[1]] if rc and rc[1] < len(cells) else None
            body = [v for i, v in enumerate(cells) if not (rc and i == rc[1])]
            first = next((i for i, v in enumerate(body) if v is not None), None)
            if first is None:
                continue
            serial = body[first] if isinstance(body[first], float) and body[first] == int(body[first]) \
                and body[first] < k["serial_below"] and first < 2 else None
            nums = [v for i, v in enumerate(body) if isinstance(v, float) and not (serial is not None and i == first)]
            words = [v for v in body if isinstance(v, str)]
            label = words[0] if words else ""
            text = " ".join(words)
            if not nums:
                if head_re.search(text):
                    heading, colhead = text[: k["max_len"]["heading"]], {}
                else:                                             # words under a heading = column titles ("Amount" / "repaid")
                    for i, v in enumerate(body):
                        if isinstance(v, str) and i != first:
                            colhead[i] = (colhead.get(i, "") + " " + v).strip()[: k["max_len"]["column_title"]]
                continue
            out.append({"key": f"{sheet}!{r + 1}", "sheet": sheet, "row": r + 1, "serial": int(serial) if serial is not None else None,
                        "label": label[: k["max_len"]["label"]], "text": text[: k["max_len"]["text"]], "numbers": nums, "heading": heading,
                        "own": str(own).strip() if isinstance(own, str) and own.strip() else "",
                        "by_col": [[colhead.get(i, ""), v] for i, v in enumerate(body) if isinstance(v, float) and v
                                   and not (serial is not None and i == first)]})
    return out


# --- SF Ref -----------------------------------------------------------------------------------------------------------

def parse_ref(ref: str) -> list[dict] | None:
    """'3CD 31(a) #2; ITR3 DPM 1' -> [{form, table, serial}, ...]; None when any part is not a valid ref."""
    g = engine.run("intake.ref")
    parts = [p.strip() for p in str(ref or "").split(";") if p.strip()]
    if not parts:
        return None
    out = []
    for p in parts:
        m = re.fullmatch(g["pattern"], p, re.I)
        if not m:
            return None
        form = re.sub(r"[\s-]", "", m.group(1)).upper()
        table = m.group(2).upper() if form != "3CD" else m.group(2).lower()
        if engine.run("intake.ref_part_ok", {"form": form, "table": table}) is not True:
            return None
        out.append({"form": form, "table": table, "serial": m.group(3) or m.group(4) or ""})
    return out


def norm_ref(ref: str) -> str:
    p = parse_ref(ref)
    return "; ".join(f"{x['form']} {x['table']}" + (f" #{x['serial']}" if x["serial"] else "") for x in p) if p else ""


def suggest(rows: list[dict], form: str) -> dict[str, str]:
    """{row key: suggested ref}. Numbered rules count their own serials per (sheet, ref) in row order."""
    itr = form.replace("-", "")
    counters: dict[tuple, int] = {}
    out, last = {}, None
    for x in rows:
        hit = None
        ask = engine.run("intake.suggest", {"label": x["label"] or "", "heading": x["heading"] or ""})
        if ask["continues"] and last and last[0] == x["sheet"]:
            hit = last[1]                                         # "14.09.25" under "Advance tax paid on" continues it
        elif x["label"] and ask["hit"]:
            hit = next(r for r in ask["rules"] if r["id"] == ask["hit"])
        if not hit:
            last = None
            continue
        ref = hit["ref"]
        cols = [c["ref"] for c in hit.get("by_column") or []
                if any(c["header"] in h.lower() for h, _v in x.get("by_col") or [])]
        parts = [p.strip().replace("{itr}", itr) for p in ("; ".join(cols) if cols else ref).split(";")]
        if hit.get("number"):                                      # each 3CD table counts its own serials
            for i, p in enumerate(parts):
                if p.startswith("3CD"):
                    n = counters[(x["sheet"], p)] = counters.get((x["sheet"], p), 0) + 1
                    parts[i] = f"{p} #{n}"
        out[x["key"]] = "; ".join(parts)
        last = (x["sheet"], hit)
    return out


# --- files ------------------------------------------------------------------------------------------------------------

def _form(cid: str, ay: str) -> str:
    c = clients.get(cid)
    return ((c.get("years") or {}).get(ay) or clients.year_defaults(c))["form"]


def files(cid: str, ay: str) -> dict:
    _dir(cid, ay)
    c = clients.get(cid)
    y = (c.get("years") or {}).get(ay) or clients.year_defaults(c)
    metas = store.read(_meta_name(cid, ay), [])
    return {"client": clients.row(c, ay), "form": y["form"], "audit": bool(y.get("audit")),
            "files": [m | counts(cid, ay, m["id"]) for m in metas]}


def add(user: dict, cid: str, ay: str, name: str, data: bytes) -> dict:
    k = settings()
    ext = Path(name).suffix.lower()
    if ext not in k["exts"]:
        _bad("bad_type", exts=" ".join(k["exts"]))
    if len(data) > k["max_mb"] * 1024 * 1024:
        _bad("too_big", mb=k["max_mb"])
    d = _dir(cid, ay)
    try:
        book = read_book(data, ext)
    except Exception:                                             # noqa: BLE001 - any unreadable workbook is one answer
        _bad("unreadable", name=name)
    rows = parse(book)
    if len(rows) > k["max_rows"]:
        _bad("too_many_rows", n=len(rows), most=k["max_rows"])
    with _LOCK:
        metas = store.read(_meta_name(cid, ay), [])
        sha = hashlib.sha256(data).hexdigest()
        if any(m["sha256"] == sha for m in metas):
            _bad("same_file", name=name)
        fid = store.new_id()
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{fid}{ext}").write_bytes(data)
        store.write(f"sf_files/{cid}/{ay}/{fid}.rows.json", rows)
        c = clients.get(cid)
        pan_seen = c["pan"] in re.sub(r"\s+", "", " ".join(str(v) for s in book.values() for r in s for v in r if v)).upper()
        meta = {"id": fid, "name": Path(name).name[: k["max_len"]["file_name"]], "ext": ext, "size": len(data), "sha256": sha,
                "sheets": list(book), "pan_seen": pan_seen, "uploaded_at": store.now(), "uploaded_by": user["id"]}
        store.write(_meta_name(cid, ay), metas + [meta])
        return meta | counts(cid, ay, fid)


def _meta(cid: str, ay: str, fid: str) -> dict:
    _dir(cid, ay)
    m = next((m for m in store.read(_meta_name(cid, ay), []) if m["id"] == fid), None)
    if not m:
        _bad("no_file", 404)
    return m


def view(cid: str, ay: str, fid: str) -> dict:
    """The file's rows, each with its ref, where the ref came from and whether it is valid."""
    m = _meta(cid, ay, fid)
    rows = store.read(f"sf_files/{cid}/{ay}/{fid}.rows.json", [])
    tags = store.read(_tags_name(cid, ay, fid), {})
    form = _form(cid, ay)
    sug = suggest(rows, form)
    for x in rows:
        if x["key"] in tags:
            x["ref"], x["from"] = tags[x["key"]], "saved"
        elif x["own"]:
            x["ref"], x["from"] = x["own"], "file"
        else:
            x["ref"], x["from"] = "", "none"
        x["suggestion"] = sug.get(x["key"], "") if x["from"] == "none" else ""
        x["state"] = engine.run("intake.row_state", {"has_ref": bool(x["ref"]), "ref_ok": bool(x["ref"] and parse_ref(x["ref"])),
                                                     "has_suggestion": bool(x["suggestion"]), "has_label": bool(x["label"])})
    return {"file": m, "form": form, "rows": rows, "counts": _count(rows)}


def _count(rows: list[dict]) -> dict:
    out = {"rows": len(rows), "tagged": 0, "suggested": 0, "untagged": 0, "invalid": 0, "total": 0}
    for x in rows:
        out[x["state"]] += 1
    return out


def counts(cid: str, ay: str, fid: str) -> dict:
    return {"counts": view(cid, ay, fid)["counts"]}


def set_tags(user: dict, cid: str, ay: str, fid: str, tags: dict) -> dict:
    """{row key: ref}; "" clears a saved ref. A ref that is not valid is refused, naming it."""
    _meta(cid, ay, fid)
    keys = {x["key"] for x in store.read(f"sf_files/{cid}/{ay}/{fid}.rows.json", [])}
    with _LOCK:
        saved = store.read(_tags_name(cid, ay, fid), {})
        for key, ref in (tags or {}).items():
            if key not in keys:
                continue
            ref = str(ref or "").strip()
            if not ref:
                saved.pop(key, None)
                continue
            n = norm_ref(ref)
            if not n:
                _bad("bad_ref", ref=ref[: settings()["max_len"]["ref_echo"]])
            saved[key] = n
        store.write(_tags_name(cid, ay, fid), saved)
    return view(cid, ay, fid)


def accept_all(user: dict, cid: str, ay: str, fid: str) -> dict:
    v = view(cid, ay, fid)
    return set_tags(user, cid, ay, fid, {x["key"]: x["suggestion"] for x in v["rows"] if x["state"] == "suggested"})


def delete(cid: str, ay: str, fid: str) -> None:
    m = _meta(cid, ay, fid)
    d = _dir(cid, ay)
    with _LOCK:
        store.write(_meta_name(cid, ay), [x for x in store.read(_meta_name(cid, ay), []) if x["id"] != fid])
        for p in (d / f"{fid}{m['ext']}", store.path_of(f"sf_files/{cid}/{ay}/{fid}.rows.json"), store.path_of(_tags_name(cid, ay, fid))):
            p.unlink(missing_ok=True)


def tagged_book(cid: str, ay: str, fid: str) -> tuple[str, bytes]:
    """The uploaded workbook as .xlsx with every row's ref in the SF Ref column (made at the right edge when absent)."""
    import openpyxl  # noqa: PLC0415
    m = _meta(cid, ay, fid)
    raw = (_dir(cid, ay) / f"{fid}{m['ext']}").read_bytes()
    refs = {x["key"]: x["ref"] for x in view(cid, ay, fid)["rows"] if x["ref"]}
    header = settings()["ref_headers"][0]
    if m["ext"] == ".xlsx":
        wb = openpyxl.load_workbook(io.BytesIO(raw))
    else:
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        for name, rows in read_book(raw, m["ext"]).items():
            ws = wb.create_sheet(name[:31])                # Excel itself allows 31 characters in a sheet name
            for row in rows:
                ws.append(row)
    k = settings()
    for ws in wb.worksheets:
        rows = [[c.value for c in r] for r in ws.iter_rows()]
        rc = ref_column([[_cell(v) for v in r] for r in rows], k)
        col = rc[1] + 1 if rc else ws.max_column + 1
        if not rc:
            ws.cell(row=1, column=col, value=header)
        for key, ref in refs.items():
            sheet, r = key.rsplit("!", 1)
            if sheet == ws.title:
                ws.cell(row=int(r), column=col, value=ref)
    buf = io.BytesIO()
    wb.save(buf)
    return f"{Path(m['name']).stem} - SF Ref.xlsx", buf.getvalue()


if __name__ == "__main__":  # ponytail: one runnable self-check - the client's own workbook from Requirements/
    import store as _portal_store  # noqa: F401 - registers this portal's chips, as the app does
    assert norm_ref("3cd 31(A) #2 ; itr-3 dpm 1") == "3CD 31(a) #2; ITR3 DPM #1"
    assert parse_ref("3CD 45") is None and parse_ref("ITR3 XYZ") is None and parse_ref("") is None
    import openpyxl  # noqa: PLC0415 - a made-up workbook in the shape client statements come in (no client data)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Income"
    for r in [["", "TOTAL INCOME STATEMENT"], [1, "House Property"], ["", "Rent received from the premises", "", 1200000],
              ["", "Less: Corporation taxes paid", "", 20000], ["", "Interest on SB a/c", "", 5000],
              ["", "Less: TDS as per certificates from"], ["", "Sample Bank Ltd", "", 500],
              ["", "Advance tax paid on", "15.06.25", 10000], ["", "", "15.09.25", 20000], ["", "", "", 30000]]:
        ws.append(r)
    ws = wb.create_sheet("Loans")
    for r in [["Statement regarding loans /deposits of Rs.20000 or more accepted during the year"],
              ["Sl", "Name", "Amount", "Amount", "Maximum"], ["No", "", "accepted", "repaid", "outstanding"],
              [1, "Lender A", 100000, 0, 100000], ["", "Some town"], [2, "Lender B", 50000, 20000, 50000],
              [3, "Lender C", None, 30000, 30000]]:
        ws.append(r)
    ws = wb.create_sheet("Dep")
    for r in [["Statement regarding depreciation as per IT Rules,1962"], [1, "Plant & Machinery", 100000, 15000],
              [2, "Computers", 50000, 20000]]:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    rows = parse(read_book(buf.getvalue(), ".xlsx"))
    by = {(x["sheet"], x["label"]): x["key"] for x in rows}
    s = suggest(rows, "ITR-3")
    assert s[by[("Income", "Rent received from the premises")]] == "ITR3 HP"
    assert s[by[("Income", "Sample Bank Ltd")]] == "ITR3 TDS2", "under 'Less: TDS as per certificates from'"
    assert [s.get(x["key"]) for x in rows if x["sheet"] == "Income" and x["row"] in (8, 9)] == ["ITR3 IT", "ITR3 IT"], "a date continues"
    assert not any(x["key"] in s for x in rows if x["sheet"] == "Income" and x["row"] == 10), "a sum with no words is not tagged"
    assert s[by[("Loans", "Lender A")]] == "3CD 31(a) #1"
    assert s[by[("Loans", "Lender B")]] == "3CD 31(a) #2; 3CD 31(b) #1", "accepted and repaid in one row"
    assert s[by[("Loans", "Lender C")]] == "3CD 31(b) #2", "repaid only = 31(b)"
    assert s[by[("Dep", "Computers")]] == "3CD 18 #2; ITR3 DPM"
    assert suggest(rows, "ITR-5")[by[("Income", "Interest on SB a/c")]] == "ITR5 OS"
    print("intake self-check OK")
