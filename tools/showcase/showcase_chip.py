"""Disposable builder (run once): writes chips/showcase.page.json + chips/showcase.settings.json for SimplyFile's public
showcase (its landing for visitors), and re-encodes the showcase parts into static/showcase/ (streamable MP4, a
poster, WebVTT captions). The chapter marks come from each part's own description.txt. The JSON is the source of truth."""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "tmp" / "tour_video"
OUT = ROOT / "static" / "showcase"

PARTS = [  # (folder, key, title, line)
    ("showcase", "sf-part1", "A CA firm, five clients", "Demo CA Filing Firm: the team, then five clients from Excel to a return ready to sign - intake, mapping, 26AS/AIS/TIS, compute and close."),
    ("showcase2", "sf-part2", "Ten more cases", "Belated, revised and updated returns, old regime or new, surcharge, a non-resident, an LLP, and undoing a wrong filing."),
    ("showcase3", "sf-part3", "Importing old returns", "Past ITR JSON becomes each client's history - matched by PAN, revised and belated returns handled."),
    ("showcase4", "sf-part4", "Delegations", "Hand over one filing, or some clients for a year - and take it back."),
    ("showcase5", "sf-part5", "Chip Chat and the tool bar", "Ask in plain words: your own work, tax worked out, dates, roles - plus Notes and Issues."),
    ("showcase6", "sf-part6", "The tax audit", "Is an audit needed, this year against last, the Form 3CD checklist and audit points."),
    ("showcase7", "sf-part7", "History", "Every change to a client, earlier versions of documents, and the firm's own history."),
    ("showcase8", "sf-part8", "The audit, taken further", "Against earlier years, GST against the books, the riskiest first, and the statutory audit."),
    # 2026-10-07: My return for individuals and HUFs, and the year's tax rules
    ("showcase9", "sf-part9", "Your own return, from your documents", "Pre-filled JSON, Form 16, a locked AIS, 26AS, a CAMS statement and a bank statement read; checked against each other; both regimes."),
    ("showcase10", "sf-part10", "The review, and the return filed", "Capital gains with the cheaper rate and 54EC, a co-owned flat, gifts, crypto, arrears, clubbing - and the ITR-2 JSON, checked."),
    ("showcase11", "sf-part11", "An HUF and a consultant", "A family HUF started from its pre-filled JSON; a consultant's 44ADA receipts from her bank statement - ITR-4, or ITR-3 on her own accounts."),
    ("showcase12", "sf-part12", "Tax rules", "The year's slabs, caps and due dates: compare the next year's with this one, and apply - with History."),
]
GROUP = lambda i: "file" if i < 3 else "more" if i < 8 else "own"  # noqa: E731
TAGS = {  # 2026-10-07 find a film (showcase.js): the words people search for - several per film; every theatre topic is one of them
    "sf-part1": ["CA firm", "team", "intake", "mapping", "26AS", "AIS", "reconcile", "compute", "ITR-3"],
    "sf-part2": ["belated", "revised", "updated return", "old regime", "surcharge", "non-resident", "LLP", "ITR-5", "undo"],
    "sf-part3": ["import", "old returns", "ITR JSON", "PAN", "revised", "belated", "analytics"],
    "sf-part4": ["delegations", "hand over", "take back", "roles"],
    "sf-part5": ["Chip Chat", "ask", "notes", "issues", "tool bar"],
    "sf-part6": ["tax audit", "3CD", "year on year", "audit points", "applicability"],
    "sf-part7": ["History", "changes", "versions", "documents"],
    "sf-part8": ["tax audit", "GST", "3CD", "earlier years", "statutory audit", "accounting standards"],
    "sf-part9": ["my return", "Form 16", "AIS", "26AS", "pre-filled JSON", "bank statement", "regime", "History"],
    "sf-part10": ["my return", "capital gains", "54EC", "indexation", "gifts", "crypto", "house property", "s.89", "ITR-2", "ITR-U"],
    "sf-part11": ["my return", "HUF", "Karta", "44ADA", "presumptive", "ITR-4", "ITR-3", "bank statement"],
    "sf-part12": ["tax rules", "slabs", "due dates", "compare", "apply", "rule book"],
}


def marks(folder: str) -> list[dict]:
    rows = []
    for ln in (SRC / folder / "description.txt").read_text(encoding="utf-8").splitlines():
        m = re.match(r"(\d+):(\d\d)\s+(.+)", ln.strip())
        if m:
            rows.append({"t": int(m.group(1)) * 60 + int(m.group(2)), "title": m.group(3).strip()})
    return rows


