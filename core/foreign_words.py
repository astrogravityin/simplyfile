"""Another domain's words never show in this portal (2026-11-11 owner, GamyFyStudio History: "What Game has to do with 26 AS").

The boilerplate came from the tax portal; its words rode into every portal's shared screens. Which words and where people read
them: chip words.foreign (a portal whose domain they are overrides it with an empty list). Chip JSON: every string a person can
read (description_nl and the chip's own list skipped); JS: everything but comment lines. `python -m core.foreign_words` fails
naming each file:line."""
from __future__ import annotations

import json
import re
from pathlib import Path

from core import engine

HERE = Path(__file__).resolve().parent.parent
SKIP_KEYS = {"description_nl", "_comment", "chip_id", "aliases"}


def _strings(v, key=""):
    if isinstance(v, str):
        if key not in SKIP_KEYS:
            yield v
    elif isinstance(v, dict):
        for k, x in v.items():
            yield from _strings(x, k)
    elif isinstance(v, list):
        for x in v:
            yield from _strings(x, key)


def found() -> list[str]:
    c = engine.run("words.foreign")
    words = [w.strip() for w in str(c["words"]).split(",") if w.strip()]
    if not words:
        return []
    pat = re.compile("|".join(rf"\b{re.escape(w)}\b" if w.isupper() or any(ch.isdigit() for ch in w) else rf"(?i:\b{re.escape(w)}\b)"
                              for w in words))
    hits = []
    for g in [x.strip() for x in str(c["places"]).split(",") if x.strip()]:
        for p in sorted(HERE.glob(g)):
            if p.name == "words.foreign.json":
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            if p.suffix == ".json":
                try:
                    lines = list(_strings(json.loads(text)))
                except ValueError:
                    continue
                hits += [f"{p.relative_to(HERE)}: {m.group(0)!r} in {s[:70]!r}" for s in lines if (m := pat.search(s))]
            else:
                for i, ln in enumerate(text.splitlines()):
                    t = ln.strip()
                    if t.startswith(("//", "/*", "*", "#")):
                        continue
                    if m := pat.search(ln):
                        hits.append(f"{p.relative_to(HERE)}:{i + 1}: {m.group(0)!r}")
    return hits


if __name__ == "__main__":
    import store  # noqa: F401 - loads the portal's chips (and its own words.foreign, if it has one)
    bad = found()
    assert not bad, "another domain's words where people read them (chip words.foreign):\n  " + "\n  ".join(bad[:30])
    print("foreign words: none")
