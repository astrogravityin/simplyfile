"""Demo GST returns for Sri Venkateswara Traders, FY 2025-26, as the portal gives them, for part 8's live upload:
GSTR-3B JSON for April-February (March not filed) and GSTR-1 for all twelve months in one zip; May's GSTR-1 is Rs 2.5 lakh higher
than its GSTR-3B. Each month's taxable value is 97% of a twelfth of the books' Rs 3.2 crore turnover. Demo figures only.
-> tools/tour_video/showcase/c3/gst/"""
import pathlib as _pl; _R = str(_pl.Path(__file__).resolve().parents[2])  # the repo root
import io
import json
import zipfile
from pathlib import Path

OUT = Path(_R + r"\tools\tour_video\showcase\c3\gst")
OUT.mkdir(parents=True, exist_ok=True)
for f in OUT.iterdir():
    f.unlink()
SALES, GSTIN = 32000000, "36AAAFS1234K1Z9"
z = io.BytesIO()
with zipfile.ZipFile(z, "w") as zf:
    for n, mm in enumerate(["04", "05", "06", "07", "08", "09", "10", "11", "12", "01", "02", "03"]):
        y = "2025" if n < 9 else "2026"
        month = round(SALES * 0.97 / 12, 2)
        if mm != "03":
            (OUT / f"GSTR3B_{GSTIN}_{mm}{y}.json").write_text(json.dumps({"gstin": GSTIN, "ret_period": f"{mm}{y}", "sup_details": {
                "osup_det": {"txval": month, "iamt": 0, "camt": round(month * 0.09, 2), "samt": round(month * 0.09, 2), "csamt": 0},
                "osup_zero": {"txval": 0, "iamt": 0, "csamt": 0}, "osup_nil_exmp": {"txval": 0}, "osup_nongst": {"txval": 0}}}))
        r1 = month + (250000 if mm == "05" else 0)
        zf.writestr(f"GSTR1_{GSTIN}_{mm}{y}.json", json.dumps({"gstin": GSTIN, "fp": f"{mm}{y}", "b2b": [{"ctin": "36AAACB0000B1Z1", "inv": [
            {"inum": f"SV/{mm}/1", "itms": [{"itm_det": {"txval": round(r1 * 0.7, 2), "camt": 0, "samt": 0, "iamt": 0}}]}]}],
            "b2cs": [{"txval": round(r1 * 0.3, 2), "camt": 0, "samt": 0}]}))
(OUT / f"GSTR1_{GSTIN}_FY2025-26.zip").write_bytes(z.getvalue())
print("gst demo files:", sorted(f.name for f in OUT.iterdir()))