def media() -> None:
    import imageio_ffmpeg  # noqa: PLC0415
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    OUT.mkdir(parents=True, exist_ok=True)
    for folder, key, _t, _l in PARTS:
        src = SRC / folder / f"{folder}.mp4"
        subprocess.run([ff, "-loglevel", "error", "-y", "-i", str(src), "-c:v", "libx264", "-preset", "slow", "-crf", "30", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(OUT / f"{key}.mp4")], check=True)
        o = subprocess.run([ff, "-i", str(src)], capture_output=True, text=True).stderr
        h, mi, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", o).groups()
        subprocess.run([ff, "-loglevel", "error", "-y", "-ss", f"{(int(h) * 3600 + int(mi) * 60 + float(s)) * 0.3:.1f}", "-i", str(src), "-frames:v", "1",
                        "-vf", "scale=960:-2", "-q:v", "4", str(OUT / f"{key}.jpg")], check=True)
        srt = (SRC / folder / f"{folder}.srt").read_text(encoding="utf-8")
        (OUT / f"{key}.vtt").write_bytes(("WEBVTT\n\n" + re.sub(r"(\d\d:\d\d:\d\d),(\d\d\d)", r"\1.\2", srt)).encode("utf-8"))
        print(key, (OUT / f"{key}.mp4").stat().st_size // 1024, "KB")


values = {
    "meta": {"title": "SimplyFile - Books in. Return out. Every figure traced.", "description": "Tax filing and tax audit for CA firms: Tally-derived Excel and 26AS, AIS, TIS in; mapped to 3CD and ITR-3 / ITR-5, reconciled, computed and filled into the official utility, ready to sign - with roles, delegations and history. And My return for individuals and HUFs: ITR-1 to ITR-4 from your own documents."},
    "skin": "ledger",
    "nav": {"brand": "SimplyFile", "tag": "For CA firms", "logo": "ledger", "menu": "Sections",
            "links": [["how", "How it works"], ["watch", "Watch"], ["play", "Try it live"], ["who", "Who it's for"], ["features", "Features"], ["faq", "Questions"]], "start": "Start here"},
    "hero": {
        "eyebrow": "SimplyFile · for CA firms",
        "title": "Books in. Return out. Every figure traced.",
        "sub": "Upload the client's Tally-derived Excel and 26AS, AIS and TIS. SimplyFile maps every figure to its 3CD clause and ITR schedule, reconciles it, computes the tax and fills the official utility - ready for the partner to sign.",
        "play": "Watch it work", "start": "Start here", "start_href": "start", "art": "ledger",
        "note": "Client data stays on your server. Nothing is sent to the income-tax portal - you upload the filled utility yourself.",
    },
    "stats": [],
    "trust": {"title": "Works with", "rows": ["Tally-derived Excel", "26AS", "AIS", "TIS", "Form 16", "Pre-filled JSON", "CAMS / broker statements", "Form 3CD", "ITR-1 to ITR-5", "Official Excel utility"]},
    "steps": {
        "eyebrow": "How it works", "title": "Four steps from books to a return you can sign.",
        "rows": [
            {"icon": "upload", "title": "Bring the books", "line": "Upload the client's Tally-derived Excel and the 26AS, AIS and TIS from the portal."},
            {"icon": "link", "title": "Tag every row", "line": "An SF Ref column sends each figure to its 3CD clause and ITR schedule - no re-typing."},
            {"icon": "check", "title": "Reconcile and check", "line": "Books against the department's statements; audit, year-on-year and GST checks flag what matters."},
            {"icon": "okcircle", "title": "Ready to sign", "line": "Tax computed, partner signs off, the official utility filled - ready to upload."},
        ],
    },
    "theatre": {
        "eyebrow": "See it, not a slide",
        "title": "A firm's year, recorded live on sf.valuestream.in",
        "sub": "Twelve films with a made-up firm, made-up clients and a made-up self-filer. Press play and they run one after another - pick any part on the left, or jump to a moment under the player.",
        "autoplay": "Play the next one by itself", "prev": "Previous", "next": "Next", "playlist": "Parts",
        "search": "Find a film - a screen, a step, a word", "found": "{n} of {total} films", "none": "No film matches that - try another word or a topic.",
        "topics": ["intake", "26AS", "reconcile", "tax audit", "3CD", "GST", "delegations", "Chip Chat", "History", "my return", "HUF", "capital gains", "tax rules"],
        "now": "Now playing", "up_next": "Up next", "watch": "Watch", "of": "Part {n} of {total}", "captions": "English captions",
        "groups": [
            {"id": "file", "title": "Filing", "line": "From the firm and its team to twenty-five returns."},
            {"id": "more", "title": "Around the filing", "line": "Delegations, Chip Chat, the tax audit and History."},
            {"id": "own", "title": "Your own return", "line": "My return for individuals and HUFs, and the year's tax rules."},
        ],
    },
    "chapters": [{"key": key, "group": GROUP(i), "title": title, "module": f"Part {i + 1}", "line": line, "tags": TAGS[key], "marks": marks(folder)}
                 for i, (folder, key, title, line) in enumerate(PARTS)],
    "pillars": {
        "eyebrow": "Why SimplyFile",
        "title": "One path. Every figure accounted for.",
        "rows": [
            {"icon": "users", "title": "Client master, once", "line": "PAN, status, address, bank and partners are entered once and carried into every assessment year."},
            {"icon": "link", "title": "Every row tagged", "line": "Upload the client's Tally-derived Excel; an SF Ref column says where each figure belongs - 3CD clause, ITR schedule."},
            {"icon": "check", "title": "Books meet 26AS, AIS and TIS", "line": "Every gap between the books and the department's statements is listed - before the partner signs off."},
        ],
    },
    "checks": {
        "eyebrow": "Built for sign-off",
        "title": "The checks a partner wants",
        "rows": [
            {"icon": "alert", "title": "Is an audit needed?", "line": "Tax audit applicability worked out from the client's own figures."},
            {"icon": "pulse", "title": "This year against last", "line": "Year-on-year swings flagged before anyone asks."},
            {"icon": "list", "title": "3CD checklist by risk", "line": "The riskiest clauses first, with audit points kept."},
            {"icon": "money", "title": "GST against the books", "line": "Turnover in GST returns matched with the books."},
            {"icon": "clock", "title": "History of every change", "line": "Who changed what, when - and earlier versions of every document."},
            {"icon": "users", "title": "Roles and delegations", "line": "Partners, managers and staff see what their role allows; hand work over and take it back."},
            {"icon": "lock", "title": "Data stays with you", "line": "Nothing is sent to the income-tax portal - you upload the filled utility yourself."},
            {"icon": "chat", "title": "Chip Chat", "line": "Ask in plain words: whose return is due, what the tax is, who has what."},
        ],
    },
    "modules": {
        "eyebrow": "Every screen",
        "title": "Everything a CA firm runs on.",
        "groups": [
            {"title": "Firm", "rows": [
                {"icon": "users", "name": "My firm", "for": "Partners", "line": "Firm details, the team and their roles."},
                {"icon": "pulse", "name": "Firm analytics", "for": "Partners", "line": "Every client and filing at a glance - due, done, stuck."},
                {"icon": "share", "name": "Delegations", "for": "Partners, managers", "line": "Hand over one filing, or some clients for a year."},
            ]},
            {"title": "Filing", "rows": [
                {"icon": "folder", "name": "Clients & years", "for": "Everyone", "line": "The client master and each assessment year."},
                {"icon": "download", "name": "Import old returns", "for": "Staff", "line": "Past ITR JSON becomes each client's history - matched by PAN."},
                {"icon": "link", "name": "Intake & map", "for": "Staff", "line": "Upload statements and tag every row to 3CD and the ITR."},
                {"icon": "check", "name": "Reconcile", "for": "Staff, managers", "line": "The books against 26AS, AIS and TIS - every gap listed."},
                {"icon": "money", "name": "Compute & close", "for": "Managers, partners", "line": "Tax computation, sign-off, ITR and 3CD JSON, and the Excel utility zip."},
                {"icon": "shield", "name": "Tax audit", "for": "Partners", "line": "Applicability, year on year, the 3CD checklist by risk, GST against the books."},
            ]},
            {"title": "For individuals", "rows": [
                {"icon": "user", "name": "My return", "for": "Individuals, HUFs", "line": "ITR-1 to ITR-4 from your own documents - read, checked, both regimes, the department's JSON."},
                {"icon": "refresh", "name": "Tax rules", "for": "Everyone (owner applies)", "line": "The year's slabs, caps and due dates: compare the next year's and apply, with History."},
            ]},
            {"title": "Every day", "rows": [
                {"icon": "chat", "name": "Chip Chat", "for": "Everyone", "line": "Ask about your own work in plain words."},
                {"icon": "notebook", "name": "Notes and Issues", "for": "Everyone", "line": "Notes on any client; issues raised and answered inside the portal."},
                {"icon": "clock", "name": "History", "for": "Everyone", "line": "Every change, every earlier version."},
                {"icon": "spark", "name": "Guide me and Tour videos", "for": "New staff", "line": "A step-by-step tour and a narrated video for every screen."},
            ]},
        ],
    },
    "features": {
        "eyebrow": "Everything that is built", "title": "The full list", "filter_all": "All", "search": "Search the features", "none": "No feature matches that.",
        "groups": [
            {"title": "Filing", "rows": [
                "Client master entered once, carried into every assessment year",
                "Tally-derived Excel read, every row tagged with an SF Ref",
                "Every figure mapped to its Form 3CD clause and ITR schedule",
                "ITR-3 and ITR-5, original, belated, revised and updated returns",
                "Old regime or new, surcharge, non-residents, LLPs, home loans",
                "Tax computation, partner sign-off, ITR and 3CD JSON",
                "The official Excel utility filled, in one zip",
                "Undo a wrong filing",
            ]},
            {"title": "Reconcile and audit", "rows": [
                "Books against 26AS, AIS and TIS - every gap listed",
                "Tax audit applicability",
                "This year against last year",
                "Form 3CD checklist by risk, with audit points",
                "GST returns against the books",
                "Statutory audit",
            ]},
            {"title": "My return", "rows": [
                "Start from documents: the pre-filled JSON or a return already filed makes the person or HUF",
                "Form 16, AIS, TIS, 26AS, CAMS / broker and bank statements read (PDF, Excel, CSV, JSON)",
                "Asked before a document is replaced; old versions kept in History",
                "Capital gains: grandfathering, indexation choice, 54 / 54EC / 54F, losses carried forward",
                "Business or profession: 44AD, 44ADA, 44AE or your own profit and loss",
                "Gifts, winnings, crypto, farm income, co-owned houses, more deductions, tax paid yourself",
                "Residential status, foreign income and assets, clubbing, s.89 relief, ITR-U worked out",
                "ITR-1, ITR-2, ITR-3 and ITR-4 JSON checked against the department's schema",
                "Tax rules: compare the next year's figures, apply with History",
            ]},
            {"title": "History and import", "rows": [
                "Import past returns from ITR JSON, matched by PAN",
                "Revised and belated returns replace or join the history",
                "A history of every change to a client",
                "Earlier versions of every document",
            ]},
            {"title": "The firm", "rows": [
                "Team with roles: partner, manager, staff",
                "Delegate one filing, or some clients for a year - and take it back",
                "Firm analytics",
                "Chip Chat: ask about your work in plain words",
                "Notes on any client; issues answered inside the portal",
                "Guide me and a tour video for every screen",
                "Client data stays on the server - nothing sent to the IT portal",
            ]},
        ],
    },
    "desks": {
        "eyebrow": "Who it's for", "title": "One standard, from a single desk to a full practice.", "start": "Start here",
        "rows": [
            {"icon": "user", "title": "Solo practice", "line": "One CA, a desk of clients, the whole season.",
             "gets": ["Client master entered once", "Books against 26AS, AIS and TIS", "Official utility filled, ready to upload"]},
            {"icon": "users", "title": "Growing firm", "pick": "Most firms", "line": "Partners, managers and staff on one path.",
             "gets": ["Roles: partner, manager, staff", "Delegate a filing or some clients - and take it back", "Firm analytics: due, done, stuck", "Notes and issues inside the portal"]},
            {"icon": "shield", "title": "Large practice", "line": "Many partners, many audits, one way of working.",
             "gets": ["Tax audit: applicability, 3CD checklist by risk", "GST returns against the books", "A history of every change", "Guide me and a tour video for new staff"]},
        ],
    },
    "faq": {
        "eyebrow": "Questions", "title": "What CA firms ask first",
        "rows": [
            {"q": "Does SimplyFile file the return for me?", "a": "No - by design. It fills the department's official Excel utility and gives you the ITR and 3CD JSON. You validate and upload with the department's own utility, so the final say stays with the CA."},
            {"q": "Where does my clients' data live?", "a": "On your firm's SimplyFile server. Nothing is sent to the income-tax portal."},
            {"q": "Which returns does it handle?", "a": "ITR-3 and ITR-5 with Form 3CD - original, belated, revised and updated returns; old regime or new, surcharge, non-residents and LLPs. My return makes ITR-1, ITR-2, ITR-3 and ITR-4 for individuals and HUFs."},
            {"q": "Can I do my own return?", "a": "Yes. Sign up as an individual, drop in your pre-filled JSON, Form 16, AIS, 26AS and your capital-gains and bank statements: My return reads them, checks them against each other, works out both regimes and gives you the department's JSON to upload yourself."},
            {"q": "What do I need to bring?", "a": "The client's Tally-derived Excel and the 26AS, AIS and TIS you download from the portal. Past returns come in as ITR JSON, matched by PAN."},
            {"q": "Can the whole team work on it?", "a": "Yes. Partners, managers and staff each see what their role allows. Hand over one filing, or some clients for a year, and take it back."},
            {"q": "How does new staff learn it?", "a": "Every screen has Guide me, a step-by-step tour, and a narrated video."},
        ],
    },
    "cta": {
        "title": "Your next return, ready to sign.",
        "sub": "Books in. Return out. Every figure traced - for the whole firm.",
        "start": "Start here", "watch": "Watch the films again", "demo": "Try the demo",
        "fine": "The firm and clients in the films are made up.",
    },
    "foot": {"line": "SimplyFile · Books in. Return out. Every figure traced.", "katha": "Powered by ValueStream", "katha_href": "https://valuestream.in/"},
    "media_base": "static/showcase/",
}


def _version(cid):
    f = ROOT / "chips" / f"{cid}.json"
    return int(json.loads(f.read_text(encoding="utf-8")).get("version") or 0) if f.is_file() else 0


VERSION = {c: _version(c) for c in ("showcase.page", "showcase.settings")}    # 2026-10-07: a re-run moves the version on, never back to 1


def chip_json(cid, label, vals, desc, audience="public"):
    return {"chip_id": cid, "kind": "accessor", "set": "showcase", "audience": audience, "label": label, "aliases": [cid.replace(".", " ")],
            "params": [{"name": k, "type": "any", "default": v, "label": k} for k, v in vals.items()],
            "expr": {"vop": "record", "fields": {k: f"${k}" for k in vals}}, "returns": "record", "version": VERSION.get(cid, 0) + 1, "status": "published",
            "description_nl": desc, "test_cases": [{"args": {}, "expect_value": vals}], "weight_basis": "Words and lists only. Edit them here, never in the page."}

values["stats"] = [
    {"n": "3", "label": "statements reconciled - 26AS, AIS, TIS"},
    {"n": str(len(values["checks"]["rows"])), "label": "checks before the partner signs"},
    {"n": str(sum(len(g["rows"]) for g in values["modules"]["groups"])), "label": "screens for the whole firm"},
    {"n": "0", "label": "client data sent to the IT portal"},
]


if __name__ == "__main__":
    if "--media" in sys.argv:
        media()
    old = {x["name"]: x["default"] for x in json.loads((ROOT / "chips" / "showcase.page.json").read_text(encoding="utf-8"))["params"]}
    values = {**values, **{k: v for k, v in old.items() if k not in values}}     # 2026-10-07: never drop a section written by hand (play)
    TRY = "Open My return for the family HUF and the consultant"
    if "play" in values and TRY not in values["play"]["tries"]:
        values["play"]["tries"] = values["play"]["tries"] + [TRY]
    if "play" in values:      # the demo firm's clients, counted in tmp/showcase/demo-final (2026-10-07: 20 + the HUF and the consultant of part 11)
        values["play"]["window"]["rows"] = [[k, "22" if k == "Clients" else v] for k, v in values["play"]["window"]["rows"]]
        values["play"]["sub"] = values["play"]["sub"].replace("20 clients", "22 clients")
    w = lambda p, d: (ROOT / "chips" / p).write_bytes((json.dumps(d, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))   # noqa: E731
    w("showcase.page.json", chip_json("showcase.page", "SimplyFile's public showcase (its landing for visitors): every word, screen, feature and film part", values,
                                      "2026-10-05 owner: \"do the same for SimplyFile\" - the landing for a visitor, drawn by static/showcase.js (shared with SteadyMove and Katha). Parts are the showcase series recorded on sf.valuestream.in with a made-up firm; marks = each part's description.txt."))
    sites = [{"edition": "simplyfile", "door": "", "page": "showcase.page"}]
    if not (ROOT / "chips" / "showcase.settings.json").is_file():    # 2026-10-07: written once - it has grown by hand since (returning_skip)
      w("showcase.settings.json", chip_json("showcase.settings", "Which sites have a public showcase, and which chip holds its words",
                                          {"editions": ["simplyfile"], "sites": sites, "path": "/showcase"}, "2026-10-05 owner: the showcase is the landing; Start here -> /start.", "admin"))
    print("wrote showcase.page + showcase.settings")
