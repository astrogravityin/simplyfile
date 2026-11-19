"""Code guards from the week's glitches (2026-11-18, gap audit B3 - week classes the starter had no check for). Each reads the
code and fails with the file:line to fix; every knob, ceiling and sentence is chip selfcheck.codeguards. Selfcheck part `static`
runs check(); `python -m core.codeguards` (part `modules`) plants each fault in a throwaway tree and must catch it.

  a11y   (class 18, CodyFy G-40)  a <button>/<a>/<input>/<select>/<textarea> in a screen file with no name a screen reader can say
                                  (no aria-label / title / words; an icon alone is not a name). The browser half - only controls
                                  a person can SEE, checkVisibility() - is tools/phone_bar.py (part phonebar).
  hosts  (class 40, G-45 / G-84)  real web addresses typed in .py/.js/.sh/.ps1 - counted against a ceiling that only falls.
  cwd    (class 41, G-53)         a script path read from the folder it was started in (Path("chips/...")), not the repo root.
  order  (class 42, G-23)         an SQL ORDER BY whose terms name no unique column - equal rows swap places between runs.
  paint  (class 47, G-83)         a screen that redraws on the push stream (onEvent) and writes innerHTML directly - it flickers.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

from core import engine

ROOT = Path(__file__).resolve().parent.parent
NAMED = re.compile(r"\b(aria-label|aria-labelledby|title)\s*=")


def cfg() -> dict:
    return engine.run("selfcheck.codeguards")


def say(key: str, **values) -> str:
    return engine.say("selfcheck.codeguards", key, **values)


def _files(root: Path, exts) -> list[Path]:
    skip = set(cfg()["skip_dirs"])
    me = Path(__file__).resolve()                  # this file names every fault it looks for
    return [f for f in sorted(root.rglob("*")) if f.suffix in exts and f.is_file() and not skip & set(f.relative_to(root).parts) and f.resolve() != me]


def _globbed(root: Path, globs) -> list[Path]:
    return sorted({f for g in globs for f in root.glob(g)})


def _line(s: str, i: int) -> int:
    return s.count("\n", 0, i) + 1


# --- JS template strings: skip a ${...} (nested braces and quotes) to find where a tag really ends -------------------------
def _skip_expr(s: str, i: int) -> int:
    depth, j = 0, i + 1
    while j < len(s):
        c = s[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return j + 1
        elif c in "'\"`":
            j += 1
            while j < len(s) and s[j] != c:
                if s[j] == "\\":
                    j += 1
                elif c == "`" and s.startswith("${", j):
                    j = _skip_expr(s, j) - 1
                j += 1
        j += 1
    return j


def _tag_end(s: str, i: int) -> int:
    j = i
    while j < len(s):
        if s.startswith("${", j):
            j = _skip_expr(s, j)
            continue
        if s[j] == ">":
            return j
        if s[j] == "`":
            return -1
        j += 1
    return -1


def _words_of(inner: str) -> str:
    """What a reader hears inside a tag: ${icon(...)} says nothing, any other ${...} is words, tags are dropped."""
    out, j = [], 0
    while j < len(inner):
        if inner.startswith("${", j):
            k = _skip_expr(inner, j)
            out.append(" " if inner[j + 2:k - 1].strip().startswith("icon(") else " w ")
            j = k
            continue
        out.append(inner[j])
        j += 1
    return re.sub(r"<[^>]*>", " ", "".join(out)).strip()


def nameless(root: Path) -> list[str]:
    """'file:line <tag ...>' for every control in the screen files with no name."""
    bad = []
    for f in _globbed(root, cfg()["a11y_globs"]):
        s = f.read_text(encoding="utf-8")
        for m in re.finditer(r"<(button|a|input|select|textarea)\b", s):
            tag, end = m.group(1), _tag_end(s, m.end())
            attrs = s[m.end():end] if end > 0 else ""
            if end < 0 or NAMED.search(attrs):
                continue
            if tag in ("button", "a"):
                close = s.find(f"</{tag}>", end)
                if close < 0 or _words_of(s[end + 1:close]):
                    continue
            else:
                if re.search(r"type=\"hidden\"|\b(placeholder|id)\s*=", attrs):
                    continue
                before = s[max(0, m.start() - 300):m.start()]
                if before.rfind("<label") > before.rfind("</label>"):
                    continue
            bad.append(f"{f.relative_to(root).as_posix()}:{_line(s, m.start())} <{tag}{attrs[:50]}>")
    return bad


def typed_hosts(root: Path) -> Counter:
    """Real web addresses typed in code, by 'host  file' (reserved test names and this machine are not real)."""
    ok, got = re.compile(cfg()["host_ok"]), Counter[str]()
    for f in _files(root, set(cfg()["host_exts"])):
        for h in re.findall(r"https?://([A-Za-z0-9.-]+)", f.read_text(encoding="utf-8", errors="replace")):
            h = h.lower().rstrip(".")
            if "." in h and not ok.search(h):
                got[f"{h}  {f.relative_to(root).as_posix()}"] += 1
    return got


def cwd_paths(root: Path) -> list[str]:
    rx = re.compile(cfg()["cwd_path_re"])
    return [f"{f.relative_to(root).as_posix()}:{n}" for f in _files(root, {".py"})
            for n, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1) if rx.search(line)]


def untied_orders(root: Path) -> list[str]:
    keys = {k.lower() for k in cfg()["order_tie_keys"]}
    bad = []
    for f in _files(root, {".py"}):
        for n, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for m in re.finditer(r"ORDER BY (.*)", line):
                terms = re.split(r"\b(?:LIMIT|OFFSET)\b|\"", m.group(1))[0]   # to LIMIT or the string's end
                if not {w.lower() for w in re.findall(r"[A-Za-z_0-9]+", terms)} & keys:
                    bad.append(f"{f.relative_to(root).as_posix()}:{n} ORDER BY {terms.strip()[:40]}")
    return bad


def direct_paints(root: Path) -> list[str]:
    return [f"{f.relative_to(root).as_posix()}:{_line(s, m.start())}" for f in _globbed(root, cfg()["push_globs"])
            for s in [f.read_text(encoding="utf-8")] if "onEvent(" in s for m in re.finditer(r"\.innerHTML\s*=(?!=)", s)]


def paint_unit(root: Path) -> str:
    """core/static/paint.js in node with a stand-in box: same HTML twice = one write; a box redrawn by someone else = painted
    again. '' when it holds (or no node here - the static half still ran), else what broke."""
    if not shutil.which("node"):
        return ""
    # 2026-11-19 Ask-Harshal deploy: node 18 on the server reads a plain .js as CommonJS, so import() of paint.js threw
    # "Unexpected token 'export'" and the deploy gate refused a good release (node 22+ guesses the module type, so the laptop
    # passed). The unit imports a .mjs copy - an ES module on every node.
    import tempfile  # noqa: PLC0415
    tmp = Path(tempfile.mkdtemp(prefix="paintunit-"))
    mjs = tmp / "paint.mjs"
    shutil.copyfile(root / "core" / "static" / "paint.js", mjs)
    js = mjs.as_uri()
    test = (f"import('{js}').then(({{ paintIfChanged: p }}) => {{ let n = 0; const el = {{ firstChild: null, set innerHTML(h) "
            "{ n++; this.firstChild = {}; } }; p(el, 'a'); p(el, 'a'); if (n !== 1) throw new Error('same HTML painted twice'); "
            "el.firstChild = {}; p(el, 'a'); if (n !== 2) throw new Error('a box redrawn by someone else was not painted again'); "
            "p(el, 'b'); if (n !== 3) throw new Error('new HTML was not painted'); })"
            ".catch((e) => { console.error(e.message); process.exit(1); });")
    try:
        r = subprocess.run(["node", *NODE_FLAGS, "-e", test], capture_output=True, text=True, encoding="utf-8", errors="replace")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return (r.stderr or r.stdout).strip()[-300:] if r.returncode else ""


NODE_FLAGS: list[str] = []   # the self-test sets --no-experimental-detect-module: today's node then reads .js the way node 18 does


def check(root: Path = ROOT) -> None:
    k = cfg()
    a = nameless(root)
    assert len(a) <= int(k["a11y_ceiling"]), say("say_a11y", n=len(a), cap=k["a11y_ceiling"], hits=a[:20])
    h = typed_hosts(root)
    n = sum(h.values())
    assert n <= int(k["host_ceiling"]), say("say_hosts", n=n, cap=k["host_ceiling"], hits=sorted(h)[:30])
    c = cwd_paths(root)
    assert not c, say("say_cwd", hits=c)
    o = untied_orders(root)
    assert not o, say("say_order", hits=o)
    p = direct_paints(root)
    assert not p, say("say_paint", hits=p)
    u = paint_unit(root)
    assert not u, f"core/static/paint.js: {u}"
    low = [f"{x} to {v}" for x, v, cap in (("a11y_ceiling", len(a), k["a11y_ceiling"]), ("host_ceiling", n, k["host_ceiling"])) if v < int(cap)]
    print(f"  code guards: controls named, {n} typed web addresses (ceiling {k['host_ceiling']}), paths from the repo root, "
          f"ORDER BY tie-broken, push redraws through paintIfChanged{' - lower ' + ', '.join(low) if low else ''} OK")


if __name__ == "__main__":
    import json
    import random
    import tempfile

    from core import ops
    check()
    # each fault planted in a throwaway tree must be caught
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        t = Path(d)
        (t / "static").mkdir()
        (t / "core" / "static").mkdir(parents=True)
        (t / "tools").mkdir()
        (t / "static" / "page-x.js").write_text(
            "onEvent('x', () => { host.innerHTML = `<button type=\"button\" data-x>${icon('trash', 12)}</button>"
            "<button title=\"${esc(w('ok'))}\">${icon('x')}</button><a href=\"${u}\">${esc(w('go'))}</a><select data-f=\"k\"></select>`; });\n",
            encoding="utf-8")
        (t / "tools" / "t.py").write_text('p = Path("chips/x.json")\nq = "https://api.real-host.io/v1"\nr = "https://a.example.com"\n'
                                          'c.execute("SELECT * FROM t ORDER BY made DESC LIMIT ?")\nc.execute("SELECT * FROM t ORDER BY made DESC, id")\n',
                                          encoding="utf-8")
        got = nameless(t)
        assert [x.split(" ")[0] for x in got] == ["static/page-x.js:1", "static/page-x.js:1"] and "<button" in got[0] and "<select" in got[1], \
            f"an icon-only button / an unlabelled select was not caught (or a named one was): {got}"
        assert list(typed_hosts(t)) == ["api.real-host.io  tools/t.py"], f"a typed real host was not counted (or a reserved one was): {typed_hosts(t)}"
        assert cwd_paths(t) == ["tools/t.py:1"], f"a cwd-relative path was not caught: {cwd_paths(t)}"
        assert untied_orders(t) == ["tools/t.py:4 ORDER BY made DESC"], f"an ORDER BY with no tie-break was not caught: {untied_orders(t)}"
        assert direct_paints(t) == ["static/page-x.js:1"], f"a push redraw writing innerHTML was not caught: {direct_paints(t)}"
        if shutil.which("node"):
            (t / "core" / "static" / "paint.js").write_text("export function paintIfChanged(el, html) { el.innerHTML = html; return true; }\n", encoding="utf-8")
            assert "same HTML painted twice" in paint_unit(t), "a paintIfChanged that always paints was not caught"
            # 2026-11-19: node 18 (the server) reads a .js file as CommonJS - the good paint.js must still pass there
            shutil.copyfile(Path(__file__).parent / "static" / "paint.js", t / "core" / "static" / "paint.js")
            flag = ["--no-experimental-detect-module"]   # node 22+ guesses ESM; node 18 has no such option and reads .js as CommonJS already
            NODE_FLAGS[:] = flag if subprocess.run(["node", *flag, "-e", "0"], capture_output=True).returncode == 0 else []
            try:
                assert paint_unit(t) == "", f"paint unit fails on a node that reads .js as CommonJS (the server's node 18): {paint_unit(t)}"
            finally:
                NODE_FLAGS[:] = []
    # class 42: the same rows in any order give byte-identical pages (equal sort keys broken by id)
    rows = [{"id": f"r{i:02d}", "made": "2026-11-12T10:00:00", "name": "same"} for i in range(30)]
    pages = set()
    for seed in range(5):
        shuffled = rows[:]
        random.Random(seed).shuffle(shuffled)
        pages.add(json.dumps(ops.rows_view(shuffled, "", ["name"], "made", True, 1, 10, 100)))
    assert len(pages) == 1, "rows_view: rows with equal sort keys came back in another order on another run (tie-break by id)"
    print("codeguards self-check OK")
