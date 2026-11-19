"""Security watch - every week, is anything we ship known to be vulnerable, and do our own security walls still stand?
(2026-11-19 owner: "Every week (or based on schedule) verify the software vulnerability and fix ... for any future changes".)

Agent ag_security_watch (chip agents.recipe.ag_security_watch - its trigger IS the schedule, on the agents clock, never a page
timer) runs three steps: securitywatch.run -> health.check -> health.warn. So every blocking finding becomes its own row on the
owners' warning bar and the bell rings ONCE for a new one (core/health.py), and the bar stays red until the next clean run.

One run (`run`):
  deps     every pinned package of the hash locks (chip securitywatch.settings `locks`) against osv.dev - the database pip-audit
           and npm audit read - through core/egress (allow-list osv_hosts). An advisory with no severity counts as
           unknown_severity, never as nothing; osv.dev unreachable is itself a blocking finding (unchecked is not clean).
  secrets  core/secretscan: tracked + served files and the last N commits
  routes   core/routeguard: every /api route has a guard (ratchet)
  csp      selfcheck_push.csp_enforced on the enforced policy (chip security.headers)
  egress   core/egress ratchet: no new direct URL opener
  python   core/pycompat: every .py parses on the lowest supported Python
  drill    core/health.drill: the last restore drill is good and recent
The every-route tenant wall (selfcheck.py route_wall) is NOT run here: it creates test firms and people, so it runs only in the
selfcheck before every ship (QA-17), never on live data.

The answer is kept in store `record` (body-free: package names and versions, advisory ids, file:line, check names - never a
value) and one ledger security event (kind ledger_kind, counts only). Probe `watch` turns the bar red when: a blocking finding
is open, the watch never ran on a server, its trigger is off, or the last run is older than every_days + grace_days.
Every number is chip securitywatch.settings; every sentence chip securitywatch.messages.
"""
from __future__ import annotations

import json
import shutil
import urllib.request
from pathlib import Path
from typing import Callable

from core import agents, egress, engine, health, store

ROOT = Path(__file__).resolve().parent.parent
RANK = {"CRITICAL": 4, "HIGH": 3, "MODERATE": 2, "MEDIUM": 2, "LOW": 1}


def K() -> dict:
    return engine.run("securitywatch.settings")


def say(key: str, **values) -> str:
    return engine.say("securitywatch.messages", key, **values)


def _post(url: str, body: dict | None) -> dict:
    """One osv.dev call through the egress door (https, public address, allow-listed host). Swapped in the self-test."""
    k = K()
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"}, method="POST" if body is not None else "GET")
    with egress.fetch(req, timeout=float(k["timeout_seconds"]), hosts=k["osv_hosts"]) as r:
        return json.loads(r.read().decode("utf-8"))


FETCH: Callable[[str, dict | None], dict] = _post


def pinned(root: Path = ROOT) -> list[tuple[str, str, str]]:
    """(ecosystem, name, version) for every exact pin of every lock file the chip names that exists."""
    out = []
    for lock in K()["locks"]:
        f = root / lock["file"]
        if not f.is_file():
            continue
        if f.suffix == ".json":
            pk = json.loads(f.read_text(encoding="utf-8")).get("packages") or {}
            out += [(lock["ecosystem"], p.split("node_modules/")[-1], v["version"]) for p, v in pk.items()
                    if p and isinstance(v, dict) and v.get("version") and not v.get("link")]
        else:
            for line in f.read_text(encoding="utf-8").splitlines():
                pin = line.split("#")[0].split(";")[0].split(" --hash")[0].strip()
                if "==" in pin:
                    name, ver = pin.split("==", 1)
                    out.append((lock["ecosystem"], name.split("[")[0].strip(), ver.strip()))
    return sorted(set(out))


def _severity(adv: dict) -> str:
    sev = str((adv.get("database_specific") or {}).get("severity") or "").upper()
    for a in adv.get("affected") or []:
        s = str((a.get("database_specific") or {}).get("severity") or a.get("ecosystem_specific", {}).get("severity") or "").upper()
        sev = s if RANK.get(s, 0) > RANK.get(sev, 0) else sev
    return sev if sev in RANK else ""


def _fixed(adv: dict, name: str) -> str:
    for a in adv.get("affected") or []:
        if str((a.get("package") or {}).get("name") or "").lower() == name.lower():
            for rg in a.get("ranges") or []:
                for ev in rg.get("events") or []:
                    if ev.get("fixed"):
                        return str(ev["fixed"])
    return ""


