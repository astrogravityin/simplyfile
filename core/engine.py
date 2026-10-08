"""The chip engine: every decision the portal makes is a chip (JSON) built from ops (core/ops.py).

This is the studio's architecture ("every reading is data"), portable and stdlib-only:

  * An OP is a generic primitive in Python (core/ops.py). It never knows the domain.
  * A CHIP is a named, reusable decision in JSON: `params` are its knobs (with defaults), `expr` is
    how the answer is built from ops and other chips, `test_cases` prove it.
  * A RULE (core/rules.py) says what the portal DOES when chips hold at a trigger.
  * Python modules gather FACTS and ask chips what they mean. They never re-derive a threshold, a
    message or a policy inline.

Where a chip lives — later layers win for the same chip_id:
    core/chips/*.json            shipped with the framework
    <portal>/chips/*.json        shipped with the portal (register_dir)
    data/builder/chips/*.json    published from the Ops & Chips Builder at runtime (never in git, so a
                                 builder save can never block a `git pull` on the server)
A chip's `status` is published | inactive. Drafts live apart (core/builder.py) and only run when a
builder passes them in as `lib` for a test.

Grammar (same as the studio backend/engine):
    {"chip": "memory.verdict", "args": {...}}      use another chip
    {"vop": "median", "values": "$rss"}            a value op (ops.OPS, or "choose" with cases/else)
    {"op": "ge", "left": ..., "right": ...}        a test: all any not eq ne in_set ge gt le lt at_least
    "$name"                                         a knob, an argument, or a fact
A test is tri-state: True, False, or None when an operand is unknown — unknown never passes.

`python -m core.engine` certifies every live chip: references resolve and every test case holds.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any

from core import ops, store

HERE = Path(__file__).resolve().parent
DIRS: list[Path] = [HERE / "chips"]
ID_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")
MAX_DEPTH = 40
RELOAD_S = 5  # an edited chip file is picked up within seconds, no restart
TESTS = ("all", "any", "not", "eq", "ne", "in_set", "ge", "gt", "le", "lt", "at_least")
_cache: dict[str, Any] = {"at": 0.0, "sig": None, "chips": {}, "unreadable": []}
_lock = threading.Lock()
_depth = threading.local()


class ChipError(ValueError):
    pass


def data_dir() -> Path:
    return store.DATA / "builder" / "chips"


def register_dir(path) -> None:
    """A portal adds its own chips folder (its core business decisions) beside the framework's."""
    p = Path(path).resolve()
    if p not in DIRS:
        DIRS.append(p)
        refresh()


def refresh() -> None:
    _cache["at"] = 0.0


def _layers() -> list[tuple[str, Path]]:
    return [("core" if d == HERE / "chips" else "portal", d) for d in DIRS] + [("data", data_dir())]


def chips() -> dict[str, dict]:
    """Every live chip by id (published and inactive), later layers winning; re-read when a file changes."""
    with _lock:
        if time.time() - _cache["at"] < RELOAD_S and _cache["chips"]:
            return _cache["chips"]
        files = [(layer, f) for layer, d in _layers() if d.is_dir() for f in sorted(d.glob("*.json"))]
        sig = tuple((str(f), f.stat().st_mtime_ns) for _, f in files)
        if sig != _cache["sig"]:
            loaded: dict[str, dict] = {}
            seen: dict[tuple, str] = {}
            unreadable: list[str] = []
            for layer, f in files:
                # 2026-09-30 sm + tv answered 500 to EVERY request: two chip files were committed half-written, the
                # server pulled them, and this reload raised inside every request. One unreadable file is named
                # (certify) and skipped - the chip keeps its last good answer when there is one; nothing else stops.
                try:
                    chip = json.loads(f.read_text(encoding="utf-8"))
                except (OSError, ValueError) as e:
                    unreadable.append(f"{f.name} cannot be read ({e})")
                    print(f"[chips] {unreadable[-1]}", file=sys.stderr, flush=True)
                    if f.stem in _cache["chips"] and f.stem not in loaded:
                        loaded[f.stem] = _cache["chips"][f.stem]
                    continue
                cid = chip.get("chip_id") or ""
                if cid != f.stem:
                    raise ChipError(f"{f.name}: chip_id must equal the file name ({cid!r})")
                if (layer, cid) in seen:
                    raise ChipError(f"{cid} is defined twice in {layer}")
                seen[(layer, cid)] = f.name
                chip.setdefault("status", "published")
                chip["_source"] = layer
                chip["_shipped"] = layer != "data" or loaded.get(cid, {}).get("_shipped", False)
                loaded[cid] = chip
            _cache.update(chips=loaded, sig=sig, unreadable=unreadable)
        _cache["at"] = time.time()
        return _cache["chips"]


