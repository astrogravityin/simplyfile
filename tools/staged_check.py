"""Gate for Commit-To-GitHub: refuse a commit that would leak client data or ship a broken file.

Checks every STAGED file (git diff --cached): client data folders are never committed, each .py compiles,
each .json parses, nothing is over GitHub's size limit. Exit 1 lists every problem. Run: python tools/staged_check.py
"""
import json
import subprocess
import sys

# The portal's memory and the client's own material (.gitignore keeps them out; a `git add -f` would not).
NEVER = ("data/", "Requirements/", "SimplyFile-Workflow.html", ".venv/", ".claude/")
MAX_MB = 50     # GitHub refuses a file over 100 MB and warns from 50


def staged() -> list[str]:
    out = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"],
                         capture_output=True, check=True).stdout.decode("utf-8")
    return [p for p in out.split("\0") if p]


def blob(path: str) -> bytes:
    """The STAGED content (what the commit will hold), not the working copy."""
    return subprocess.run(["git", "show", f":{path}"], capture_output=True, check=True).stdout


def problems(paths: list[str], read=blob) -> list[str]:
    bad = []
    for p in paths:
        if any(p == n.rstrip("/") or p.startswith(n) for n in NEVER):
            bad.append(f"{p}: client data / local-only - never committed")
            continue
        data = read(p)
        if len(data) > MAX_MB * 1024 * 1024:
            bad.append(f"{p}: {len(data) / 1048576:.0f} MB - over {MAX_MB} MB")
        elif p.endswith(".py"):
            try:
                compile(data, p, "exec")
            except SyntaxError as e:
                bad.append(f"{p}: line {e.lineno}: {e.msg}")
        elif p.endswith(".json"):
            try:
                json.loads(data.decode("utf-8-sig"))
            except ValueError as e:
                bad.append(f"{p}: {e}")
    return bad


def main() -> int:
    bad = problems(staged())
    for b in bad:
        print("  " + b)
    if bad:
        print(f"Staged file check: {len(bad)} problem(s).")
        return 1
    print("Staged file check OK.")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        files = {"a.py": b"x = 1\n", "b.py": b"def (:\n", "c.json": b'{"x": 1}', "d.json": b"{x}", "data/u.json": b"{}"}
        got = problems(list(files), read=files.__getitem__)
        assert [g.split(":")[0] for g in got] == ["b.py", "d.json", "data/u.json"], got
        print("selftest OK")
        sys.exit(0)
    sys.exit(main())
