"""Chip Chat - ask SimplyFile a question (2026-10-04 owner: "build Chip Chat for each firm and at role level ... preempt all
the questions"; chosen: chips first, like AstroStage's).

Facts only. The questions and answers are chip chat.faq (filtered to the person's role) plus the firm's own answers and the
phrases its admins taught; this module scores how well each matches (word stems, chip chat.settings), chip chat.route
decides answer / offer choices / does-not-know, and a live answer is worked out from the person's own work (their
assigned client-years, the radar, a client, their role, what is lent to them, the team, the firm's papers, the owner's
queue) and worded by chip ui.chipchat. A question it could not answer is kept (question, firm, role - never the person's
name) for the firm admin or the portal owner to teach.
"""
from __future__ import annotations

import math
import re
import threading

from fastapi import HTTPException

import analytics
import chatfam
import clients
import delegation
import firms
from core import access, engine, store

TURNS, CUSTOM, TAUGHT = "sf_chat_turns", "sf_chat_custom", "sf_chat_taught"
_LOCK = threading.Lock()


def _k() -> dict:
    return engine.run("chat.settings", {})


def say(key: str, **v) -> str:
    s = str(engine.run("ui.chipchat", {}).get(key, key))
    for k, x in v.items():
        s = s.replace("{" + k + "}", str(x))
    return s


def role_key(u: dict) -> str:
    return "owner" if firms.is_owner(u) else (u.get("firm_role") or "none") if u.get("firm_id") else "none"


def _stems(text: str, k: dict) -> set[str]:
    stop, n = set(k["stop"]), int(k["stem"])
    return {w[:n] for w in re.findall(r"[a-z0-9()]+(?:-[a-z0-9]+)*", text.lower()) if w not in stop and len(w) > 1}


def entries(u: dict) -> list[dict]:
    """What this person can be answered with: the portal's questions for their role, their firm's own answers, and the
    phrases taught for their firm (added to an entry's words)."""
    rk, fid = role_key(u), u.get("firm_id", "")
    rows = [dict(e) for e in engine.run("chat.faq", {})["rows"] if not e["roles"] or rk in e["roles"] or rk == "owner"]   # the owner sees every answer
    rows += [{"id": c["id"], "q": c["q"], "words": "", "a": c["a"], "roles": [], "go": "", "live": "", "own": True}
             for c in store.read(CUSTOM, []) if c.get("firm_id", "") in ("", fid)]
    by = {e["id"]: e for e in rows}
    for t in store.read(TAUGHT, []):
        if t.get("firm_id", "") in ("", fid) and t["entry"] in by:
            by[t["entry"]]["words"] = f"{by[t['entry']]['words']} {t['phrase']}"
    return rows


def _rank(q: str, rows: list[dict], k: dict, names: list[str] = ()) -> list[tuple[float, dict]]:
    """Each entry's match: the share of the asked words it has, each word weighted by how rare it is across the entries
    (so 'client' or 'return' count little, 'draft' or '234b' a lot). A question naming one of the person's clients also
    scores the client entry by how much of the name it carries."""
    want = _stems(q, k)
    if not want:
        return []
    bags = [(e, _stems(e["q"], k), _stems(f"{e['q']} {e['words']}", k)) for e in rows]
    n = len(bags)
    wt = {w: math.log(1 + n / (1 + sum(1 for _, _, b in bags if w in b))) for w in want}
    total = sum(wt.values()) or 1
    named = max((len(want & _stems(x, k)) / max(1, len(_stems(x, k))) for x in names), default=0)
    out = []
    for e, own_q, own in bags:
        s = sum(wt[w] for w in want & own) / total * k["w_words"] + len(want & own_q) / max(1, len(own_q)) * k["w_question"]
        if e.get("live") == "client" and named:
            s = max(s, k["name_base"] + named * k["name_weight"])
        out.append((round(s, 3), e))
    return sorted(out, key=lambda x: -x[0])