def knobs(chip_id: str, lib: dict | None = None) -> dict:
    """A chip's knob defaults — what a screen shows next to a decision so a person sees the numbers."""
    chip = (lib or chips()).get(chip_id) or {}
    return {p["name"]: p.get("default") for p in chip.get("params", [])}


# --- evaluation ---------------------------------------------------------------------------------

def value(node: Any, env: dict, lib: dict | None = None) -> Any:
    if isinstance(node, str):
        return env.get(node[1:]) if node.startswith("$") else node
    if isinstance(node, list):
        return [value(x, env, lib) for x in node]
    if not isinstance(node, dict):
        return node
    if "chip" in node:
        return run(node["chip"], {k: value(v, env, lib) for k, v in (node.get("args") or {}).items()}, lib)
    if "op" in node:
        return test(node, env, lib)
    if "vop" in node:
        name = node["vop"]
        if name == "choose":  # lazy: only the case that wins is worked out
            for case in node.get("cases") or []:
                if test(case.get("when"), env, lib) is True:
                    return value(case.get("then"), env, lib)
            return value(node.get("else"), env, lib)
        return ops.run(name, {k: value(v, env, lib) for k, v in node.items() if k != "vop"})
    return {k: value(v, env, lib) for k, v in node.items()}


def test(node: Any, env: dict, lib: dict | None = None) -> bool | None:
    if not isinstance(node, dict) or node.get("op") is None:
        v = value(node, env, lib)
        return None if v is None else bool(v)
    op = node["op"]
    if op in ("all", "any", "at_least"):
        results = [test(c, env, lib) for c in node.get("items") or []]
        if op == "at_least":
            n = int(ops._num(value(node.get("n", 1), env, lib)) or 0)
            hits = sum(r is True for r in results)
            return True if hits >= n else (None if hits + sum(r is None for r in results) >= n else False)
        decide, other = (False, True) if op == "all" else (True, False)
        return decide if decide in results else (None if None in results else other)
    if op == "not":
        r = test(node.get("item"), env, lib)
        return None if r is None else not r
    if op == "in_set":
        v, members = value(node.get("value"), env, lib), value(node.get("set"), env, lib)
        return None if v is None or not isinstance(members, list) else v in members
    left, right = value(node.get("left"), env, lib), value(node.get("right"), env, lib)
    if left is None or right is None:
        return None
    if op in ("eq", "ne"):
        ln, rn = ops._num(left), ops._num(right)
        same = ln == rn if ln is not None and rn is not None else str(left) == str(right)
        return same if op == "eq" else not same
    if op in ("ge", "gt", "le", "lt"):
        ln, rn = ops._num(left), ops._num(right)
        if ln is None or rn is None:
            if not (isinstance(left, str) and isinstance(right, str)):
                return None
            ln, rn = left, right
        return ops._CMP[op](ln, rn)
    raise ChipError(f"no test named {op!r}")


_memo: dict = {"lib": None, "got": {}}


def run_memo(memo: dict | None, chip_id: str, args: dict | None = None) -> Any:
    """run(), answered once per distinct FLAT args within one request (2026-10-02 load test: a shelf list of 5,000 works
    asked shelf.may_see / shelf.age_ok / shelf.shared_shows 25,000 times with a handful of distinct true/false answers).
    `memo` = a dict the caller makes for ONE request and drops after it - the chip still decides every answer; nothing is
    kept across requests, so a chip edit is seen on the next one. memo None = a plain run()."""
    if memo is None:
        return run(chip_id, args)
    key = (chip_id, tuple(sorted((k, tuple(v) if isinstance(v, list) else v) for k, v in (args or {}).items())))
    if key not in memo:
        memo[key] = run(chip_id, args)
    return memo[key]


