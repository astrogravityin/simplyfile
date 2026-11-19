"""2026-10-24 Agents (core/agents.py + core/health.py, the SteadyMove / AstroStage runtime; chips agents.*, health.*, ui.agents,
guide.agents) - boilerplate, the same in every Fy portal. Every recipe's steps are attached by a module AND described (side
effect and words); the screen and the owners' warning bar are on the shell, with a Guide me and a tour; on the real portal
the screen is the Portal Admin's alone, a dry run writes nothing, Approve does exactly what the dry run showed, and the
Daily health check's answer becomes the owners' bar. Run by the portal's selfcheck.py:

    selfcheck_agents.static_check(app); selfcheck_agents.walk(app, owner, {"me": <a signed-in client who is not the Portal Admin>})
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _chip(rel: str) -> dict:
    return {p["name"]: p["default"] for p in json.loads((HERE / rel).read_text(encoding="utf-8"))["params"]}


def static_check(app) -> None:  # noqa: ARG001 - the shared signature
    from core import access, agents, engine
    recipes = agents.recipes()
    assert "ag_health" in recipes, "the Daily health check agent is gone (chip agents.recipe.ag_health)"
    bad = {aid: agents.problems(r) for aid, r in recipes.items() if agents.problems(r)}
    assert not bad, f"an agent needs a step no module attached or chip agents.actions does not describe: {bad}"
    words = engine.run("ui.agents")
    cat = agents.catalog()
    for aid, r in recipes.items():
        assert words.get(f"name_{aid}") and words.get(f"about_{aid}"), f"{aid} has no name or about in ui.agents"
        for s in r.get("steps") or []:
            assert words.get(f"act_{s['action'].replace('.', '_')}"), f"{aid}: action {s['action']} has no words in ui.agents"
            assert (cat.get(s["action"]) or {}).get("side_effect") in ("read", "write", "external", "paid"), f"{s['action']}: no side effect"
    assert "agents" in access._BY_ID, "Agents is not on the Admin menu (core/access.py CORE_SCREENS)"  # noqa: SLF001
    # 2026-10-24 (TradyFy has its own "Agents" research screen): access.load drops a portal screen whose id is a core one, silently -
    # a portal's screen must never share a core screen's id, or its people lose it without a word
    # a row that only sets a core screen's flags ({"id": "syscheck", "hidden": true}) is a setting on that screen
    # (core/access.py load), not a screen of the portal's own
    own = {s["id"] for s in json.loads((HERE / "catalog.json").read_text(encoding="utf-8")) if set(s) - {"id", "hidden", "admin"}}
    clash = own & {s["id"] for s in access.CORE_SCREENS}
    assert not clash, f"catalog.json uses a core screen's id {sorted(clash)} - that screen would be replaced by core's; rename the portal's"
    shell = (HERE / "core" / "static" / "shell.js").read_text(encoding="utf-8")
    assert "agents: () => import('./page-agents.js')" in shell, "the shell lost the Agents screen"
    assert "${healthBanner()}" in shell and "state.health = d.health" in shell, "the owners' health bar is gone from the shell"
    g = engine.run("guide.agents")   # core's walk, or the portal's own (chips/guide.agents.json wins - a portal with its own agents adds steps)
    tour = next(iter(sorted((HERE / "tours").glob("*-agents.json"))), None)
    assert tour, "Agents has no tour (tours/<prefix>-agents.json, made from chip guide.agents)"
    says = [x["say"].replace("{product}", engine.product_name()) for x in json.loads(tour.read_text(encoding="utf-8"))["steps"]]
    assert says == [g["lede"]] + [x["say"] for x in g["steps"]], f"{tour.name} is not the Guide me walk of Agents - rebuild it from chip guide.agents"
    print(f"  agents: {len(recipes)} {'agent' if len(recipes) == 1 else 'agents'}, {len(agents.ACTIONS)} actions attached and described, "
          "screen + health bar on the shell OK")


def walk(app, c, co) -> None:
    """The real portal: the Portal Admin's screen; a dry run of the Daily health check writes nothing, Approve writes the bar."""
    from core import health, store
    assert co["me"].get("/api/core/agents").status_code == 403, "someone who is not the Portal Admin reached Agents"
    got = c.get("/api/core/agents")
    assert got.status_code == 200 and any(a["id"] == "ag_health" and not a["problems"] for a in got.json()["agents"]), got.text[:300]
    # a problem to find: a probe that fails (the check must report it in its own words, never crash)
    health.PROBES["selfcheck"] = lambda: {"ok": False, "say": "selfcheck probe"}
    try:
        store.write(health.BAR, {})
        dry = c.post("/api/core/agents/ag_health/run", json={})
        assert dry.status_code == 200, dry.text[:300]
        run = dry.json()["run"]
        assert not (store.read(health.BAR, {}) or {}).get("problems"), "a dry run changed the owners' bar"
        assert c.get("/api/bootstrap").json().get("health") is None, "the bar shows before anyone approved"
        if run.get("waiting"):
            ok = c.post("/api/core/agents/ag_health/run", json={"approve": True, "ref": run["ref"], "seal": run["seal"]})
            assert ok.status_code == 200, ok.text[:300]
        else:   # a portal whose chip lets the health check approve itself: run it for real the same way a trigger would
            from core import agents
            agents.execute("ag_health", "run", c.get("/api/bootstrap").json()["user"]["id"])
        bar = c.get("/api/bootstrap").json().get("health") or {}
        assert any(p["id"] == "selfcheck" for p in bar.get("problems") or []), ("Approve did not put the problem on the owners' bar", bar)
        assert co["me"].get("/api/bootstrap").json().get("health") is None, "the health bar shows to someone who is not the owner"
        assert c.get("/api/core/agents/ag_health/runs").json()["runs"], "History has no run"
    finally:
        health.PROBES.pop("selfcheck", None)
        store.write(health.BAR, {})
    print("  agents walk: the Portal Admin's screen, a dry run writes nothing, Approve sets the owners' health bar, History kept OK")
