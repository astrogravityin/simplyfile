"""Before part 6 (Tax audit): Sri Venkateswara Traders's books for AY 2026-27 come again, as final accounts usually do - with
last year's column beside this year's - so the audit screen has a last year to stand against (AY 2025-26 is filed and closed).
This year's figures are unchanged (same tagged lines, same totals); last year is about 6% lower, with the movements an auditor
should catch: rent and interest nearly doubled, unsecured loans tripled, creditors up two-thirds, travel up 65%, advertisement
new this year, a donation gone. The file carries its own SF Ref column, so every row arrives tagged. Data dir = argv[1].
Demo figures, not a real client's."""
import pathlib as _pl; _R = str(_pl.Path(__file__).resolve().parents[2])  # the repo root
import io
import os
import sys

os.environ["TV_DATA"] = sys.argv[1]
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
now, _ = audit.figures(c["id"], "2026-27")
itr = c["years"]["2026-27"]["form"].replace("-", "")      # ITR3 / ITR5, as the refs are written
books = next(m for m in intake.files(c["id"], "2026-27")["files"] if any(r["state"] == "tagged" and ("PL" in r["ref"] or "BS" in r["ref"])
                                                                       for r in intake.view(c["id"], "2026-27", m["id"])["rows"]))
# last year as a share of this year: most lines 1/1.06; these move the way an auditor should notice
RATIO = {("PL", "rent"): 0.53, ("PL", "interest"): 0.5, ("BS", "unsecured_other"): 0.31, ("BS", "creditors"): 0.6,
         ("PL", "travel"): 0.6, ("PL", "salaries"): 0.62, ("PL", "advertisement"): 0, ("PL", "sales"): 0.93}
wb = Workbook()
ws = wb.active
ws.title = "Final accounts"
ws.append(["Final accounts for the year ended 31.03.2026 (AY 2026-27)"])
ws.append(["Particulars", "Amount (Rs)", "Previous year (Rs)", "SF Ref"])
for (table, item), v in sorted(now.items()):
    ws.append([item.replace("_", " ").capitalize(), v, round(v * RATIO.get((table, item), 1 / 1.06), -3), f"{itr} {table} {item}"])
ws.append(["Donation", 0, 150000, f"{itr} PL donation"])
buf = io.BytesIO()
wb.save(buf)
intake.add(me, c["id"], "2026-27", books["name"], buf.getvalue(), replace=books["id"])
tr = audit.trend(c["id"], "2026-27")
print("pre6:", tr["source"], "lines", len(tr["rows"]), "flagged", [(x["item"], x["flag"]) for x in tr["rows"] if x["flag"]])