def deps(root: Path = ROOT) -> tuple[list[dict], int]:
    """Findings for vulnerable pins, and how many pins were checked."""
    k = K()
    pins = pinned(root)
    hits: dict[int, list[str]] = {}
    size = int(k["batch_size"])
    for i in range(0, len(pins), size):
        part = pins[i:i + size]
        got = FETCH(k["osv_batch_url"], {"queries": [{"package": {"ecosystem": e, "name": n}, "version": v} for e, n, v in part]})
        for j, res in enumerate(got.get("results") or []):
            ids = [x["id"] for x in res.get("vulns") or [] if x.get("id")]
            if ids:
                hits[i + j] = ids
    read: dict[str, dict] = {}
    for ids in hits.values():
        for vid in ids:
            if vid not in read and len(read) < int(k["max_advisories"]):
                read[vid] = FETCH(k["osv_vuln_url"].replace("{id}", vid), None)
    found = []
    for idx, ids in sorted(hits.items()):
        eco, name, ver = pins[idx]
        sevs = [_severity(read[v]) for v in ids if v in read]
        known = [s for s in sevs if s]
        sev = max(known, key=lambda s: RANK[s]) if known else str(k["unknown_severity"])
        fixed = next((f for f in (_fixed(read[v], name) for v in ids if v in read) if f), "")
        found.append({"key": f"dep:{eco}:{name}", "check": "deps", "sev": sev,
                      "say": say("dep", pkg=name, ver=ver, eco=eco, sev=sev.lower(), ids=", ".join(ids[:3]),
                                 fixed=say("fixed_in", v=fixed) if fixed else "")})
    return found, len(pins)


def _portal_app():
    import app as portal  # noqa: PLC0415 - the running portal (uvicorn app:app); imported only when the watch runs
    return portal.app


def _csp() -> None:
    import selfcheck_push  # noqa: PLC0415 - the one CSP rule, shared with the selfcheck
    selfcheck_push.csp_enforced(engine.run("security.headers")["headers"]["Content-Security-Policy"])


def _secrets() -> None:
    from core import secretscan  # noqa: PLC0415
    secretscan.check(ROOT)


def _routes() -> None:
    from core import routeguard  # noqa: PLC0415
    routeguard.check(_portal_app())


def _egress() -> None:
    bad = egress.ratchet_problems(ROOT)
    assert not bad, "; ".join(bad)


def _python() -> None:
    from core import pycompat  # noqa: PLC0415
    pycompat.check(ROOT)


def _drill() -> None:
    d = health.drill()
    assert d["ok"], d["say"]


CHECKS: dict[str, tuple[str, Callable[[], None]]] = {
    "secrets": ("CRITICAL", _secrets), "routes": ("HIGH", _routes), "csp": ("HIGH", _csp),
    "egress": ("HIGH", _egress), "python": ("HIGH", _python), "drill": ("MODERATE", _drill),   # the drill has its own red row
}


def run(_args: dict | None = None, ctx: dict | None = None) -> dict:
    """The agent step. A dry run only says what it will check (cheap, so Approve's seal holds); a real run checks and keeps it."""
    k = K()
    if (ctx or {}).get("preview"):
        return {"would": say("plan", n=sum((ROOT / x["file"]).is_file() for x in k["locks"]))}
    found: list[dict] = []
    try:
        dep, pkgs = deps()
        found += dep
    except Exception as e:  # noqa: BLE001 - unchecked is never clean: the reason is the finding
        pkgs = 0
        found.append({"key": "deps:unchecked", "check": "deps", "sev": "HIGH", "say": say("dep_unchecked", why=str(e)[:200])})
    for name, (sev, fn) in CHECKS.items():
        try:
            fn()
        except AssertionError as e:
            found.append({"key": f"check:{name}", "check": name, "sev": sev, "say": say("check_failed", check=name, why=str(e)[:300])})
        except Exception as e:  # noqa: BLE001 - a wall we cannot look at is not standing
            found.append({"key": f"check:{name}", "check": name, "sev": "HIGH", "say": say("check_missing", check=name, why=str(e)[:200])})
    block = [f for f in found if f["sev"] in k["block_severities"]]
    lower = [f for f in found if f not in block][:int(k["lower_shown"])]
    rec = {"at": store.now(), "checks": len(CHECKS) + 1, "packages": pkgs, "blocking": block, "lower": lower}
    store.write(k["record"], rec)
    try:
        from core import ledger  # noqa: PLC0415 - ledger imports the web layer
        ledger.security(k["ledger_kind"], "", f"{len(block)}/{len(found)}")
    except Exception:  # noqa: BLE001,S110 - a bare test has no ledger; the record above is the answer
        pass
    return {"blocking": len(block), "lower": len(lower), "packages": pkgs}


def probe(here: bool | None = None) -> dict:
    k = K()
    rec = store.read(k["record"], None)
    r = agents.recipe(k["agent"])
    if not any(agents.trigger_on(k["agent"], t) for t in r.get("triggers") or [] if t.get("kind") == "schedule"):
        return {"ok": False, "say": say("off")}
    if not isinstance(rec, dict):
        here = bool(shutil.which("systemctl")) if here is None else here
        return {"ok": not here, "say": say("never" if here else "not_here")}
    days = store.seconds_since(rec["at"]) / 86400
    each = [{"key": f["key"], "say": f["say"]} for f in rec.get("blocking") or []]
    if days > float(k["every_days"]) + float(k["grace_days"]):
        each.append({"key": "overdue", "say": say("overdue", days=int(days), every=k["every_days"])})
    return {"ok": not each, "each": each, "say": say("ok", at=rec["at"], checks=rec.get("checks", 0), pkgs=rec.get("packages", 0),
                                                       lower=len(rec.get("lower") or []))}


