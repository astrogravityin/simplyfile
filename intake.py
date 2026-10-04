"""Intake & map - SimplyFile phase 2 (2026-10-03 client: "insert in one column in all excel sheets the table and serial
number of the relevant statement in 3CD or in ITR 3 or ITR 5").

A client's statements (.xls / .xlsx / .xlsm / .csv - a Tally export saved as Excel is the same thing; a text PDF best-effort) are uploaded per client
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


class Unreadable(ValueError):
    """Why a file could not be read - the key of its words in chip ui.intake."""

    def __init__(self, key: str):
        super().__init__(key)
        self.key = key


def text_amount(s: str, k: dict):
    """An amount written as text -> a number: "1,23,456.00 Dr", "(12,500)", "Rs. 5,000", "5,000 Cr", "₹ 2.5". Anything else
    stays text, unchanged. The currency marks, Dr / Cr words and their signs are chip intake.settings."""
    t = s.strip().lower()
    for c in k["number_currency"]:
        t = t.replace(c, " ")
    t, sign = t.strip(), 1
    for word in sorted(k["number_debit"] + k["number_credit"], key=len, reverse=True):
        if t.endswith(word) and (len(t) == len(word) or not t[-len(word) - 1].isalpha()):
            sign, t = (k["debit_sign"] if word in k["number_debit"] else k["credit_sign"]), t[: -len(word)].strip()
            break
    t = t.replace(",", "").replace(" ", "")
    if t.startswith("(") and t.endswith(")"):
        sign, t = sign * k["bracket_sign"], t[1:-1]
    return float(t) * sign if re.fullmatch(r"-?\d+(\.\d+)?", t) else s


def read_book(data: bytes, ext: str) -> dict[str, list[list]]:
    """{sheet: [row cells]} with cells as str, float or None. Raises Unreadable (with the reason) or ValueError."""
    k = settings()
    cell = lambda v: (text_amount(c, k) if isinstance(c := _cell(v), str) else c)  # noqa: E731
    if ext == ".csv":
        text = next((t for t in (_decode(data, e) for e in k["csv_encodings"]) if t is not None), data.decode("utf-8", errors="replace"))
        try:
            dialect = csv.Sniffer().sniff(text[:20000], delimiters="".join(k["csv_delimiters"]))
        except csv.Error:
            dialect = csv.excel
        return {"CSV": [[cell(c) for c in r] for r in csv.reader(io.StringIO(text), dialect)]}
    if ext == ".pdf":
        return _read_pdf(data, k, cell)
    if data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" and ext in (".xlsx", ".xlsm"):
        raise Unreadable("locked")                     # an encrypted .xlsx is an OLE box, not a zip
    if ext == ".xls":
        import xlrd  # noqa: PLC0415
        try:
            b = xlrd.open_workbook(file_contents=data)
        except xlrd.biffh.XLRDError as e:
            raise Unreadable("locked" if "encrypt" in str(e).lower() else "unreadable") from e
        out = {}
        for s in b.sheets():
            rows = []
            for r in range(s.nrows):
                cells = []
                for c in s.row(r):
                    v = c.value
                    if c.ctype == xlrd.XL_CELL_DATE:
                        v = xlrd.xldate.xldate_as_datetime(v, b.datemode)
                    cells.append(cell(v))
                rows.append(cells)
            out[s.name] = rows
        return out
    import openpyxl  # noqa: PLC0415
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    return {ws.title: [[cell(v) for v in r] for r in ws.iter_rows(values_only=True)] for ws in wb.worksheets}


def _decode(data: bytes, enc: str) -> str | None:
    try:
        return data.decode(enc)
    except UnicodeDecodeError:
        return None


def _read_pdf(data: bytes, k: dict, cell) -> dict[str, list[list]]:
    """A text PDF, best-effort: each page's lines in reading layout, cut into cells where two or more spaces stand.
    A PDF with no text (a scan) is said to be one."""
    from pypdf import PdfReader  # noqa: PLC0415
    try:
        pdf = PdfReader(io.BytesIO(data))
        if pdf.is_encrypted:
            raise Unreadable("locked")
        pages = [p.extract_text(extraction_mode="layout") or "" for p in pdf.pages]
    except Unreadable:
        raise
    except Exception as e:  # noqa: BLE001 - a broken PDF is one answer
        raise Unreadable("unreadable") from e
    if sum(len(p.strip()) for p in pages) < k["pdf_min_chars"]:
        raise Unreadable("pdf_scan")
    gap = re.compile(r"\s{%d,}" % int(k["pdf_gap_spaces"]))
    return {f"Page {i}": [[cell(c) for c in gap.split(line.strip())] for line in p.splitlines() if line.strip()]
            for i, p in enumerate(pages, 1)}


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
    for sheet, whole in book.items():
        at = two_sided_at(whole, k)
        parts = [("", whole)] if at is None else [("", [c[:at] for c in whole]), (k["right_suffix"], [c[at:] for c in whole])]
        for suffix, rows in parts:                               # a two-sided statement: its left side, then its right side
            _parse_part(sheet, rows, suffix, k, head_re, out)
    return out


def two_sided_at(rows: list[list], k: dict) -> int | None:
    """The column where the right side of a two-sided statement starts (liabilities | assets, expenditure | income), or None.
    A header row must name a left side and, at least two_sided_min_gap columns further right, a right side (chip words) - and
    at least two_sided_min_rows rows below must carry words and an amount on BOTH sides; a ledger with Dr and Cr columns is
    not two-sided."""
    word = lambda v: set(re.findall(r"[a-z]+", v.lower())) if isinstance(v, str) else set()  # noqa: E731
    left, right = set(k["two_sided_left"]), set(k["two_sided_right"])
    for r, cells in enumerate(rows[: k["header_scan_rows"]]):
        i = next((n for n, v in enumerate(cells) if word(v) & left), None)
        if i is None:
            continue
        j = next((n for n, v in enumerate(cells) if n >= i + k["two_sided_min_gap"] and word(v) & right), None)
        if j is None:
            continue
        both = lambda c: any(isinstance(v, str) for v in c) and any(isinstance(v, float) for v in c)  # noqa: E731
        if sum(1 for c in rows[r + 1:] if both(c[:j]) and both(c[j:])) >= k["two_sided_min_rows"]:
            return j
    return None


def _parse_part(sheet: str, rows: list[list], suffix: str, k: dict, head_re, out: list) -> None:
    """One sheet (or one side of a two-sided sheet): every row with words or numbers."""
    rc = ref_column(rows, k)
    heading, colhead = "", {}
    for r, cells in enumerate(rows):
        if rc and r == rc[0]:                                 # the SF Ref title row may carry the heading too
            words = next((v for i, v in enumerate(cells) if isinstance(v, str) and i != rc[1]), "")   # its first words, not "Amount (Rs)"
            heading = words[: k["max_len"]["heading"]] if head_re.search(words) else heading
            # ... and the column titles ("Amount (Rs)", "Previous year") - numbered as the body below is, without the SF Ref cell
            colhead = {i: v[: k["max_len"]["column_title"]] for i, v in enumerate(c for j, c in enumerate(cells) if j != rc[1])
                       if isinstance(v, str) and v.strip()}
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
        titles = [colhead.get(i, "") for i, v in enumerate(body) if isinstance(v, float) and not (serial is not None and i == first)]
        out.append({"key": f"{sheet}!{r + 1}{suffix}", "sheet": sheet, "row": r + 1, "side": "right" if suffix else "",
                    "serial": int(serial) if serial is not None else None,
                    "amount": nums[int(engine.run("intake.amount_col", {"titles": titles}))] if nums else 0.0,
                    "label": label[: k["max_len"]["label"]], "text": text[: k["max_len"]["text"]], "numbers": nums, "heading": heading,
                    "own": str(own).strip() if isinstance(own, str) and own.strip() else "",
                    "by_col": [[colhead.get(i, ""), v] for i, v in enumerate(body) if isinstance(v, float) and v
                               and not (serial is not None and i == first)]})


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
    return {"client": clients.row(c, ay), "form": y["form"], "audit": bool(y.get("audit")), "exts": settings()["exts"],
            "files": [m | counts(cid, ay, m["id"]) for m in metas]}


def add(user: dict, cid: str, ay: str, name: str, data: bytes, replace: str = "") -> dict:
    clients.guard_open(cid, ay)                                  # a closed (filed) year changes no more
    k = settings()
    ext = Path(name).suffix.lower()
    if ext not in k["exts"]:                                     # said plainly: why not, and what to do instead
        _bad("bad_type", why=say(f"cant_{k['cant_exts'].get(ext, 'other')}"))
    if len(data) > k["max_mb"] * 1024 * 1024:
        _bad("too_big", mb=k["max_mb"])
    d = _dir(cid, ay)
    try:
        book = read_book(data, ext)
    except Unreadable as e:                                      # a scan, a password, a broken file - each its own words
        _bad(e.key, name=name)
    except Exception:                                             # noqa: BLE001 - any other unreadable workbook is one answer
        _bad("unreadable", name=name)
    rows = parse(book)
    if len(rows) > k["max_rows"]:
        _bad("too_many_rows", n=len(rows), most=k["max_rows"])
    with _LOCK:
        metas = store.read(_meta_name(cid, ay), [])
        sha = hashlib.sha256(data).hexdigest()
        # 2026-10-04 owner "Can't I override?": the same file, or one of the same name, is offered as a replacement
        same = next((m for m in metas if m["sha256"] == sha or m["name"] == Path(name).name[: k["max_len"]["file_name"]]), None)
        if same and replace != same["id"]:
            raise HTTPException(409, {"message": say("same_file", name=name), "replace": same["id"],
                                      "ask": say("replace_ask", name=same["name"]), "yes": say("replace_yes")})
        old = next((m for m in metas if m["id"] == replace), None) if replace else None
        if replace and not old:
            _bad("no_file", 404)
        fid = old["id"] if old else store.new_id()
        d.mkdir(parents=True, exist_ok=True)
        if old:   # the old version is kept beside (never listed); refs stay on rows whose place and words did not change
            (d / f"{fid}{old['ext']}").replace(d / f"{fid}.v{old.get('version', 1)}{old['ext']}")
            was = {x["key"]: x["label"] for x in store.read(f"sf_files/{cid}/{ay}/{fid}.rows.json", [])}
            now_ = {x["key"]: x["label"] for x in rows}
            tags = store.read(_tags_name(cid, ay, fid), {})
            store.write(_tags_name(cid, ay, fid), {key: ref for key, ref in tags.items() if was.get(key) == now_.get(key)})
            metas = [m for m in metas if m["id"] != fid]
        (d / f"{fid}{ext}").write_bytes(data)
        store.write(f"sf_files/{cid}/{ay}/{fid}.rows.json", rows)
        c = clients.get(cid)
        pan_seen = c["pan"] in re.sub(r"\s+", "", " ".join(str(v) for s in book.values() for r in s for v in r if v)).upper()
        meta = {"id": fid, "name": Path(name).name[: k["max_len"]["file_name"]], "ext": ext, "size": len(data), "sha256": sha,
                "sheets": list(book), "pan_seen": pan_seen, "uploaded_at": store.now(), "uploaded_by": user["id"],
                "notes": ([say("pdf_warn")] if ext in k["best_effort_exts"] else []) + ([say("two_sided_note")] if any(x.get("side") for x in rows) else []),
                "version": (old or {}).get("version", 0) + 1}
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
    rows = _rows(cid, ay, m)
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
    return {"file": m, "form": form, "rows": rows, "counts": _count(rows), "groups": groups(rows),
            "client": clients.row(clients.get(cid), ay)}


def _rows(cid: str, ay: str, m: dict) -> list[dict]:
    """The parsed rows; a file read by an older parser (no amount column) is read again from the kept original, once.
    Keys (sheet!row) do not change, so the refs already saved stay on their rows."""
    name = f"sf_files/{cid}/{ay}/{m['id']}.rows.json"
    rows = store.read(name, [])
    if rows and "amount" not in rows[0]:
        try:
            rows = parse(read_book((_dir(cid, ay) / f"{m['id']}{m['ext']}").read_bytes(), m["ext"]))
            store.write(name, rows)
        except (OSError, ValueError):                             # Unreadable is a ValueError too
            pass
    return rows


def groups(rows: list[dict]) -> list[dict]:
    """Each heading's rows added the way the statement means them (chip intake.row_sign: add / less / total / note),
    and, when the statement states its own total, whether the sum agrees with it (chip recon.agrees)."""
    out: list[dict] = []
    for x in rows:
        h = x.get("heading") or ""
        if not out or out[-1]["heading"] != h:
            out.append({"heading": h, "first": x["key"], "last": x["key"], "n": 0, "net": 0.0, "stated": None})
        gp = out[-1]
        gp["last"], gp["n"] = x["key"], gp["n"] + 1
        x["group"] = len(out) - 1
        sign = engine.run("intake.row_sign", {"label": x.get("label") or ""})
        x["sign"] = sign
        amt = float(x.get("amount", (x.get("numbers") or [0])[0]) or 0)
        if sign == "total":
            gp["stated"] = amt
        elif sign in ("add", "less"):
            gp["net"] += amt if sign == "add" else -amt
    for gp in out:
        gp["net"] = round(gp["net"], 2)
        gp["agrees"] = None if gp["stated"] is None else engine.run("recon.agrees", {"books": gp["net"], "portal": gp["stated"]}) is True
    return out


def _count(rows: list[dict]) -> dict:
    out = {"rows": len(rows), "tagged": 0, "suggested": 0, "untagged": 0, "invalid": 0, "total": 0}
    for x in rows:
        out[x["state"]] += 1
    return out


def counts(cid: str, ay: str, fid: str) -> dict:
    return {"counts": view(cid, ay, fid)["counts"]}


def set_tags(user: dict, cid: str, ay: str, fid: str, tags: dict) -> dict:
    """{row key: ref}; "" clears a saved ref. A ref that is not valid is refused, naming it."""
    clients.guard_open(cid, ay)                                  # a closed (filed) year changes no more
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
    clients.guard_open(cid, ay)                                  # a closed (filed) year changes no more
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
    if m["ext"] in (".xlsx", ".xlsm"):
        wb = openpyxl.load_workbook(io.BytesIO(raw))   # an .xlsm comes back as .xlsx: the refs, not the macros
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
        right = None
        for key, ref in refs.items():
            sheet, r = key.rsplit("!", 1)
            if sheet != ws.title:
                continue
            if r.endswith(k["right_suffix"]):                     # a two-sided statement's right side: its own SF Ref column
                if right is None:
                    right = ws.max_column + 1
                    ws.cell(row=1, column=right, value=k["right_header"])
                ws.cell(row=int(r[: -len(k["right_suffix"])]), column=right, value=ref)
            else:
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
    # 2026-10-04: more formats, and plain reasons for what cannot be read
    k = settings()
    assert text_amount("1,23,456.00 Dr", k) == 123456 and text_amount("(12,500)", k) == -12500 and text_amount("Rs. 5,000", k) == 5000
    assert text_amount("Others", k) == "Others" and text_amount("To Rent", k) == "To Rent"
    semi = 'Particulars;Amount\nRent received;"1,20,000.00 Cr"\nCaf\xe9 bills;(2,500)\n'.encode("cp1252")
    assert read_book(semi, ".csv")["CSV"][1] == ["Rent received", 120000.0] and read_book(semi, ".csv")["CSV"][2] == ["Caf\xe9 bills", -2500.0]
    wb2 = openpyxl.Workbook()
    for r in [["BALANCE SHEET AS AT 31.03.2026"], ["Liabilities", "Amount", "Assets", "Amount"], ["Capital", 500000, "Fixed assets", 300000],
              ["Loans", 200000, "Debtors", "1,50,000"], ["Creditors", 100000, "Cash", 350000]]:
        wb2.active.append(r)
    b2 = io.BytesIO()
    wb2.save(b2)
    two = parse(read_book(b2.getvalue(), ".xlsm"))
    assert [(x["label"], x["amount"], x["side"]) for x in two] == [("Capital", 500000, ""), ("Loans", 200000, ""), ("Creditors", 100000, ""),
                                                                   ("Fixed assets", 300000, "right"), ("Debtors", 150000, "right"), ("Cash", 350000, "right")], two
    led = openpyxl.Workbook()
    for r in [["Date", "Particulars", "Dr", "Cr"], ["01.04.25", "Opening", 1000, None], ["02.04.25", "Rent", None, 500], ["03.04.25", "Bank", 200, None]]:
        led.active.append(r)
    b3 = io.BytesIO()
    led.save(b3)
    assert not any(x.get("side") for x in parse(read_book(b3.getvalue(), ".xlsx"))), "a ledger with Dr / Cr columns is not two-sided"

    def pdf(lines):   # a one-page text PDF, written by hand (no PDF library needed to make it)
        text = "BT /F1 10 Tf 40 800 Td 14 TL " + " ".join(f"({x}) Tj T*" for x in lines) + " ET"
        objs = ["<</Type/Catalog/Pages 2 0 R>>", "<</Type/Pages/Kids[3 0 R]/Count 1>>",
                "<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
                f"<</Length {len(text)}>>stream\n{text}\nendstream", "<</Type/Font/Subtype/Type1/BaseFont/Courier>>"]
        out, offs = b"%PDF-1.4\n", []
        for i, o in enumerate(objs, 1):
            offs.append(len(out))
            out += f"{i} 0 obj{o}endobj\n".encode()
        x = len(out)
        out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode() + b"".join(f"{o:010d} 00000 n \n".encode() for o in offs)
        return out + f"trailer<</Size {len(objs) + 1}/Root 1 0 R>>\nstartxref\n{x}\n%%EOF".encode()
    got = parse(read_book(pdf(["STATEMENT OF INCOME FOR THE YEAR", "Rent received          1,20,000.00", "Interest on FD          45,000.00"]), ".pdf"))
    assert [(x["label"], x["amount"]) for x in got] == [("Rent received", 120000.0), ("Interest on FD", 45000.0)], got
    try:
        read_book(pdf([]), ".pdf")
        raise AssertionError("a PDF with no text is a scan")
    except Unreadable as e:
        assert e.key == "pdf_scan"
    try:
        read_book(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"0" * 64, ".xlsx")
        raise AssertionError("an encrypted workbook is said to be one")
    except Unreadable as e:
        assert e.key == "locked"
    assert "save it as .xlsx" in say("bad_type", why=say(f"cant_{k['cant_exts']['.xlsb']}"))
    print("intake self-check OK")
