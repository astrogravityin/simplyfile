"""Lists: any list that grows with the number of people is searched, sorted and paged on the server - one page reaches
the browser, never the whole list (2026-09-28 owner: "Lend - it goes beyond 10 we are gone. Need a strategy for tens of
thousands ... a common framework ... only chips and ops").

    chip  list.<id>      search_keys, sort_key, sort_desc, sorts (what a viewer may sort by), page_size, max_page_size
    op    rows_view      the search, the sort and the page (core/ops.py) - the only list logic there is
    route GET /api/lists/<id>?q=&page=&sort=&desc=&<filters>   one route for every list
    JS    listBox()      core/static/ui.js: search box, rows, pager - the one way a screen shows a long list

A module says WHERE its rows come from, as THIS person may see them, and (optionally) how the rows of one page are
filled in with anything costly (a spend window, a name) - so the cost is one page, never the whole list:

    lists.source("keys_lent", rows=lambda user, args: [...], fill=lambda user, rows, args: [...])

chip list.backlog names the lists still sent whole; tv selfcheck lets it only shrink.
"""
from __future__ import annotations

from typing import Any
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Request

from core import auth, engine, limits, ops

router = APIRouter()
SOURCES: dict[str, dict] = {}


def source(list_id: str, rows: Callable[[dict, dict], list], fill: Callable[[dict, list, dict], list] | None = None,
           screen: str = "") -> None:
    """`screen`: the screen whose people may read this list ("a|b": the people of either) - /api/lists asks access.may before any row is built
    (2026-10-02 review: the route only knew "signed in", so a list of a screen someone is denied stayed readable)."""
    # 2026-09-30: a second module took the id of the framework's Storage list and silently replaced it - an id is one list
    # (a module run as its own self-check is "__main__" and its imported self at once - that is one module)
    if list_id in SOURCES and "__main__" not in (was := SOURCES[list_id]["rows"].__module__, rows.__module__) and was != rows.__module__:
        raise ValueError(f"list {list_id!r} already belongs to {SOURCES[list_id]['rows'].__module__}")
    SOURCES[list_id] = {"rows": rows, "fill": fill, "screen": screen}


def view(list_id: str) -> dict:
    return engine.run(f"list.{list_id}")


def page(list_id: str, user: dict, args: dict) -> dict:
    """One page of list `list_id` for `user`; `args` = q, page, sort, desc and the list's own filters."""
    if list_id not in SOURCES:
        raise HTTPException(404, engine.say("lists.messages", "no_list"))
    v, src = view(list_id), SOURCES[list_id]
    if src.get("screen"):
        from core import access  # noqa: PLC0415 - access registers its own lists here
        if not any(access.may(user, sc) for sc in src["screen"].split("|")):   # "a|b": either screen's people (2026-10-07)
            raise HTTPException(403, engine.say("lists.messages", "no_list"))
    s = engine.run("lists.settings")
    sort = str(args.get("sort") or "")
    sort = sort if limits.one_of(sort, v.get("sorts") or []) else v["sort_key"]
    desc = args.get("desc")
    desc = v["sort_desc"] if desc in (None, "") else limits.one_of(str(desc).lower(), s["yes_words"])
    rows, q = src["rows"](user, args), limits.clip(args.get("q") or "", s["q_max"])
    # a list whose chip sets fuzzy_min searches forgivingly (op fuzzy_rows): typos and half words, best match first
    if engine.run("lists.searches_fuzzy", {"q": q, "fuzzy_min": float(v.get("fuzzy_min") or 0)}) is True:
        rows, q = ops.fuzzy_rows(rows, q, v["search_keys"], v["fuzzy_min"], s["match_key"]), ""
        if not args.get("sort"):
            sort, desc = s["match_key"], True
    got = ops.rows_view(rows, q, v["search_keys"], sort, desc, args.get("page") or 1, v["page_size"], v["max_page_size"])
    if src["fill"] and got["rows"]:
        got["rows"] = src["fill"](user, got["rows"], args)
    return got | {"sort": sort, "desc": desc}


@router.get("/api/lists/{list_id}")
def api_list(list_id: str, request: Request, u: dict = Depends(auth.signed_in)):
    return page(list_id, u, dict(request.query_params))


if __name__ == "__main__":  # ponytail: one runnable self-check - 20,000 rows, one page out, the costly part paid per page
    filled: list[Any] = []
    SOURCES.clear()
    source("t", rows=lambda user, a: [{"id": i, "name": f"p{i}", "n": i % 7} for i in range(20000) if not a.get("odd") or i % 2],
           fill=lambda user, rows, a: filled.append(len(rows)) or [r | {"x": 1} for r in rows])
    globals()["view"] = lambda lid: {"search_keys": ["name"], "sort_key": "id", "sort_desc": False, "sorts": ["n"], "page_size": 25, "max_page_size": 100}
    r = page("t", {}, {"q": "p1999", "page": 1})
    assert r["total"] == 11 and len(r["rows"]) == 11 and r["rows"][0]["x"] == 1, r["total"]
    r = page("t", {}, {"page": 3, "sort": "evil", "odd": "1"})
    assert r["total"] == 10000 and len(r["rows"]) == 25 and r["sort"] == "id" and r["rows"][0]["id"] == 101, "an unknown sort falls back"
    assert filled == [11, 25], "only one page is ever filled in"
    assert page("t", {}, {"sort": "n", "desc": "YES"})["desc"] is True and page("t", {}, {"desc": "no"})["desc"] is False, "desc words: chip lists.settings"
    assert page("t", {}, {"q": "p1 " + "x" * 500})["total"] == 0, "a very long search is clipped, not refused"
    import types  # a second module may not take a list's id
    mod = lambda name: types.FunctionType((lambda user, a: []).__code__, {"__name__": name})  # noqa: E731
    SOURCES.clear()
    source("t", rows=mod("one"))
    source("t", rows=mod("one"))                        # the same module again (a reload) is fine
    try:
        source("t", rows=mod("elsewhere"))
        raise AssertionError("a list id was taken by a second module")
    except ValueError:
        pass
    # 2026-10-24 owner "every list = flexi search": the browser's own pick lists (core/static/ui.js flexiHit, pickMany) forgive a typo,
    # two swapped letters and missing letters - checked in node when node really runs here (else said and skipped, never failed)
    import json
    import shutil
    import subprocess
    from pathlib import Path
    node = shutil.which("node")
    if node and subprocess.run([node, "-e", "process.exit(0)"], capture_output=True).returncode == 0:
        src = (Path(__file__).resolve().parent / "static" / "ui.js").read_text(encoding="utf-8")
        assert "flexiHit(String(x.name" in src, "pickMany's search is exact again - it must use flexiHit"
        body = src[src.index("export function flexiHit"):src.index("export function pickMany")].replace("export function flexiHit", "return function flexiHit")
        out = subprocess.run([node, "-e", f"const f=new Function({json.dumps(body)})();console.log(JSON.stringify(["
                              "f('Phone app (Expo)','phnoe'),f('React screen + Python API','rctpy'),f('Python API only','pythn'),"
                              "f('Plain web page','zzz')]))"], capture_output=True, text=True).stdout.strip()
        assert out == "[true,true,true,false]", f"the pick lists' search is not forgiving: {out}"
    else:
        print("lists: node does not run on this computer - the pick lists' flexi search check is skipped")
    print("lists self-check OK")
