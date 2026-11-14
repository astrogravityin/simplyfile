"""One shared function per job: find copy-pasted functions in a portal's own code (owner 2026-11-02, portal-review parameter 7).

2026-11-11 (W1.3): it also finds a run of lines repeated back to back anywhere in a file (Shoperative's selfcheck.py:40-49
carried the same two lines five times - no function, so the function compare never saw them). Ceilings in chip
selfcheck.clones (min_tokens, repeat_min_tokens).

Every Python and JavaScript function outside core/ and .venv/ is normalised (comments, strings, numbers and names
stripped) and hashed. Two or more functions with the same body are a clone group - one of them should be the shared
function and the rest should call it. Tiny functions (under MIN_TOKENS) are ignored: getters and one-liners are not clones.

    python tools/clones.py            list clone groups; exit 1 if any group is not in chip selfcheck.clones' allowed list
    python tools/clones.py --selftest

selfcheck.py runs it ("clones"). A group may be allowed - with its reason - in chip selfcheck.clones (allowed: list of
"file:function" sets), never silently.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIN_TOKENS = 40
SKIP = ("core/", ".venv/", "venv/", "venvs/", ".cache/", "tmp/", "data/", "node_modules/", "tools/tour_video/", "static/vendor/",
        "template-patches/")   # 2026-11-02: staged copies of framework files for the template are not this portal's code
JS_FN = re.compile(r"(?:function\s+(\w+)\s*\([^)]*\)|(\w+)\s*[:=]\s*(?:async\s*)?function\s*\([^)]*\)|(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)\s*\{")


def _tokens(code: str) -> list[str]:
    code = re.sub(r"/\*.*?\*/", " ", code, flags=re.S)
    code = re.sub(r"(?m)(//|#).*$", " ", code)
    code = re.sub(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`(?:\\.|[^`\\])*`", "S", code)
    code = re.sub(r"\b[A-Za-z_]\w*\b", "I", code)
    code = re.sub(r"\b\d+(?:\.\d+)?\b", "N", code)
    return re.findall(r"I|S|N|[^\sA-Za-z0-9]", code)


def _js_body(text: str, start: int) -> str:
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return text[start:]


def sources(root: Path = ROOT):
    """(rel path, text) of every .py / .js file of the portal's own - skipped folders are never walked into (.venv is big)."""
    skip_dirs = {s.rstrip("/") for s in SKIP}
    for dirpath, dirs, files in os.walk(root):
        base = Path(dirpath).relative_to(root).as_posix()
        dirs[:] = sorted(d for d in dirs if (f"{base}/{d}" if base != "." else d) not in skip_dirs and d not in ("__pycache__", ".git"))
        for f in sorted(files):
            rel = f if base == "." else f"{base}/{f}"
            if f.endswith((".py", ".js")) and not f.endswith(".min.js") and not rel.startswith(SKIP):
                yield rel, (Path(dirpath) / f).read_text(encoding="utf-8", errors="replace")