def run(chip_id: str, args: dict | None = None, lib: dict | None = None) -> Any:
    """A chip's answer for these arguments; a knob not given keeps its default. `lib` = a library to
    evaluate against (a builder's drafts over the live chips); default = the live, published chips."""
    # 2026-09-30 owner "a screen cannot slow down with more assets - we can have thousands": a chip asked with its own
    # defaults answers the same until a chip file changes, and one list page asked 10,000 times. The answer is kept per
    # loaded library (chips() hands a new one when a file changes); the top level is handed out as a copy.
    keep = lib is None and not args
    lib = lib if lib is not None else chips()
    if keep:
        if _memo["lib"] is not lib:
            _memo.update(lib=lib, got={})
        if chip_id in _memo["got"]:
            got = _memo["got"][chip_id]
            return dict(got) if isinstance(got, dict) else list(got) if isinstance(got, list) else got
    chip = lib.get(chip_id)
    if chip is None:
        raise ChipError(f"no chip named {chip_id!r}")
    if chip.get("status") == "inactive":
        raise ChipError(f"chip {chip_id} is switched off")
    depth = getattr(_depth, "n", 0)
    if depth > MAX_DEPTH:
        raise ChipError(f"{chip_id}: chips call each other in a loop")
    _depth.n = depth + 1
    try:
        env = knobs(chip_id, lib) | (args or {})
        got = test(chip["expr"], env, lib) if chip.get("kind") == "predicate" else _named(value(chip["expr"], env, lib), lib)
        if keep and _memo["lib"] is lib:
            _memo["got"][chip_id] = got
            return dict(got) if isinstance(got, dict) else list(got) if isinstance(got, list) else got
        return got
    finally:
        _depth.n = depth


def product_name(lib: dict | None = None) -> str:
    """The product's one name - chip edition.settings, this server's edition row (2026-10-08 owner: "the name should be
    chip/ops - one place change, everywhere changed"). Read from the chip itself, not run(), so naming never recurses."""
    lib = lib if lib is not None else chips()
    if _pn["lib"] is lib:
        return _pn["name"]
    knob = {p["name"]: p.get("default") for p in (lib.get("edition.settings") or {}).get("params", [])}
    want = (os.getenv("PORTAL_EDITION") or os.getenv("TV_EDITION") or knob.get("default_edition") or "").strip().lower()
    _pn.update(lib=lib, name=next((r.get("product_name", "") for r in knob.get("rows") or [] if r.get("id") == want), ""))
    return _pn["name"]


_pn: dict = {"lib": None, "name": ""}


def _named(got: Any, lib: dict) -> Any:
    """Every word a chip answers says {product} for the product's name; filled here, so no chip ever spells the name.
    ponytail: walks every answer (no-arg answers are memoised); skip the walk per chip if a hot rule ever shows in a profile."""
    if isinstance(got, str):
        return got.replace("{product}", product_name(lib) or "{product}") if "{product}" in got else got
    if isinstance(got, list):
        return [_named(x, lib) for x in got]
    if isinstance(got, dict):
        return {k: _named(v, lib) for k, v in got.items()}
    return got


def say(chip_id: str, key: str, **values) -> str:
    """One sentence from a messages chip, with {placeholders} filled in:
    `raise HTTPException(404, engine.say("access.messages", "no_group"))`."""
    return ops.template(run(chip_id)[key], values)


def setting(chip_id: str, key: str):
    """One value from a settings chip: `engine.setting("video.settings", "max_title_length")`."""
    return run(chip_id)[key]


def css_vars(chip_id: str) -> str:
    """A record chip as CSS custom properties: field `brand_sub_gap_px: 5` -> `--brand-sub-gap:5px` (`_em` -> em).
    2026-10-03 owner "move spacing into a ui chip": sizes live in the chip, edited in Ops & chips; portal.css reads
    var(--x, fallback). Numbers only - a field that is not a finite number, or has no unit suffix, is left out."""
    out = []
    for name, v in (run(chip_id) or {}).items():
        unit = next((u for u in ("px", "em") if name.endswith("_" + u)), None)
        if unit and isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v):
            out.append(f"--{name[:-len(unit) - 1].replace('_', '-')}:{v:g}{unit}")
    return ":root{" + ";".join(out) + "}" if out else ""


def with_drafts(drafts: list[dict] | dict | None) -> dict:
    """The live library with some chips replaced by unsaved or draft versions (for a builder test)."""
    lib = dict(chips())
    for c in (drafts.values() if isinstance(drafts, dict) else drafts or []):
        if isinstance(c, dict) and c.get("chip_id"):
            lib[c["chip_id"]] = {**c, "status": "published"}
    return lib


# --- structure: references, usages, validation --------------------------------------------------

def refs(node: Any, found: dict | None = None) -> dict:
    """{chips, vops, tests, params} a node uses."""
    found = found if found is not None else {"chips": set(), "vops": set(), "tests": set(), "params": set()}
    if isinstance(node, list):
        for x in node:
            refs(x, found)
    elif isinstance(node, dict):
        if "chip" in node:
            found["chips"].add(node["chip"])
        if "vop" in node and node["vop"] != "choose":
            found["vops"].add(node["vop"])
        if "op" in node:
            found["tests"].add(node["op"])
        for v in node.values():
            refs(v, found)
    elif isinstance(node, str) and node.startswith("$"):
        found["params"].add(node[1:].split(".")[0])
    return found


