"""Secret-scan gate (2026-11-18, gap audit C1-12): no key or token in a tracked file, nor anywhere under static/ or core/static/
(vendored chunks and long minified lines included - portal-review's scan stops at long lines, this one does not).

Shapes: chip security.secret_patterns (copied from skills/portal-review/scan_rules.json). Run: python -m core.secretscan [folder]
(selfcheck part `secrets`). A public-by-design key goes in the chip's `allow` list, never a skip in code.

2026-11-18 gap audit S10: the history too - the lines ADDED in the last `history_commits` commits (git log -p). A key committed
and deleted in a later commit is still in the repo for anyone who clones it: rotate it, then name it in `history_allow`."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from core import engine

ROOT = Path(__file__).resolve().parent.parent


def _rules() -> dict:
    return engine.run("security.secret_patterns")


def compiled() -> list[tuple[str, re.Pattern]]:
    return [(p["kind"], re.compile(p["re"])) for p in _rules()["patterns"]]


def files_of(root: Path) -> list[Path]:
    """Tracked files (git) plus everything under static/ and core/static/, tracked or not."""
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True).stdout.decode("utf-8", "replace")
        tracked = {root / f for f in out.split("\0") if f}
    except (OSError, subprocess.CalledProcessError):      # not a git folder (a release copy): every file
        tracked = {f for f in root.rglob("*") if f.is_file() and ".git" not in f.parts}
    served = {f for d in ("static", "core/static") if (root / d).is_dir() for f in (root / d).rglob("*") if f.is_file()}
    return sorted(f for f in tracked | served if f.is_file())


def scan(root: Path) -> list[str]:
    """'path:line kind' for every hit, and 'path secret file' for a tracked secret file. Values are never printed."""
    rules = _rules()
    pats = compiled()
    names = [(f["kind"], re.compile(f["re"])) for f in rules["files"]]
    allow = set(rules["allow"])
    hits = []
    for f in files_of(root):
        rel = f.relative_to(root).as_posix()
        if rel in allow:
            continue
        hits += [f"{rel} {kind}" for kind, rx in names if rx.search(rel)]
        raw = f.read_bytes()
        if b"\0" in raw[:4096]:                           # binary (images, fonts, wasm)
            continue
        for n, line in enumerate(raw.decode("utf-8", "replace").splitlines(), 1):
            hits += [f"{rel}:{n} {kind}" for kind, rx in pats if rx.search(line)]
    return hits


def history(root: Path, n: int | None = None) -> list[str]:
    """'<commit> <path> <kind>' for every key shape on a line ADDED in the last n commits (chip history_commits) under root."""
    rules = _rules()
    n = int(rules.get("history_commits") or 0) if n is None else n
    if n <= 0:
        return []
    try:
        out = subprocess.run(["git", "log", "-p", f"-n{n}", "--no-color", "--no-ext-diff", "--unified=0", "--relative", "--format=@%h"],
                             cwd=root, capture_output=True, check=True).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.CalledProcessError):      # not a git folder (a release copy): no history to read
        return []
    pats, allow, done = compiled(), set(rules["allow"]), set(rules.get("history_allow") or [])
    hits, sha, path = [], "", ""
    for line in out.splitlines():
        if line.startswith("@") and not line.startswith("@@"):
            sha = line[1:]
        elif line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else ""
        elif line.startswith("+") and path and path not in allow and f"{sha} {path}" not in done:
            hits += [f"{sha} {path} {kind}" for kind, rx in pats if rx.search(line)]
    return sorted(set(hits))


def check(root: Path = ROOT) -> None:
    hits = scan(root)
    assert not hits, f"{len(hits)} secret(s) in tracked or served files - remove and rotate them (values not shown): {hits[:20]}"
    old = history(root)
    assert not old, (f"{len(old)} secret(s) in git history (added in a recent commit, maybe deleted since) - rotate each key, then "
                     f"name it in chip security.secret_patterns history_allow (values not shown): {old[:20]}")
    print(f"  secrets: {len(files_of(root))} tracked and served files and the last {_rules().get('history_commits')} commits, "
          "no key or token, no secret file OK")


def _self_test() -> None:
    import tempfile  # noqa: PLC0415
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        (d / "static").mkdir()
        (d / "static" / "chunk.js").write_text("x" * 5000 + " AKIA" + "Q" * 16 + " " + "x" * 50, encoding="utf-8")   # a long vendored line
        (d / ".env").write_text("A=1", encoding="utf-8")
        got = scan(d)
        assert any(h.startswith("static/chunk.js:1 AWS") for h in got), got
        assert any(h.startswith(".env ") for h in got), got
        assert all("Q" * 16 not in h for h in got), "a hit never prints the value"
        (d / "static" / "chunk.js").write_text("AKIA-not-a-key", encoding="utf-8")
        (d / ".env").unlink()
        assert scan(d) == [], scan(d)
    _history_self_test()
    rules = Path(ROOT.parent / "skills" / "portal-review" / "scan_rules.json")
    if rules.is_file():                                   # in DomainTemplate: the chip follows portal-review's rules
        import json  # noqa: PLC0415
        theirs = {s["kind"]: s["re"] for s in json.loads(rules.read_text(encoding="utf-8"))["secrets"]}
        drift = [p["kind"] for p in _rules()["patterns"] if theirs.get(p["kind"]) != p["re"]]
        assert not drift, f"chip security.secret_patterns drifted from scan_rules.json: {drift}"
    print("core.secretscan OK")


def _history_self_test() -> None:
    """A key added in one commit and removed in the next: the files are clean, the history is not - and a rotated one, allowed."""
    import tempfile  # noqa: PLC0415
    from unittest import mock  # noqa: PLC0415
    g = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        if subprocess.run(["git", "init", "-q", str(d)], capture_output=True).returncode:
            print("  (no git here - history self-test skipped)")
            return
        (d / "a.py").write_text("x = 1\n", encoding="utf-8")
        subprocess.run([*g, "add", "-A"], cwd=d, check=True)
        subprocess.run([*g, "commit", "-qm", "one"], cwd=d, check=True)
        (d / "a.py").write_text("x = 1\nKEY = '" + "AKIA" + "Z" * 16 + "'\n", encoding="utf-8")
        subprocess.run([*g, "commit", "-qam", "key"], cwd=d, check=True)
        (d / "a.py").write_text("x = 1\n", encoding="utf-8")
        subprocess.run([*g, "commit", "-qam", "gone"], cwd=d, check=True)
        assert scan(d) == [], "the files are clean now"
        got = history(d, 10)
        assert len(got) == 1 and got[0].endswith(" a.py AWS access key") and "Z" * 16 not in got[0], got
        assert history(d, 1) == [], "outside the window (only the last commit read): not seen"
        sha = got[0].split()[0]
        with mock.patch(__name__ + "._rules", lambda: {**engine.run("security.secret_patterns"), "history_allow": [f"{sha} a.py"]}):
            assert history(d, 10) == [], "a rotated key named in history_allow passes"


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        check(Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT)
    else:
        _self_test()
