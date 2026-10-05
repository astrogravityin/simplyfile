"""Audit phase 2 test data for Sri Venkateswara Traders (AY 2026-27): two more earlier years of statements (AY 2023-24 and
2024-25, a steady ~6% a year) so each line has a history, and the year's GST returns as the portal gives them - GSTR-3B for 11
months (March missing), GSTR-1 for all 12, May's GSTR-1 higher than its GSTR-3B. Run after pre6.py. Data dir = argv[1].
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

# GST: the year's sales, spread over the months; GSTR-3B a little below the books, March's not filed; May's GSTR-1 higher
sales = sum(v for (t, i), v in now.items() if t == "PL" and i in audit.settings()["revenue_items"])
gstin = "36AAAFS1234K1Z9"
files = []
for n, mm in enumerate(["04", "05", "06", "07", "08", "09", "10", "11", "12", "01", "02", "03"]):
    y = "2025" if n < 9 else "2026"
    month = round(sales * 0.97 / 12, 2)
    if mm != "03":
        files.append((f"GSTR3B_{mm}{y}.json", json.dumps({"gstin": gstin, "ret_period": f"{mm}{y}", "sup_details": {
            "osup_det": {"txval": month, "iamt": 0, "camt": round(month * 0.09, 2), "samt": round(month * 0.09, 2), "csamt": 0},
            "osup_zero": {"txval": 0, "iamt": 0, "csamt": 0}, "osup_nil_exmp": {"txval": 0}, "osup_nongst": {"txval": 0}}}).encode()))
    r1 = month + (250000 if mm == "05" else 0)
    files.append((f"GSTR1_{mm}{y}.json", json.dumps({"gstin": gstin, "fp": f"{mm}{y}", "b2b": [{"ctin": "36AAACB0000B1Z1", "inv": [
        {"inum": f"SV/{mm}/1", "itms": [{"itm_det": {"txval": round(r1 * 0.7, 2), "camt": 0, "samt": 0, "iamt": 0}}]}]}],
        "b2cs": [{"txval": round(r1 * 0.3, 2), "camt": 0, "samt": 0}]}).encode()))
# the portal gives GSTR-1 as a zip of JSON: send them that way
z = io.BytesIO()
import zipfile  # noqa: E402

with zipfile.ZipFile(z, "w") as zf:
    for name, data in files:
        if name.startswith("GSTR1"):
            zf.writestr(name, data)
got = audit.add_gst(me, c["id"], "2026-27", [(n, d) for n, d in files if n.startswith("GSTR3B")] + [("GSTR1_FY2025-26.zip", z.getvalue())])
print("audit phase 2 data:", len(got["trend"]["history_ays"]), "earlier years,", got["added"], "GST returns,",
      got["gst"]["books_3b"], got["gst"]["r3b_1"])
