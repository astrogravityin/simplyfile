"""Set a demo site's account password (and, optionally, its email) from the VPS console - the password is typed, never echoed,
never stored anywhere but as its hash.

    sudo -u <service user> /opt/simplyfile/.venv/bin/python /opt/simplyfile/deploy/demo/account.py /opt/simplyfile-demo/tax/data you@x.com
    ... account.py <data dir> <current email> --new-email someone@valuestream.in
    ... account.py <data dir> <email> --generate     (no typing: prints a one-time password, changed at first sign-in)
"""
import getpass
import os
import sys

if len(sys.argv) < 3:
    sys.exit(__doc__)
os.environ["PORTAL_DATA"] = sys.argv[1]
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
import store  # noqa: E402,F401 - registers this portal's chips
from core import auth, store as cs  # noqa: E402

email = sys.argv[2].strip().lower()
u = cs.find_user(email)
if not u:
    sys.exit(f"No account {email} in {sys.argv[1]}")
if "--new-email" in sys.argv:
    new = sys.argv[sys.argv.index("--new-email") + 1].strip().lower()
    auth.check_fields(email=new)
    with cs._LOCK:  # noqa: SLF001 - the framework's own users file
        rows = cs.users()
        for x in rows:
            if x["id"] == u["id"]:
                x["email"] = new
        cs.write("users", rows)
    email = new
if "--generate" in sys.argv:
    # For a console that cannot take typed input (VPS Console Terminal tab): a one-time password, printed once, that
    # must be changed at the first sign-in - so the printed one stops working as soon as it is used.
    import secrets  # noqa: PLC0415
    pw = secrets.token_urlsafe(12)
    cs.set_password(email, pw, must_change=True)
    cs.end_sessions_for(u["id"])
    print(f"Done: {email} one-time password: {pw}\nSign in with it once; the portal then asks for your own password.")
    sys.exit(0)
pw = getpass.getpass(f"New password for {email}: ")
if pw != getpass.getpass("Again: "):
    sys.exit("The two did not match - nothing changed.")
auth.check_fields(password=pw, confirm=pw, known_user=u.get("username", ""))
cs.set_password(email, pw, must_change=False)
cs.end_sessions_for(u["id"])
print(f"Done: {email} has its new password; its old sessions are signed out.")
