"""Tour Video (2026-10-02 owner: "Tour Video card we have in the studio - bring that to sm, visible to portal
admin"). A narrated MP4 of each screen, recorded from its tour script by the studio's own runner (tools/tour_video/
make_tour.py, skill module-tour-video): Check steps walks it silently, Record makes MP4 + subtitles + chapters, Sign in
opens a window on this computer once. Where things are, which Python records, and the words: chips tourvideo.settings,
tourvideo.state (none / stale / ready), list.tour_videos, ui.tourvideo. Glue only: one job at a time, its log kept.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

from fastapi import HTTPException

from core import auth, engine, events, guide, lists, store

ROOT = Path(__file__).resolve().parent          # SimplyFile: everything lives in this folder
_JOB: dict = {}
_LOCK = threading.Lock()


def settings() -> dict:
    return engine.run("tourvideo.settings")


def python() -> str:
    """The first Python in the chip's list that is here (2026-11-14: the server has no `python`, only its recorder venv)."""
    for c in settings()["python"]:
        if (ROOT / c).is_file():
            return str(ROOT / c)
        if shutil.which(c):
            return c
    return settings()["python"][-1]


def ensure_recorder() -> str:
    """deploy.sh: the server's recorder Python (the chip's first candidate): made with the chip's install line, then
    brought to the recorder's requirements on every deploy with its update line (pip: seconds when nothing changed)."""
    first = ROOT / settings()["python"][0]
    made = first.is_file()          # 2026-11-14: made once but never updated - edge-tts 7.2.8 then got 403 from the voice service
    subprocess.run(settings()["update" if made else "install"], shell=True, cwd=ROOT, check=True)   # noqa: S602 - the chip's own line
    return "tour recorder: " + ("updated" if made else "installed")


def session_file(u: dict, base: str, name: str) -> tuple[Path, str]:
    """Record signed in as the person who pressed Record: a short session of theirs, as the recorder's auth file
    (TOUR_AUTH). No password is kept anywhere; the session ends when the run does (chip session_minutes)."""
    from urllib.parse import urlparse  # noqa: PLC0415
    ttl = int(settings()["session_minutes"]) * 60
    token = store.start_session(u, ttl)
    host, secure = urlparse(base).hostname or "", base.startswith("https://")
    jar = [{"name": n, "value": v, "domain": host, "path": auth.BASE or "/", "expires": time.time() + ttl,
            "httpOnly": True, "secure": secure, "sameSite": "Lax"} for n, v in ((auth.COOKIE, token), (getattr(auth, "KNOWN", ""), "1")) if n]
    f = ROOT / settings()["out_dir"] / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"cookies": jar, "origins": []}), encoding="utf-8")
    return f, token


def say(key: str, **values) -> str:
    return engine.run("ui.tourvideo")[key].format(**values)


def _tours() -> dict[str, Path]:
    k = settings()
    return {p.stem: p for p in sorted((ROOT / k["tours_dir"]).glob(k["tours_glob"]))}


def out_dir(key: str) -> Path:
    return ROOT / settings()["out_dir"] / key


def file_of(key: str, fid: str) -> tuple[Path, str]:
    if key not in _tours():
        raise HTTPException(404, say("empty"))
    f = next((x for x in settings()["files"] if x["id"] == fid), None)
    p = out_dir(key) / f["name"].format(key=key) if f else None
    if not p or not p.is_file():
        raise HTTPException(404, say("no_video"))
    return p, f["type"]


