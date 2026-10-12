"""2026-10-11 owner "I lost all the demo data": a demo seat kept in the snapshot pointed at a firm an older snapshot had,
so that visitor sat in no firm and saw nothing. Every code sign-in now runs the seaters, and seat_demo re-seats only a
seat whose firm is gone. Run from a portal's root (re-runnable): python tools/fix_demo_reseat.py"""
from pathlib import Path


def patch(path, a, b):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    if b in s:
        return
    assert s.count(a) == 1, (path, a[:60])
    p.write_text(s.replace(a, b), encoding="utf-8")
    print("patched", path)


patch("firms.py",
      '    """A demo visitor\'s new account joins the demo firm (chip demo.host) - core/demo.py calls this once per visitor."""\n'
      '    k = engine.run("demo.host")',
      '    """A demo visitor\'s account joins the demo firm (chip demo.host) - core/demo.py calls this at each code sign-in.\n'
      '    2026-10-11 owner "I lost all the demo data": a seat kept in the snapshot pointed at a firm an older snapshot had, so\n'
      '    the visitor sat in no firm and saw nothing. A seat whose firm still exists is left alone; any other is re-seated."""\n'
      '    if u.get("firm_id") and any(x.get("id") == u["firm_id"] for x in _all()):\n'
      '        return\n'
      '    k = engine.run("demo.host")')
patch("core/demo.py",
      "        for seat in SEATERS:\n            seat(u)\n        u = store.find_user(email)\n    return auth._sign_in",
      "    for seat in SEATERS:   # every sign-in: a seat left pointing at a firm the snapshot no longer has is put back (2026-10-11)\n"
      "        seat(u)\n    u = store.find_user(email)\n    return auth._sign_in")
