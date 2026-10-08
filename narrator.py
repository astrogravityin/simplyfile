"""Video Narrator — narrate a screen recording someone made by hand (Snipping Tool, OBS, a phone).

Upload the video → get a TIMED script (the LLM Bridge, by hand, or Draft with AI) → edit every line
→ pick a voice → Generate: each line is spoken, placed at its start time over the video, and written
out as one MP4 plus subtitles and YouTube chapters.

Nothing here knows what the video is about. The prompt is built from the registered project's name
and from whatever that project's own published manual already says about the screen, so the same
code narrates a banking app and a game.

ponytail: files on disk under data/videos/<id>/, one background job per project held in memory.
Video projects are working material, not records — give them a table the day they must survive a
disk wipe or be shared between servers.

Chips (tv/chips/narrator.*.json) hold every sentence, limit, file type, the prompt, the cost estimate
and how a Google refusal is read. This file uploads, polls, speaks, mixes and writes files.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

from fastapi import HTTPException

from core import jobs

import manuals
import media
import store
from core import engine, ops

engine.register_dir(Path(__file__).resolve().parent / "chips")   # also when run on its own (self-check)

DATA = Path(os.getenv("TV_VIDEO_ROOT", store.DATA / "videos"))
_ID = re.compile(r"^[0-9a-f]{12}$")                   # a storage id, so a path can never escape DATA
_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()


def say(key: str, **values) -> str:
    return engine.say("narrator.messages", key, **values)


def log_text(key: str, **values) -> str:
    return engine.say("narrator.job_texts", key, **values)


def limit(key: str):
    return engine.setting("narrator.settings", key)


def video_ext() -> set[str]:
    """The file types accepted as a recording (narrator.settings video_extensions)."""
    return {str(e).lower() for e in limit("video_extensions")}


# --- project files ------------------------------------------------------------------------------

def folder(pid: str) -> Path:
    if not _ID.match(pid or ""):
        raise HTTPException(400, say("bad_id"))
    d = DATA / pid
    if not (d / "project.json").exists():
        raise HTTPException(404, say("no_project"))
    return d


_FILE_LOCK = threading.RLock()


def _retry(fn):
    """Windows cannot open a file while it is being replaced, nor replace one that is open: a job thread
    saves project.json while the page polls it (2026-09-18, PermissionError in the self-check). Reads and
    writes share one lock; a short retry covers another process (a virus scanner) holding it."""
    for attempt in range(6):
        try:
            with _FILE_LOCK:
                return fn()
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.05)
    return None


def _read(path: Path) -> dict:
    return _retry(lambda: json.loads(path.read_text(encoding="utf-8")))


def load(pid: str) -> dict:
    path = folder(pid) / "project.json"
    return _retry(lambda: json.loads(path.read_text(encoding="utf-8")))


def save(p: dict) -> None:
    path = DATA / p["id"] / "project.json"

    def write():
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(p, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    _retry(write)
    if owners().get(p["id"]) != (p.get("owner_id") or ""):
        _owners_put(p["id"], p.get("owner_id") or "")


# 2026-09-28 owner "tens of thousands": a person's recordings are found through this index (recording id -> owner id),
# never by opening every recording folder of every account on each request. Missing = rebuilt once by one scan.
_OWNERS_FILE = "_owners.json"
_OWNERS_LOCK = threading.Lock()


def owners() -> dict:
    """The index, healed: a folder written without save() (an import, a copy) is read once and added; a folder gone
    is dropped. ponytail: one listdir per call (names only, no file opened) - a sharded layout if that ever shows."""
    f = DATA / _OWNERS_FILE
    got: dict = {}
    if f.exists():
        try:
            got = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            got = {}
    names = set(os.listdir(DATA)) if DATA.exists() else set()
    new = [n for n in names if n not in got and _ID.match(n) and (DATA / n / "project.json").exists()]
    gone = [n for n in got if n not in names]
    if new or gone or (DATA.exists() and not f.exists()):
        for n in new:
            got[n] = _read(DATA / n / "project.json").get("owner_id") or ""
        for n in gone:
            got.pop(n)
        f.write_text(json.dumps(got), encoding="utf-8")
    return got


def _owners_put(pid: str, owner_id: str | None) -> None:
    with _OWNERS_LOCK:
        d = owners()
        if owner_id is None:
            d.pop(pid, None)
        else:
            d[pid] = owner_id
        (DATA / _OWNERS_FILE).write_text(json.dumps(d), encoding="utf-8")


def folders_of(user: dict | None) -> list[Path]:
    """The recording folders this person may own (owns: theirs, and an ownerless one is the portal owner's) - through
    the index; everyone's when `user` is None (the portal-wide sweeps)."""
    if not DATA.exists():
        return []
    if user is None:
        return [d for d in DATA.iterdir() if d.is_dir()]
    return [DATA / pid for pid, o in owners().items()
            if (o == user["id"] if o else user.get("role") == "owner") and (DATA / pid).is_dir()]


def source_of(pid: str) -> Path:
    exts = video_ext()
    hits = [f for f in folder(pid).iterdir() if f.stem == "source" and f.suffix in exts]
    if not hits:
        raise HTTPException(404, say("source_gone"))
    return hits[0]


def cover_path(pid: str) -> Path | None:
    """A Video's card cover (2026-09-29 owner: "use the video's own thumbnail as its cover"): a frame of the narrated
    video, else of the recording (chip narrator.settings cover_at_seconds). None = the drawn cover."""
    d = folder(pid)
    src = d / "narrated.mp4" if (d / "narrated.mp4").is_file() else (source_of(pid) if has_source(pid) else None)
    return media.still(src, d / "cover.png", limit("cover_at_seconds")) if src else None


def has_source(pid: str) -> bool:
    if not (DATA / pid).is_dir():
        return False
    exts = video_ext()
    return any(f.stem == "source" and f.suffix in exts for f in (DATA / pid).iterdir())


# --- what this is costing the server -------------------------------------------------------------
# A hosted portal pays for disk whether or not anybody is watching. Every project carries the bytes
# it occupies, written when it grows, so "how much is this account using" is a sum of stored numbers
# and never a walk over every file on the disk.

def folder_bytes(pid: str) -> int:
    d = DATA / pid
    return sum(f.stat().st_size for f in d.iterdir() if f.is_file()) if d.is_dir() else 0


def stamp_bytes(pid: str) -> int:
    """Measure one project and remember it. Called after anything that writes into its folder."""
    n = folder_bytes(pid)
    p = load(pid)
    if p.get("bytes") != n:
        p["bytes"] = n
        save(p)
    return n


def used_bytes(mine, user: dict | None = None) -> int:
    """Disk held by the projects `mine` accepts. Uses the stored number, measuring only a project
    that has never been measured (one written before this existed)."""
    total = 0
    if not DATA.exists():
        return 0
    for d in folders_of(user):
        pj = d / "project.json"
        if not pj.exists():
            continue
        p = _read(pj)
        if not mine(p):
            continue
        total += int(p.get("bytes") or 0) or folder_bytes(p["id"])
    return total


def sweep_sources(days: int) -> int:
    """Delete the uploaded recording of any project whose narrated video is older than `days`.

    The narrated MP4, the subtitles and the script all stay - what goes is the raw upload, which is
    the biggest file in the folder and the one nobody opens again once the narration exists. 0 keeps
    every recording for ever, which is what a portal on your own laptop wants."""
    if days <= 0 or not DATA.exists():
        return 0
    cutoff, freed, exts = time.time() - days * 86400, 0, video_ext()
    for d in DATA.iterdir():
        out = d / "narrated.mp4"
        if not (d / "project.json").exists() or not out.exists() or out.stat().st_mtime > cutoff:
            continue
        for f in d.iterdir():
            if f.is_file() and f.stem == "source" and f.suffix in exts:
                freed += f.stat().st_size
                f.unlink()
        if freed:
            stamp_bytes(d.name)
    return freed


def storage_items(owner_of) -> list[dict]:
    """Every recording on the disk as one storage item, for the owner's Storage screen.
    `owner_of(project)` names the account a project belongs to (see app.owns)."""
    out = []
    for d in DATA.iterdir() if DATA.exists() else []:
        pj = d / "project.json"
        if not pj.exists():
            continue
        p = _read(pj)
        files = [f for f in d.iterdir() if f.is_file() and f.name != "project.json"]
        out.append({"id": p["id"], "owner_id": owner_of(p), "title": p.get("title") or p["id"],
                    "bytes": int(p.get("bytes") or 0) or folder_bytes(p["id"]), "files": len(files),
                    "created_at": p.get("created_at") or ""})
    return out


HELP_PLAY = "/api/help/play/"      # a recording's How to Use address: a link like any other in How to Use pages


def owner_of(row: dict) -> str:
    """A recording made before accounts were plural has no owner_id: it is the first owner's."""
    if row.get("owner_id"):
        return row["owner_id"]
    return next((u["id"] for u in store.users() if u.get("role") == "owner"), "")


def owns(row: dict, u: dict) -> bool:
    """Anyone may sign up, so every recording belongs to the person who made it; one with no owner_id is the owner's."""
    return (row.get("owner_id") == u["id"]) if row.get("owner_id") else (u.get("role") == "owner")


def get_mine(user_id: str, pid: str) -> dict:
    """The recording, if it is this person's (someone else's id reads as "no such recording")."""
    p = load(pid) if _ID.match(pid or "") and (DATA / pid / "project.json").exists() else None
    if not p or owner_of(p) != user_id:
        raise HTTPException(404, say("no_project"))
    return p


def script_text(p: dict, times: bool = False) -> str:
    """The whole narration, in order: a chapter starts a new paragraph under its heading; `times` puts [mm:ss] before
    each line. 2026-09-28 owner: "Download Script - all the narration - and from it make a doodle, film, comic" - the
    download and "Make into" read this one text, so they never differ."""
    out, para = [], []
    for s in sorted(p.get("segments") or [], key=lambda x: float(x.get("start") or 0)):
        text = str(s.get("text") or "").strip()
        if s.get("chapter"):
            if para:
                out.append(" ".join(para) if not times else "\n".join(para))
                para = []
            out.append(str(s["chapter"]).strip())
        if text:
            para.append(f"[{media.stamp(float(s.get('start') or 0), False)}] {text}" if times else text)
    if para:
        out.append(" ".join(para) if not times else "\n".join(para))
    return "\n\n".join(out)


def rename(user_id: str, pid: str, title: str) -> dict:
    p = get_mine(user_id, pid)
    p["title"] = str(title or "").strip()[: int(engine.setting("portal.settings", "title_max"))] or p.get("title", "")
    save(p)
    return p


def delete_mine(user_id: str, pid: str) -> None:
    get_mine(user_id, pid)
    try:
        delete_project(pid)
    except ValueError as e:                              # in use / being made: the App Message says what to do first
        raise HTTPException(409, str(e)) from None


def facts(row: dict) -> dict:
    """What chip quality.rules checks a recording against (a listing row: segments, has_output)."""
    return {"segments": int(row.get("segments") or 0), "made": 1 if row.get("has_output") else 0,
            "done": 1 if row.get("has_output") else 0, "total": 1, "left_usd": 0}


def help_index(live_only: bool = False) -> dict:
    """{recording id: [page id, ...]}: which pages' How to Use links point at a recording. ONE source of truth -
    How to Use pages (core/howto.py, store "howto"), the same model as the studio's Page Configuration: any page,
    any number of links. 2026-09-22 owner: a Studio-only checkbox "is completely wrong - if I want another video
    in another place, then?" `live_only`: only links ticked Live (what a reader can play)."""
    out: dict = {}
    for page, links in (store.read("howto", {}) or {}).items():
        for ln in links or []:
            url = str(ln.get("url") or "")
            if url.startswith(HELP_PLAY) and (ln.get("active", True) or not live_only):
                out.setdefault(url[len(HELP_PLAY):].split("?")[0].strip("/"), []).append(page)
    return out


def help_pages_named(pages: list[str]) -> str:
    from core import howto  # noqa: PLC0415
    names = {p["id"]: p["label"] for p in howto.pages()}
    return ", ".join(names.get(p, p) for p in pages)


def delete_project(pid: str) -> None:
    """Remove a recording and everything made from it. Refuses while a job is writing into it, and while a screen
    uses it as its How to Use video (2026-09-22 owner: "I can delete the How to Use video - a video in use must
    not be deletable; warn and ask to unlink first"). Both doors - Videos and Storage - come through here."""
    d = folder(pid)
    if job_of(pid).get("status") == "running":
        raise ValueError(say("job_running"))
    used = help_index().get(pid) or []
    if used:
        raise ValueError(say("in_use", screens=help_pages_named(used)))
    shutil.rmtree(d)
    _owners_put(pid, None)
    _JOBS.pop(pid, None)


def listing(project_id: str = "", mine: callable | None = None, user: dict | None = None) -> list[dict]:
    """`mine` decides whose recordings these are — see app.owns. Everyone brings their own key and
    their own recordings here, so a listing without that filter belongs to nobody."""
    out, helps = [], help_index()          # the page warns BEFORE a delete is tried (images do the same)
    if DATA.exists():
        for d in sorted(folders_of(user), key=lambda x: x.stat().st_mtime, reverse=True):
            pj = d / "project.json"
            if not pj.exists():
                continue
            p = _read(pj)
            if project_id and p.get("project_id") != project_id:
                continue
            if mine is not None and not mine(p):
                continue
            out.append({k: p.get(k) for k in ("id", "project_id", "title", "created_at", "duration", "screen_key")}
                       | {"in_use": say("in_use", screens=help_pages_named(helps[p["id"]])) if helps.get(p["id"]) else ""}
                       | {"segments": len(p.get("segments", [])), "has_output": (d / "narrated.mp4").exists(),
                          "bytes": int(p.get("bytes") or 0) or folder_bytes(p["id"]),
                          "has_source": has_source(p["id"]),
                          "busy": (_JOBS.get(p["id"]) or {}).get("status") == "running"})
    return out


# --- segments -----------------------------------------------------------------------------------

def clean_segments(raw: list[dict], duration: float) -> list[dict]:
    """Sorted, inside the video, each ending after it starts, none overlapping the next."""
    out = []
    text_max, chapter_max, voice_max = limit("line_text_max"), limit("chapter_max"), limit("voice_max")
    for s in raw or []:
        try:
            start, end = float(s.get("start", 0)), float(s.get("end", 0))
        except (TypeError, ValueError):
            raise HTTPException(400, say("line_needs_times"))
        out.append({"start": round(max(0.0, start), 2), "end": round(end, 2),
                    "text": str(s.get("text", "")).strip()[:text_max],
                    "chapter": str(s.get("chapter", "")).strip()[:chapter_max],
                    "voice": str(s.get("voice", "")).strip()[:voice_max]})
    out.sort(key=lambda s: s["start"])
    for i, s in enumerate(out, 1):
        if s["end"] <= s["start"]:
            raise HTTPException(400, say("line_ends_early", n=i))
        if duration and s["start"] >= duration:
            raise HTTPException(400, say("line_after_video", n=i, duration=float(duration)))
        if not s["text"]:
            raise HTTPException(400, say("line_no_words", n=i))
    tolerance = limit("overlap_tolerance_s")
    for i in range(len(out) - 1):
        if out[i]["end"] > out[i + 1]["start"] + tolerance:
            raise HTTPException(400, say("line_overlaps", n=i + 1, next=i + 2))
    return out


def check_voices(segs: list[dict], master: str = "") -> None:
    known = {v["id"] for v in media.voices()["voices"]}
    for i, s in enumerate(segs, 1):
        if s.get("voice") and s["voice"] not in known:
            raise HTTPException(400, say("line_unknown_voice", n=i, voice=s["voice"]))
    if master and master not in known:
        raise HTTPException(400, say("unknown_voice"))


# --- the prompt (narrator.prompt) ---------------------------------------------------------------

def screen_context(project_id: str, screen_key: str) -> str:
    """What this project's own manual already says about the screen, so the draft uses its words."""
    if not screen_key:
        return ""
    bits = []
    words = engine.run("narrator.prompt")
    most = limit("manual_context_max")
    for row in manuals.all_manuals():
        if row.get("project_id") != project_id:
            continue
        for page in row["manual"]["pages"]:
            if page.get("screen_key") == screen_key:
                text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page.get("description", ""))).strip()
                if text:
                    bits.append(ops.template(words["context_line"], {
                        "header": page.get("header") or words["page_fallback"], "text": text[:most]}))
    return ops.template(words["context"], {"lines": "\n".join(bits)}) if bits else ""