def repeats(root: Path = ROOT, min_tokens: int = 8) -> list[str]:
    """file:line for every run of lines that is repeated straight after itself (copy-paste or a script run twice)."""
    found = []
    for rel, text in sources(root):
        lines = [x.rstrip() for x in text.splitlines()]     # indent kept: a line inside a loop and the same line after it differ
        n, i = len(lines), 0
        while i < n:
            hit = 0
            for size in range(1, min(12, (n - i) // 2) + 1):
                block = lines[i:i + size]
                if block == lines[i + size:i + 2 * size] and all(block) and len(_tokens(" ".join(block))) >= min_tokens:
                    hit = size
                    break
            if hit:
                found.append(f"{rel}:{i + 1} ({hit} line(s) repeated)")
                i += 2 * hit
            else:
                i += 1
    return found


def functions(root: Path = ROOT):
    """(file, line, name, token list) for every function worth comparing."""
    for rel, text in sources(root):
        p = Path(rel)
        if p.suffix == ".py":
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            lines = text.splitlines(keepends=True)
            for n in ast.walk(tree):
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    seg = lines[n.lineno - 1:n.end_lineno or n.lineno]   # ast.get_source_segment re-splits the file every call (60 s)
                    body = "".join(seg)[n.col_offset:]
                    body = body.split(":", 1)[1] if ":" in body else body          # the signature's names do not count
                    yield rel, n.lineno, n.name, _tokens(body)
        else:
            for m in JS_FN.finditer(text):
                yield rel, text.count("\n", 0, m.start()) + 1, next(g for g in m.groups() if g), _tokens(_js_body(text, m.end() - 1))


def groups(root: Path = ROOT) -> list[list[str]]:
    by: dict[str, list[str]] = {}
    for rel, line, name, toks in functions(root):
        if len(toks) >= MIN_TOKENS:
            by.setdefault(hashlib.sha1(" ".join(toks).encode()).hexdigest(), []).append(f"{rel}:{line}:{name}")
    return sorted((sorted(g) for g in by.values() if len(g) > 1), key=lambda g: g[0])


def knobs(root: Path = ROOT) -> dict:
    p = root / "chips" / "selfcheck.clones.json"
    return {x["name"]: x["default"] for x in json.loads(p.read_text(encoding="utf-8"))["params"]} if p.exists() else {}


def allowed(root: Path = ROOT) -> list[set]:
    return [set(r["members"]) for r in knobs(root).get("allowed", [])]


def check(root: Path = ROOT) -> list[list[str]]:
    """Clone groups not allowed by the chip. A group is allowed when its file:function members match an allowed row."""
    ok = allowed(root)
    strip = lambda g: {re.sub(r":\d+:", ":", m) for m in g}  # noqa: E731 - line numbers move; file and name do not
    return [g for g in groups(root) if strip(g) not in ok]


def selftest() -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as t:
        r = Path(t)
        body = "    total = 0\n    for row in rows:\n        if row.get('paise', 0) > limit:\n            total += row['paise'] * 2\n    return {'total': total, 'count': len(rows), 'limit': limit}\n"
        (r / "a.py").write_text(f"def one(rows, limit):\n{body}", encoding="utf-8")
        (r / "b.py").write_text(f"def two(items, cap):\n{body.replace('rows', 'items').replace('limit', 'cap')}", encoding="utf-8")
        (r / "c.js").write_text("function tiny(a){ return a + 1; }\n", encoding="utf-8")
        g = groups(r)
        assert len(g) == 1 and {m.split(':')[0] for m in g[0]} == {"a.py", "b.py"}, f"renamed copy must be found: {g}"
        (r / "chips").mkdir()
        (r / "chips" / "selfcheck.clones.json").write_text(json.dumps({"params": [{"name": "allowed", "default": [{"members": ["a.py:one", "b.py:two"], "why": "test"}]}]}))
        assert check(r) == [], "an allowed group is not reported"
        twice = ['SCREENS += [s for s in ("cart", "orders") if s not in SCREENS]', 'WORK += ["cart", "orders"]']
        (r / "d.py").write_text("\n".join(["x = 1", *twice * 3, "y = 2", "}", "}", ""]), encoding="utf-8")
        assert repeats(r) == ["d.py:2 (2 line(s) repeated)"], f"lines pasted back to back must be found (and a bare closer not): {repeats(r)}"
        (r / "d.py").write_text("for t in ts:\n    out.write_text(json.dumps(lines) + newline)\nout.write_text(json.dumps(lines) + newline)\n", encoding="utf-8")
        assert repeats(r) == [], f"the same line inside a loop and after it is not a paste: {repeats(r)}"
    print("clones self-check OK")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
        sys.exit(0)
    every = groups()
    ok = allowed()
    bad = [g for g in every if {re.sub(r":\d+:", ":", m) for m in g} not in ok]
    for g in bad:
        print("clone group:", ", ".join(g))
    rep = [r for r in repeats(ROOT, knobs().get("repeat_min_tokens", 8)) if r.split(" ")[0].rsplit(":", 1)[0] not in knobs().get("repeat_allowed", [])]
    for r in rep:
        print("repeated lines:", r)
    print(f"  clones: {len(every)} clone group(s), {len(bad)} not allowed; {len(rep)} repeated run(s) of lines")
    sys.exit(1 if bad or rep else 0)