# --- live answers: worked out from the person's own work ------------------------------------------------------------------

def _days(n: int) -> str:
    return say("days_late", n=-n) if n < 0 else say("days_left", n=n)


def _dmy(iso: str) -> str:
    return "/".join(reversed(iso.split("-"))) if iso else ""


def _stage(sid: str) -> str:
    return next((s["label"] for s in clients.settings()["stages"] if s["id"] == sid), sid)


def _radar(u: dict) -> list[dict]:
    return analytics.report(u, "")["radar"] if firms.firm_of(u) and firms.may(u, "clients")["ok"] else []


def _rows(rows: list[dict], n: int) -> list[dict]:
    return [{"text": say("row_due", name=r["name"], form=r["form"], stage=_stage(r["stage"]), due=_dmy(r["due"]), days=_days(r["days_left"])),
             "go": f"#/compute?c={r['id']}"} for r in rows[:n]]


def live(u: dict, kind: str, q: str) -> dict:
    n = int(_k()["rows_n"])
    if kind in ("pending_me", "overdue", "due_soon", "client", "team", "leads", "firm_ready") and not firms.firm_of(u):
        return {"text": say("access_none") if not firms.is_owner(u) else say("access_owner")}
    if kind == "pending_me":
        me = {x.lower() for x in (u.get("name"), u.get("email"), u.get("id")) if x}
        rows = [r for r in _radar(u) if r["assigned"].lower() in me]
        return {"text": say("pending_head", n=len(rows)) if rows else say("pending_none"), "rows": _rows(rows, n)}
    if kind in ("overdue", "due_soon"):
        rows = [r for r in _radar(u) if (r["days_left"] < 0 if kind == "overdue" else 0 <= r["days_left"] <= _k()["soon_days"])]
        head, none = ("overdue_head", "overdue_none") if kind == "overdue" else ("soon_head", "soon_none")
        return {"text": say(head, n=len(rows)) if rows else say(none), "rows": _rows(rows, n)}
    if kind == "client":
        k = _k()
        words = _stems(q, k) - _stems("client status stage where stand how far progress", k)
        mine = [c for c in clients._mine(u) if not c.get("archived_at")]  # noqa: SLF001
        hit = sorted(((len(words & _stems(c["name"], k)), c) for c in mine), key=lambda x: -x[0])
        hit = [c for s, c in hit if s and s == hit[0][0]][:n] if words and hit else []
        if not words:
            return {"text": say("client_ask")}
        if not hit:
            return {"text": say("client_none")}
        ay = clients.settings()["current_ay"]
        out = []
        for c in hit:
            a = ay if ay in (c.get("years") or {}) else max(c.get("years") or {"-": 0})
            y = (c.get("years") or {}).get(a) or {}
            cur = next((f for f in (y.get("filings") or []) if f.get("status") == "current"), None)
            out.append({"text": say("client_row", name=c["name"], pan=c.get("pan", ""), ay=a, stage=_stage(y.get("stage", "")), form=y.get("form", ""),
                                    filed=say("client_filed", kind=cur["kind"], on=_dmy(cur["filed_on"])) if cur else "",
                                    who=say("client_who", who=y["assigned"]) if y.get("assigned") else ""), "go": f"#/compute?c={c['id']}&ay={a}"})
        return {"text": "", "rows": out}
    if kind == "my_access":
        if firms.is_owner(u):
            return {"text": say("access_owner")}
        if not u.get("firm_id"):
            return {"text": say("access_none")}
        r = firms.role_of(u.get("firm_role", ""))
        return {"text": say("access_head", role=r["label"]), "rows": [{"text": delegation._label(g)} for g in r["grants"]]}  # noqa: SLF001
    if kind == "lent_me":
        rows = [d for d in delegation.page(u)["received"] if d["state"] == "active"]
        return {"text": say("lent_head") if rows else say("lent_none"),
                "rows": [{"text": say("lent_row", what=", ".join(d["grant_labels"]), scope=", ".join(d.get("client_names") or []) + (f" {d['ay']}" if d.get("ay") else ""),
                                      lender=d["from_label"], until=_dmy(d["ends"])), "go": "#/delegate"} for d in rows]}
    if kind == "team":
        t = firms.team(u)
        f = firms.firm_of(u) or {}
        return {"text": say("team_head", n=len(t), firm=f.get("name", "")),
                "rows": [{"text": say("team_row", name=x["name"] or x["email"], role=firms.role_of(x["role"])["label"])} for x in t]}
    if kind == "firm_ready":
        f = firms.me(u)["firm"]
        k = firms.settings()
        state = next((s["label"] for s in k["states"] if s["id"] == f["state"]), f["state"])
        miss = f["ready"].get("missing") or []
        labels = {d["id"]: d["label"] for d in k["docs"]}
        return {"text": say("ready_head", state=state) if miss else say("ready_ok", state=state), "rows": [{"text": labels.get(m, m), "go": "#/firm"} for m in miss]}
    if kind == "leads":
        if not firms.may(u, "analytics")["ok"]:
            return {"text": say("leads_none")}
        d = analytics.report(u, "")
        words = engine.run("ui.analytics", {})
        rows = [{"text": say("lead_row", what=words.get(f"l_{lid}", lid), names=", ".join(x["name"] for x in d["leads"][lid][:n])), "go": "#/analytics"}
                for lid in d["lead_order"] if d["leads"].get(lid)]
        return {"text": say("leads_head") if rows else say("leads_none"), "rows": rows}
    if kind == "owner_queue":
        rows = firms.queue(firms.settings()["waiting_state"])
        return {"text": say("owner_head", n=len(rows)) if rows else say("owner_none"),
                "rows": [{"text": f.get("name") or f.get("email", ""), "go": "#/approvals"} for f in rows[:n]]}
    return {"text": ""}


