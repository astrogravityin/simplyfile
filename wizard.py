"""New filing - the guided way into every return (2026-10-11 owner, after a client demo: "the flow is not intuitive ... it must
be a wizard: what they are trying to do, which documents are needed, upload them, identify each, create the client from it,
ask in a popup for anything missing, prompt for further documents the uploads imply"; later the same day: "it must cover every
filing SimplyFy supports").

Four steps (chip wizard.settings steps): What you're filing (who - chip wizard.settings who: a person, an HUF, a partnership
firm, an LLP, an AOP / BOI, and a company or a trust shown as not yet (wizard.who_state); offered by wizard.offered - and what
applies, with "What kind of work?" for a business (chip wizard.scenarios, wizard.work_open); the likely form, chip wizard.form),
Documents (chip wizard.docs, each needed / good to have by wizard.doc_need), Upload (a person's or an HUF's file read by
myreturn_read.read - the same readers My return uses - and who it names by myreturn.who / myreturn_read.who_of; a business's by
wizard_firm.read; the client made from the PAN and name found, or found by PAN; the popup's questions are chip wizard.asks; what
the documents imply, chip wizard.prompts), Review (into My return at the step chip wizard.next_step names, or the firm screen
wizard.firm_next names). No second tax engine: a document is added to the return with myreturn.add_doc (or intake.add /
recon.add / audit.add_gst for a business), an answer with myreturn.answer, the client with clients.save. Progress is kept per
filing on the server (store sf_wizard/<firm>/<id>.json), so it can be carried on later; files wait in sf_wizard/<firm>/<id>/
until the client is known. Every word is chip ui.wizard.
"""
from __future__ import annotations

import re
import threading
from pathlib import Path

from fastapi import HTTPException

import clients
import myreturn
import wizard_firm
from core import engine, store
from core.ops import template

_LOCK = threading.Lock()
CARD = ("id", "name", "ext", "size", "kind", "method", "found", "problems", "who", "state", "doc_id", "seen", "added_at", "dest", "already")
WHO_KEYS = ("pan", "name", "dob", "ay", "gstin", "status", "partners", "company", "address")


def settings() -> dict:
    return engine.run("wizard.settings")


def say(key: str, **values) -> str:
    return template(engine.run("ui.wizard")[key], values)


def _bad(key: str, code: int = 400, **values):
    raise HTTPException(code, say(key, **values))


# --- where a filing lives ------------------------------------------------------------------------------------------------

def _tenant(u: dict) -> str:
    return clients.firm_id(u) or "house"


