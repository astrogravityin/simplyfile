"""New filing for a business (2026-10-11 owner: "it must cover every filing SimplyFy supports"): a partnership firm, an LLP, an
AOP / BOI - the firm flow (Clients & years -> Intake & map -> Reconcile -> Compute & close -> Tax audit), not My return.

What each upload is: the GST certificate, the deed / LLP agreement and the books are told apart by chip wizard.entity_sniff
(words, then the GSTIN, legal name, constitution, partners, PAN in the text); a GSTR-3B / GSTR-1 JSON (or their zip) by the tax
audit's own reader (audit.read_gst); last year's ITR-5 JSON by the old-returns reader (itr_import.read); 26AS, AIS, a bank
statement by My return's readers (myreturn_read). Where it goes once the client is known: chip wizard.route - the books and a bank
statement into Intake & map (intake.add), 26AS / AIS / TIS into Reconcile (recon.add), GST returns into the tax audit
(audit.add_gst), the certificate and the deed onto the client (clients.save). No second reader, no second store.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import HTTPException

import clients
from core import engine


def sniff() -> dict:
    return engine.run("wizard.entity_sniff")


def route() -> dict:
    return engine.run("wizard.route")


def _first(pats, text: str) -> str:
    for p in [pats] if isinstance(pats, str) else pats or []:
        if m := re.search(p, text, re.M):
            return re.sub(r"\s+", " ", m.group(1)).strip()
    return ""


def text_of(name: str, data: bytes, password: str = "", pan: str = "", dob: str = "") -> str:
    """The words of a document: a workbook's cells row by row, a PDF's or a text file's text."""
    import intake  # noqa: PLC0415
    import myreturn_read  # noqa: PLC0415
    ext = Path(name).suffix.lower()
    if ext in (".xlsx", ".xls", ".xlsm") or (ext == ".csv" and data[:2] != b"PK"):
        try:
            book = intake.read_book(data, ext)
            return "\n".join(" ".join(str(v) for v in r if v not in (None, "")) for rows in book.values() for r in rows)
        except Exception:  # noqa: BLE001 - not a workbook: read as text below
            pass
    try:
        return myreturn_read._text_of(data, password, pan, dob)  # noqa: SLF001 - the same text My return's readers see
    except Exception:  # noqa: BLE001
        return ""


def _status_of(constitution: str) -> str:
    return engine.run("wizard.constitution", {"text": constitution}) if constitution else ""


