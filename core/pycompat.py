"""Every .py here parses on the LOWEST Python this project supports (pyproject.toml requires-python), not just the one it ran on.

2026-11-18: selfcheck.py gained f"... {__import__("time").time()} ..." - the same quote nested inside an f-string is legal only
from Python 3.12 (PEP 701); CodyFy's 3.11 venv could not even start the selfcheck. ast.parse(feature_version=(3, 11)) does
NOT catch it, so on 3.12+ the tokenizer looks inside each f-string's {...} for what 3.11 refuses there: the outer quote and a
backslash. On 3.11 itself every file is simply compiled. Run: python -m core.pycompat (selfcheck part modules)."""
from __future__ import annotations

import re
import subprocess
import sys
import tokenize
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def lowest(root: Path = ROOT) -> tuple[int, int]:
    """(3, 11) from pyproject.toml `requires-python = ">=3.11"`; the running version when none is declared."""
    f = root / "pyproject.toml"
    m = re.search(r'requires-python\s*=\s*"[^"]*?(\d+)\.(\d+)', f.read_text(encoding="utf-8")) if f.is_file() else None
    return (int(m.group(1)), int(m.group(2))) if m else sys.version_info[:2]


def problems(src: str) -> list[int]:
    """Line numbers where an f-string's {...} holds its own quote or a backslash (3.11 cannot parse these)."""
    if sys.version_info < (3, 12):                    # 3.11 has no f-string tokens: just compile
        try:
            compile(src, "<src>", "exec")
            return []
        except SyntaxError as e:
            return [e.lineno or 0]
    start, middle = tokenize.FSTRING_START, tokenize.FSTRING_MIDDLE   # type: ignore[attr-defined]  # 3.12+
    end = tokenize.FSTRING_END                                         # type: ignore[attr-defined]
    stack: list[str] = []
    bad = []
    for t in tokenize.generate_tokens(StringIO(src).readline):
        if t.type == start:
            if stack and stack[-1] in t.string.lstrip("rRbBfF")[:1] and len(stack[-1]) == 1:
                bad.append(t.start[0])
            stack.append(t.string.lstrip("rRbBfF"))
        elif t.type == end:
            stack.pop()
        elif stack and t.type != middle:
            q = stack[-1]
            if (len(q) == 1 and t.type == tokenize.STRING and q in t.string.lstrip("rRbBuU")[:1]) or "\\" in t.string:
                bad.append(t.start[0])
    return sorted(set(bad))


def files(root: Path) -> list[Path]:
    out = subprocess.run(["git", "ls-files", "-z", "*.py"], cwd=root, capture_output=True).stdout.decode("utf-8", "replace")
    return [root / f for f in out.split("\0") if f and (root / f).is_file()] or sorted(root.rglob("*.py"))


def check(root: Path = ROOT) -> str:
    low = lowest(root)
    hits = [f"{f.relative_to(root).as_posix()}:{n}" for f in files(root) for n in problems(f.read_text(encoding="utf-8"))]
    assert not hits, (f"{len(hits)} line(s) need Python 3.12+ but pyproject says >={low[0]}.{low[1]} - inside an f-string's "
                      f"{{...}} use the other quote and no backslash (hoist it into a variable): {hits[:20]}")
    return f"  python {low[0]}.{low[1]}: every tracked .py parses on the lowest supported Python OK"


if __name__ == "__main__":
    q = '"'
    assert problems("x = f" + q + "{d['k']}" + q + "\n") == [], "the other quote inside is fine on 3.11"
    assert problems("x = f" + q + "{d[" + q + "k" + q + "]}" + q + "\n") == [1], "the same quote inside needs 3.12"
    assert problems("x = f" + q + "{'a\\\\nb'}" + q + "\n") == [1], "a backslash inside {...} needs 3.12"
    assert problems("x = f" + q * 3 + "{d[" + q + "k" + q + "]}" + q * 3 + "\n") == [], "inside a triple-quoted f-string it is fine"
    print(check())