def _name(u: dict, wid: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{6,40}", wid or ""):
        _bad("no_wizard", 404)
    return f"sf_wizard/{_tenant(u)}/{wid}"          # store adds .json


def _folder(u: dict, wid: str) -> Path:
    _name(u, wid)
    p = store.DATA / "sf_wizard" / _tenant(u) / wid
    p.mkdir(parents=True, exist_ok=True)
    return p


def _load(u: dict, wid: str) -> dict:
    """A filing of THIS person's firm (the tenant wall: another firm's id is not found)."""
    s = store.read(_name(u, wid), None)
    if not s or s.get("firm_id", "") != clients.firm_id(u) or s.get("discarded_at"):
        _bad("no_wizard", 404)
    return s


def _put(u: dict, s: dict) -> None:
    s["updated_at"], s["updated_by"] = store.now(), u["id"]
    (store.DATA / "sf_wizard" / _tenant(u)).mkdir(parents=True, exist_ok=True)
    store.write(_name(u, s["id"]), s)


def _index(u: dict) -> list[dict]:
    d = store.DATA / "sf_wizard" / _tenant(u)
    out = []
    for f in sorted(d.glob("*.json")) if d.is_dir() else []:
        s = store.read(f"sf_wizard/{_tenant(u)}/{f.stem}", None)
        if s and s.get("firm_id", "") == clients.firm_id(u) and not s.get("discarded_at") and not s.get("finished_at"):
            out.append(s)
    return sorted(out, key=lambda s: s.get("updated_at", ""), reverse=True)


# --- who and what -----------------------------------------------------------------------------------------------------------

def _mode(u: dict) -> str:
    import firms  # noqa: PLC0415
    f = firms.firm_of(u)
    k = settings()
    return k["self_mode"] if f and firms.kind_of(f["kind"]).get("self_client") else k["firm_mode"]


def _state(w: dict) -> str:
    """open, or not_yet (chip wizard.who_state): switched on, and the client register knows the status."""
    return engine.run("wizard.who_state", {"supported": bool(w.get("supported", True)), "status_known": all(clients.status_of(x) for x in w.get("statuses") or [w["status"]])})


def _mine(u: dict) -> list[dict]:
    m = _mode(u)
    return [w for w in settings()["who"] if engine.run("wizard.offered", {"who": m, "not_for": [], "only_for": [w["for"]]}) is True]


def who_rows(u: dict) -> list[dict]:
    return [w for w in _mine(u) if _state(w) == "open"]


def not_yet_rows(u: dict) -> list[dict]:
    return [w for w in _mine(u) if _state(w) != "open"]


def _row(who: str) -> dict:
    return next((w for w in settings()["who"] if w["id"] == who), {})


def _flow(who: str) -> str:
    return _row(who).get("flow") or "myreturn"


def offered(who: str) -> list[str]:
    return [r["id"] for r in engine.run("wizard.scenarios")["rows"]
            if engine.run("wizard.offered", {"who": who, "not_for": r["not_for"], "only_for": r.get("only_for") or []}) is True]


def _years(ay: str) -> dict:
    y = int(ay[:4])
    return {"ay": ay, "fy": f"{y - 1}-{str(y)[2:]}", "cy": str(y - 1)}


def _filled(row: dict, ay: str) -> dict:
    v = _years(ay)
    return {k: template(x, v) if isinstance(x, str) else x for k, x in row.items()}


def _picks(who: str, picked: list) -> list[str]:
    rows = {r["id"]: r for r in engine.run("wizard.scenarios")["rows"]}
    ok = set(offered(who))
    out = []
    for p in picked or []:
        p = str(p)
        if p not in ok:
            _bad("bad_pick", id=p)
        out += [x for x in [p, *rows[p]["implies"]] if x in ok and x not in out]
    return out


def _self_client(u: dict) -> dict | None:
    return next((c for c in clients._mine(u) if not c.get("archived_at")), None)  # noqa: SLF001 - a self-filer's one client


def _film(film: str) -> bool:
    k = engine.run("wizard.cases")
    return (Path(__file__).resolve().parent / k["film_dir"] / f"{film}{k['film_ext']}").is_file()


def cases(u: dict) -> list[dict]:
    """The worked examples for the cards this person sees, each with whether its film is there to play."""
    k = engine.run("wizard.cases")
    mine = {w["id"] for w in who_rows(u)}
    return [{x: c[x] for x in ("id", "who", "ay", "title", "line", "form", "opens", "film")} | {"has_film": _film(c["film"])}
            for c in k["rows"] if c["who"] in mine]


def home(u: dict) -> dict:
    k = clients.settings()
    who = who_rows(u)
    return {"who": [_filled(w, k["current_ay"]) for w in who], "not_yet": [_filled(w, k["current_ay"]) for w in not_yet_rows(u)],
            "offered": {w["id"]: offered(w["id"]) for w in who},
            "scenarios": [_filled(r, k["current_ay"]) for r in engine.run("wizard.scenarios")["rows"]],
            "steps": settings()["steps"], "current_ay": k["current_ay"], "years": k["years"], "cases": cases(u),
            "sessions": [_brief(s) for s in _index(u)]}


def _brief(s: dict) -> dict:
    c = _client(s)
    return {"id": s["id"], "who": s["who"], "ay": s["ay"], "step": s.get("step", ""), "picked": s.get("picked", []),
            "files": len(s.get("files") or []), "updated_at": s.get("updated_at", ""), "client": c["name"] if c else ""}


def start(u: dict, body: dict) -> dict:
    k = settings()
    who = str(body.get("who") or "")
    if who in {w["id"] for w in not_yet_rows(u)}:
        _bad("not_yet", 409, who=_row(who).get("label", who))
    if who not in {w["id"] for w in who_rows(u)}:
        _bad("bad_who")
    ay = str(body.get("ay") or clients.settings()["current_ay"])
    if ay not in clients.settings()["years"]:
        raise HTTPException(400, clients.say("bad_ay", ay=ay))
    if len(_index(u)) >= int(k["sessions_max"]):
        _bad("too_many_open", 409, n=k["sessions_max"])
    s = {"id": store.new_id(), "firm_id": clients.firm_id(u), "by": u["id"], "created_at": store.now(), "who": who, "ay": ay,
         "picked": _picks(who, body.get("picked") or []), "step": str(body.get("step") or k["steps"][1]), "files": [], "given": {}, "cid": ""}
    if who == k["self_mode"] and (c := _self_client(u)):
        s["cid"] = c["id"]
    with _LOCK:
        _put(u, s)
    return view(u, s)


def update(u: dict, wid: str, body: dict) -> dict:
    with _LOCK:
        s = _load(u, wid)
        if "who" in body and body["who"] != s["who"]:
            if s.get("cid") or str(body["who"]) not in {w["id"] for w in who_rows(u)} or _flow(str(body["who"])) != _flow(s["who"]) and s.get("files"):
                _bad("bad_who")
            s["who"] = str(body["who"])
            s["picked"] = [p for p in s["picked"] if p in offered(s["who"])]
        if "picked" in body:
            s["picked"] = _picks(s["who"], body["picked"])
        if body.get("step") in settings()["steps"]:
            s["step"] = body["step"]
        if "answers" in body:
            _answers(u, s, body["answers"] or {})
        _put(u, s)
    _resolve(u, s)
    return view(u, s)


def discard(u: dict, wid: str) -> dict:
    """Discard = the wizard's progress dropped (kept on disk, never listed again); the client and the return stay."""
    with _LOCK:
        s = _load(u, wid)
        s["discarded_at"] = store.now()
        _put(u, s)
    return home(u)


def finish(u: dict, wid: str) -> dict:
    with _LOCK:
        s = _load(u, wid)
        if not s.get("cid"):
            _bad("no_wizard", 409)
        v = view(u, s, deep=True)
        s["finished_at"] = store.now()
        _put(u, s)
    return {"link": v["link"], "said": say("done")}


# --- the popup's answers ------------------------------------------------------------------------------------------------------

def _partners(v) -> list[dict]:
    if not isinstance(v, list):
        _bad("bad_choice", value=str(v)[:40])
    if len(v) > int(settings()["partners_max"]):
        _bad("too_many_partners", n=settings()["partners_max"])
    out = []
    for p in v:
        if not isinstance(p, dict) or not str(p.get("name") or "").strip():
            continue
        pan = re.sub(r"\s", "", str(p.get("pan") or "")).upper()
        if pan and engine.run("clients.shape_ok", {"kind": "pan", "value": pan}) is not True:
            _bad("bad_pan", pan=pan)
        out.append({"name": str(p["name"]).strip()[:120], "pan": pan, "share": str(p.get("share") or "").strip()[:10]})
    return out


def _answers(u: dict, s: dict, a: dict) -> None:
    ok = {x["id"]: x for x in settings()["asks"]}
    g = s.setdefault("given", {})
    for f, v in a.items():
        if f not in ok:
            _bad("bad_answer", field=f)
        if ok[f]["input"] == "partners":
            g[f] = _partners(v)
            continue
        if ok[f]["input"] == "company":                     # checked whole by company.clean when the client is saved
            if not isinstance(v, dict):
                _bad("bad_choice", value=str(v)[:40])
            g[f] = {"cin": str(v.get("cin") or "").strip().upper()[:21], "incorporated": str(v.get("incorporated") or "")[:10],
                    "option": str(v.get("option") or ""), "manufacturing": v.get("manufacturing") in (True, "yes", "true", "on"),
                    "directors": [
                        {"name": str(d.get("name") or "").strip()[:125], "din": re.sub(r"\D", "", str(d.get("din") or ""))[:8],
                         "pan": re.sub(r"\s", "", str(d.get("pan") or "")).upper()[:10]} for d in (v.get("directors") or [])[: int(settings()["partners_max"])]
                        if isinstance(d, dict) and str(d.get("name") or "").strip()]}
            continue
        v = str(v or "").strip()
        if ok[f]["input"] == "pan":
            v = re.sub(r"\s", "", v).upper()
            if v and engine.run("clients.shape_ok", {"kind": "pan", "value": v}) is not True:
                _bad("bad_pan", pan=v)
        if ok[f]["input"] == "gstin":
            v = re.sub(r"\s", "", v).upper()
            if v and not re.fullmatch(wizard_firm.sniff()["gstin"], v):
                _bad("bad_gstin", gstin=v)
        if f == "status":
            st = _found_status(s, g.get("pan") or _found(s)["pan"])
            to = next((w for w in who_rows(u) if st and st["id"] in (w.get("statuses") or [w["status"]])), None)
            if v != "switch" or not to:
                _bad("bad_choice", value=v)
            s["who"] = to["id"]
            s["picked"] = [p for p in s["picked"] if p in offered(s["who"])]
            continue
        if f == "mobile":
            v = re.sub(r"\D", "", v)[-10:]
            if v and not re.fullmatch(r"[6-9]\d{9}", v):
                _bad("bad_mobile")
        if f == "email" and v and not re.fullmatch(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", v):
            _bad("bad_email")
        if f == "residence" and v not in ("yes", "no", "later"):
            _bad("bad_choice", value=v)
        if f == "pan_pick" and v not in _found(s)["pans"]:
            _bad("bad_choice", value=v)
        g[f] = v[:125]
        if f == "dob" and v and engine.run("clients.shape_ok", {"kind": "date", "value": v}) is not True:
            raise HTTPException(400, clients.say("bad_dob", dob=v))


def offered_who(u: dict) -> set:
    return {w["id"] for w in who_rows(u)}


def _status_of_pan(pan: str) -> dict | None:
    return next((x for x in clients.settings()["statuses"] if pan and x["pan_letter"] == pan[3:4]), None)


def _found_status(s: dict, pan: str) -> dict | None:
    """The status the documents say: a GST certificate's constitution, else the PAN's 4th letter."""
    st = _found(s).get("status")
    return clients.status_of(st) if st and clients.status_of(st) else _status_of_pan(pan)


def _want(s: dict) -> dict:
    """The status the return needs: a self-filer's own client's (an HUF may file its own), else the chosen card's - and of an
    AOP / BOI card, the one the PAN's 4th letter names."""
    if s["who"] == settings()["self_mode"] and (c := _client(s)):
        return clients.status_of(c["status"])
    w = _row(s["who"])
    sts = [clients.status_of(x) for x in w.get("statuses") or [w["status"]] if clients.status_of(x)]
    pan = (_client(s) or {}).get("pan") or _found(s)["pan"]
    return next((x for x in sts if pan and x["pan_letter"] == pan[3:4]), sts[0] if sts else clients.status_of(w["status"]))


def _pan_fit(s: dict, pan: str) -> str:
    w = _row(s["who"])
    sts = [clients.status_of(x) for x in w.get("statuses") or [w["status"]] if clients.status_of(x)]
    if s["who"] == settings()["self_mode"]:
        sts = [_want(s)]
    return engine.run("wizard.pan_kind", {"pan": pan, "letter": pan[3:4], "wants": [x["pan_letter"] for x in sts],
                                          "found_status": _found(s).get("status") or "", "want_statuses": [x["id"] for x in sts]})


def _found(s: dict) -> dict:
    """What the documents say about the person or business: every PAN named, and the name / date of birth (and a business's
    GSTIN, constitution and partners) of the chosen one."""
    cards = [c for c in s.get("files") or [] if c["state"] != "other"]
    pans = list(dict.fromkeys(c["who"]["pan"] for c in cards if (c.get("who") or {}).get("pan")))
    g = s.get("given") or {}
    pan = g.get("pan") or g.get("pan_pick") or (pans[0] if len(pans) == 1 else "")
    mine = [c["who"] for c in cards if (c.get("who") or {}).get("pan") == pan or (c["kind"] == "bank" and not (c.get("who") or {}).get("pan"))]
    first = lambda f: next((w[f] for w in mine if w.get(f)), "")  # noqa: E731
    cert = next((c["who"] for c in cards if c["kind"] in ("gst_cert", "coi") and c["who"].get("pan") == pan), {})
    return {"pans": pans, "pan": pan, "name": cert.get("name") or first("name"), "dob": first("dob"), "gstin": first("gstin"), "address": first("address"),
            "status": cert.get("status") or "", "partners": next((w["partners"] for w in mine if w.get("partners")), []),
            "company": next((w["company"] for w in mine if w.get("company")), {})}


def _resolve(u: dict, s: dict) -> None:
    """Once the PAN and name are known (from the documents or the popup), the client is made - or found by PAN - and every
    document waiting is added to its return; the popup's answers for the return (Karta, residence) go in too. A business: the
    client with its status, GSTIN and partners, its year set (ITR-5, the audit, 44AD), each document into its screen."""
    import firms  # noqa: PLC0415
    g = s.get("given") or {}
    firm_flow = _flow(s["who"]) == settings()["firm_flow"]
    if not s.get("cid"):
        f = _found(s)
        want = _want(s)
        name = g.get("huf_name") or g.get("name") or f["name"]
        if not f["pan"] or _pan_fit(s, f["pan"]) != "ok" or not name:
            return
        if firm_flow:
            if want.get("has_partners") and "partners" not in g and not (_by_pan(u, f["pan"]) or {}).get("partners"):
                return                                      # the popup shows the deed's partners to confirm first; the client waits
            if want.get("has_company") and "company" not in g and not ((_by_pan(u, f["pan"]) or {}).get("company") or {}).get("cin"):
                return                                      # a company: its CIN, option and directors confirmed first
            got = wizard_firm.make_client(u, s, _row(s["who"]), f, g, want)
            s["made"], s["cid"] = got["made"], got["client"]["id"]
        else:
            c = next((c for c in clients._mine(u) if c["pan"] == f["pan"] and not c.get("archived_at")), None)  # noqa: SLF001
            s["made"] = not c
            if not c:
                firms.may_add_client(u, clients.count(u))
                c = clients.save(u, {"name": name, "pan": f["pan"], "status": want["id"], "dob": g.get("dob") or f["dob"], "ay": s["ay"]})
            s["cid"] = c["id"]
    elif firm_flow and (g.get("partners") or g.get("gstin")):
        c = clients.get(s["cid"])
        if (g.get("partners") and not c.get("partners")) or (g.get("gstin") and not c.get("gst")):
            clients.save(u, wizard_firm._client_body(c, partners=c.get("partners") or g.get("partners") or [], gst=c.get("gst") or g.get("gstin") or ""), c["id"])  # noqa: SLF001
    c = clients.get(s["cid"])
    if not firm_flow and g.get("dob") and not c.get("dob") and c.get("status") == "individual":
        clients.save(u, c | {"dob": g["dob"]}, c["id"])
    for card in s.get("files") or []:                       # documents that waited for the client - and locked ones, now with a DOB
        if card["state"] in ("held", "locked"):
            if firm_flow:
                _firm_in(u, s, card)
            else:
                _into_return(u, s, card, replay=True)
    if not firm_flow:
        ans = {}
        for f2 in ("karta_name", "karta_pan", "mobile", "address", "email", "father"):
            if g.get(f2) and (myreturn.state(s["cid"], s["ay"]).get("answers") or {}).get(f2) != g[f2]:
                ans[f2] = g[f2]
        if g.get("residence") in ("yes", "no") and "resident" not in (myreturn.state(s["cid"], s["ay"]).get("answers") or {}):
            ans["resident"] = g["residence"] == "yes"
        if ans:
            myreturn.answer(u, s["cid"], s["ay"], {"answers": ans})
        kind = engine.run("wizard.biz_kind", {"picked": s.get("picked") or []})     # the kind of work -> My return's business kind
        if kind and not (myreturn.state(s["cid"], s["ay"]).get("business") or {}).get("kind"):
            myreturn.answer(u, s["cid"], s["ay"], {"business": {"kind": kind}})
    with _LOCK:
        s2 = store.read(_name(u, s["id"]), {}) or {}
        s2.update({x: s[x] for x in ("cid", "made", "files", "who", "picked") if x in s})
        _put(u, s2)


def _firm_in(u: dict, s: dict, card: dict) -> None:
    c = clients.get(s["cid"])
    if card["who"].get("pan") and card["who"]["pan"] != c["pan"]:
        card["state"] = "other_pan"
    else:
        wizard_firm.into(u, s, card, (_folder(u, s["id"]) / f"{card['id']}{card['ext']}").read_bytes())
    _keep_card(u, s, card)


# --- the documents ----------------------------------------------------------------------------------------------------------

def _seen(got: dict) -> dict:
    """What a document implies, counted: fund / share sales, 194IA rows, salary TANs, crypto sold, fees with TDS (chip
    myreturn.settings business_sections), the Form 16's own TAN."""
    f = got.get("facts") or {}
    biz = set(myreturn.settings()["business_sections"])
    fees = [t for t in f.get("tds") or [] if str(t.get("section") or "") in biz]
    return {"sales": float(f.get("sales") or 0), "ia": len(f.get("tds_194ia") or []), "ia_amount": sum(float(x.get("income") or 0) for x in f.get("tds_194ia") or []),
            "vda_seen": float(f.get("vda_seen") or 0), "fees": sum(float(t.get("income") or 0) for t in fees),
            "sections": sorted({str(t["section"]) for t in fees}),
            "salary_tans": sorted({str(t.get("tan") or "").upper() for t in f.get("tds") or [] if t.get("kind") == "salary" and t.get("tan")}
                                  | ({str(e.get("tan") or "").upper() for e in f.get("employers") or [] if e.get("tan")} if got.get("kind") == "prefill" else set())),
            "form16_tans": sorted({str(e.get("tan") or "").upper() for e in f.get("employers") or [] if e.get("tan")}) if got.get("kind") == "form16" else []}


def upload(u: dict, wid: str, filename: str, data: bytes, password: str = "", on_same: str = "") -> dict:
    """One file in: kept, read (My return's readers, or a business's - wizard_firm.read), its card made; added to the return (or
    the business's screens) when the client is known."""
    import myreturn_read  # noqa: PLC0415
    k, mk = settings(), myreturn.settings()
    s = _load(u, wid)
    ext = Path(filename).suffix.lower()
    if ext not in mk["exts"]:
        raise HTTPException(400, myreturn.say("bad_ext", exts=", ".join(mk["exts"])))
    if len(data) > int(mk["max_mb"]) * 1024 * 1024:
        raise HTTPException(400, myreturn.say("too_big", mb=mk["max_mb"]))
    if len(s.get("files") or []) >= int(k["files_max"]):
        _bad("too_many", n=k["files_max"])
    c = clients.get(s["cid"]) if s.get("cid") else {}
    f = _found(s)
    pan, dob = c.get("pan") or f["pan"], c.get("dob") or (s.get("given") or {}).get("dob") or f["dob"]
    firm_flow = _flow(s["who"]) == k["firm_flow"]
    if firm_flow:
        got = wizard_firm.read(filename, data, password=password, ay=s["ay"], pan=pan, dob=dob)
        who = got["who"]
    else:
        got = myreturn_read.read(filename, data, password=password, ay=s["ay"], pan=pan, dob=dob)
        who = myreturn.who(got)
        if not who.get("pan") and got["kind"] not in ("form16", "prefill", "filed", "filed_prev"):
            who = myreturn_read.who_of(data, password, pan, dob) | who
    who = who | {"address": ((got.get("facts") or {}).get("person") or {}).get("flat", "")}   # 2026-10-13: a bank statement's address
    locked = got["kind"] == "other" and any(p in (myreturn_read.say("need_password"), myreturn_read.say("bad_password")) for p in got.get("problems") or [])
    fid = store.new_id()
    card = {"id": fid, "name": Path(filename).name[:120], "ext": ext, "size": len(data), "kind": got["kind"], "method": got["method"],
            "found": wizard_firm.found_rows(got.get("found")), "problems": got.get("problems") or [],
            "who": {x: who.get(x, [] if x == "partners" else "") for x in WHO_KEYS},
            "state": "locked" if locked else "other" if got["kind"] == "other" else "held", "doc_id": "", "seen": _seen(got), "added_at": store.now()}
    (_folder(u, wid) / f"{fid}{ext}").write_bytes(data)
    with _LOCK:
        s = _load(u, wid)
        s.setdefault("files", []).append(card)
        _put(u, s)
    if s.get("cid") and card["state"] == "held" and firm_flow:
        _firm_in(u, s, card)
        _resolve(u, s)
    elif s.get("cid") and card["state"] == "held":
        ask = _into_return(u, s, card, password, on_same)
        if ask:                                             # the "already here?" question (myreturn.doc_clash): the card waits for the answer
            with _LOCK:
                s = _load(u, wid)
                s["files"] = [x for x in s["files"] if x["id"] != fid]
                _put(u, s)
            (_folder(u, wid) / f"{fid}{ext}").unlink(missing_ok=True)
            return view(u, s) | {"ask": ask}
    else:
        _resolve(u, s)
    s = _load(u, wid)
    return view(u, s) | {"added": {x: card[x] for x in ("id", "name", "kind")}}


def _into_return(u: dict, s: dict, card: dict, password: str = "", on_same: str = "", replay: bool = False) -> dict | None:
    """A read document into the client's return (myreturn.add_doc - the same reader, the same "already here?" question; a
    document that waited for the client is kept beside one of its kind). A document naming another PAN stays out; a locked one
    is tried again with the client's PAN + date of birth and stays out while it does not open."""
    import myreturn_read  # noqa: PLC0415
    c = clients.get(s["cid"])
    if card["who"].get("pan") and card["who"]["pan"] != c["pan"]:
        card["state"] = "other_pan"
        _keep_card(u, s, card)
        return None
    data = (_folder(u, s["id"]) / f"{card['id']}{card['ext']}").read_bytes()
    if card["state"] == "locked":
        got = myreturn_read.read(card["name"], data, password=password, ay=s["ay"], pan=c["pan"], dob=c.get("dob") or (s.get("given") or {}).get("dob", ""))
        if got["kind"] == "other":
            return None
        w = myreturn_read.who_of(data, password, c["pan"], c.get("dob", "")) | myreturn.who(got)
        card["who"] = {x: w.get(x, [] if x == "partners" else "") for x in WHO_KEYS}
        card["seen"] = _seen(got)
        if card["who"].get("pan") and card["who"]["pan"] != c["pan"]:
            card["state"] = "other_pan"
            _keep_card(u, s, card)
            return None
    r = myreturn.add_doc(u, s["cid"], s["ay"], card["name"], data, password, on_same or ("keep" if replay else ""))
    if r.get("ask"):
        return r["ask"]
    a = r["added"]
    card.update(doc_id=a["id"], kind=a["kind"], found=wizard_firm.found_rows(a["found"]), problems=a["problems"], state="other" if a["kind"] == "other" else "in",
                dest="myreturn")
    _keep_card(u, s, card)
    return None


def _keep_card(u: dict, s: dict, card: dict) -> None:
    with _LOCK:
        s2 = store.read(_name(u, s["id"]), {}) or {}
        s2["files"] = [card if x["id"] == card["id"] else x for x in s2.get("files") or []]
        s2["cid"] = s.get("cid") or s2.get("cid", "")
        _put(u, s2)
    s["files"] = [card if x["id"] == card["id"] else x for x in s.get("files") or []]


def remove(u: dict, wid: str, fid: str) -> dict:
    """Remove = out of this filing and out of the return (My return keeps the file for History; a business's file comes out of
    Intake & map / Reconcile / the GST check); the wizard's copy is kept."""
    with _LOCK:
        s = _load(u, wid)
        card = next((x for x in s.get("files") or [] if x["id"] == fid), None)
        if not card:
            raise HTTPException(404, myreturn.say("no_doc"))
        s["files"] = [x for x in s["files"] if x["id"] != fid]
        s.setdefault("removed", []).append(card | {"removed_at": store.now(), "removed_by": u["id"]})
        _put(u, s)
    if _flow(s["who"]) == settings()["firm_flow"]:
        wizard_firm.take_out(u, s, card)
    elif card.get("doc_id") and s.get("cid") and any(d["id"] == card["doc_id"] for d in myreturn.state(s["cid"], s["ay"]).get("docs") or []):
        myreturn.remove_doc(u, s["cid"], s["ay"], card["doc_id"])
    return view(u, s)


# --- what the wizard shows ----------------------------------------------------------------------------------------------------

def _by_pan(u: dict, pan: str) -> dict | None:
    return next((c for c in clients._mine(u) if pan and c["pan"] == pan and not c.get("archived_at")), None)  # noqa: SLF001


def _client(s: dict) -> dict | None:
    try:
        return clients.get(s["cid"]) if s.get("cid") else None
    except HTTPException:
        return None


def view(u: dict, s: dict, deep: bool = False) -> dict:
    k = settings()
    ay = s["ay"]
    picked = list(s.get("picked") or [])
    flow = _flow(s["who"])
    firm_flow = flow == k["firm_flow"]
    row = _row(s["who"])
    cards = [{x: c.get(x) for x in CARD} for c in s.get("files") or []]
    live = [c for c in cards if c["state"] in ("in", "held", "kept")]
    kinds = [c["kind"] for c in live]
    # the checklist: each document needed / good to have for these picks (the who counts as a pick: "self" asks for proofs)
    docs = []
    for r in engine.run("wizard.docs")["rows"]:
        need = engine.run("wizard.doc_need", {"required_for": r["required_for"], "optional_for": r["optional_for"], "picked": picked + [s["who"]],
                                              "flows": r.get("flows") or [flow], "flow": flow,
                                              "except_for": r.get("except_for") or []})
        if need:
            docs.append(_filled(r, ay) | {"need": need, "have": kinds.count(r["kind"]) if r["kind"] else 0, "typed": not r["kind"]})
    c = _client(s)
    st = myreturn.state(c["id"], ay) if c and not firm_flow else {}
    f = _found(s)
    g = s.get("given") or {}
    want = _want(s)
    pan = c["pan"] if c else f["pan"]
    clash = bool(pan) and _pan_fit(s, pan) == "clash"
    partners_need = firm_flow and bool(want.get("has_partners")) and "partners" not in g and not (c or _by_pan(u, pan) or {}).get("partners")
    company_need = firm_flow and bool(want.get("has_company")) and "company" not in g and not ((c or _by_pan(u, pan) or {}).get("company") or {}).get("cin")
    asks = engine.run("wizard.asks", {
        "client": bool(c), "files": len(live) + sum(1 for x in cards if x["state"] == "locked"), "pans": len(f["pans"]) if not g.get("pan_pick") and not g.get("pan") else 1,
        "name": (c or {}).get("name") or g.get("name") or g.get("huf_name") or f["name"], "dob": (c or {}).get("dob") or g.get("dob") or f["dob"],
        "who": s["who"], "karta_name": g.get("karta_name") or (st.get("answers") or {}).get("karta_name") or "",
        "karta_pan": g.get("karta_pan") or (st.get("answers") or {}).get("karta_pan") or "", "clash": clash,
        "nri": "nri" in picked, "resident": g.get("residence") or ("x" if "resident" in (st.get("answers") or {}) else ""),
        "partners_need": partners_need, "gstin_need": firm_flow and "gst" in picked and not ((c or {}).get("gst") or g.get("gstin") or f["gstin"]), "company_need": company_need,
        # 2026-10-13: the bank-statement-only path asks the mobile and the address when the statement / return does not have them
        "bank_only": "bankonly" in picked and not firm_flow,
        "mobile": g.get("mobile") or (st.get("answers") or {}).get("mobile") or (c or {}).get("phone") or "",
        "address": g.get("address") or (st.get("answers") or {}).get("address") or (c or {}).get("address")
        or next((x for d in st.get("docs") or [] if (x := ((d.get("facts") or {}).get("person") or {}).get("flat"))), "") or f.get("address", ""),
        "email": g.get("email") or (st.get("answers") or {}).get("email") or (c or {}).get("email") or "",
        "father": g.get("father") or (st.get("answers") or {}).get("father") or ""})
    fst = _found_status(s, pan) or {}
    ask_rows = [x | {"options": f["pans"] if x["id"] == "pan_pick" else ["yes", "no", "later"] if x["id"] == "residence" else ["switch"] if x["id"] == "status" else [],
                     "pan": pan, "kind": fst.get("id", ""), "chosen": want["id"], "partners": f["partners"] if x["id"] == "partners" else [],
                     "company": f["company"] if x["id"] == "company" else {},
                     "co_options": engine.run("company.settings")["options"] if x["id"] == "company" else []}
                for x in k["asks"] if x["id"] in asks]
    # what the documents imply
    seen = [c2["seen"] or {} for c2 in cards if c2["state"] in ("in", "held")]
    salary_tans = sorted({t for x in seen for t in x.get("salary_tans") or []})
    f16_tans = {t for x in seen for t in x.get("form16_tans") or []}
    missing_tans = [t for t in salary_tans if t not in f16_tans] if not firm_flow else []
    cg_rows = st.get("cg_rows") or []
    facts = {"sales": max([x.get("sales", 0) for x in seen] or [0]) if not firm_flow else 0, "cg_docs": kinds.count("cg"),
             "ia": max([x.get("ia", 0) for x in seen] or [0]) if not firm_flow else 0, "property_rows": sum(1 for r in cg_rows if r.get("asset") in ("land", "house")),
             "tans_missing": len(missing_tans), "vda_seen": max([x.get("vda_seen", 0) for x in seen] or [0]), "vda_rows": len(st.get("vda") or []),
             "fees": max([x.get("fees", 0) for x in seen] or [0]), "business": "business" in picked or bool((st.get("business") or {}).get("kind")),
             "gst_docs": kinds.count("gst"), "losses": "losses" in picked, "prev_docs": kinds.count("filed_prev"),
             "foreign": "foreign" in picked, "fa_rows": len(st.get("fa_rows") or []) + len(st.get("foreign_rows") or []),
             "arrears": "arrears" in picked, "arrear_rows": len(st.get("arrears") or [])}
    if firm_flow:
        facts |= wizard_firm.facts(s, cards, picked, want)
    due = engine.run("wizard.prompts", facts)
    amounts = {"cams": facts["sales"], "property": max([x.get("ia_amount", 0) for x in seen] or [0]), "vda": facts["vda_seen"], "business": facts["fees"]}
    prompts = [p | {"tans": ", ".join(missing_tans), "amount": amounts.get(p["id"], 0),
                    "sections": ", ".join(sorted({s2 for x in seen for s2 in x.get("sections") or []}))} for p in k["prompts"] if p["id"] in due]
    out = {"id": s["id"], "who": s["who"], "ay": ay, "step": s.get("step") or k["steps"][1], "steps": k["steps"], "picked": picked, "flow": flow,
           "offered": offered(s["who"]), "work_open": engine.run("wizard.work_open", {"flow": flow, "picked": picked}) is True,
           "form": engine.run("wizard.form", {"picked": picked, "who": s["who"], "flow": flow, "entity_form": row.get("form") or ""}), "docs": docs, "cards": cards,
           "client": {"id": c["id"], "name": c["name"], "pan": c["pan"], "dob": c.get("dob", ""), "status": c["status"], "made": bool(s.get("made")),
                      "gst": c.get("gst", ""), "partners": len(c.get("partners") or [])} if c else None,
           "self": s["who"] == k["self_mode"], "asks": ask_rows, "prompts": prompts, "updated_at": s.get("updated_at", ""),
           "found": {"pans": f["pans"], "name": f["name"]}}
    if c and firm_flow:
        out["next"] = wizard_firm.next_screen(s, picked)
        out["link"] = f"#/{out['next']}?c={c['id']}&ay={ay}"
    elif c:
        red = 0
        if deep or out["step"] == k["steps"][-1]:
            w = myreturn.work(c["id"], ay)
            red = sum(1 for x in w["checks"] if x["level"] == "bad" and not x.get("accepted"))
            out["checks"] = {"red": red, "amber": sum(1 for x in w["checks"] if x["level"] == "warn" and not x.get("accepted"))}
            out["form"] = w["form"] | {"from": "return"}
        missing = sum(1 for d in docs if d["need"] == "required" and not d["typed"] and not d["have"])
        typed = sum(1 for p in prompts if not p["kind"])
        out["next"] = engine.run("wizard.next_step", {"required_missing": missing, "typed": typed, "red": red,
                                                      "classify": "bankonly" in picked and myreturn.bank_open(st)})
        out["link"] = f"#/myreturn?c={c['id']}&ay={ay}&step={out['next']}"
    return out


def view_of(u: dict, wid: str) -> dict:
    return view(u, _load(u, wid))


if __name__ == "__main__":  # ponytail: one runnable self-check - the chips the wizard asks, on made-up facts
    import store as _portal_store  # noqa: F401 - registers this portal's chips, as the app does
    assert engine.run("wizard.doc_need", {"required_for": ["any"], "optional_for": [], "picked": []}) == "required"
    assert engine.run("wizard.form", {"picked": ["salary"], "who": "individual"})["form"] == "ITR-1"
    assert engine.run("wizard.form", {"picked": ["trading"], "who": "firm", "flow": "firm", "entity_form": "ITR-5"})["form"] == "ITR-5"
    assert engine.run("wizard.asks", {"client": False, "files": 1, "pans": 0, "name": "", "dob": "", "who": "individual", "karta_name": "",
                                      "karta_pan": "", "clash": False, "nri": False, "resident": ""}) == ["pan", "name", "dob"]
    assert "salary" not in offered("huf") and "salary" in offered("individual") and "salary" not in offered("firm")
    assert "partners_pay" in offered("firm") and "partners_pay" not in offered("aop") and "presumptive" not in offered("llp")
    assert _picks("individual", ["employers"]) == ["employers", "salary"], "a second employer brings salary with it"
    assert _picks("individual", ["trading"]) == ["trading", "business"], "a kind of work brings the business with it"
    assert _picks("firm", ["audit"]) == ["audit", "books"], "a tax audit brings the books; a firm has no 'business' card"
    assert _state(_row("company")) == "open" and _state(_row("trust")) == "not_yet" and _state(_row("firm")) == "open"
    try:
        _picks("huf", ["salary"])
        raise AssertionError("an HUF has no salary")
    except HTTPException as e:
        assert e.status_code == 400
    assert _years("2026-27") == {"ay": "2026-27", "fy": "2025-26", "cy": "2025"}
    print("wizard self-check OK")