def _answer(u: dict, e: dict, q: str) -> dict:
    body = live(u, e["live"], q) if e.get("live") else {"text": e["a"]}
    return {"id": e["id"], "q": e["q"], "go": e.get("go", ""), **body}


def _next(aid: str) -> list[str]:
    """What to ask after this answer (chip chat.next), by the prepared question's id or the question family."""
    nx = engine.run("chat.next", {})
    return list(nx["after"].get(aid.removeprefix("fam:"), []))[: int(nx["n"])]


def _log(u: dict, q: str, route: str, aid: str, method: str) -> None:
    """Every question asked is a turn the Train tab can review (the firm and role - never the person's name)."""
    keep = int(engine.run("chat.train", {})["keep_turns"])
    with _LOCK:
        rows = store.read(TURNS, [])
        rows.append({"id": store.new_id(), "q": q, "route": route, "answer": aid, "method": method, "firm_id": u.get("firm_id", ""),
                     "role": role_key(u), "at": store.now(), "review": ""})
        store.write(TURNS, rows[-keep:])


def ask(u: dict, q: str) -> dict:
    q = str(q or "").strip()[:300]
    if not q:
        raise HTTPException(400, say("ask_ph"))
    k = _k()
    rows = entries(u)
    names = [c["name"] for c in clients._mine(u) if not c.get("archived_at")] if u.get("firm_id") else []  # noqa: SLF001
    ranked = _rank(q, rows, k, names)
    top = ranked[0][0] if ranked else 0
    second = ranked[1][0] if len(ranked) > 1 else 0
    route = engine.run("chat.route", {"top": top, "second": second, "min_score": k["min_score"], "gap_min": k["gap_min"]})
    fm = chatfam.match(q)
    route = engine.run("chat.pick", {"fam_ready": fm["ready"], "fam_hits": fm["hits"], "faq": route})
    if route == "family":
        _log(u, q, "answer", f"fam:{fm['id']}", "family")
        return {"route": "answer", "family": fm["id"], "answer": {"id": f"fam:{fm['id']}", "go": "", **chatfam.answer(u, fm)}, "next": _next(fm["id"])}
    if route == "ask":
        _log(u, q, "ask_blank", f"fam:{fm['id']}", "family")
        return {"route": "pick_one", "family": fm["id"], "say": chatfam.ask_for(fm["missing"]), "options": []}
    if route == "answer":
        e = ranked[0][1]
        _log(u, q, "answer", e["id"], "taught" if any(t["phrase"].lower() == q.lower() for t in store.read(TAUGHT, [])) else "own" if e.get("own") else "prepared")
        return {"route": route, "answer": _answer(u, e, q), "next": _next(e["id"])}
    if route == "pick_one":
        _log(u, q, "pick_one", ranked[0][1]["id"], "prepared")
        return {"route": route, "say": say("pick"), "options": [{"id": e["id"], "q": e["q"]} for s, e in ranked[: int(k["pick_n"])] if s >= k["min_score"]]}
    _log(u, q, "no_match", "", "")
    return {"route": route, "say": say("no_match"), "options": []}