def row(key: str, path: Path) -> dict:
    t = json.loads(path.read_text(encoding="utf-8"))
    screen = t.get("start_url", "").split("/")[-1].split("?")[0]
    # Guide me changing makes the video stale too - wherever that chip lives (core/chips, this portal's chips, an import in
    # the data layer; "connect-ai" plays guide.connect_ai). 2026-11-18 week class 41: this read only <ROOT>/chips/guide.<screen>
    # - a core-held or hyphenated screen's guide never made its video stale (SteadyMove G-53, the same miss across repos)
    script_at = max([path.stat().st_mtime] + [f.stat().st_mtime for f in engine.files_of(guide.chip_of(screen))])
    mp4 = out_dir(key) / f"{key}.mp4"
    video_at = mp4.stat().st_mtime if mp4.is_file() else 0
    return {"id": key, "key": key, "title": t.get("title") or key, "steps": len(t.get("steps") or []), "screen": screen,
            "script_at": round(script_at), "video_at": round(video_at),
            "state": engine.run("tourvideo.state", {"video_at": video_at, "script_at": script_at})}


lists.source("tour_videos", lambda user, args: [row(k, p) for k, p in _tours().items()], screen="tourvideo")


def job() -> dict:
    return dict(_JOB) or {"status": "idle", "log": []}


def _tell() -> None:
    """2026-11-11 A20: the run's state goes down the push stream to whoever started it - the page never polls."""
    events.to_person(_JOB.get("uid", ""), "job", {"url": "/api/tourvideo/job", "job": job()})


def start(what: str, key: str, base: str, uid: str = "", u: dict | None = None) -> dict:
    """what = check | record | login. One at a time; the runner's own lines are the log."""
    k, tours = settings(), _tours()
    if what != "login" and key not in tours:
        raise HTTPException(404, say("empty"))
    with _LOCK:
        if _JOB.get("status") == "running":
            raise HTTPException(409, say("busy"))
        base = (auth.settings().get("portal_url") or "").strip().rstrip("/") or base
        if auth.BASE and not base.endswith(auth.BASE):     # a portal under a path (demo copies: /vui, /healthyfy) - its pages live there
            base += auth.BASE
        args = [python(), str(ROOT / k["runner"])] + (["--login"] if what == "login" else [str(tours[key])]) + \
               (["--check"] if what == "check" else []) + ["--base", base]
        title = row(key, tours[key])["title"] if key in tours else ""
        _JOB.clear()
        _JOB.update({"status": "running", "what": what, "key": key, "log": [], "started_ms": int(time.time() * 1000),
                     "activity": say(f"working_{what}", title=title), "uid": uid})
        env, token, jar = dict(os.environ), "", None
        if u and what != "login":                         # login stays for a computer with a screen
            jar, token = session_file(u, base, f".auth-{_JOB['started_ms']}.json")
            env["TOUR_AUTH"] = str(jar)
    threading.Thread(target=_run, args=(args, int(k["log_keep"]), env, token, jar), daemon=True).start()
    return job()


def _run(args: list[str], keep: int, env: dict | None = None, token: str = "", jar: Path | None = None) -> None:
    try:
        _record(args, keep, env)
    finally:                                              # the recorder's session never outlives its run
        if token:
            store.end_session(token)
        if jar:
            jar.unlink(missing_ok=True)


