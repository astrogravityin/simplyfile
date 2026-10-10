"""2026-10-10 slim chip myreturn.tax (1.18 MB on disk; owner: "why is it big?").

Why it was big: the chip language has no "let" - a record's field cannot use another field's answer, so each field held a full copy
of the fields it needs (the surcharge's marginal relief needs the tax before it, the cess needs the surcharge, the tax needs the
cess...): `tax` alone held 80 KB of copies, the whole expression 167 KB, and two-space indenting 50 levels deep made the file 1.18 MB.

What this does: the same expressions worked out in stages. A chip's arguments are worked out once before it runs, so a call is a
"let": myreturn.tax hands its knobs to myreturn.tax_s1 (the fields that need nothing else), whose answer goes to myreturn.tax_s2 as
`b`, and so on; each stage reads what the stages before it worked out ({"vop": "get", "value": "$b", "path": ...}) where the copy
stood. Every stage's expression is the old one with the copies swapped out - nothing is worked out differently. The old chip is kept
in memory and both are asked the chip's own cases and many thousand random returns; the answers must be identical, or nothing is
written. Re-runnable: a chip already staged is left alone.

2026-10-10 (later): chip myreturn.year_tax (an earlier year's tax, 1.76 MB for the same reason) staged the same way, with its own stage
list and its own random returns (every year the rates know, and a year they do not). Both chips by default; --chip <id> for one.

Re-run after tools/make_wave4_chips.py (it writes myreturn.year_tax whole again) or whichever tool rewrites myreturn.tax.

Run from D:/Simplyfile:  .venv/Scripts/python.exe tools/slim_myreturn_tax.py [--chip myreturn.year_tax] [--n 20000] [--check]"""
import copy
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CH = ROOT / "chips"
sys.path.insert(0, str(ROOT))
NOTE = "2026-10-10: "
STAGE_LISTS = {  # per chip: the fields worked out in each stage; a stage's fields may use any field of the stages before it
    "myreturn.tax": [
        ["total", "basic_left", "on_normal", "on_aggregate", "agri_rebate", "on_111a", "on_112a", "on_112", "on_115bb", "on_115bbj", "on_115bbh",
         "surcharge_rate"],
        ["on_special", "rebate", "relief_87a"],
        ["surcharge"],
        ["cess"],
        ["tax"],
    ],
    "myreturn.year_tax": [
        ["known", "total", "on_normal", "on_111a", "on_112a", "on_112", "on_special"],
        ["rebate", "surcharge_rate"],
        ["surcharge"],
        ["cess"],
        ["tax"],
    ],
}
BUSY = {  # each stage's second own case: a busy return
    "myreturn.tax": {"normal": 5100000, "stcg_111a": 400000, "ltcg_112a": 300000, "vda": 100000, "agri": 200000, "regime": "old"},
    "myreturn.year_tax": {"fy": 2022, "normal": 5100000, "stcg_111a": 400000, "ltcg_112a": 300000, "ltcg_112": 200000, "special": 100000, "regime": "old"},
}
key = lambda n: json.dumps(n, sort_keys=True)  # noqa: E731


def swap_known(node, known):
    """`node` with every subtree that is a field (or a rounded field's unrounded value) of an earlier stage read from $b instead."""
    k = key(node)
    if k in known:
        return {"vop": "get", "value": "$b", "path": known[k]}
    if isinstance(node, dict):
        return {a: swap_known(v, known) for a, v in node.items()}
    if isinstance(node, list):
        return [swap_known(v, known) for v in node]
    return node