health.probe("watch", probe)
agents.action("securitywatch.run", run)


if __name__ == "__main__":
    import sys
    import tempfile
    from datetime import datetime, timedelta, timezone

    k = K()
    rec_key = k["record"]
    # 1. lock files are read: pip pins with hashes and extras, npm lock packages
    with tempfile.TemporaryDirectory() as t:
        tp = Path(t)
        (tp / "requirements.lock").write_text("# made\nJinja2==2.10 --hash=sha256:00\nuvicorn[standard]==0.30.0 ; python_version >= '3'\n",
                                              encoding="utf-8")
        (tp / "package-lock.json").write_text(json.dumps({"packages": {"": {"version": "1.0.0"}, "node_modules/lodash": {"version": "4.17.4"},
                                                                         "node_modules/x": {"version": "1", "link": True}}}), encoding="utf-8")
        pins = pinned(tp)
        assert pins == [("PyPI", "Jinja2", "2.10"), ("PyPI", "uvicorn", "0.30.0"), ("npm", "lodash", "4.17.4")], pins

        # 2. a known-vulnerable pin is reported HIGH (canned osv.dev answers; `--live` asks the real one)
        canned: dict[str, dict] = {"GHSA-high": {"id": "GHSA-high", "database_specific": {"severity": "HIGH"},
                                "affected": [{"package": {"name": "Jinja2"}, "ranges": [{"events": [{"introduced": "0"}, {"fixed": "2.10.1"}]}]}]},
                  "PYSEC-none": {"id": "PYSEC-none"}}

        def fake(url: str, body: dict | None) -> dict:
            if body is not None:
                return {"results": [{"vulns": [{"id": "GHSA-high"}]} if q["package"]["name"] == "Jinja2" else
                                    {"vulns": [{"id": "PYSEC-none"}]} if q["package"]["name"] == "lodash" else {} for q in body["queries"]]}
            return canned[url.rsplit("/", 1)[-1]]

        live = "--live" in sys.argv
        if not live:
            FETCH = fake
        found, n = deps(tp)
        by = {f["key"]: f for f in found}
        assert n == 3, n
        j = by.get("dep:PyPI:Jinja2")
        assert j and j["sev"] in ("HIGH", "CRITICAL"), ("a known-vulnerable pinned package was not reported High", found)
        if not live:
            assert "2.10.1" in j["say"], j
            assert by["dep:npm:lodash"]["sev"] == k["unknown_severity"], ("an advisory with no severity counted as nothing", found)
            assert "dep:PyPI:uvicorn" not in by, "a clean pin was reported"
        print(f"  watch deps: {len(found)} finding(s) from {n} pins, Jinja2 2.10 = {j['sev']}" + (" (live osv.dev)" if live else ""))

    # 3. the bar: off -> red, never ran on a server -> red, overdue -> red, a blocking finding -> its own red row, clean -> green
    store.write(rec_key, None)
    agents.set_trigger(k["agent"], "weekly", False)
    assert not probe()["ok"] and probe()["say"] == say("off"), ("the watch was off and the bar stayed green", probe())
    agents.set_trigger(k["agent"], "weekly", True)
    assert not probe(here=True)["ok"], "a server that never ran the watch looked fine"
    old = (datetime.now(timezone.utc) - timedelta(days=k["every_days"] + k["grace_days"] + 1)).isoformat(timespec="seconds")
    store.write(rec_key, {"at": old, "checks": 7, "packages": 3, "blocking": [], "lower": []})
    p = probe()
    assert not p["ok"] and any(e["key"] == "overdue" for e in p["each"]), ("an overdue watch looked fine", p)
    store.write(rec_key, {"at": store.now(), "checks": 7, "packages": 3, "blocking": [j], "lower": []})
    p = probe()
    assert not p["ok"] and [e["key"] for e in p["each"]] == ["dep:PyPI:Jinja2"], ("a High finding did not turn the bar red", p)
    store.write(rec_key, {"at": store.now(), "checks": 7, "packages": 3, "blocking": [], "lower": []})
    assert probe()["ok"], probe()
    # 4. a dry run is cheap and says what it checks; osv.dev unreachable is a blocking finding, never a clean answer
    assert "would" in run({}, {"preview": True})

    def down(url: str, body: dict | None) -> dict:
        raise OSError("network unreachable")
    FETCH = down
    CHECKS = {}
    got = run({}, {"preview": False})
    rec = store.read(rec_key, {})
    assert got["blocking"] == 1 and rec["blocking"][0]["key"] == "deps:unchecked", ("osv.dev down read as clean", rec)
    store.write(rec_key, None)
    print("  security watch: deps High reported, no-severity counted, off / never / overdue / blocking turn the bar red, "
          "unreachable osv.dev blocks OK")
