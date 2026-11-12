"""Shape walk: every write route (POST / PUT / PATCH, the portal's and the framework's) is sent bodies of the wrong shape -
no body, a list, a bare string, every key it reads with a wrong type, a huge string, nulls - and must answer anything
but a server error (W1.3, 2026-11-11: core/doctor.py int(body['line']) turned a browser's "abc" into a 500 and no guard saw it).

    python tools/shape_walk.py              walk, exit 1 on any 5xx (selfcheck part "shapes")
    python tools/shape_walk.py --selftest   the walk must catch a planted int(body["x"]) route
    python tools/shape_walk.py --only=/api/core/doctor --verbose   one corner, with timings

Every value, size and skipped route is in chip selfcheck.shapes (Chip Builder): the bad values, the huge string's
length, the path values, and the routes left out - each with its reason.
"""
from __future__ import annotations

import inspect
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WRITE = {"POST", "PUT", "PATCH"}
VERBOSE = "--verbose" in sys.argv
ONLY = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")), "")   # walk the routes whose path holds this
KEY = re.compile(r"""\.get\(\s*["'](\w+)["']|\[\s*["'](\w+)["']\s*\]""")


def chip(root: Path = ROOT) -> dict:
    d = json.loads((root / "chips" / "selfcheck.shapes.json").read_text(encoding="utf-8"))
    return {p["name"]: p["default"] for p in d["params"]}


def flat_routes(routes, prefix: str = ""):
    """(path, methods, endpoint) for every route - FastAPI >= 0.140 wraps an included router (core's) in one
    _IncludedRouter entry, so app.routes alone misses every framework route."""
    for r in routes:
        inc = getattr(r, "include_context", None)
        if inc is not None:
            yield from flat_routes(inc.included_router.routes, prefix + (inc.prefix or ""))
        else:
            yield prefix + getattr(r, "path", ""), set(getattr(r, "methods", None) or ()), getattr(r, "endpoint", None)


def keys_of(endpoint) -> list[str]:
    """The body keys a handler reads: body.get("k") / body["k"] in its source, a pydantic model's fields, its own params."""
    keys: list[str] = []
    try:
        keys += [a or b for a, b in KEY.findall(inspect.getsource(endpoint))]
    except (OSError, TypeError):
        pass
    for name, p in inspect.signature(endpoint).parameters.items():
        ann = p.annotation
        if hasattr(ann, "model_fields"):
            keys += list(ann.model_fields)
        elif name not in ("request", "body", "response", "background", "file", "files"):
            keys.append(name)
    return list(dict.fromkeys(keys))


def bodies(keys: list[str], values: list, per_key: list, huge: str, max_keys: int):
    """(label, kwargs) for TestClient: no body, wrong top-level shapes, every key at once with each bad value (and a huge
    string), then each key alone with a few type probes (an earlier key's 400 must not hide a later key's 500)."""
    yield "no body", {}
    for top in ([], "text", None, 0):
        yield f"top {json.dumps(top)}", {"json": top}
    yield "not json", {"content": b"{not json", "headers": {"content-type": "application/json"}}
    for v in [*values, huge]:
        yield f"all={json.dumps(v)[:20]}", {"json": {k: v for k in keys[:max_keys]}}
    for k in keys[:max_keys]:
        for v in per_key:
            yield f"{k}={json.dumps(v)[:20]}", {"json": {k: v}}
    yield "garbage file", {"files": {"file": ("x.bin", b"\x00\xff\xfe not a document")}}


def fill(path: str, real: dict, default: str) -> str:
    return re.sub(r"\{(\w+)(?::[^}]*)?\}", lambda m: str(real.get(m.group(1), default)), path)


def walk(app, client, cfg: dict, real: dict, sign_in) -> tuple[list[str], int, int]:
    """Returns (server errors, routes walked, requests sent)."""
    skip = {s["route"] for s in cfg["skip"]}
    huge = "x" * int(cfg["huge_len"])
    bad, routes, sent = [], 0, 0
    for path, methods, ep in flat_routes(app.routes):
        for m in sorted(methods & WRITE):
            if ep is None or f"{m} {path}" in skip or ONLY not in path:
                continue
            routes += 1
            url, t0 = fill(path, real, cfg["path_default"]), time.monotonic()
            for label, kw in bodies(keys_of(ep), cfg["values"], cfg["per_key_values"], huge, int(cfg["max_keys"])):
                sent += 1
                r = client.request(m, url, **kw)
                if r.status_code >= 500:
                    bad.append(f"{m} {path} [{label}] -> {r.status_code}")
                if r.status_code == 401:     # a route that signs out (or a body that did): sign in again and go on
                    sign_in()
            if VERBOSE:
                print(f"    {m} {path} {time.monotonic() - t0:.1f}s", flush=True)
    return bad, routes, sent


def selftest() -> None:
    from fastapi import Body, FastAPI
    from fastapi.exceptions import RequestValidationError
    from fastapi.testclient import TestClient
    sys.path.insert(0, str(ROOT))
    from core import doctor  # noqa: PLC0415
    a = FastAPI()
    a.add_exception_handler(RequestValidationError, doctor.bad_shape)   # a binary upload to a JSON route: 422, not 500

    @a.post("/bad")
    def bad(body: dict = Body(default={})):   # the defect, planted
        return {"n": int(body.get("line") or 0)}

    @a.post("/good")
    def good(body: dict = Body(default={})):
        s = str(body.get("line") or 0)[:9]
        return {"n": int(s) if s.isdecimal() else 0}
    cfg = chip() | {"skip": []}
    found, n, _ = walk(a, TestClient(a, raise_server_exceptions=False), cfg, {}, lambda: None)
    assert n == 2 and found and all(f.startswith("POST /bad") for f in found), f"the walk must catch int(body['line']) and pass the fix: {found}"
    assert keys_of(bad) == ["line"], keys_of(bad)
    print("shape walk self-check OK")


def main() -> int:
    cfg = chip()
    data = str(Path(tempfile.mkdtemp(prefix="shapes-")) / "data")   # always its own throw-away folder (one copy per folder)
    os.environ["TV_DATA"] = os.environ["PORTAL_DATA"] = data
    os.environ.pop("PORTAL_EDITION", None)
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    from fastapi.testclient import TestClient
    import app  # noqa: PLC0415 - after TV_DATA
    if cfg.get("rates_off"):      # a rate-limited route answers "slow down" before it reads the body: the probes must reach it
        from core import limits  # noqa: PLC0415
        limits.allow = lambda *_a, **_k: True
    c = TestClient(app.app, raise_server_exceptions=False)
    acct = cfg["owner"]
    assert c.post("/api/auth/first-account", json=acct).status_code == 200, "the walk's owner account"

    def sign_in() -> None:
        c.post("/api/auth/signin", json={"identity": acct["email"], "password": acct["password"]})
    real = dict(cfg["path_values"])
    for name, (route, body, field) in cfg["seed"].items():     # real ids, so a body is read past "not found"
        r = c.post(route, json=body)
        if r.status_code == 200:
            real[name] = r.json().get(field, real.get(name))
    bad, routes, sent = walk(app.app, c, cfg, real, sign_in)
    for b in bad:
        print("server error:", b)
    print(f"  shapes: {routes} write routes, {sent} wrong-shape bodies, {len(bad)} server errors")
    return 1 if bad else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
        sys.exit(0)
    sys.exit(main())
