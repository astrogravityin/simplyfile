"""Before part 8 (audit phase 2) - test data for Sri Venkateswara Traders (AY 2026-27): two more earlier years of statements (AY 2023-24 and
2024-25, a steady ~6% a year) so each line has a history. Run after pre6.py. Data dir = argv[1].
Demo figures, not a real client's."""
import pathlib as _pl; _R = str(_pl.Path(__file__).resolve().parents[2])  # the repo root
import io
import json
import os
import sys

os.environ["TV_DATA"] = os.environ["PORTAL_DATA"] = sys.argv[1]
sys.path.insert(0, _R + r"")
os.chdir(_R + r"")
import app  # noqa: E402,F401 - registers chips and the catalog
import audit  # noqa: E402
import clients  # noqa: E402
import intake  # noqa: E402
from core import store  # noqa: E402
from openpyxl import Workbook  # noqa: E402

c = next(x for x in clients._all() if x["name"].startswith("Sri Venkateswara"))  # noqa: SLF001
me = next(u for u in store.users() if u.get("firm_id") == c.get("firm_id") and u.get("firm_role") == "firm_admin")
now, col = audit.figures(c["id"], "2026-27")      # col: last year (AY 2025-26), the previous-year column pre6.py added
itr = c["years"]["2026-27"]["form"].replace("-", "")
# the two years before last: most lines ~6% a year below last year; rent, interest and unsecured loans were flat until this year
FLAT = {("PL", "rent"), ("PL", "interest"), ("BS", "unsecured_other")}
for ay, back in [("2023-24", 3), ("2024-25", 2)]:
    clients.set_year(me, c["id"], ay, {"form": c["years"]["2026-27"]["form"]})
    wb = Workbook()
    ws = wb.active
    ws.append([f"Final accounts, AY {ay}"])
    ws.append(["Particulars", "Amount (Rs)", "SF Ref"])
    for (table, item), v in sorted(col.items()):
        r = (0.98 if back == 3 else 1) if (table, item) in FLAT else 1.06 ** -(back - 1)
        ws.append([item.replace("_", " ").capitalize(), round(v * r, -3), f"{itr} {table} {item}"])
    buf = io.BytesIO()
    wb.save(buf)
    intake.add(me, c["id"], ay, f"Final accounts {ay}.xlsx", buf.getvalue())

print("pre8: earlier years", [ay for ay in ("2023-24", "2024-25") if ay in clients.get(c["id"])["years"]])