def languages() -> list[dict]:
    """The languages a script may be written or translated into: chip narrator.languages."""
    return engine.run("narrator.languages")["rows"]


def default_language() -> str:
    return engine.setting("narrator.languages", "default_code")


def language_name(code: str) -> str:
    """The English name of a language code, or "" when this portal does not offer it."""
    row = next((r for r in languages() if r["code"] == (code or "").strip().lower()), None)
    return row["name"] if row else ""


def language_line(code: str) -> str:
    """The sentence added to the prompt for a language; nothing at all for the default one."""
    name = language_name(code)
    return "" if not name or code == default_language() else engine.say("narrator.prompt", "language_line",
                                                                        language=name)


def cut_say(key: str, **values) -> str:
    return engine.say("media.cut_messages", key, **values)


def new_project(seed: dict, title: str, duration: float, source: Path, who_: str, user_id: str) -> dict:
    """A recording made FROM other recordings is a project like any other: its own folder, its own
    script, its own narration. Nothing about trimming or joining is a special case downstream."""
    pid = store.new_id()
    d = DATA / pid                       # folder() answers 404 until project.json exists, so make it here
    d.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(d / f"source{source.suffix or '.mp4'}"))
    p = {k: seed.get(k, "") for k in ("project_id", "screen_key", "notes")} | {
        "id": pid, "owner_id": user_id, "title": title[:int(engine.setting("portal.settings", "title_max"))],
        "created_at": store.now(), "created_by": who_, "duration": round(duration, 2),
        "has_audio": media.has_audio(d / f"source{source.suffix or '.mp4'}"), "segments": [],
        "voice": seed.get("voice") or media.voices()["default"], "language": seed.get("language") or default_language()}
    save(p)
    stamp_bytes(pid)
    return p


