"""Where a project's code lives: a folder on this machine, or a Git repository the portal clones.

Scanning only ever READS. A local project is read where it sits and never written to. A Git project
is cloned shallow into `data/sources/<project id>/` and pulled on later scans — your working copy is
never touched either way.

What a Git address and a branch may look like are the chips `source.git_url_ok` / `source.branch_ok`
(their test cases pin the shell-character refusals); depth, timeout, token and scrub rules are
`source.settings`; every sentence is `source.messages`. Python runs git.

ponytail: shelling out to `git` beats a Python Git library here — the binary is already on every
machine that has a checkout, and a shallow clone is two commands.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import store
from core import engine

engine.register_dir(Path(__file__).resolve().parent / "chips")

SOURCES = store.DATA / "sources"      # where clones live (infrastructure, not a decision)


def _cfg() -> dict:
    return engine.run("source.settings")


def _say(key: str, **values) -> str:
    return engine.say("source.messages", key, **values)


def git_url_ok(url: str) -> bool:
    """Deliberately strict: the address is handed to a subprocess, and a project address has no business
    containing spaces, quotes or shell characters. The WHOLE text must fit (a trailing newline does not)."""
    return engine.run("source.git_url_ok", {"url": url}) is True


def branch_ok(branch: str) -> bool:
    return engine.run("source.branch_ok", {"branch": branch}) is True


def is_windows_path(raw: str) -> bool:
    """A drive letter: "D:\\Work" or "C:/Users/me". Typed by someone thinking of their own laptop."""
    return re.search(_cfg()["windows_path_pattern"], raw or "") is not None


def have_git() -> bool:
    return bool(shutil.which("git"))


def _run(args: list[str], cwd: Path | None = None, cfg: dict | None = None) -> str:
    cfg = cfg or _cfg()
    r = subprocess.run(["git", *args], cwd=str(cwd) if cwd else None, capture_output=True,
                       text=True, timeout=cfg["timeout_seconds"])
    if r.returncode:
        last = (r.stderr or r.stdout or _say("git_failed_blank")).strip().splitlines()[-1]
        raise ValueError(_say("git_failed", command=args[0], error=_scrub(last, cfg)))
    return r.stdout.strip()


def _scrub(text: str, cfg: dict | None = None) -> str:
    """A failing git command likes to echo the URL back, token and all. Not into a browser it doesn't."""
    cfg = cfg or _cfg()
    return re.sub(cfg["scrub_pattern"], cfg["scrub_replacement"], text)


def _authed(url: str, token: str, cfg: dict | None = None) -> str:
    """A token is carried on the command line for that one fetch and never written to the remote."""
    cfg = cfg or _cfg()
    if token and url.startswith("https://"):
        return "https://" + cfg["token_user"] + ":" + token + "@" + url[len("https://"):]
    return url


def path_of(project: dict) -> Path:
    """Where this project's files are right now, without fetching anything."""
    if (project.get("source_kind") or "local") == "git":
        return SOURCES / project["id"]
    return Path(project.get("folder") or "").expanduser()


def sync(project: dict) -> dict:
    """Bring the project's files up to date and say where they are. Local projects: nothing to do."""
    kind = project.get("source_kind") or "local"
    if kind != "git":
        raw = (project.get("folder") or "").strip()
        folder = Path(raw).expanduser()
        if not folder.is_dir():
            raise ValueError(missing_folder_message(raw))
        return {"path": folder, "kind": "local", "note": ""}

    cfg = _cfg()
    url = (project.get("git_url") or "").strip()
    branch = (project.get("git_branch") or "").strip()
    if not git_url_ok(url):
        raise ValueError(_say("bad_git_url"))
    if branch and not branch_ok(branch):
        raise ValueError(_say("bad_branch"))
    if not have_git():
        raise ValueError(_say("no_git"))

    dest = SOURCES / project["id"]
    token = (project.get("git_token") or "").strip()
    fetch_url = _authed(url, token, cfg)
    depth, remote = str(cfg["clone_depth"]), cfg["remote"]
    try:
        if (dest / ".git").is_dir():
            _run(["remote", "set-url", remote, fetch_url], dest, cfg)
            _run(["fetch", "--depth", depth, remote, *([branch] if branch else [])], dest, cfg)
            _run(["reset", "--hard", f"{remote}/{branch}" if branch else "FETCH_HEAD"], dest, cfg)
            note = _say("pulled")
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.rmtree(dest, ignore_errors=True)
            _run(["clone", "--depth", depth, *(["--branch", branch] if branch else []), fetch_url, str(dest)], cfg=cfg)
            note = _say("cloned")
    finally:
        # The token never survives the command that needed it.
        if (dest / ".git").is_dir():
            try:
                _run(["remote", "set-url", remote, url], dest, cfg)
            except ValueError:
                pass
    commit = _run(["log", "-1", f"--format={cfg['commit_format']}"], dest, cfg)[:cfg["commit_max_length"]]
    return {"path": dest, "kind": "git", "note": _say("synced", note=note, commit=commit)}


def missing_folder_message(raw: str) -> str:
    """Why the folder is not there — the reason, not just the fact.

    The usual cause is the whole point of a HOSTED portal: "this machine" is the server, not the
    laptop the person is sitting at. A Windows path on a Linux server can never resolve, however
    many times they press Scan."""
    if not raw:
        return _say("no_folder")
    if is_windows_path(raw) and os.name != "nt":
        system = os.uname().sysname if hasattr(os, "uname") else _say("unknown_system")
        return _say("windows_path_on_server", system=system, path=raw)
    return _say("folder_not_found", path=raw)


def forget(project_id: str) -> None:
    shutil.rmtree(SOURCES / project_id, ignore_errors=True)


if __name__ == "__main__":  # ponytail: one runnable self-check
    assert git_url_ok("https://github.com/owner/repo.git")
    assert git_url_ok("git@github.com:owner/repo.git")
    assert not git_url_ok("https://github.com/owner/repo.git; rm -rf /"), "no shell characters"
    assert not git_url_ok("file:///etc")
    assert not git_url_ok("https://github.com/o/r.git\n"), "a trailing newline is not part of an address"
    assert not git_url_ok("--upload-pack=touch /tmp/x"), "an option is not an address"
    assert branch_ok("feature/x-1") and not branch_ok("main; rm -rf /") and not branch_ok("")
    assert _authed("https://github.com/o/r.git", "abc").startswith("https://x-access-token:abc@github.com/")
    assert _authed("git@github.com:o/r.git", "abc") == "git@github.com:o/r.git", "ssh carries no token"
    assert _scrub("fatal: https://x-access-token:SECRET@github.com/o/r not found") \
        == "fatal: https://github.com/o/r not found", "a token never reaches the screen"
    assert "SECRET" not in _scrub("a https://SECRET@h/x and https://u:SECRET@h/y"), "every token, not the first"
    assert is_windows_path("D:\\Work") and is_windows_path("c:/Users/me")
    assert not is_windows_path("/srv/app") and not is_windows_path("srv/app")
    assert "by hand" in missing_folder_message("/nope") and "No folder is set" in missing_folder_message("")
    print("source self-check OK")
