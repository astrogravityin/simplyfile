"""Saves the rule book as a file, to send a CA a copy (2026-10-06). Run from D:/Simplyfile:  python tools/rulebook.py
You do not need this to keep it current - the portal builds it fresh each time (Filing > Tax rules > Rule book)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import store  # noqa: E402,F401 - registers the portal's chips
import rulebook  # noqa: E402

OUT = ROOT / "docs" / "rulebook.html"
if __name__ == "__main__":
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(rulebook.build(), encoding="utf-8")
    print("wrote", OUT)