def read(name: str, data: bytes, password: str = "", ay: str = "", pan: str = "", dob: str = "") -> dict:
    """One business document -> {kind, method, found, problems, who: {pan, name, ay, gstin, status, partners}}."""
    import audit  # noqa: PLC0415
    import itr_import  # noqa: PLC0415
    import myreturn  # noqa: PLC0415
    import myreturn_read  # noqa: PLC0415
    k = sniff()
    who = {"pan": "", "name": "", "dob": "", "ay": "", "gstin": "", "status": "", "partners": [], "company": {}}
    head = data[:4096].lstrip()
    if head[:1] in (b"{", b"[") or (data[:2] == b"PK" and Path(name).suffix.lower() == ".zip"):
        try:
            gst = audit.read_gst(name, data)
        except HTTPException:
            gst = []
        if gst:
            g = gst[0]["gstin"]
            periods = sorted({r["period"] for r in gst})
            return {"kind": "gst_json", "method": "json", "problems": [], "facts": {"gst": gst},
                    "found": [{"label": "f_gstin", "value": g}, {"label": "f_periods", "value": str(len(periods))}],
                    "who": who | {"gstin": g, "pan": g[k["gstin_pan_from"]:k["gstin_pan_to"]]}}
        try:
            doc = json.loads(data.decode("utf-8-sig")) if head[:1] in (b"{", b"[") else None
        except ValueError:
            doc = None
        root = next((r for r in (doc or {}).get("ITR", {}) if r in k["itr_roots"]), None) if isinstance(doc, dict) and isinstance(doc.get("ITR"), dict) else None
        if root:
            try:
                f = itr_import.read(data)
            except HTTPException:
                f = {}
            return {"kind": "itr_prev", "method": "json", "problems": [], "facts": {},
                    "found": [{"label": "f_form", "value": k["itr_roots"][root]}, {"label": "f_ay", "value": str(f.get("ay") or "")}],
                    "who": who | {"pan": str(f.get("pan") or ""), "name": str(f.get("name") or ""), "ay": str(f.get("ay") or "")}}
    text = text_of(name, data, password, pan, dob)
    low = text[: int(k["head_chars"])].lower()
    for kind in k["kinds"]:
        hit = (all if kind["all"] else any)(w in low for w in kind["words"])
        if not hit:
            continue
        top = text[: int(k["head_chars"])]
        if kind["id"] == "gst_cert":
            g = _first(k["gstin"], top)
            const = _first(k["constitution"], top)
            w = who | {"gstin": g, "pan": g[k["gstin_pan_from"]:k["gstin_pan_to"]] if g else "", "name": _first(k["legal_name"], top), "status": _status_of(const)}
            found = [{"label": "f_gstin", "value": g}, {"label": "f_name", "value": w["name"]}, {"label": "f_constitution", "value": const}]
        elif kind["id"] == "coi":
            dirs = [{"name": re.sub(r"\s+", " ", a).strip(), "din": b, "pan": c} for a, b, c in re.findall(k["director"], top)]
            co = {"cin": _first(k["cin"], top), "incorporated": _first(k["incorporated"], top), "directors": dirs}
            w = who | {"name": _first(k["coi_name"], top), "pan": _first(k["pan"], top), "status": "company", "company": co}
            found = [{"label": "f_cin", "value": co["cin"]}, {"label": "f_name", "value": w["name"]}, {"label": "f_directors", "value": str(len(dirs))}]
        elif kind["id"] == "deed":
            parts = [{"name": re.sub(r"\s+", " ", a).strip(), "pan": b, "share": c} for a, b, c in re.findall(k["partner"], top)]
            w = who | {"name": _first(k["deed_name"], top), "pan": _first(k["pan"], top), "partners": parts}
            found = [{"label": "f_name", "value": w["name"]}, {"label": "f_partners", "value": str(len(parts))}]
        else:
            w = who | {"name": _first(k["book_name"], text), "pan": _first(k["pan"], top), "ay": _first(r"Assessment Year\D{0,20}(20\d\d-\d\d)", top)}
            found = [{"label": "f_name", "value": w["name"]}, {"label": "f_pan", "value": w["pan"]}]
        return {"kind": kind["id"], "method": "text", "problems": [], "facts": {}, "found": [x for x in found if x["value"]], "who": w}
    got = myreturn_read.read(name, data, password=password, ay=ay, pan=pan, dob=dob)
    w = myreturn.who(got)
    if not w.get("pan"):
        w = myreturn_read.who_of(data, password, pan, dob) | w
    return got | {"who": who | {x: w.get(x, "") for x in ("pan", "name", "dob", "ay")}}


def found_rows(found: list) -> list:
    """A reader's found lines as cards show them: the firm readers name their label by a word key (f_*), My return's by text."""
    return [{"label": f["label"], "value": f["value"], "key": f["label"].startswith("f_")} for f in found or []]


def _client_body(c: dict, **over) -> dict:
    return {x: c.get(x) for x in ("name", "pan", "status", "relation", "dob", "nri", "father", "signer_pan", "address", "email", "phone", "gst", "banks",
                                  "partners", "notes", "company") if x in c} | over


def make_client(u: dict, s: dict, row: dict, found: dict, given: dict, want: dict) -> dict:
    """The business's client: found by PAN in this firm's register, else made from what the documents (and the popup) said - its
    status, GSTIN and partners; a found one gets the GSTIN or partners it lacks. Then the year: its form, the audit and 44AD flags."""
    import firms  # noqa: PLC0415
    pan = found["pan"]
    partners = given.get("partners") or found["partners"]
    gst = given.get("gstin") or found["gstin"]
    co = (found.get("company") or {}) | (given.get("company") or {}) if want.get("has_company") else None   # a company: CIN, option, directors
    c = next((c for c in clients._mine(u) if c["pan"] == pan and not c.get("archived_at")), None)  # noqa: SLF001
    made = not c
    if not c:
        firms.may_add_client(u, clients.count(u))
        body = {"name": given.get("name") or found["name"], "pan": pan, "status": want["id"], "gst": gst, "partners": partners, "ay": s["ay"]}
        c = clients.save(u, body | ({"company": co} if co is not None else {}))
    else:
        fill = {"company": co} if co and not (c.get("company") or {}).get("cin") else {}
        if (gst and not c.get("gst")) or (partners and not c.get("partners")) or fill:
            c = clients.save(u, _client_body(c, gst=c.get("gst") or gst, partners=c.get("partners") or partners, **fill), c["id"])
    flags = {"audit": "audit" in s["picked"], "presumptive": "presumptive" in s["picked"]}
    if row.get("form") in clients.settings()["forms"]:
        flags["form"] = row["form"]
    clients.set_year(u, c["id"], s["ay"], flags)
    return {"client": clients.get(c["id"]), "made": made}