def staged(old):
    CID, STAGES = old["chip_id"], STAGE_LISTS[old["chip_id"]]
    F = old["expr"]["fields"]
    assert old["expr"]["vop"] == "record" and sorted(sum(STAGES, [])) == sorted(F), "the stages name every field once"
    params = old["params"]
    pargs = {p["name"]: f"${p['name']}" for p in params}
    known, chips_, prev = {}, [], []
    for n, names in enumerate(STAGES, 1):
        fields = {f: {"vop": "get", "value": "$b", "path": f} for f in prev}
        for f in names:
            fields[f] = swap_known(F[f], known)
            if isinstance(F[f], dict) and F[f].get("vop") == "round_to" and set(F[f]) == {"vop", "value"}:
                fields[f"_raw_{f}"] = swap_known(F[f]["value"], known)
        for f in names:                                   # what the next stages may read instead of a copy
            known[key(F[f])] = f
            if f"_raw_{f}" in fields:
                known[key(F[f]["value"])] = f"_raw_{f}"
        prev = list(fields)                               # the next stage hands all of it on
        last = n == len(STAGES)
        if last:                                          # the last stage answers exactly the old record (no _raw_ fields), in its order
            fields = {f: fields[f] for f in F}
        chips_.append({"chip_id": f"{CID}_s{n}", "kind": "accessor", "set": old.get("set", "myreturn"),
                       "label": f"{old['label'].split(' - ')[0]}, stage {n} of {len(STAGES)} ({', '.join(names)})",
                       "aliases": [], "params": copy.deepcopy(params) + ([] if n == 1 else [{"name": "b", "type": "json", "default": {},
                                                                                              "label": f"what stage {n - 1} worked out"}]),
                       "expr": {"vop": "record", "fields": fields}, "returns": "record", "version": 1, "status": "published",
                       "description_nl": NOTE + f"part of chip {CID}, split so that no field holds a copy of another (see tools/slim_myreturn_tax.py). "
                                                f"Stage {n} works out {', '.join(names)}" + ("" if n == 1 else f" from its knobs and what stage {n - 1} worked out (b)")
                                                + (" - and answers the whole record." if last else "; the _raw_ fields are the unrounded values the next stages use."),
                       "test_cases": []})
    call = {"chip": f"{CID}_s1", "args": dict(pargs)}
    for n in range(2, len(STAGES) + 1):
        call = {"chip": f"{CID}_s{n}", "args": dict(pargs) | {"b": call}}
    new = copy.deepcopy(old)
    new["expr"] = call
    return new, chips_


