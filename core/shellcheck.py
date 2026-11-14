"""The portal shell's own guard, carried with core into every portal (each portal's selfcheck runs `python -m core.shellcheck`,
and so does System checks).

1. Every page script parses as an ES module (2026-11-14: a stray ')' in CodyFy page-requests.js killed every signed-in screen with
   "Missing } in template expression", and its selfcheck had no parse step). node --check on a bare .js says nothing for a broken
   ES module, so each file is checked through a .mjs copy. No node = a failure, never a silent pass.
2. The shell offers Side pane / Top menu (2026-11-14 owner: "change the Side Pane to Top Menu in all the site"): chip shell.nav,
   its words in ui.shell, the bootstrap carries it, shell.js draws one menu in both shapes, portal.css has the top shape.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "core"


def scripts() -> list[Path]:
    """The portal's own page scripts and core's - never a bundled build (connect-plus chunks)."""
    return [f for d in (ROOT / "static", CORE / "static") if d.is_dir()
            for f in sorted(d.rglob("*.js")) if "connect-plus" not in f.parts and "node_modules" not in f.parts]


def parse_problems(files: list[Path]) -> list[str]:
    node = shutil.which("node")
    if not node:
        return ["node is not installed - the page scripts cannot be parsed (install node; an unparsed script is never clean)"]
    bad = []
    with tempfile.TemporaryDirectory() as tmp:
        mjs = Path(tmp) / "check.mjs"
        for f in files:
            mjs.write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
            r = subprocess.run([node, "--check", str(mjs)], capture_output=True, text=True)
            if r.returncode:
                why = [ln for ln in r.stderr.splitlines() if "Error" in ln] or r.stderr.strip().splitlines() or ["?"]
                bad.append(f"{f.relative_to(ROOT).as_posix()} does not parse: {why[0][:200]}")
    return bad


def chip(cid: str) -> dict:
    p = CORE / "chips" / f"{cid}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def nav_problems() -> list[str]:
    out = []
    knobs = {p["name"]: p.get("default") for p in chip("shell.nav").get("params", [])}
    layouts = knobs.get("layouts") or []
    if not {"side", "top"} <= set(layouts):
        out.append("chip shell.nav must offer the layouts side and top")
    if knobs.get("default_layout") not in layouts:
        out.append("chip shell.nav default_layout must be one of its layouts")
    words = {p["name"] for p in chip("ui.shell").get("params", [])}
    out += [f"chip ui.shell lacks the word {w}" for w in ["nav_layout"] + [f"nav_{x}" for x in layouts] if w not in words]
    if 'engine.run("shell.nav")' not in (CORE / "auth.py").read_text(encoding="utf-8"):
        out.append("core/auth.py bootstrap must carry chip shell.nav")
    shell = (CORE / "static" / "shell.js").read_text(encoding="utf-8")
    for need, why in (("const navLayout = () =>", "the person's pick"), ("${navRow()}", "the Menu row in the user menu"),
                      ("wireNavGroups(root);", "the top menu's group buttons"), ("${top ? 'top' : ''}", "the shell's top class"),
                      ("navGroupBadge(a.closest('.ng'))", "a balloon still counts on a shut group")):
        if need not in shell and not (need.startswith("navGroupBadge") and "export function setBadge" not in shell):
            out.append(f"core/static/shell.js lost {why} ({need})")
    if "export function choicePicker" not in (CORE / "static" / "ui.js").read_text(encoding="utf-8"):
        out.append("core/static/ui.js lost choicePicker")
    if not re.search(r"\.shell\.top \.ng-items\{", (CORE / "static" / "portal.css").read_text(encoding="utf-8")):
        out.append("core/static/portal.css lost the top menu's shape (.shell.top)")
    return out


if __name__ == "__main__":
    problems = nav_problems() + parse_problems(scripts())
    assert not problems, "shell check:\n  " + "\n  ".join(problems)
    print(f"shell check: Side pane / Top menu offered, {len(scripts())} page scripts parse OK")