def _record(args: list[str], keep: int, env: dict | None) -> None:
    try:
        p = subprocess.Popen(args, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    except OSError as e:                                  # no such Python: say what to install
        _JOB.update({"status": "failed", "log": [str(e), say("needs", install=settings()["install"])]})
        _tell()
        return
    for line in p.stdout:
        _JOB["log"] = (_JOB["log"] + [line.rstrip()])[-keep:]
        _tell()
    code = p.wait()
    if code and any("No module named" in x for x in _JOB["log"]):
        _JOB["log"].append(say("needs", install=settings()["install"]))
    _JOB["status"] = "finished" if code == 0 else "failed"
    _tell()


if __name__ == "__main__":  # ponytail: the list reads every tour; a bad key and a missing video are refused
    import store  # noqa: F401 - loads the portal chips
    try:                                                # 2026-10-02: the list sits behind its screen (lists.source screen=)
        lists.page("tour_videos", {"id": "x", "role": "member"}, {})
        raise AssertionError("someone without Tour Video read its list")
    except HTTPException as e:
        assert e.status_code == 403, e
    rs = [row(k, p) for k, p in _tours().items()]     # the rows the list pages (no portal catalog in this self-check)
    # 2026-11-18 week class 41 (SteadyMove G-53): the guide a tour plays lives in whichever chips folder holds it - another
    # repo's / layer's folder and a hyphenated screen (zz-wk41 -> guide.zz_wk41) still make its video stale
    import tempfile  # noqa: PLC0415
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as _d:
        _other = Path(_d) / "chips"
        _other.mkdir()
        (_other / "guide.zz_wk41.json").write_text(json.dumps({"chip_id": "guide.zz_wk41", "kind": "accessor", "params": [],
                                                               "expr": {"vop": "record", "fields": {}}}), encoding="utf-8")
        _tour = Path(_d) / "st-zz-wk41.json"
        _tour.write_text(json.dumps({"start_url": "/#/zz-wk41", "steps": [{"say": "x"}]}), encoding="utf-8")
        os.utime(_tour, (1_000_000_000, 1_000_000_000))
        engine.register_dir(_other)
        try:
            assert row("zz-wk41", _tour)["script_at"] > 1_000_000_000, "a tour's Guide me in another chips folder (or a hyphenated screen) never makes its video stale - read the guide through engine.files_of(guide.chip_of(screen))"
        finally:
            engine.DIRS.remove(_other.resolve())
            engine.refresh()
    assert rs and all(r["state"] in ("none", "stale", "ready") and r["steps"] for r in rs), rs[:2]
    for bad in (lambda: file_of("../app", "mp4"), lambda: file_of(rs[0]["key"], "nope"), lambda: start("check", "../x", "http://x")):
        try:
            bad()
            raise SystemExit("a bad key or file was accepted")
        except HTTPException as e:
            assert e.status_code == 404
    assert python() and isinstance(settings()["python"], list), "tourvideo.settings python is a list of candidates"
    assert settings()["python"][0].startswith(".venv/"), "the server recorder lives under .venv/ - code scanners skip it (2026-11-14: .tourvenv failed 3 deploys)"
    assert not any(".venv/tour/bin/pip " in settings()[k] for k in ("install", "update")),         "call pip as python -m pip: a release folder's venv pip names a release that is gone (2026-11-16 sf deploy, exit 127)"
    _mine = lambda: sum(1 for x in store.read("sessions", []) if x.get("user_id") == "tv-selftest")  # noqa: E731
    _before = _mine()
    _f, _t = session_file({"id": "tv-selftest"}, "https://tv.example", ".auth-selftest.json")   # 2026-11-14
    _c = json.loads(_f.read_text(encoding="utf-8"))["cookies"]
    assert {c["name"] for c in _c} == {auth.COOKIE, getattr(auth, "KNOWN", auth.COOKIE)} and _c[0]["domain"] == "tv.example" and _c[0]["secure"], _c
    _run(["no-such-python-tv"], 5, None, _t, _f)       # even a run that cannot start ends its session + file
    assert not _f.exists() and _mine() == _before, "the recorder session outlived its run"
    import importlib.util  # noqa: PLC0415 - 2026-10-16: the recorder's email mask works before paint, in a real browser
    _spec = importlib.util.spec_from_file_location("make_tour", Path(__file__).resolve().parent / "tools" / "tour_video" / "make_tour.py")
    _mt = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mt)
    _bad = _mt.mask_probe()
    _no_browser = any(x.startswith("playwright is not installed") for x in _bad)   # a server that never records: said, not failed
    assert _no_browser or not _bad, "the Tour Video email mask lets a real address be painted: " + "; ".join(_bad)
    print("tourvideo self-check OK", len(rs), "tours,", "email mask NOT checked here (no Playwright - nothing can record here either)"
          if _no_browser else "email mask before paint")
