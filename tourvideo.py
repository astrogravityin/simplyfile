"""Tour Video (2026-10-02 owner: "Tour Video card we have in the studio - bring that to sm, visible to portal
admin"). A narrated MP4 of each screen, recorded from its tour script by the studio's own runner (tools/tour_video/
make_tour.py, skill module-tour-video): Check steps walks it silently, Record makes MP4 + subtitles + chapters, Sign in
opens a window on this computer once. Where things are, which Python records, and the words: chips tourvideo.settings,
tourvideo.state (none / stale / ready), list.tour_videos, ui.tourvideo. Glue only: one job at a time, its log kept.
"""
from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path

from fastapi import HTTPException

from core import engine, lists

ROOT = Path(__file__).resolve().parent          # SimplyFile: everything lives in this folder
_JOB: dict = {}
_LOCK = threading.Lock()


def settings() -> dict:
    return engine.run("tourvideo.settings")


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
    guide = ROOT / "chips" / f"guide.{screen}.json"           # Guide me changing makes the video stale too
    script_at = max(path.stat().st_mtime, guide.stat().st_mtime if guide.is_file() else 0)
    mp4 = out_dir(key) / f"{key}.mp4"
    video_at = mp4.stat().st_mtime if mp4.is_file() else 0
    return {"id": key, "key": key, "title": t.get("title") or key, "steps": len(t.get("steps") or []), "screen": screen,
            "script_at": round(script_at), "video_at": round(video_at),
            "state": engine.run("tourvideo.state", {"video_at": video_at, "script_at": script_at})}


lists.source("tour_videos", lambda user, args: [row(k, p) for k, p in _tours().items()], screen="tourvideo")


def job() -> dict:
    return dict(_JOB) or {"status": "idle", "log": []}


def start(what: str, key: str, base: str) -> dict:
    """what = check | record | login. One at a time; the runner's own lines are the log."""
    k, tours = settings(), _tours()
    if what != "login" and key not in tours:
        raise HTTPException(404, say("empty"))
    with _LOCK:
        if _JOB.get("status") == "running":
            raise HTTPException(409, say("busy"))
        args = [k["python"], str(ROOT / k["runner"])] + (["--login"] if what == "login" else [str(tours[key])]) + \
               (["--check"] if what == "check" else []) + ["--base", base]
        title = row(key, tours[key])["title"] if key in tours else ""
        _JOB.clear()
        _JOB.update({"status": "running", "what": what, "key": key, "log": [], "started_ms": int(time.time() * 1000),
                     "activity": say(f"working_{what}", title=title)})
    threading.Thread(target=_run, args=(args, int(k["log_keep"])), daemon=True).start()
    return job()


def _run(args: list[str], keep: int) -> None:
    try:
        p = subprocess.Popen(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    except OSError as e:                                  # no such Python: say what to install
        _JOB.update({"status": "failed", "log": [str(e), say("needs", install=settings()["install"])]})
        return
    for line in p.stdout:
        _JOB["log"] = (_JOB["log"] + [line.rstrip()])[-keep:]
    code = p.wait()
    if code and any("No module named" in x for x in _JOB["log"]):
        _JOB["log"].append(say("needs", install=settings()["install"]))
    _JOB["status"] = "finished" if code == 0 else "failed"


if __name__ == "__main__":  # ponytail: the list reads every tour; a bad key and a missing video are refused
    import store  # noqa: F401 - loads the portal chips
    try:                                                # 2026-10-02: the list sits behind its screen (lists.source screen=)
        lists.page("tour_videos", {"id": "x", "role": "member"}, {})
        raise AssertionError("someone without Tour Video read its list")
    except HTTPException as e:
        assert e.status_code == 403, e
    rs = [row(k, p) for k, p in _tours().items()]     # the rows the list pages (no portal catalog in this self-check)
    assert rs and all(r["state"] in ("none", "stale", "ready") and r["steps"] for r in rs), rs[:2]
    for bad in (lambda: file_of("../app", "mp4"), lambda: file_of(rs[0]["key"], "nope"), lambda: start("check", "../x", "http://x")):
        try:
            bad()
            raise SystemExit("a bad key or file was accepted")
        except HTTPException as e:
            assert e.status_code == 404
    import importlib.util  # noqa: PLC0415 - 2026-10-16: the recorder's email mask works before paint, in a real browser
    _spec = importlib.util.spec_from_file_location("make_tour", Path(__file__).resolve().parent / "tools" / "tour_video" / "make_tour.py")
    _mt = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mt)
    _bad = _mt.mask_probe()
    _no_browser = any(x.startswith("playwright is not installed") for x in _bad)   # a server that never records: said, not failed
    assert _no_browser or not _bad, "the Tour Video email mask lets a real address be painted: " + "; ".join(_bad)
    print("tourvideo self-check OK", len(rs), "tours,", "email mask NOT checked here (no Playwright - nothing can record here either)"
          if _no_browser else "email mask before paint")