def usages(kind: str, name: str, rules: dict | None = None) -> dict:
    """Which chips (and rules) use a chip or an op — the impact of changing it."""
    key = "chips" if kind == "chip" else "vops"
    used_by = sorted(cid for cid, c in chips().items() if name in refs(c.get("expr"))[key])
    in_rules = sorted(rid for rid, r in (rules or {}).items()
                      if name in refs([r.get("values"), r.get("when"), r.get("then")])[key])
    return {"chips": used_by, "rules": in_rules}


def problems(chip: dict, lib: dict | None = None, disabled_ops: set | None = None) -> list[str]:
    """What is wrong with one chip, in words. Empty = it may be published."""
    lib = lib if lib is not None else chips()
    cid = chip.get("chip_id") or ""
    out: list[str] = []
    if not ID_RE.match(cid):
        out.append("The chip id must look like set.name — lower-case letters, digits and _ , e.g. memory.verdict.")
    for field in ("kind", "label", "params", "expr", "returns", "description_nl"):
        if chip.get(field) in (None, ""):
            out.append(f"{cid}: {field} is empty")
    if chip.get("kind") not in ("predicate", "accessor"):
        out.append(f"{cid}: kind must be predicate (true/false) or accessor (a value)")
    names = [p.get("name") for p in chip.get("params") or []]
    if len(names) != len(set(names)):
        out.append(f"{cid}: two knobs share a name")
    found = refs(chip.get("expr"))
    out += [f"{cid}: uses ${p} but has no knob or argument of that name" for p in sorted(found["params"] - set(names))]
    out += [f"{cid}: no op named {v}" for v in sorted(found["vops"] - set(ops.OPS))]
    out += [f"{cid}: op {v} is switched off" for v in sorted(found["vops"] & (disabled_ops or set()))]
    out += [f"{cid}: no test named {t}" for t in sorted(found["tests"] - set(TESTS))]
    for c in sorted(found["chips"]):
        if c not in lib:
            out.append(f"{cid}: no chip named {c}")
        elif lib[c].get("status") == "inactive":
            out.append(f"{cid}: uses {c}, which is switched off")
    # a loop through other chips never finishes: walk the graph
    stack, seen = list(found["chips"]), set()
    while stack:
        c = stack.pop()
        if c == cid:
            out.append(f"{cid}: calls itself through {', '.join(sorted(seen)) or 'itself'}")
            break
        if c in seen or c not in lib:
            continue
        seen.add(c)
        stack += list(refs(lib[c].get("expr"))["chips"])
    if not chip.get("test_cases"):
        out.append(f"{cid}: no test cases — a chip nobody has checked is a guess")
    return out


def same(got, want) -> bool:
    """Test equality that forgives float noise: a sum of floats lands on 92.27000000000001 or 92.27 depending on the
    order it was added in, and a chip's answer is not wrong for that."""
    if isinstance(got, float) or isinstance(want, float):
        return (isinstance(got, (int, float)) and isinstance(want, (int, float)) and not isinstance(got, bool)
                and not isinstance(want, bool) and math.isclose(got, want, rel_tol=1e-9, abs_tol=1e-9))
    if isinstance(got, dict) and isinstance(want, dict):
        return got.keys() == want.keys() and all(same(got[k], want[k]) for k in got)
    if isinstance(got, (list, tuple)) and isinstance(want, (list, tuple)):
        return len(got) == len(want) and all(same(g, w) for g, w in zip(got, want))
    return got == want


def run_tests(chip: dict, lib: dict, scenarios: dict | None = None) -> list[dict]:
    """Every test case of a chip: {n, args, want, got, ok, error}."""
    results = []
    for i, case in enumerate(chip.get("test_cases") or []):
        args = dict(((scenarios or {}).get(case.get("scenario")) or {}).get("facts") or {}) | (case.get("args") or {})
        want_key = "expect" if "expect" in case else "expect_value"
        row = {"n": i + 1, "scenario": case.get("scenario", ""), "args": args, "want": _named(case.get(want_key), lib)}
        try:
            row["got"] = run(chip["chip_id"], args, lib)
            row["ok"] = same(row["got"], row["want"])
        except Exception as e:  # noqa: BLE001 - reported, the rest still run
            row.update(got=None, ok=False, error=str(e))
        results.append(row)
    return results


