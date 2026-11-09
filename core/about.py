"""About us - who we are, and which build this server runs (2026-11-09 owner: "It is becoming extremely difficult to know if
user is working on the latest version/build").

The profile menu's About us (core/static/about.js) reads GET /api/about/build: the page-code build every answer already names
(X-Portal-Build, core/__init__.py BUILD), plus the git commit, its date and when it was checked out here (the deploy). All of it is
read from this server's own checkout when it starts, never typed in, so a stale server or an old open tab shows itself.
The words and the logo are chip ui.about (an astrology portal overrides it with the AstroGravity block)."""
from __future__ import annotations

import datetime as dt
import functools
import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends

from core.auth import signed_in

ROOT = Path(__file__).resolve().parent.parent
router = APIRouter()


@functools.lru_cache(maxsize=1)
def commit() -> dict:
    """{commit, commit_date, deployed_at} of this checkout, read once (a deploy restarts the server). None where unknown."""
    out = {"commit": None, "commit_date": None, "deployed_at": None}
    try:   # safe.directory: on the VPS the checkout may belong to another user than the service
        got = subprocess.run(["git", "-c", "safe.directory=*", "-C", str(ROOT), "log", "-1", "--format=%h|%cI"],
                             capture_output=True, text=True, timeout=10)
        if got.returncode == 0 and "|" in got.stdout:
            out["commit"], out["commit_date"] = got.stdout.strip().split("|", 1)
        top = subprocess.run(["git", "-c", "safe.directory=*", "-C", str(ROOT), "rev-parse", "--git-dir"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        moved = (ROOT / top / "logs" / "HEAD") if top else None   # written by every pull / checkout = the deploy time
        if moved and moved.is_file():
            out["deployed_at"] = dt.datetime.fromtimestamp(moved.stat().st_mtime, dt.timezone.utc).isoformat(timespec="seconds")
    except (OSError, subprocess.SubprocessError):
        pass   # no git here (a copied folder): About us says the commit is not known
    return out


STARTED = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


@router.get("/api/about/build")
def api_build(_user=Depends(signed_in)):   # signed in: the menu that opens it is; a commit is not for strangers
    from core import BUILD  # noqa: PLC0415 - set by install()
    return {"build": BUILD, **commit(), "started_at": STARTED}


def check() -> list[str]:
    """What a portal without About us lacks (selfcheck runs `python -m core.about`; ui_audit opens it at three sizes)."""
    import json  # noqa: PLC0415
    import re  # noqa: PLC0415
    bad = []
    sh = (ROOT / "core/static/shell.js").read_text(encoding="utf-8")
    if not re.search(r'id="about-us">[^\n]*\n[ \t]*<button type="button" id="signout">', sh):
        bad.append("shell.js: About us is not the line just above Sign out in the profile menu")
    if "#about-us').onclick" not in sh or "'about'" not in sh:
        bad.append("shell.js: About us is not wired (click, words 'about' at boot)")
    if "about," not in (ROOT / "core/__init__.py").read_text(encoding="utf-8"):
        bad.append("core/__init__.py: the about router is not installed")
    own = ROOT / "chips/ui.about.json"
    chip = json.loads((own if own.exists() else ROOT / "core/chips/ui.about.json").read_text(encoding="utf-8"))
    w = {p["name"]: p["default"] for p in chip["params"]}
    for k in ("menu", "headline", "body", "logo", "build_title", "newer"):
        if not str(w.get(k, "")).strip():
            bad.append(f"chip ui.about: '{k}' is empty")
    if not (ROOT / str(w.get("logo", "")).replace("core-static/", "core/static/")).is_file():
        bad.append(f"chip ui.about: logo {w.get('logo')} is not a file")
    if (ROOT / ".git").exists() and not commit()["commit"]:
        bad.append("a git checkout, but the commit could not be read (About us would say 'not known')")
    return bad


if __name__ == "__main__":
    problems = check()
    assert not problems, "About us: " + "; ".join(problems)
    print("about: About us above Sign out, who we are, live build", commit())