def answer_id(u: dict, eid: str) -> dict:
    e = next((x for x in entries(u) if x["id"] == eid), None)
    if not e:
        raise HTTPException(404, say("no_match"))
    return {"route": "answer", "answer": _answer(u, e, e["q"]), "next": _next(e["id"])}


# --- example questions and Surprise me: drawn afresh every time, from every question Chip Chat knows -----------------------

_POOL: list[str] = []


def _pool() -> list[str]:
    """Every question Chip Chat knows - the 10,000+ of tools/chat_corpus.py - built once per process."""
    if not _POOL:
        import sys  # noqa: PLC0415
        from pathlib import Path  # noqa: PLC0415
        sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
        import chat_corpus  # noqa: PLC0415
        _POOL.extend(sorted({r["q"] for r in chat_corpus.build()}))
    return _POOL


def examples(u: dict, screen: str = "") -> dict:
    """{examples, placeholder}: a fresh set each time - some from the person's own work and screen, the rest from all."""
    import random  # noqa: PLC0415
    k = engine.run("chat.examples", {})
    rows = entries(u)
    own = [e["q"] for e in rows if e.get("live")] + [e["q"] for e in rows if screen and e.get("go", "").startswith(f"#/{screen}")]
    rnd = random.Random()
    pick = rnd.sample(own, min(int(k["live_share"]), len(own)))
    pick += [q for q in rnd.sample(_pool(), int(k["n"]) * 2) if q not in pick][: int(k["n"]) - len(pick)]
    return {"examples": pick, "placeholder": rnd.choice(k["placeholders"]), "teach": _teacher(u) is not None}


def surprise(u: dict, n: int = 0) -> dict:
    """A good question, different for each person, each hour and each press (chip chat.surprise)."""
    import datetime  # noqa: PLC0415
    import random  # noqa: PLC0415
    k = engine.run("chat.surprise", {})
    since = (datetime.datetime.utcnow() - datetime.timedelta(days=int(k["asked_days"]))).isoformat()
    counts: dict[str, int] = {}
    for t in store.read(TURNS, []):
        if t["route"] == "answer" and t["at"] >= since and (not u.get("firm_id") or t["firm_id"] in ("", u["firm_id"])):
            counts[t["q"]] = counts.get(t["q"], 0) + 1
    sources = {"asked": [q for q, _ in sorted(counts.items(), key=lambda x: -x[1])[: int(k["asked_top"])]], "curated": k["curated"], "pool": _pool()}
    rnd = random.Random(f"{u.get('id')}|{datetime.datetime.utcnow():%Y%m%d%H}|{n}")
    live = [s for s in sources if sources[s]]
    src = rnd.choices(live, weights=[k["weights"][s] for s in live])[0]
    return {"question": rnd.choice(sources[src])}


# --- the Train tab: the firm admin (their firm's questions) and the portal owner (every firm's) ----------------------------

