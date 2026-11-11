"""deploy/deploy.sh asks this for its settings: chip deploy.settings for one target, as shell lines.

    python deploy/settings.py <repo folder> <target>   ->   DEPLOY_BASE='/opt/simplyfile' ...

The chip is read through the engine (so an edit made in Ops & chips, kept in the data layer, wins); a checkout without
the engine reads the chip file's defaults. For one run any value can be overridden by an environment variable
DEPLOY_<NAME> (DEPLOY_BASE, DEPLOY_PORT, DEPLOY_KEEP_RELEASES, ...). Nothing here holds a value of its own.
"""
from __future__ import annotations

import json
import os
import shlex
import sys
from pathlib import Path

CHIP = "deploy.settings"


def _chip(repo: Path) -> dict:
    try:
        sys.path.insert(0, str(repo))
        from core import engine  # noqa: PLC0415
        engine.register_dir(repo / "chips")
        return engine.run(CHIP)
    except Exception:  # noqa: BLE001 - no engine here (a bare checkout): the chip file's own defaults
        chip = json.loads((repo / "chips" / f"{CHIP}.json").read_text(encoding="utf-8"))
        return {p["name"]: p.get("default") for p in chip["params"]}


def settings(repo: Path, target: str | None) -> dict:
    got = _chip(repo)
    name = target or os.environ.get("DEPLOY_TARGET") or got["default_target"]
    targets = got.pop("targets")
    if name not in targets:
        raise SystemExit(f"deploy: no target {name!r} in chip {CHIP} (have: {', '.join(targets)})")
    flat = {"target": name, **got, **targets[name]}
    for key in list(flat):
        env = os.environ.get(f"DEPLOY_{key.upper()}")
        if env is not None and key != "target":
            flat[key] = env
    return flat


def shell(values: dict) -> str:
    out = []
    for key, val in values.items():
        if isinstance(val, bool):
            val = "1" if val else ""
        elif isinstance(val, list):
            val = " ".join(str(v) for v in val)
        out.append(f"DEPLOY_{key.upper()}={shlex.quote(str(val))}")
    return "\n".join(out)


if __name__ == "__main__":
    print(shell(settings(Path(sys.argv[1]).resolve(), sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None)))