def trim(pid: str, start: float, end: float, who_: str, user_id: str) -> dict:
    """Keep one stretch of a recording as a NEW one; the original is never touched. The knobs are chip
    media.cut, every sentence is media.cut_messages."""
    p = load(pid)
    src = source_of(pid)
    if not has_source(pid):
        raise HTTPException(400, cut_say("source_gone", title=p.get("title", "")))
    k = media.cut_settings()
    duration = float(p.get("duration") or 0)
    start, end = max(0.0, float(start)), float(end)
    if end <= start:
        raise HTTPException(400, cut_say("bad_range"))
    if duration and end > duration + float(k["end_tolerance_seconds"]):
        raise HTTPException(400, cut_say("past_end", duration=duration))
    if end - start < float(k["min_seconds"]):
        raise HTTPException(400, cut_say("too_short", min=k["min_seconds"]))

    def work(job):
        job["progress"], job["stage"] = 10, cut_say("trimming", **{"from": start, "to": end})
        job["log"].append(job["stage"])
        out = folder(pid) / "trimmed.mp4"
        r = subprocess.run(media.trim_command(src, start, end, out), capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(cut_say("cut_failed", reason=(r.stderr.strip().splitlines() or ["?"])[-1]))
        made = new_project(p, cut_say("trim_title", title=p.get("title", "")), media.duration(out), out,
                           who_, user_id)
        job["progress"], job["made"] = 100, made["id"]
        job["log"].append(cut_say("trimmed", seconds=made["duration"], was=duration))

    return start_job(pid, "trim", work)


def join(parts: list, mine, who_: str, user_id: str, title: str = "") -> dict:
    """Several recordings - or stretches of them - one after another, as a NEW recording. A part is a
    project id, or {id, start, end} to keep only that stretch (2026-09-18 composer: "take video 1, trim
    it, add it to video 2, make video 3"). The same recording may appear more than once. Every piece is
    checked to be this person's own before a frame is read."""
    k = media.cut_settings()
    parts = [x if isinstance(x, dict) else {"id": str(x)} for x in (parts or [])]
    if len(parts) < 2:
        raise HTTPException(400, cut_say("need_two"))
    if len(parts) > int(k["max_parts"]):
        raise HTTPException(400, cut_say("too_many", max=int(k["max_parts"])))
    rows, spans = [], []
    for part in parts:
        pid = str(part.get("id") or "")
        p = load(pid)
        if not mine(p):
            raise HTTPException(403, cut_say("not_yours"))
        if not has_source(pid):
            raise HTTPException(400, cut_say("source_gone", title=p.get("title", "")))
        length = float(p.get("duration") or 0)
        if part.get("start") is None and part.get("end") is None:
            spans.append(None)
        else:
            a, b = max(0.0, float(part.get("start") or 0)), float(part.get("end") or length)
            if b <= a:
                raise HTTPException(400, cut_say("bad_range"))
            if length and b > length + float(k["end_tolerance_seconds"]):
                raise HTTPException(400, cut_say("past_end", duration=length))
            if b - a < float(k["min_seconds"]):
                raise HTTPException(400, cut_say("too_short", min=k["min_seconds"]))
            whole = float(k["whole_tolerance_seconds"])
            spans.append(None if a <= whole and length and b >= length - whole else (a, min(b, length or b)))
        rows.append(p)
    pids = [p["id"] for p in rows]

    def work(job):
        job["progress"], job["stage"] = 10, cut_say("joining", n=len(rows))
        job["log"].append(job["stage"])
        out = folder(pids[0]) / "joined.mp4"
        r = subprocess.run(media.join_command([source_of(p["id"]) for p in rows], out,
                                             [bool(p.get("has_audio")) for p in rows],
                                             [float(p.get("duration") or 0) for p in rows], spans),
                           capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(cut_say("cut_failed", reason=(r.stderr.strip().splitlines() or ["?"])[-1]))
        name = title.strip() or cut_say("join_title", title=rows[0].get("title", ""), n=len(rows) - 1)
        made = new_project(rows[0], name, media.duration(out), out, who_, user_id)
        job["progress"], job["made"] = 100, made["id"]
        job["log"].append(cut_say("joined", n=len(rows), seconds=made["duration"]))

    return start_job(pids[0], "join", work)


def voice_language(voice_id: str) -> str:
    """The language a voice actually speaks, from voices.json (its `lang`, else the front of its id)."""
    row = next((v for v in media.voices()["voices"] if v["id"] == voice_id), None)
    return (row or {}).get("lang") or str(voice_id or "").split("-")[0]


# --- premium voices (2026-09-20 owner: "better voices"): Google's TTS model on the person's own key -------------

def tts_settings() -> dict:
    return engine.run("narrator.tts")


def paid_voice(voice_id: str) -> str:
    """The provider a voice is paid on ("" for the free edge-tts voices) - voices.json says, never the id's shape."""
    row = next((v for v in media.voices()["voices"] if v["id"] == voice_id), None)
    return str((row or {}).get("paid") or "")


def tts_estimate(segs: list[dict], master: str, user_id: str) -> dict:
    """What the premium lines of this script would cost THIS person before a rupee is spent: the lines whose voice
    (their own, else the master) is paid, their characters through chip narrator.tts_estimate, their funds and key."""
    import providers  # noqa: PLC0415 - providers imports narrator at call time only
    k = tts_settings()
    paid = [s for s in segs if paid_voice(s.get("voice") or master)]
    chars = sum(len(media.spoken(str(s.get("text") or ""))) for s in paid)
    est = engine.run("narrator.tts_estimate", {"chars": chars, "chars_per_token": k["chars_per_token"], "chars_per_second": k["chars_per_second"],
                                               "audio_tokens_per_second": k["audio_tokens_per_second"],
                                               "usd_per_1m_in": k["usd_per_1m_in"], "usd_per_1m_out": k["usd_per_1m_out"]})
    return {"paid": bool(paid), "lines": len(paid), "chars": chars, "provider": k["provider"], "model": k["model"],
            "cost_usd": float(est["cost_usd"]), "seconds": est["seconds"], "tokens_in": est["tokens_in"], "tokens_out": est["tokens_out"],
            "funds": store.funds_for(user_id, k["provider"]), "have_key": providers.have_key(user_id, k["provider"])}


def tts_line_cost(text: str) -> float:
    """The estimate for one line's characters (chip narrator.tts_estimate) - no funds or key lookups, so a 300-line
    script plans in one pass."""
    k = tts_settings()
    return float(engine.run("narrator.tts_estimate", {"chars": len(text), "chars_per_token": k["chars_per_token"],
                                                      "chars_per_second": k["chars_per_second"], "audio_tokens_per_second": k["audio_tokens_per_second"],
                                                      "usd_per_1m_in": k["usd_per_1m_in"], "usd_per_1m_out": k["usd_per_1m_out"]})["cost_usd"])


def tts_cost(tokens_in: int, tokens_out: int) -> float:
    k = tts_settings()
    return float(engine.run("narrator.tts_cost", {"tokens_in": int(tokens_in), "tokens_out": int(tokens_out),
                                                  "usd_per_1m_in": k["usd_per_1m_in"], "usd_per_1m_out": k["usd_per_1m_out"]}))


def gemini_speak(key: str, model: str, text: str, voice_name: str) -> tuple[bytes, int, int]:
    """One line as PCM from Google's TTS model. Returns (pcm bytes, text tokens in, audio tokens out)."""
    from google import genai  # noqa: PLC0415
    from google.genai import types  # noqa: PLC0415
    client = genai.Client(api_key=key)                # held: a temporary client closes before its call answers
    cfg = types.GenerateContentConfig(response_modalities=["AUDIO"], speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name))))
    resp = client.models.generate_content(model=model, contents=text, config=cfg)
    parts = [p for c in (getattr(resp, "candidates", None) or []) for p in (getattr(getattr(c, "content", None), "parts", None) or [])]
    pcm = next((p.inline_data.data for p in parts if getattr(p, "inline_data", None) and getattr(p.inline_data, "data", None)), b"")
    if not pcm:
        raise RuntimeError(say("tts_nothing_back"))
    um = getattr(resp, "usage_metadata", None)
    return pcm, int(getattr(um, "prompt_token_count", 0) or 0), int(getattr(um, "candidates_token_count", 0) or 0)


def pcm_to_mp3(pcm: bytes, sample_rate: int, out: Path, faster: int = 0) -> None:
    """Google's raw 16-bit mono PCM into the MP3 every other voice clip is - faster by `faster` percent when a line
    must fit its window (atempo keeps the pitch; edge-tts does the same with its rate)."""
    import wave  # noqa: PLC0415
    tmp = out.with_suffix(".wav")
    with wave.open(str(tmp), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(sample_rate))
        w.writeframes(pcm)
    cmd = [media.ffmpeg(), "-y", "-i", str(tmp)]
    if faster:
        cmd += ["-af", f"atempo={1 + faster / 100:.4f}"]
    r = subprocess.run(cmd + [str(out)], capture_output=True, text=True)
    tmp.unlink(missing_ok=True)
    if r.returncode:
        raise RuntimeError((r.stderr.strip().splitlines() or ["ffmpeg"])[-1])


def regions() -> list[dict]:
    """Where a voice sounds from (India, US, Europe...): chip voice.regions."""
    return engine.run("voice.regions")["rows"]


def region_line(text: str, region: str) -> str:
    """A premium voice speaks any accent: the line as the model is asked to say it in this region's (chip voice.regions
    style). No region, or one the chip does not have = the line as it is."""
    r = next((x for x in regions() if x["id"] == region), None)
    return r["style"].replace("{text}", text) if r and r.get("style") else text


