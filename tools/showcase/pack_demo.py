# Pack a recorded data folder as the demo snapshot: python pack_demo.py <data dir> <out.tgz>
# Drops sign-ins, codes, the portal secret, mail settings, the activity ledger and chat turns; every password becomes random
# (the owner sets real ones on the VPS with deploy/demo/account.py). Run from the repo root.
import json, secrets, shutil, sys, tarfile, tempfile
from pathlib import Path

sys.path.insert(0, ".")
from core.store import hash_password

src, out = Path(sys.argv[1]), Path(sys.argv[2])
DROP = {"sessions.json", "codes.json", "code_log.json", "tokens.json", "secret.json", "smtp.json", "ledger.sqlite3",
        "sf_chat_turns.json", "geo"}
stage = Path(tempfile.mkdtemp()) / "snap"
shutil.copytree(src, stage, ignore=lambda d, names: [n for n in names if Path(d) == src and n in DROP])
users = json.loads((stage / "users.json").read_text(encoding="utf-8"))
# 2026-10-08: a snapshot holds made-up people only. A real address (the /tax demo kept a gmail portal owner) would give
# whoever reads that inbox every Admin menu on the public demo; the demo's owner is named by the server (PORTAL_DEMO_OWNER).
MADE_UP = (".example", ".test", ".invalid", ".localhost")                                 # reserved names (RFC 2606)
OURS = {"example.com", "example.org", "example.net", "valuestream.in"}                     # reserved, and our own domain
dom = lambda u: u.get("email", "").lower().split("@")[-1]  # noqa: E731
real = [u for u in users if not (dom(u).endswith(MADE_UP) or dom(u) in OURS)]
users = [u for u in users if u not in real]
if real:
    print(f"left out {len(real)} account(s) with a real address:", ", ".join(u.get("name", "?") for u in real))
for u in users:
    u["password"] = hash_password(secrets.token_urlsafe(24))
    u["must_change_password"] = False
(stage / "users.json").write_text(json.dumps(users, indent=2), encoding="utf-8")
with tarfile.open(out, "w:gz") as t:
    for p in sorted(stage.iterdir()):
        t.add(p, arcname=p.name)
left = sorted(p.name for p in stage.iterdir())
assert not DROP & set(left), DROP & set(left)
print("packed", out, f"{out.stat().st_size // 1024} KB:", ", ".join(left), "|", len(users), "accounts, passwords random")
shutil.rmtree(stage.parent)