def into(u: dict, s: dict, card: dict, data: bytes) -> None:
    """A read document into the business's year where it belongs (chip wizard.route). The same file already there = Already there."""
    import audit  # noqa: PLC0415
    import intake  # noqa: PLC0415
    import recon  # noqa: PLC0415
    r = route()
    dest = r["dest"].get(card["kind"], r["dest_default"])
    card["dest"] = dest
    cid, ay = s["cid"], s["ay"]
    try:
        if dest == "intake":
            card["doc_id"] = intake.add(u, cid, ay, card["name"], data)["id"]
        elif dest == "recon":
            card["doc_id"] = recon.add(u, cid, ay, card["name"], data)["id"]
        elif dest == "gst":
            audit.add_gst(u, cid, ay, [(card["name"], data)])
        elif dest == "client":                               # a certificate or deed after the client: what it lacks, from it
            c, w = clients.get(cid), card.get("who") or {}
            fill = {k: v for k, v in (("gst", w.get("gstin")), ("partners", w.get("partners"))) if v and not c.get(k)}
            if fill:
                clients.save(u, _client_body(c, **fill), cid)
        card["state"] = "in" if dest != "keep" else "kept"
    except HTTPException as e:
        d = e.detail if isinstance(e.detail, dict) else {"message": str(e.detail)}
        if e.status_code == 409 and d.get("replace"):
            card["state"], card["already"] = "in", True
        else:
            card["state"], card["problems"] = "other", [str(d.get("message") or d)]


def take_out(u: dict, s: dict, card: dict) -> None:
    """Remove = out of the business's year too: the Intake & map / Reconcile file, the GST returns it brought."""
    import audit  # noqa: PLC0415
    import intake  # noqa: PLC0415
    import recon  # noqa: PLC0415
    if card.get("already") or card.get("state") != "in" or not s.get("cid"):
        return
    cid, ay = s["cid"], s["ay"]
    if card.get("dest") == "intake" and card.get("doc_id"):
        if any(f["id"] == card["doc_id"] for f in intake.files(cid, ay)["files"]):
            intake.delete(cid, ay, card["doc_id"])
    elif card.get("dest") == "recon" and card.get("doc_id"):
        if any(f["id"] == card["doc_id"] for f in recon.files(cid, ay)):
            recon.delete(cid, ay, card["doc_id"])
    elif card.get("dest") == "gst":
        names = {card["name"]} | {f"{card['name']}/"}
        w = audit.page(u, cid, ay)
        for g in ((w.get("gst") or {}).get("files") or []):
            if g.get("name") in names or str(g.get("name", "")).startswith(f"{card['name']}/"):
                audit.remove_gst(u, cid, ay, g["id"])


def facts(s: dict, cards: list, picked: list, want: dict) -> dict:
    """What the firm-flow hints need (chip wizard.prompts): which kinds are in, what was picked."""
    live = [c for c in cards if c["state"] in ("in", "held", "kept")]
    kinds = [c["kind"] for c in live]
    return {"flow": "firm", "books_docs": kinds.count("books"), "gst_pick": "gst" in picked, "gst_json_docs": kinds.count("gst_json"),
            "has_partners": bool(want.get("has_partners")), "deed_docs": kinds.count("deed"), "stock_pick": "stock" in picked,
            "dep_pick": "depreciation" in picked, "prev5_docs": kinds.count("itr_prev"), "audit_pick": "audit" in picked,
            "losses": "losses" in picked, "prev_docs": kinds.count("itr_prev")}


def next_screen(s: dict, picked: list) -> str:
    import intake  # noqa: PLC0415
    import recon  # noqa: PLC0415
    cid, ay = s["cid"], s["ay"]
    fs = intake.files(cid, ay)["files"]
    return engine.run("wizard.firm_next", {"books": len(fs), "untagged": sum(int(f.get(x) or 0) for f in fs for x in ("untagged", "suggested", "invalid")),
                                           "portal": len(recon.files(cid, ay)), "audit": "audit" in picked})