def speak_paid(user_id: str, text: str, voice_id: str, out: Path, window: float | None = None, region: str = "") -> dict:
    """One line in a premium voice, on this person's own key, booked at the model's reported usage. Fit to `window`
    by speeding the clip up locally (no second paid call). `region` = the accent it is asked for (chip voice.regions).
    Returns {said, cost_usd, tokens_in, tokens_out, faster}."""
    import providers  # noqa: PLC0415
    k = tts_settings()
    name = voice_id[len(k["voice_prefix"]):] if voice_id.startswith(k["voice_prefix"]) else voice_id
    def one(line):
        return providers.call_with_keys(user_id, k["provider"], lambda key: gemini_speak(key, k["model"], region_line(line, region), name))[0]
    try:
        pcm, tin, tout = one(text)
    except RuntimeError as err:
        # 2026-09-30: Gemini TTS returned NO SOUND for some lines (lists of terms, odd spellings) - every module stopped on it.
        # Ask again one sentence at a time (chip speech.rules no_sound_split) and join the sound; a single sentence re-raises.
        parts = [x for x in re.split(engine.say("speech.rules", "no_sound_split"), text) if x.strip()]
        if str(err) != say("tts_nothing_back") or len(parts) < 2:
            raise
        got = [one(x) for x in parts]
        pcm, tin, tout = b"".join(g[0] for g in got), sum(g[1] for g in got), sum(g[2] for g in got)
    cost = tts_cost(tin, tout)
    store.spend(user_id, k["provider"], cost)
    pcm_to_mp3(pcm, int(k["sample_rate"]), out)
    said = media.duration(out)
    faster = media.speed_up_percent(said, window) if window else 0
    if faster:
        pcm_to_mp3(pcm, int(k["sample_rate"]), out, faster)
        said = media.duration(out)
    return {"said": said, "cost_usd": cost, "tokens_in": tin, "tokens_out": tout, "faster": faster}


def voice_for(code: str) -> str:
    """The narrator a script in this language should be read with: the language's own row (chip
    narrator.languages), else any voice in voices.json that speaks it, else the portal default.
    2026-09-18 owner: "how can the script be narrated in the language it was translated into?" - by
    never leaving a Telugu script pointed at an English mouth."""
    row = next((r for r in languages() if r["code"] == code), None)
    ids = {v["id"] for v in media.voices()["voices"]}
    if row and row.get("voice") in ids:
        return row["voice"]
    speaks = next((v["id"] for v in media.voices()["voices"] if voice_language(v["id"]) == code), "")
    return speaks or media.voices()["default"]


def fit_times(segs: list[dict], duration: float) -> list[dict]:
    """Auto-fit: every line gets the time its own words need, with a breath between, and the whole set
    is stretched or squeezed to end just before the recording does (chip narrator.fit). Words and order
    are never touched - only the clock. 2026-09-18: a drafted or translated script often carries times
    that no longer match the words, and fixing 30 lines by hand is nobody's idea of a portal."""
    k = engine.run("narrator.fit")
    if not segs:
        return []
    wps, gap = float(k["words_per_second"]) or 1.0, float(k["gap_seconds"])
    floor_s, tail = float(k["min_line_seconds"]), float(k["tail_seconds"])
    start = float(segs[0].get("start") or 0) if k["keep_first_start"] else float(k["start_at"])
    needs = [float(engine.run("narrator.line_need", {"words": len(str(s.get("text") or "").split()),
                                                      "words_per_second": wps, "min_line_seconds": floor_s}))
             for s in segs]
    room = max(0.0, float(duration or 0) - start - tail)
    span = sum(needs) + gap * (len(segs) - 1)
    # Squeeze always (words must fit the recording); stretch only when the owner wants the narration
    # to cover the whole thing rather than finish early (chip narrator.fit spread_to_end).
    factor = (room / span) if room and span and (span > room or k["spread_to_end"]) else 1.0
    out, at = [], start
    for s, need in zip(segs, needs):
        length = max(floor_s * factor, need * factor)
        out.append(dict(s, start=round(at, 2), end=round(at + length, 2)))
        at += length + gap * factor
    if duration:                                      # never past the end of the recording
        out[-1]["end"] = min(out[-1]["end"], round(float(duration) - tail, 2))
        if out[-1]["end"] <= out[-1]["start"]:
            out[-1]["end"] = round(float(duration), 2)
    return out


def script_from_text(pid: str, text: str) -> dict:
    """Portal does it (2026-09-24 owner, four roads): the person's own text cut at sentence ends into lines of about
    line_words words, each timed to its words across the recording (fit_times) - free, no model. A rough first cut."""
    k = engine.run("narrator.fit")
    parts = [x.strip() for x in re.split(k["sentence_split"], re.sub(r"\s+", " ", str(text or ""))) if x.strip()]
    if not parts:
        raise HTTPException(400, say("text_needed"))
    lines, cur = [], []
    for sent in parts:
        cur.append(sent)
        if len(" ".join(cur).split()) >= int(k["line_words"]):
            lines.append(" ".join(cur))
            cur = []
    if cur:
        lines.append(" ".join(cur))
    p = load(pid)
    p["segments"] = fit_times([{"start": 0, "end": 0, "text": t, "chapter": "", "voice": ""} for t in lines], float(p.get("duration") or 0))
    p["script_road"] = "portal"
    save(p)
    return p


def script_characters(segs: list[dict]) -> int:
    return sum(len(str(s.get("text") or "")) for s in segs)


def translate_estimate(pid: str, user_id: str, code: str = "") -> dict:
    """What translating this script would cost THIS person - beside what drafting again would cost, so
    the cheaper road is visible before anything is spent."""
    p = load(pid)
    segs = p.get("segments") or []
    mine = store.keys_of(user_id)
    model = mine.get("gemini_model") or store.DEFAULT_KEYS["gemini_model"]
    est = engine.run("narrator.translate_estimate", {"characters": script_characters(segs), "lines": len(segs)})
    tokens_in, tokens_out = int(est["tokens_in"]), int(est["tokens_out"])
    return {"provider": "gemini", "model": model, "tokens_in": tokens_in, "tokens_out": tokens_out,
            "cost_usd": media.cost_usd(model, tokens_in, tokens_out), "seconds": est["seconds"],
            "lines": len(segs), "language": code or "", "funds": store.funds_for(user_id, "gemini"),
            "have_key": bool(mine.get("gemini_api_key")),
            "draft": draft_estimate(p.get("duration") or 0, user_id)}