def _teacher(u: dict) -> str | None:
    """'' = the portal owner (portal-wide); a firm id = that firm's admin; None = may not teach."""
    if firms.is_owner(u):
        return ""
    return u.get("firm_id") if u.get("firm_id") and _k()["teach_grant"] in firms.role_of(u.get("firm_role", ""))["grants"] else None


def _mine_turns(u: dict) -> tuple[str, list[dict]]:
    fid = _teacher(u)
    if fid is None:
        raise HTTPException(403, say("train_none"))
    return fid, [t for t in store.read(TURNS, []) if fid == "" or t["firm_id"] == fid]


def train(u: dict, review: str = "open") -> dict:
    fid, rows = _mine_turns(u)
    tr = engine.run("chat.train", {})
    rule = tr["filter_rules"].get(review) or tr["filter_rules"]["all"]       # what each filter shows is chip chat.train's

    def want(t: dict) -> bool:
        return all(t.get(f) == v for f, v in rule["is"].items()) and not any(t.get(f) == v for f, v in rule["not"].items())
    label = lambda r: say("role_owner") if r == "owner" else say("role_none") if r == "none" else firms.role_of(r)["label"]  # noqa: E731
    shown = [t | {"role_label": label(t["role"])} for t in reversed(rows) if want(t)][: int(tr["page"])]
    by_route: dict[str, int] = {}
    for t in rows:
        by_route[t["route"]] = by_route.get(t["route"], 0) + 1
    return {"turns": shown, "stats": {"total": len(rows), "answered": by_route.get("answer", 0), "taught": sum(1 for t in rows if t["review"] == "taught"),
                                     "by_route": by_route},
            "entries": [{"id": e["id"], "q": e["q"]} for e in entries(u)], "taught": [t for t in store.read(TAUGHT, []) if fid == "" or t.get("firm_id") == fid],
            "custom": [c for c in store.read(CUSTOM, []) if fid == "" or c.get("firm_id") == fid], "portal": fid == "", "filters": tr["filters"]}


def teach(u: dict, tid: str, body: dict) -> dict:
    """Point an asked question at the right answer - or write the firm's own - so it is answered from now on."""
    fid, _ = _mine_turns(u)
    with _LOCK:
        rows = store.read(TURNS, [])
        t = next((x for x in rows if x["id"] == tid and (fid == "" or x["firm_id"] == fid)), None)
        if not t:
            raise HTTPException(404, say("train_none"))
        entry = str(body.get("entry") or "")
        if body.get("answer"):
            entry = add_custom(u, {"q": t["q"], "a": body["answer"], "portal": body.get("portal")}, lock=False)["id"]
        if not entry or entry not in {e["id"] for e in entries(u)}:
            raise HTTPException(400, say("teach_pick"))
        taught = store.read(TAUGHT, [])
        taught.append({"id": store.new_id(), "phrase": t["q"], "entry": entry, "firm_id": t["firm_id"] if fid else "", "at": store.now()})
        store.write(TAUGHT, taught)
        t["review"] = "taught"
        store.write(TURNS, rows)
    return {"say": say("taught")}


def skip(u: dict, tid: str) -> dict:
    fid, _ = _mine_turns(u)
    with _LOCK:
        rows = store.read(TURNS, [])
        t = next((x for x in rows if x["id"] == tid and (fid == "" or x["firm_id"] == fid)), None)
        if t:
            t["review"] = "skipped"
            store.write(TURNS, rows)
    return {"ok": True}


def drop_taught(u: dict, aid: str) -> dict:
    fid, _ = _mine_turns(u)
    with _LOCK:
        rows = store.read(TAUGHT, [])
        store.write(TAUGHT, [t for t in rows if not (t["id"] == aid and (fid == "" or t.get("firm_id") == fid))])
    return {"ok": True}