def write(c):
    (CH / f"{c['chip_id']}.json").write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def randoms(cid, n, seed=20261010):
    rnd = random.Random(seed)
    amt = lambda hi: rnd.choice([0, 0, rnd.randint(0, hi), rnd.randint(0, hi // 10), round(rnd.randint(0, hi), -5)])  # noqa: E731
    big = [0, 300000, 700000, 1200000, 1275000, 1500000, 5000000, 5100000, 10000000, 10100000, 20000000, 20500000, 50000000, 51000000]
    for _ in range(n):
        if cid == "myreturn.year_tax":                    # every year the rates know (2015-2025), now and then one they do not
            a = {"fy": rnd.choice(list(range(2015, 2026)) * 6 + [2013, 2014, 2026]), "normal": rnd.choice(big + [amt(60000000)] * 4),
                 "stcg_111a": amt(30000000), "ltcg_112a": amt(30000000), "ltcg_112": amt(30000000), "special": amt(5000000),
                 "regime": rnd.choice(["new", "old"]), "band": rnd.choice(["below60", "60to80", "80plus"]), "resident": rnd.random() < 0.85,
                 "early": rnd.random() < 0.3}
            yield {k: v for k, v in a.items() if rnd.random() < 0.8 or k in ("fy", "normal", "regime")}
            continue
        a = {"normal": rnd.choice(big + [amt(60000000)] * 4), "stcg_111a": amt(30000000), "ltcg_112a": amt(30000000), "ltcg_112": amt(30000000),
             "regime": rnd.choice(["new", "old"]), "band": rnd.choice(["below60", "60to80", "80plus"]), "resident": rnd.random() < 0.85,
             "status": rnd.choice(["individual", "individual", "huf"]), "lottery": amt(3000000), "online_games": amt(3000000), "vda": amt(30000000),
             "agri": amt(1000000), "excess_112": amt(500000)}
        yield {k: v for k, v in a.items() if rnd.random() < 0.8 or k in ("normal", "regime")}


def main():
    want_ = sys.argv[sys.argv.index("--chip") + 1] if "--chip" in sys.argv else None
    for cid in STAGE_LISTS:
        if want_ in (None, cid):
            slim(cid)


def slim(CID):
    from core import engine  # noqa: PLC0415
    import store  # noqa: F401,PLC0415 - registers the portal's chips
    STAGES = STAGE_LISTS[CID]
    old = json.loads((CH / f"{CID}.json").read_text(encoding="utf-8"))
    if isinstance(old["expr"], dict) and old["expr"].get("chip") == f"{CID}_s{len(STAGES)}":
        print(f"{CID} is already staged - nothing to do")
        return
    size_file = (CH / f"{CID}.json").stat().st_size
    new, parts = staged(old)
    engine.refresh()
    lib = dict(engine.chips())
    lib_old = dict(lib)
    lib_new = dict(lib) | {CID: new} | {c["chip_id"]: c for c in parts}
    engine.RELOAD_S = 10 ** 9                             # ask each library as the live one, so nested no-args chips are kept per run

    def ask(lib_, cid, a):
        engine._cache["chips"] = lib_
        return engine.run(cid, a)
    cases = [tc.get("args") or {} for tc in old["test_cases"]] + list(randoms(CID, int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 20000))
    t_old = t_new = 0.0
    for i, a in enumerate(cases):
        t0 = time.perf_counter()
        want = ask(lib_old, CID, a)
        t1 = time.perf_counter()
        got = ask(lib_new, CID, a)
        t_old, t_new = t_old + (t1 - t0), t_new + (time.perf_counter() - t1)
        if got != want or list(got) != list(want):
            raise SystemExit(f"DIFFERENT for {a}: " + json.dumps({k: (got.get(k), want.get(k)) for k in want if got.get(k) != want.get(k)}))
    for tc in old["test_cases"]:
        assert ask(lib_new, CID, tc.get("args") or {}) == tc["expect_value"], tc["args"]
    size_old = len(json.dumps(old, indent=2, ensure_ascii=False))
    size_new = sum(len(json.dumps(c, indent=2, ensure_ascii=False)) for c in [new, *parts])
    print(f"{CID}: identical on {len(cases)} returns ({len(old['test_cases'])} of the chip's own cases); "
          f"time old {t_old:.1f}s new {t_new:.1f}s; on disk {size_old:,} -> {size_new:,} bytes in {1 + len(parts)} files")
    for c in parts:
        print(f"  {c['chip_id']}: {len(json.dumps(c['expr'])):,} bytes of expression")
    if "--check" in sys.argv:
        return
    for c in parts:                                       # each stage's own case: the knobs' defaults, then a busy return
        lib_new = dict(lib_new)
        for a in ({}, BUSY[CID]):
            if c["chip_id"] != f"{CID}_s1":
                n = int(c["chip_id"].rsplit("_s", 1)[1])
                prev = {"chip": f"{CID}_s{n - 1}", "args": {p["name"]: a.get(p["name"], p["default"]) for p in old["params"]}}
                a = a | {"b": engine.value(prev, {}, lib_new)}
            c["test_cases"].append({"args": a, "expect_value": engine.run(c["chip_id"], a, lib_new)})
    for c in parts:
        write(c)
    new["version"] = old["version"] + 1
    new["description_nl"] = old.get("description_nl", "") + " " + NOTE + (
        f"the same expressions in stages (chips {CID}_s1 - s{len(STAGES)}, each reading what the stage before worked out) instead of every field "
        f"holding a copy of the fields it needs - {size_file / 1e6:.2f} MB on disk to a few dozen KB; answers checked identical on the chip's cases and "
        f"{len(cases) - len(old['test_cases']):,} random returns (tools/slim_myreturn_tax.py), {t_old / max(t_new, 1e-9):.1f} times faster.")
    write(new)
    print("wrote", CID, "v", new["version"], "and", ", ".join(c["chip_id"] for c in parts))


if __name__ == "__main__":
    main()