def translate(pid: str, code: str, who: str, user_id: str) -> dict:
    """The words only - the recording is never uploaded again, which is why this costs a fraction of a
    fresh draft. Times are kept; Auto-fit is one press away if the new words need different room."""
    p = load(pid)
    segs = p.get("segments") or []
    name = language_name(code)
    if not name:
        raise HTTPException(400, say("unknown_language"))
    if not segs:
        raise HTTPException(400, say("nothing_to_translate"))
    if (p.get("language") or default_language()) == code:
        raise HTTPException(400, say("already_that_language", language=name))
    mine = store.keys_of(user_id)
    key = _gemini_key(user_id)
    if not key:
        raise HTTPException(400, say("draft_needs_key"))
    model = mine.get("gemini_model") or store.DEFAULT_KEYS["gemini_model"]

    def work(job):
        from google import genai
        from google.genai import types

        started = time.time()
        est = translate_estimate(pid, user_id, code)
        usage = {"provider": "gemini", "model": model, "tokens_in": 0, "tokens_out": 0, "cost_usd": None,
                 "elapsed_s": 0, "funds": store.funds_for(user_id, "gemini")}
        job["usage"], job["progress"], job["stage"] = usage, 10, log_text("translating", language=name)
        job["log"].append(job["stage"])
        prompt = engine.say("narrator.prompt", "translate_template", language=name, n=len(segs),
                            lines="\n".join(f'{i + 1}. {s.get("text") or ""}' for i, s in enumerate(segs))) + media.for_ear()
        client = genai.Client(api_key=key)
        resp = client.models.generate_content(
            model=model, contents=[prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json"))
        m = getattr(resp, "usage_metadata", None)
        usage["tokens_in"] = int(getattr(m, "prompt_token_count", 0) or 0)
        usage["tokens_out"] = int(getattr(m, "candidates_token_count", 0) or 0)
        usage["cost_usd"] = media.cost_usd(model, usage["tokens_in"], usage["tokens_out"])
        usage["elapsed_s"] = round(time.time() - started, 1)
        store.spend(user_id, "gemini", usage["cost_usd"])
        usage["funds"] = store.funds_for(user_id, "gemini")
        job["usage"] = dict(usage)
        store.log_run({"video": pid, "what": log_text("translate_run", language=name,
                                        title=p.get("title", "")[:limit("run_title_max")]),
                       "who": who, "user_id": user_id} | usage)
        money = log_text("money_unknown") if usage["cost_usd"] is None else log_text("money", cost=store.money_text(user_id, usage["cost_usd"]))
        job["log"].append(log_text("cost", money=money, tokens_in=usage["tokens_in"],
                                   tokens_out=usage["tokens_out"], model=model))
        data = json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", (getattr(resp, "text", "") or "").strip()))
        lines = data.get("lines", data) if isinstance(data, dict) else data
        lines = [str(t).strip() for t in lines] if isinstance(lines, list) else []
        if not any(lines):
            raise RuntimeError(log_text("translate_none"))
        fresh = load(pid)
        kept = fresh.get("segments") or segs
        fresh["segments"] = [dict(s, text=lines[i] or s.get("text", "")) if i < len(lines) else s
                             for i, s in enumerate(kept)]
        fresh["language"], fresh["translated_at"] = code, store.now()
        # The point of translating is to be HEARD in that language: a voice that cannot say the words
        # is switched for one that can, and every line that had its own English voice is freed to it.
        if voice_language(fresh.get("voice") or "") != code:
            fresh["voice"] = voice_for(code)
            fresh["segments"] = [dict(s, voice="") if voice_language(s.get("voice") or "") != code else s
                                 for s in fresh["segments"]]
            job["log"].append(log_text("voice_switched", voice=fresh["voice"], language=name))
        save(fresh)
        job["progress"] = 100
        job["log"].append(log_text("translate_ready", language=name, n=len(lines)))

    return start_job(pid, "translate", work)


def build_prompt(p: dict) -> str:
    """The prompt WITHOUT the "what to learn" line: Draft with AI appends the project's notes, the
    LLM Bridge appends what the author types in its dialog."""
    from projects import get_project
    proj = get_project(p.get("project_id", "")) or {}
    return engine.say("narrator.prompt", "template",
                      product=proj.get("name") or engine.setting("narrator.prompt", "product_fallback"),
                      duration=float(p.get("duration") or 0), title=p.get("title", ""),
                      context=screen_context(p.get("project_id", ""), p.get("screen_key", ""))
                      ) + language_line(p.get("language") or default_language()) + media.for_ear()


def learn_line(notes: str) -> str:
    return engine.say("narrator.prompt", "learn_line",
                      notes=notes.strip() or engine.setting("narrator.prompt", "learn_default"))


def parse_draft(raw: str, duration: float) -> list[dict]:
    txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", (raw or "").strip())
    data = json.loads(txt)
    items = data.get("segments", data) if isinstance(data, dict) else data
    segs = []
    for it in items if isinstance(items, list) else []:
        try:
            st, en = float(it.get("start", 0)), float(it.get("end", 0))
        except (TypeError, ValueError, AttributeError):
            continue
        text = str(it.get("text", "")).strip()
        if text and en > st:
            segs.append({"start": max(0.0, st), "end": min(en, duration) if duration else en,
                         "text": text[:limit("line_text_max")],
                         "chapter": str(it.get("chapter", ""))[:limit("chapter_max")], "voice": ""})
    # A model occasionally overlaps by a fraction; clip each end to the next start rather than reject.
    segs.sort(key=lambda s: s["start"])
    shortest = limit("min_clipped_line_s")
    for a, b in zip(segs, segs[1:]):
        if a["end"] > b["start"]:
            a["end"] = max(a["start"] + shortest, b["start"])
    segs, _factor = media.rescale_timeline([s for s in segs if s["end"] > s["start"]], duration)
    return clean_segments(segs, duration)


# --- jobs ---------------------------------------------------------------------------------------

def start_job(pid: str, kind: str, target) -> dict:
    with _LOCK:
        job = _JOBS.get(pid)
        if job and job["status"] == "running":
            raise HTTPException(409, say("busy", kind=job["kind"]))
        job = {"kind": kind, "status": "running", "log": [], "started": store.now(),
               "started_ms": int(time.time() * 1000), "progress": 0, "stage": "starting", "usage": None}
        _JOBS[pid] = job

    def run():
        try:
            if target(job) == "stopped":             # a resumable job stopped cleanly: its parts are kept
                job["status"] = "stopped"
            else:
                job["status"], job["progress"], job["stage"] = "finished", 100, "done"
        except Exception as e:  # noqa: BLE001 - the page shows the reason; nothing else is waiting
            job["log"].append(log_text("failed", reason=str(e).splitlines()[0] if str(e) else type(e).__name__))
            job["status"] = "failed"
        job["elapsed_s"] = round((int(time.time() * 1000) - job["started_ms"]) / 1000, 1)

    threading.Thread(target=run, daemon=True, name=f"narrator-{kind}-{pid}").start()
    return job


def job_of(pid: str) -> dict:
    job = dict(_JOBS.get(pid) or {"status": "idle", "log": []})
    jid = f"shorts-{pid}" if job.get("kind") == "cut" else render_job_id(pid)
    job["steps"] = jobs.summary(jobs.load(jid))    # the saved steps: resume, ready, stopped
    return job


def render_job_id(pid: str) -> str:
    return f"render-{pid}"


def line_key(text: str, voice: str, window: float) -> str:
    """A voiced line is reused only when its words, its voice and its room are the same as last time."""
    import hashlib  # noqa: PLC0415
    return hashlib.sha1(f"{text}|{voice}|{window:.2f}".encode("utf-8")).hexdigest()[:16]


# --- what Draft with AI costs -------------------------------------------------------------------

def gemini_json(key: str, model: str, prompt: str, video: Path | None = None, stage=lambda pct, text: None,
                youtube_url: str | None = None, images: list[Path] | None = None):
    """One call to Gemini that must answer JSON. With `video`, the recording is uploaded and watched
    (priced per second of video); without, only the words go (a fraction of the cost). `images`: small
    pictures sent inline (a few hundred tokens each - the film's continuity check). Returns
    (text, tokens_in, tokens_out). The uploaded copy is deleted straight after."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=key)
    contents, up = [prompt], None
    if youtube_url:          # Gemini watches a public YouTube video by its link - nothing is downloaded here
        contents = [types.Part(file_data=types.FileData(file_uri=youtube_url)), prompt]
    for img in images or []:
        mime = "image/png" if img.suffix.lower() == ".png" else "image/webp" if img.suffix.lower() == ".webp" else "image/jpeg"
        contents.append(types.Part.from_bytes(data=img.read_bytes(), mime_type=mime))
    if video is not None:
        stage(5, log_text("uploading"))
        up = client.files.upload(file=str(video))
        stage(35, log_text("processing"))
        for n in range(int(limit("processing_polls"))):
            if getattr(up.state, "name", str(up.state)) != "PROCESSING":
                break
            time.sleep(limit("processing_poll_s"))
            up = client.files.get(name=up.name)
        if getattr(up.state, "name", str(up.state)) == "FAILED":
            raise RuntimeError(log_text("processing_failed"))
        contents = [up, prompt]
    stage(60, log_text("writing"))
    try:
        resp = client.models.generate_content(
            model=model, contents=contents, config=types.GenerateContentConfig(response_mime_type="application/json"))
    finally:
        if up is not None:
            try:
                client.files.delete(name=up.name)
            except Exception:  # noqa: BLE001 - the uploaded copy expires on its own within two days
                pass
    m = getattr(resp, "usage_metadata", None)
    return (getattr(resp, "text", "") or "", int(getattr(m, "prompt_token_count", 0) or 0),
            int(getattr(m, "candidates_token_count", 0) or 0))


def draft_estimate(duration: float, user_id: str) -> dict:
    """What Draft with AI would cost THIS person, with THEIR key and THEIR balance."""
    mine = store.keys_of(user_id)
    model = mine.get("gemini_model") or store.DEFAULT_KEYS["gemini_model"]
    # The rates and the formula are narrator.draft_estimate; Google's video token rate is media's.
    est = engine.run("narrator.draft_estimate", {"duration": duration,
                                                  "video_tokens_per_second": media.VIDEO_TOKENS_PER_SECOND})
    tokens_in, tokens_out = int(est["tokens_in"]), int(est["tokens_out"])
    return {"provider": "gemini", "model": model, "tokens_in": tokens_in, "tokens_out": tokens_out,
            "cost_usd": media.cost_usd(model, tokens_in, tokens_out),
            "seconds": est["seconds"], "funds": store.funds_for(user_id, "gemini"),
            "have_key": bool(mine.get("gemini_api_key"))}


def explain_key_error(detail: str, key: str, model: str) -> tuple[int, str]:
    """Google's refusal, as the one thing the person has to change — with Google's own sentence
    attached, always, so the next failure explains itself (chips narrator.key_error and
    narrator.key_error_kind).

    Key FORMAT is never judged here. Gemini keys used to start with "AIza" (39 characters); AI Studio
    now issues "AQ." keys (53 characters), and both go to Google the same way (x-goog-api-key).
    2026-09-17: an "AQ." key was reported as "your key works, but it cannot use gemini-2.5-flash"
    because ANY "not found" was blamed on the model, and Google's text was thrown away. The model is
    blamed only when Google's sentence names a model (narrator.model_refused)."""
    said = engine.run("narrator.key_error", {"detail": detail, "model": model})
    return int(said["status"]), said["message"]


def model_refused(detail: str, model: str) -> bool:
    """Google refused the MODEL, not the key (narrator.model_refused)."""
    return engine.run("narrator.model_refused", {"detail": detail, "model": model}) is True


def _gemini_key(user_id: str) -> str:
    """The Gemini key to use now: the pool's first usable one (several keys since 2026-09-19), else the field."""
    import providers  # noqa: PLC0415
    return providers.key_for(user_id, "gemini") or str(store.keys_of(user_id).get("gemini_api_key") or "")


def probe_key(key: str, model: str) -> str:
    """Four words to Google on ONE key. Returns the model that answered (the first preferred one this key can
    see, when the asked-for model is withheld from it). Raises with Google's own sentence otherwise."""
    from google import genai
    client = genai.Client(api_key=key)                # held: see check_key
    ask = limit("key_check_prompt")
    try:
        client.models.generate_content(model=model, contents=ask)
        return model
    except Exception as first:  # noqa: BLE001
        if not model_refused(str(first), model):
            raise
        seen = {str(getattr(m, "name", "")).split("/")[-1] for m in client.models.list()}
        better = next((m for m in store.MODEL_PREFERENCE if m in seen and m != model), "")
        if not better:
            raise
        client.models.generate_content(model=better, contents=ask)
        return better


def check_key(user_id: str, who: str = "") -> dict:
    """Prove a key works the moment it is saved, not days later inside a job.

    The cheapest real call there is: four words to the model the person picked. It costs a fraction
    of a cent, and it is the only way to tell a working key from a typo, a revoked one, or a key
    whose project has no access to that model. The attempt is booked like any other paid run."""
    mine = store.keys_of(user_id)
    import providers  # noqa: PLC0415 - the default pooled key (several keys per provider since 2026-09-19)
    key = providers.key_for(user_id, "gemini") or mine.get("gemini_api_key")
    model = mine.get("gemini_model") or store.DEFAULT_KEYS["gemini_model"]
    if not key:
        raise HTTPException(400, say("save_key_first"))
    started = time.time()
    ask = limit("key_check_prompt")
    try:
        from google import genai
    except ImportError:
        raise HTTPException(503, say("missing_genai"))
    try:
        # Hold the client in a name. Chaining the call straight off the constructor lets the Client
        # be garbage-collected the moment `.models` is read, and google-genai closes its HTTP client
        # when that happens: every test then failed with "Cannot send a request, as the client has
        # been closed" — reported as a network fault, for a key that worked everywhere else.
        client = genai.Client(api_key=key)
        switched_from = ""
        try:
            resp = client.models.generate_content(model=model, contents=ask)
        except Exception as first:  # noqa: BLE001
            # The key may be fine and the MODEL refused to it — Google withholds older models from new
            # keys. Ask what this key can see (free), move to the first preferred one, try once more.
            if not model_refused(str(first), model):
                raise
            seen = {str(getattr(m, "name", "")).split("/")[-1] for m in client.models.list()}
            better = next((m for m in store.MODEL_PREFERENCE if m in seen and m != model), "")
            if not better:
                raise
            resp = client.models.generate_content(model=better, contents=ask)
            store.save_keys_for(user_id, {"gemini_model": better})
            switched_from, model = model, better
    except Exception as e:  # noqa: BLE001 — every failure here is one sentence for a human
        detail = str(e).strip().splitlines()[0][:300]
        store.log_run({"what": log_text("key_check_failed"), "who": who, "user_id": user_id,
                       "provider": "gemini", "model": model, "cost_usd": 0,
                       "elapsed_s": round(time.time() - started, 1), "error": detail})
        status, message = explain_key_error(detail, key, model)
        raise HTTPException(status, message)
    m = getattr(resp, "usage_metadata", None)
    tin = int(getattr(m, "prompt_token_count", 0) or 0)
    tout = int(getattr(m, "candidates_token_count", 0) or 0)
    cost = media.cost_usd(model, tin, tout)
    store.spend(user_id, "gemini", cost)
    elapsed = round(time.time() - started, 1)
    store.log_run({"what": log_text("key_check"), "who": who, "user_id": user_id, "provider": "gemini",
                   "model": model, "tokens_in": tin, "tokens_out": tout, "cost_usd": cost,
                   "elapsed_s": elapsed})
    return {"ok": True, "model": model, "switched_from": switched_from, "elapsed_s": elapsed, "cost_usd": cost,
            "funds": store.funds_for(user_id, "gemini")}


# --- Draft with AI ------------------------------------------------------------------------------

def draft(pid: str, who: str, user_id: str, code: str = "") -> dict:
    """Runs on the signed-in person's own key and spends their own balance, never the portal's."""
    p = load(pid)
    if code:
        if not language_name(code):
            raise HTTPException(400, say("unknown_language"))
        p["language"] = code
        fresh = load(pid) | {"language": code}
        if voice_language(fresh.get("voice") or "") != code:
            fresh["voice"] = voice_for(code)          # a Hindi script is read by a Hindi voice, by default
        save(fresh)
    src = source_of(pid)
    mine = store.keys_of(user_id)
    key = _gemini_key(user_id)
    if not key:
        raise HTTPException(400, say("draft_needs_key"))
    model = mine.get("gemini_model") or store.DEFAULT_KEYS["gemini_model"]

    def work(job):
        from google import genai
        from google.genai import types

        started = time.time()
        usage = {"provider": "gemini", "model": model, "tokens_in": 0, "tokens_out": 0,
                 "cost_usd": None, "elapsed_s": 0, "funds": store.funds_for(user_id, "gemini")}
        job["usage"] = usage

        def stage(pct: int, text: str):
            job["progress"], job["stage"] = pct, text
            job["log"].append(text)
            usage["elapsed_s"] = round(time.time() - started, 1)
            job["usage"] = dict(usage)

        client = genai.Client(api_key=key)
        stage(5, log_text("uploading"))
        up = client.files.upload(file=str(src))
        stage(35, log_text("processing"))
        for n in range(int(limit("processing_polls"))):
            if getattr(up.state, "name", str(up.state)) != "PROCESSING":
                break
            job["progress"] = min(int(limit("processing_progress_to")), int(limit("processing_progress_from")) + n)
            time.sleep(limit("processing_poll_s"))
            up = client.files.get(name=up.name)
        if getattr(up.state, "name", str(up.state)) == "FAILED":
            raise RuntimeError(log_text("processing_failed"))
        stage(60, log_text("writing"))
        try:
            resp = client.models.generate_content(
                model=model, contents=[up, build_prompt(p) + learn_line(p.get("notes") or "")],
                config=types.GenerateContentConfig(response_mime_type="application/json"))
        finally:
            try:
                client.files.delete(name=up.name)
            except Exception:  # noqa: BLE001 - the uploaded copy expires on its own within two days
                pass
        m = getattr(resp, "usage_metadata", None)
        usage["tokens_in"] = int(getattr(m, "prompt_token_count", 0) or 0)
        usage["tokens_out"] = int(getattr(m, "candidates_token_count", 0) or 0)
        usage["cost_usd"] = media.cost_usd(model, usage["tokens_in"], usage["tokens_out"])
        store.spend(user_id, "gemini", usage["cost_usd"])
        usage["funds"] = store.funds_for(user_id, "gemini")
        store.log_run({"video": pid, "what": log_text("draft_run", title=p.get("title", "")[:limit("run_title_max")]),
                       "who": who, "user_id": user_id} | usage)
        money = log_text("money_unknown") if usage["cost_usd"] is None else log_text("money", cost=store.money_text(user_id, usage["cost_usd"]))
        stage(95, log_text("cost", money=money, tokens_in=usage["tokens_in"], tokens_out=usage["tokens_out"], model=model))

        segs = parse_draft(getattr(resp, "text", "") or "", p.get("duration") or 0)
        if not segs:
            raise RuntimeError(log_text("no_lines"))
        fresh = load(pid)
        fresh["segments"], fresh["drafted_at"] = segs, store.now()
        save(fresh)
        job["log"].append(log_text("draft_ready", n=len(segs)))

    return start_job(pid, "draft", work)


# --- Generate -----------------------------------------------------------------------------------

def render(pid: str, voice: str, keep_original_audio: bool, who: str, user_id: str) -> dict:
    p = load(pid)
    voice = voice or p.get("voice") or media.voices()["default"]
    if not p.get("segments"):
        raise HTTPException(400, say("script_first"))
    check_voices(p["segments"], voice)
    src, d = source_of(pid), folder(pid)
    keep = bool(keep_original_audio and p.get("has_audio"))
    # 2026-09-20 premium voices: a paid line needs the person's own key, and the page has already shown the estimate
    est = tts_estimate(p["segments"], voice, user_id)
    if est["paid"] and not est["have_key"]:
        raise HTTPException(400, say("draft_needs_key"))
    tk = tts_settings()

    def work(job):
        import edge_tts

        started = time.time()
        segs, total = p["segments"], p.get("duration") or 0
        audio_dir = d / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        overrun_s = limit("overrun_warning_s")
        # 2026-09-18: every line is a SAVED step (core/jobs.py). A failure at line 20, a Stop, or a server
        # restart keeps lines 1-19; pressing Generate again voices only what is missing or changed.
        plan = []
        for i, s in enumerate(segs):
            text, window = media.spoken(s["text"]), media.speech_window(segs, i, total)
            line_voice = s.get("voice") or voice        # a line's own voice wins over the master
            paid = paid_voice(line_voice)
            line_est = tts_line_cost(text) if paid else 0.0
            plan.append({"key": line_key(text, line_voice, window), "label": log_text("step_line", n=i + 1),
                         "text": text, "voice": line_voice, "window": window, "paid": paid, "estimate_usd": line_est})
        manifest = jobs.open_job(render_job_id(pid), user_id, "render",
                                 [{"key": x["key"], "label": x["label"], "estimate_usd": x["estimate_usd"]} for x in plan])
        characters, spent = [0], [0.0]

        def voice_line(i, step):
            x = plan[i]
            clip = audio_dir / f"{x['key']}.mp3"
            cost = 0.0
            if x["paid"]:
                got = speak_paid(user_id, x["text"], x["voice"], clip, x["window"])
                said, faster, cost = got["said"], got["faster"], got["cost_usd"]
                spent[0] += cost
            else:
                asyncio.run(edge_tts.Communicate(x["text"], x["voice"]).save(str(clip)))
                said = media.duration(clip)
                faster = media.speed_up_percent(said, x["window"])
                if faster:
                    asyncio.run(edge_tts.Communicate(x["text"], x["voice"], rate=f"+{faster}%").save(str(clip)))
                    said = media.duration(clip)
            note = ((log_text("line_voice", voice=x["voice"]) if x["voice"] != voice else "")
                    + (log_text("line_faster", faster=faster) if faster else "")
                    + (log_text("line_paid", cost=store.money_text(user_id, cost)) if x["paid"] else ""))
            if said > x["window"] + overrun_s:
                note += log_text("line_overrun", over=said - x["window"])
            job["log"].append(log_text("line_ok", n=i + 1, total=len(segs), said=said, window=x["window"], note=note))
            characters[0] += len(x["text"])
            job["progress"], job["stage"] = int(5 + 80 * (i + 1) / len(segs)), log_text("voicing", n=i + 1, total=len(segs))
            job["usage"] = ({"provider": tk["provider"], "model": tk["model"], "free": False, "characters": characters[0],
                             "cost_usd": round(spent[0], 4), "elapsed_s": round(time.time() - started, 1),
                             "funds": store.funds_for(user_id, tk["provider"])} if est["paid"] else
                            {"provider": "edge-tts", "model": voice, "free": True, "characters": characters[0],
                             "cost_usd": 0.0, "elapsed_s": round(time.time() - started, 1)})
            return {"out": clip, "cost_usd": cost}

        def funds():
            f = store.funds_for(user_id, tk["provider"])
            return {"has_budget": bool(f.get("loaded_usd")), "left_usd": f.get("left_usd")}

        manifest = jobs.run(manifest, voice_line, funds=funds if est["paid"] else None, log=job["log"].append,
                            money=lambda v: store.money_text(user_id, v, 0))
        if spent[0]:
            store.log_run({"video": pid, "what": log_text("tts_run", title=p.get("title", "")[:limit("run_title_max")]), "who": who,
                           "user_id": user_id, "provider": tk["provider"], "model": tk["model"], "cost_usd": round(spent[0], 4),
                           "elapsed_s": round(time.time() - started, 1)})
        if manifest["status"] != "done":
            job["log"].append(manifest["reason"])
            job["stage"] = manifest["reason"]
            return "stopped"
        clips = [Path(s["out"]) for s in manifest["steps"]]
        lengths = [media.duration(c) for c in clips]
        # 2026-09-26: a line's voiced clip is no longer deleted when the line changes - its key is text + voice + timing,
        # so changing a line back reuses it instead of paying again. # ponytail: unused clips stay; prune when disk matters

        spoken = voice_language(voice)
        if spoken != tk["any_language"] and spoken != (p.get("language") or default_language()):
            job["log"].append(log_text("voice_mismatch", voice=voice,
                                       language=language_name(p.get("language") or default_language())
                                       or (p.get("language") or "")))
        job["progress"], job["stage"] = 90, log_text("combining")
        out = d / "narrated.mp4"
        # Never two voices at once. A line that cannot fit its window starts when the one before it
        # has finished — late and clear beats on time and garbled.
        starts = media.stagger([s["start"] for s in segs], lengths)
        late_s = limit("late_warning_s")
        for i, (s_, was) in enumerate(zip(segs, starts)):
            if was - s_["start"] > late_s:
                job["log"].append(log_text("line_late", n=i + 1, late=was - s_["start"]))
        # The picture is copied only when it is a format every player handles for free; a phone's HEVC
        # recording is re-encoded to H.264 (chips media.playback / media.needs_reencode), so nobody is
        # asked to buy a codec to watch what this portal made.
        source_codec = media.video_codec(src)
        job["log"].append(log_text("picture", codec=source_codec or log_text("picture_unknown"),
                                   how=log_text("picture_copied" if media.picture_args(source_codec) == ["-c:v", "copy"]
                                                else "picture_converted")))
        cmd = media.mix_command(src, clips, starts, out, total, keep, source_codec)
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode and "copy" in cmd:   # a codec MP4 cannot hold by copy: re-encode the picture instead
            r = subprocess.run([c if c != "copy" else "libx264" for c in cmd], capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(log_text("ffmpeg_failed",
                                        reason=(r.stderr.strip().splitlines() or [log_text("ffmpeg_unknown")])[-1]))

        (d / "narrated.srt").write_text("\n".join(
            f"{i}\n{media.stamp(s['start'], True)} --> {media.stamp(s['end'], True)}\n{s['text']}\n"
            for i, s in enumerate(segs, 1)), encoding="utf-8")
        chapters = [f"{'00:00' if n == 0 else media.stamp(s['start'], False)} {s['chapter']}"
                    for n, s in enumerate(x for x in segs if x.get("chapter"))]
        (d / "description.txt").write_text(p.get("title", "") + "\n\n" + "\n".join(chapters) + "\n", encoding="utf-8")

        fresh = load(pid)
        fresh["voice"], fresh["rendered_at"] = voice, store.now()
        save(fresh)
        store.log_run({"video": pid, "what": log_text("render_run", title=p.get("title", "")[:limit("run_title_max")]), "who": who,
                       "user_id": user_id, "provider": "edge-tts", "model": voice, "free": True, "characters": characters[0],
                       "cost_usd": 0.0, "elapsed_s": round(time.time() - started, 1)})
        stamp_bytes(pid)         # the narrated copy is new disk: count it the moment it exists
        job["log"].append(log_text("done"))

    return start_job(pid, "render", work)


def partial(pid: str) -> dict:
    """Play what is ready: the lines voiced so far, over the video up to where the last of them ends.
    Free (this server's ffmpeg). 2026-09-18 owner: "whatever has been generated can be played till that
    point, and the person is told how far it got"."""
    p = load(pid)
    m = jobs.load(render_job_id(pid))
    n = jobs.ready(m) if m else 0
    segs = p.get("segments") or []
    if not n:
        raise HTTPException(400, log_text("nothing_ready"))
    clips = [Path(s["out"]) for s in m["steps"][:n]]
    lengths = [media.duration(c) for c in clips]
    starts = media.stagger([s["start"] for s in segs[:n]], lengths)
    heard = max(st + ln for st, ln in zip(starts, lengths)) + float(engine.setting("narrator.fit", "tail_seconds"))
    until = min(float(p.get("duration") or 0), heard) if p.get("duration") else heard
    src, out = source_of(pid), folder(pid) / "partial.mp4"
    codec = media.video_codec(src)
    r = subprocess.run(media.mix_command(src, clips, starts, out, until, False, codec),
                       capture_output=True, text=True)
    if r.returncode:
        raise HTTPException(500, log_text("ffmpeg_failed", reason=(r.stderr.strip().splitlines() or ["?"])[-1]))
    return {"lines": n, "total": len(segs), "seconds": round(until, 1),
            "said": log_text("partial_ready", n=n, total=len(segs), seconds=until)}


def outputs() -> dict:
    """The files a narrated video has (chip narrator.settings outputs): name -> file, type, download-name tail."""
    return limit("outputs")


if __name__ == "__main__":  # ponytail: one runnable self-check
    # 2026-10-01 owner: a premium voice is asked for the region's accent on every line (chip voice.regions)
    assert region_line("Hello", "") == "Hello" and region_line("Hello", "nowhere") == "Hello", "no region = the line as it is"
    assert "Hello" in region_line("Hello", "india") and region_line("Hello", "india") != "Hello", "a region asks for its accent"
    # 2026-09-30: Gemini TTS returned NO SOUND for a line - speak_paid asks again one sentence at a time and joins the sound
    import providers as _pv
    import tempfile as _tf0
    _calls, _saved = [], (_pv.call_with_keys, globals()["gemini_speak"], globals()["pcm_to_mp3"], media.duration, store.spend)

    def _fake_speak(key, model, line, name):
        _calls.append(line)
        if ". " in line:
            raise RuntimeError(say("tts_nothing_back"))
        return b"\0\0" * 10, 1, 1
    _pv.call_with_keys = lambda uid, prov, call: (call("k"), "k")
    globals()["gemini_speak"], globals()["pcm_to_mp3"] = _fake_speak, (lambda pcm, sr, out, faster=0: out.write_bytes(pcm))
    media.duration, store.spend = (lambda _p: 1.0), (lambda *a_, **k_: None)
    try:
        _o = Path(_tf0.mkdtemp()) / "l.mp3"
        speak_paid("u1", "Venus rises. Mars sets.", "gemini:Charon", _o)
        assert _calls == ["Venus rises. Mars sets.", "Venus rises.", "Mars sets."] and _o.stat().st_size == 40, (_calls, _o.stat().st_size)
    finally:
        _pv.call_with_keys, globals()["gemini_speak"], globals()["pcm_to_mp3"], media.duration, store.spend = _saved
    # 2026-09-28 owner "Download Script - all the narration": every line, in time order, chapters as headings
    _p = {"segments": [{"start": 9, "text": "Save it.", "chapter": ""}, {"start": 0, "text": "Open Setup.", "chapter": "Start"},
                       {"start": 4, "text": "Add a project.", "chapter": ""}, {"start": 12, "text": "Record.", "chapter": "Record"}]}
    assert script_text(_p) == "Start\n\nOpen Setup. Add a project. Save it.\n\nRecord\n\nRecord.", script_text(_p)
    assert script_text(_p, True).splitlines()[2] == "[00:00] Open Setup." and "[00:09] Save it." in script_text(_p, True)
    aq = "AQ." + "x" * 50                                  # the current AI Studio key format
    st, msg = explain_key_error("404 NOT_FOUND. Requested entity was not found.", aq, "gemini-2.5-flash")
    assert "cannot use" not in msg and "Requested entity was not found" in msg, "not found alone is not the model's fault"
    assert "AIza" not in msg and "not a Gemini" not in msg, "an AQ. key is a real Gemini key: never judge the format"
    st, msg = explain_key_error("404 NOT_FOUND. models/gemini-9 is not found for API version v1beta", aq, "gemini-9")
    assert "cannot use" in msg and "models/gemini-9" in msg, "a real missing model is still named, with Google's words"
    assert explain_key_error("Connection reset", "AIza" + "x" * 35, "m")[0] == 502
    segs = parse_draft('```json\n{"segments":[{"start":0,"end":5,"text":"One"},{"start":4,"end":9,"text":"Two"}]}\n```', 10)
    assert [s["start"] for s in segs] == [0, 4] and segs[0]["end"] == 4, "overlap clipped, not rejected"
    assert parse_draft('{"segments":[{"start":0,"end":0,"text":"x"}]}', 10) == [], "zero-length line dropped"
    try:
        clean_segments([{"start": 0, "end": 5, "text": "a"}, {"start": 2, "end": 6, "text": "b"}], 10)
        raise AssertionError("overlap must be refused on save")
    except HTTPException as e:
        assert "overlaps" in e.detail
    # 2026-09-17: "could not reach Google" with nothing else said left the admin guessing between
    # DNS, a proxy and a TLS-interception certificate. The library's sentence must ride along.
    # 2026-09-17: Gemini answered in MINUTES (0 … 0.32 for a 54-second recording). Every window was
    # a few hundredths of a second, the lines were voiced on top of each other, and the MP4 was a
    # garble. A draft whose words cannot fit the span it claims is stretched onto the real video.
    minutes = ('{"segments":[{"start":0,"end":0.03,"text":"To sign in, first enter your username in '
               'the Username field, then type your password."},'
               '{"start":0.29,"end":0.32,"text":"Click the Sign In button to proceed."}]}')
    out = parse_draft(minutes, 54)
    assert out[-1]["end"] > 40, "a timeline in minutes must be stretched, not voiced on top of itself"
    assert out[0]["end"] > 1, "the first line needs a window it can actually speak in"
    # 2026-09-17: a hosted portal pays for disk. Usage is a sum of stored numbers, and retention
    # takes the raw upload once its narrated copy is old enough - never the narrated copy itself.
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        keep = DATA
        globals()["DATA"] = Path(tmp)                       # a data root nobody else is using
        d = Path(tmp) / "aaaaaaaaaaaa"
        d.mkdir()
        (d / "source.mp4").write_bytes(b"x" * 5000)
        (d / "project.json").write_text(json.dumps({"id": "aaaaaaaaaaaa", "owner_id": "u1"}), encoding="utf-8")
        assert used_bytes(lambda p: p.get("owner_id") == "u1") > 5000, "an unmeasured project still counts"
        assert used_bytes(lambda p: p.get("owner_id") == "u2") == 0, "one account never counts another's"
        assert stamp_bytes("aaaaaaaaaaaa") >= 5000, "a measured project remembers its size"
        assert sweep_sources(0) == 0, "0 days keeps every recording for ever"
        assert sweep_sources(1) == 0, "a project with no narrated copy keeps its recording"
        (d / "narrated.mp4").write_bytes(b"y" * 800)
        os.utime(d / "narrated.mp4", (time.time() - 3 * 86400, time.time() - 3 * 86400))
        assert sweep_sources(1) == 5000, "the recording goes once its narrated copy is old enough"
        assert (d / "narrated.mp4").exists() and not has_source("aaaaaaaaaaaa"),             "retention takes the upload, never the narrated video"
        # 2026-09-29 owner: "use the video's own thumbnail as its cover" - a frame of the narrated video, else the recording
        import subprocess
        def _clip(to_, colour_):
            subprocess.run([media.ffmpeg(), "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c={colour_}:s=64x48:d=1", str(to_)], check=True)
        assert cover_path("aaaaaaaaaaaa") is None, "no readable video: the drawn cover"
        (d / "narrated.mp4").unlink()
        _clip(d / "source.mp4", "red")
        cv_ = cover_path("aaaaaaaaaaaa")
        assert cv_ and cv_.name == "cover.png" and cv_.is_file(), "the recording gives the cover"
        _clip(d / "narrated.mp4", "blue")
        os.utime(d / "narrated.mp4", (time.time() + 5, time.time() + 5))
        from PIL import Image as _Im
        assert _Im.open(cover_path("aaaaaaaaaaaa")).convert("RGB").getpixel((5, 5))[2] > 200, "the narrated video wins, and a newer one remakes it"
        # 2026-09-28 "tens of thousands": a person's recordings come through the owner index, never every folder
        for pid_, who_ in (("bbbbbbbbbbbb", "u2"), ("cccccccccccc", "")):
            (Path(tmp) / pid_).mkdir()
            (Path(tmp) / pid_ / "project.json").write_text(json.dumps({"id": pid_, "owner_id": who_}), encoding="utf-8")
        assert [x["id"] for x in listing(user={"id": "u1"})] == ["aaaaaaaaaaaa"], "a folder written without save() still counts"
        assert [x["id"] for x in listing(user={"id": "u9", "role": "owner"})] == ["cccccccccccc"], "an ownerless one is the owner's"
        assert owners() == {"aaaaaaaaaaaa": "u1", "bbbbbbbbbbbb": "u2", "cccccccccccc": ""}
        opened = []
        real_read = globals()["_read"]
        globals()["_read"] = lambda pj: opened.append(pj.parent.name) or real_read(pj)
        listing(user={"id": "u2"})
        globals()["_read"] = real_read
        assert opened == ["bbbbbbbbbbbb"], ("only this person's folder is opened", opened)
        shutil.rmtree(Path(tmp) / "bbbbbbbbbbbb")
        assert "bbbbbbbbbbbb" not in owners(), "a folder gone leaves the index"
        globals()["DATA"] = keep
    net = explain_key_error("SSL: CERTIFICATE_VERIFY_FAILED", "AIza" + "x" * 35, "m")[1]
    assert "Your key is saved" in net and "CERTIFICATE_VERIFY_FAILED" in net, "network failure hides its cause again"
    # 2026-09-17 owner: every sentence, limit and pattern is a chip. A literal creeping back fails here.
    me = Path(__file__).read_text(encoding="utf-8")
    assert not re.search(r"HTTPException\(\d+,\s*f?[\"']", me), "a refusal sentence is back in Python: narrator.messages"
    assert "VIDEO" + "_EXT =" not in me and "PROMPT" + " = " not in me, "file types / prompt belong in chips"
    assert ".mkv" in video_ext() and "{duration:.1f}" in engine.setting("narrator.prompt", "template")
    assert "0 to 12.0 seconds" in build_prompt({"duration": 12, "title": "T"}), "the prompt fills its duration"
    assert learn_line("  ").endswith("how to use this screen")
    # 2026-09-18 Auto-fit: every line gets the time its own words need, and the set fits the recording.
    rough = [{"start": 0, "end": 5, "text": "one two three four five six seven eight nine ten eleven twelve"},
             {"start": 5, "end": 8, "text": "a short line"}]
    fitted = fit_times(rough, 30)
    assert fitted[0]["start"] == 0 and fitted[-1]["end"] <= 30, fitted
    assert fitted[0]["end"] - fitted[0]["start"] > fitted[1]["end"] - fitted[1]["start"], (
        "more words must get more time")
    assert all(b["start"] >= a["end"] for a, b in zip(fitted, fitted[1:])), "fitted lines never overlap"
    squeezed = fit_times(rough, 6)
    assert squeezed[-1]["end"] <= 6, "a long script is squeezed into the recording, never past its end"
    assert [s["text"] for s in squeezed] == [s["text"] for s in rough], "Auto-fit touches the clock, not the words"
    assert fit_times([], 30) == []
    # 2026-09-18: a translated script must be READ in its language, not by an English mouth
    assert voice_language("te-IN-ShrutiNeural") == "te" and voice_language("en-IN-NeerjaNeural") == "en"
    for row in languages():
        got = voice_for(row["code"])
        assert voice_language(got) == row["code"], (row["code"], got, "every language needs a voice that speaks it")
    # the languages are a chip; nothing in Python names one
    assert language_name("te") and not language_name("zz"), "only the offered languages are accepted"
    assert language_line(default_language()) == "", "the default language needs no sentence in the prompt"
    assert language_name("hi") in language_line("hi"), "another language is asked for by name"
    assert len(languages()) >= 12, "the portal offers a dozen languages"
    est = draft_estimate(100, "nobody")
    assert (est["tokens_in"], est["tokens_out"], est["seconds"]) == (int(100 * media.VIDEO_TOKENS_PER_SECOND) + 1500, 1200, 80)
    print("narrator self-check OK")