def export_jsonl(u: dict) -> str:
    """Question -> answer pairs, one JSON line each: the taught phrases and the questions answered."""
    import json  # noqa: PLC0415
    fid, rows = _mine_turns(u)
    pairs = [{"question": t["phrase"], "answer": t["entry"]} for t in store.read(TAUGHT, []) if fid == "" or t.get("firm_id") == fid]
    pairs += [{"question": t["q"], "answer": t["answer"]} for t in rows if t["route"] == "answer" and t["answer"]]
    return "\n".join(json.dumps(p, ensure_ascii=False) for p in pairs) + "\n"


def unanswered_csv(u: dict) -> str:
    """The questions it could not answer, most asked first: question, times asked, firms that asked, last asked."""
    import csv  # noqa: PLC0415
    import datetime  # noqa: PLC0415
    import io  # noqa: PLC0415
    _, rows = _mine_turns(u)
    since = (datetime.datetime.utcnow() - datetime.timedelta(days=int(engine.run("chat.train", {})["unanswered_days"]))).isoformat()
    by: dict[str, dict] = {}
    for t in rows:
        if t["route"] == "no_match" and t["at"] >= since:
            key = " ".join(t["q"].lower().split())
            b = by.setdefault(key, {"q": t["q"], "n": 0, "firms": set(), "last": ""})
            b["n"] += 1
            b["firms"].add(t["firm_id"])
            b["last"] = max(b["last"], t["at"])
    out = io.StringIO()
    wr = csv.writer(out)
    wr.writerow([say("h_question"), say("h_asked"), say("h_firms"), say("h_last")])
    for b in sorted(by.values(), key=lambda b: -b["n"]):
        wr.writerow([b["q"], b["n"], len(b["firms"]), b["last"][:16].replace("T", " ")])
    return out.getvalue()


def add_custom(u: dict, body: dict, lock: bool = True) -> dict:
    fid = _teacher(u)
    if fid is None:
        raise HTTPException(403, say("teach_none"))
    q, a = str(body.get("q") or "").strip()[:300], str(body.get("a") or "").strip()[:3000]
    if not q or not a:
        raise HTTPException(400, say("own_a"))
    row = {"id": f"own-{store.new_id()}", "q": q, "a": a, "firm_id": "" if (fid == "" and body.get("portal")) else (fid or ""), "by": u.get("email", ""), "at": store.now()}

    def put():
        rows = store.read(CUSTOM, [])
        rows.append(row)
        store.write(CUSTOM, rows)
    if lock:
        with _LOCK:
            put()
    else:
        put()
    return row


def delete_custom(u: dict, cid: str) -> dict:
    fid = _teacher(u)
    with _LOCK:
        rows = store.read(CUSTOM, [])
        keep = [c for c in rows if not (c["id"] == cid and fid is not None and (fid == "" or c.get("firm_id") == fid))]
        if len(keep) == len(rows):
            raise HTTPException(404, say("own_none"))
        store.write(CUSTOM, keep)
    return {"ok": True}


if __name__ == "__main__":  # ponytail: the words that matter match, and a near-miss question finds its answer
    import store as _s  # noqa: F401 - registers this portal's chips
    k = _k()
    rows = [dict(e) for e in engine.run("chat.faq", {})["rows"]]
    for q, want in [("what is pending for me", "my_pending"), ("which files can I upload", "file_formats"), ("how do i add a client", "add_client"),
                    ("whats the due date for audit cases", "due_dates"), ("can i upload json directly to the income tax portal", "json_upload"),
                    ("why cant i sign off", "why_no_signoff"), ("how to delegate my work while on leave", "delegate_how"),
                    ("what is an sf ref", "sf_ref"), ("how is 234b interest calculated", "interest_234")]:
        got = _rank(q, rows, k)[0][1]["id"]
        assert got == want, (q, got)
    assert engine.run("chat.route", {"top": 0.1, "second": 0, "min_score": k["min_score"], "gap_min": k["gap_min"]}) == "no_match"
    print("chipchat OK")
