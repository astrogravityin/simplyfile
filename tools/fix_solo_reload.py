"""2026-10-09 owner (TradyFy): an Individual investor desk is approved the moment it is sent, but the side menu was drawn
before that, so the research screens stayed hidden until a manual refresh. Sending that lands the desk approved reloads
the portal so the menu is drawn again. Run from a portal's root (re-runnable): python tools/fix_solo_reload.py"""
from pathlib import Path

j = Path(__file__).resolve().parent.parent / "static" / "page-firm.js"   # the portal root, not the cwd (week class 41)
s = j.read_text(encoding="utf-8")
a = "        toast(r.say, 'ok'); firmPage(host);\n"
b = ("        toast(r.say, 'ok');\n"
     "        if (r.state === d.settings.working_state) { setTimeout(() => location.reload(), 900); return; }   // approved at once: redraw the menu\n"
     "        firmPage(host);\n")
if b not in s:
    assert s.count(a) == 1
    j.write_text(s.replace(a, b), encoding="utf-8")
    print("page-firm.js reload on approve")
