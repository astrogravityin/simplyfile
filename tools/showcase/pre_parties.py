"""The party master in the demo (2026-10-05 owner: "yes" to demo data for 3CD from a party master). Sri Venkateswara Traders
(AY 2026-27) gets its loans and related-party statement the way CAs write it - each party's name, then its address and PAN on
the lines below - tagged 3CD 31(a) / 3CD 23, and Fill from statements run, so its party master holds every party and the
Form 3CB-3CD JSON carries their addresses and PANs. One lender's PAN is missing on purpose: the CA types it once in the master.
Run on a data dir after the showcase parts (record_all.sh does): python pre_parties.py <data dir>. Demo figures, not a real client's."""
import pathlib as _pl; _R = str(_pl.Path(__file__).resolve().parents[2])  # the repo root
import io
import os
import sys

os.environ["TV_DATA"] = os.environ["PORTAL_DATA"] = sys.argv[1]
sys.path.insert(0, _R)
os.chdir(_R)
import app  # noqa: E402,F401 - registers chips and the catalog
import clients  # noqa: E402
import intake  # noqa: E402
import itr_json  # noqa: E402
from core import store  # noqa: E402
from openpyxl import Workbook  # noqa: E402

AY = "2026-27"
NAME = "Sri Venkateswara Traders - Loans and related parties AY 2026-27.xlsx"
c = next(x for x in clients._all() if x["name"].startswith("Sri Venkateswara"))  # noqa: SLF001
me = next(u for u in store.users() if u.get("firm_id") == c.get("firm_id") and u.get("firm_role") == "firm_admin")
if any(f["name"] == NAME for f in intake.files(c["id"], AY)["files"]):
    sys.exit(f"pre_parties: {NAME} is there already")

# (name, address, PAN, accepted, repaid, squared up, maximum outstanding, otherwise than account payee)
LENDERS = [("Smt Padmavathi Rao", "Dilsukhnagar, Hyderabad", "ABMPR2201K", 1500000, 0, "No", 1500000, "No"),
           ("Sri Raghavendra Rao, HUF", "Dilsukhnagar, Hyderabad", "AAJHR3302L", 2500000, 500000, "No", 2500000, "No"),
           ("Kiran Kumar Gupta", "Kukatpally, Hyderabad", "BCKPG4403M", 1000000, 1000000, "Yes", 1000000, "No"),
           ("Anitha Reddy", "Banjara Hills, Hyderabad", "BFAPR5504N", 800000, 0, "No", 1200000, "No"),
           ("Sri Sai Agencies", "Secunderabad", "AAKFS6605P", 3000000, 1200000, "No", 3000000, "No"),
           ("Venkat Narayana Murthy", "Ameerpet, Hyderabad", "", 600000, 0, "No", 600000, "No"),
           ("Lalitha Devi Chowdary", "Miyapur, Hyderabad", "CDLPC7706Q", 1200000, 0, "No", 1800000, "No"),
           ("Ramana Murthy Sastry", "Tarnaka, Hyderabad", "AGRPS8807R", 900000, 300000, "No", 900000, "No"),
           ("Bhaskar Rao Naidu", "Uppal, Hyderabad", "BHBPN9908S", 1100000, 0, "No", 1100000, "No"),
           ("Sunitha Agarwal", "Begumpet, Hyderabad", "AFSPA1109T", 700000, 0, "No", 700000, "No")]
RELATED = [("Smt Lakshmi Rao", "Wife of partner", "Banjara Hills, Hyderabad", "ABCPR9911K", "Interest on loan", 180000),
           ("Ravi Teja Rao", "Son of partner", "Banjara Hills, Hyderabad", "BRTPR2212U", "Salary", 360000),
           ("Sri Raghavendra Rao, HUF", "HUF of partner", "Dilsukhnagar, Hyderabad", "AAJHR3302L", "Interest on loan", 300000)]

wb = Workbook()
ws = wb.active
ws.title = "Parties"
ws.append(["Sri Venkateswara Traders"]); ws.append(["P.A.No.", "AAFFS4721M"]); ws.append(["Asst. Year", AY]); ws.append([])  # noqa: E702
ws.append(["", "Statement regarding payments to persons specified u/s 40A(2)(b)"]); ws.append([])  # noqa: E702
ws.append(["Sl.No.", "Name and address of the party", "Amount", "Nature of payment", "Relationship"])
at = {}
for i, (n, rel, addr, pan, nature, amt) in enumerate(RELATED, 1):
    ws.append([i, n, amt, nature, rel]); at[(n, "23")] = ws.max_row  # noqa: E702
    ws.append(["", addr]); ws.append(["", pan])  # noqa: E702
ws.append([]); ws.append([])  # noqa: E702
ws.append(["", "Statement regarding loans or deposits accepted (Form 3CD clause 31)"]); ws.append([])  # noqa: E702
ws.append(["Sl", "Name & address of the lender / depositor", "Amount accepted", "Amount repaid", "Whether squared up during the year",
           "Maximum amount outstanding", "Whether accepted otherwise than through account payee cheque or draft"])
for i, (n, addr, pan, acc, rep, sq, mx, oth) in enumerate(LENDERS, 1):
    ws.append([i, n, acc, rep, sq, mx, oth]); at[(n, "31(a)")] = ws.max_row  # noqa: E702
    ws.append(["", addr])
    if pan:
        ws.append(["", pan])
ws.column_dimensions["B"].width = 44
buf = io.BytesIO()
wb.save(buf)

f = intake.add(me, c["id"], AY, NAME, buf.getvalue())
keys = {x["row"]: x["key"] for x in intake.view(c["id"], AY, f["id"])["rows"]}
tags = {keys[row]: f"3CD {cl}" for (n, cl), row in at.items()}       # a 31(a) row repaid in the year is a repayment by itself
intake.set_tags(me, c["id"], AY, f["id"], tags)
got = clients.learn_parties(me, c["id"], itr_json.statement_parties(c["id"], AY))
doc, rep = itr_json.build(c["id"], AY, "tar")
f3 = next(iter(doc.values()))
f3 = next(iter(f3.values()))
lenders = f3.get("Form3cdAmtSec269ssDetail") or []
assert sum(1 for x in lenders if x.get("LenderAddress") not in ("", "-")) >= len(LENDERS), "every lender has its address"
print(f"pre_parties: {got['added']} parties in the master; 3CD JSON: {len(lenders)} loans, "
      f"{len(f3.get('Form3cdAmtSec269tDetail') or [])} repayments, {len(f3.get('Form3cdPymtSec40a2bDetail') or [])} related payments")