def certify(scenarios: dict | None = None) -> list[str]:
    """Every problem with the live catalog, in words. Empty = every published chip is sound and holds."""
    out: list[str] = []
    lib = chips()
    out += _cache["unreadable"]
    for cid, chip in lib.items():
        if chip.get("status") == "inactive":
            continue
        out += problems(chip, lib)
        out += [f"{cid} test {r['n']}: expected {r['want']!r}, got {r.get('error') or repr(r['got'])}"
                for r in run_tests(chip, lib, scenarios) if not r["ok"]]
    return out


def public(chip: dict) -> dict:
    return {k: v for k, v in chip.items() if not k.startswith("_")} | {"source": chip.get("_source", "")}


if __name__ == "__main__":
    # 2026-10-06 the VPS (Python 3.12 compensated sum) logged assess.by/assess.estimate as failing on 92.27 vs
    # 92.27000000000001: a test answer is compared with float tolerance, never exact ==
    assert same({"a": [92.27000000000001, 1]}, {"a": [92.27, 1]}) and not same(92.28, 92.27) and not same(True, 1.0)
    _run = run
    globals()["run"] = lambda *a, **k: 0.1 + 0.2
    assert run_tests({"chip_id": "x.float", "test_cases": [{"expect_value": 0.3}]}, {})[0]["ok"], "float noise failed a test"
    globals()["run"] = _run
    _m = {}
    assert run_memo(_m, "find.score", {}) == run("find.score") and len(_m) == 1 and run_memo(None, "find.score") == run("find.score")
    # 2026-10-08 owner "the name should be chip/ops": {product} in any answer is the edition's product_name
    _ed = {"chip_id": "edition.settings", "params": [{"name": "default_edition", "default": "x"},
                                                     {"name": "rows", "default": [{"id": "x", "product_name": "Namely"}]}]}
    _w = {"chip_id": "x.words", "kind": "accessor", "params": [], "expr": {"hi": "Welcome to {product}", "n": [1, "{product}"]}}
    _lib = {"edition.settings": _ed, "x.words": _w}
    assert run("x.words", {"z": 1}, _lib) == {"hi": "Welcome to Namely", "n": [1, "Namely"]}, "{product} not filled"
    assert _w["expr"]["hi"] == "Welcome to {product}", "filling the name changed the chip itself"
    if len(sys.argv) > 1:
        register_dir(sys.argv[1])
    bad = certify()
    # 2026-09-30 owner "Avatar Video screen taking long time to load - we can have thousands" (12 s for 7 videos):
    # a chip asked with its own defaults is worked out once per loaded library; each caller gets its own top level
    _cid = next(c for c, v in chips().items() if v.get("status") != "inactive" and v.get("kind") != "predicate" and isinstance(run(c), dict))
    _real, _n = value, [0]
    globals()["value"] = lambda *a, **k: (_n.__setitem__(0, _n[0] + 1), _real(*a, **k))[1]
    _memo.update(lib=None)
    _a = run(_cid)
    _first = _n[0]
    _b = run(_cid)
    globals()["value"] = _real
    assert _first and _n[0] == _first, f"{_cid}: asked again with its own defaults, it was worked out again"
    assert _a == _b and _a is not _b, "a kept answer is handed out as a copy - one caller's change never reaches the next"
    refresh()
    lib = with_drafts([{"chip_id": "x.loop_a", "kind": "accessor", "label": "a", "params": [], "returns": "number",
                        "description_nl": "a", "expr": {"chip": "x.loop_b"}, "test_cases": [{"expect_value": 1}]},
                       {"chip_id": "x.loop_b", "kind": "accessor", "label": "b", "params": [], "returns": "number",
                        "description_nl": "b", "expr": {"chip": "x.loop_a"}, "test_cases": [{"expect_value": 1}]}])
    assert any("calls itself" in p for p in problems(lib["x.loop_a"], lib)), "a loop between chips is caught"
    assert problems({"chip_id": "Bad Id"}, lib), "a malformed chip is refused"
    # 2026-09-30 sm + tv 500 on every request: a half-written chip file is named and skipped, never raised
    _half = DIRS[0] / "x.half_written_.json"
    _half.write_text('{"chip_id": "x.half_written_", "expr": {', encoding="utf-8")
    try:
        refresh()
        assert _cid in chips(), "one unreadable chip file took the whole library down"
        assert any("x.half_written_.json" in p for p in certify()), "an unreadable chip file is not named"
    finally:
        _half.unlink()
        refresh()
    assert chips() and not _cache["unreadable"], "the unreadable list clears once the file is mended or gone"
    if bad:
        raise SystemExit("chip certification FAILED:\n  " + "\n  ".join(bad))
    print(f"core.engine self-check OK ({len(chips())} chips certified)")
