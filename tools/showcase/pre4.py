"""Before part 4: Kavitha (partner) has lent Anand (reviewer) the filing of every 2026-27 return while she is away - so the firm
admin's Delegations shows a firm-wide row. Data dir = argv[1] (the running rehearsal server reads the file again on change)."""
import pathlib as _pl; _R = str(_pl.Path(__file__).resolve().parents[2])  # the repo root
import datetime
import os
import sys

os.environ["TV_DATA"] = sys.argv[1]
sys.path.insert(0, _R + r"")
os.chdir(_R + r"")
import app  # noqa: E402,F401 - registers chips and the catalog
import delegation  # noqa: E402
from core import store  # noqa: E402

us = {u.get("name"): u for u in store.users()}
kav, anand = us["Kavitha Menon"], us["Anand Murthy"]
t = datetime.date.today()
r = delegation.create(kav, {"to": anand["id"], "kind": "year_all", "ay": "2026-27", "grants": ["compute.file"], "starts": t.isoformat(),
                            "ends": (t + datetime.timedelta(days=12)).isoformat(), "note": "I am away - please file the returns once signed off"})
print("pre4:", r["say"])
