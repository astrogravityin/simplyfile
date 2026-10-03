"""Account rescue from the command line, for when nobody can get in.

There is no email server behind this portal, so there is no "forgot password" link. This is the way
back in: run it on the machine that holds `data/`, where being able to read the folder already means
you own the portal.

    python admin.py list
    python admin.py owner  chandra.s.vempati@gmail.com
    python admin.py passwd chandra.s.vempati@gmail.com
    python admin.py add    someone@example.com --name "Someone" --role member   (member | author | editor | owner)

Passwords are typed at a prompt, never passed as an argument — an argument lands in your shell
history and in `ps`.
"""
from __future__ import annotations

import getpass
import sys

import store


def _ask_password(label: str = "New password") -> str:
    first = getpass.getpass(f"{label}: ")
    confirm = getpass.getpass("Repeat it: ")
    from core import engine  # noqa: PLC0415 - the same password rules the sign-in card uses (chip auth.password_problem)
    problem = engine.run("auth.password_problem", {"password": first, "confirm": confirm, "password_lower": first.lower()})
    if problem:
        raise SystemExit(problem)
    return first


def cmd_list() -> None:
    rows = store.users()
    if not rows:
        print("No accounts yet. The first person to open the portal creates one.")
        return
    width = max(len(u["email"]) for u in rows)
    for u in rows:
        print(f'{u["email"]:<{width}}  {u.get("username", ""):<20}  {u["role"]:<6}  {u.get("name", "")}')


def cmd_owner(email: str) -> None:
    """Promote an existing account, or create it if the portal is empty."""
    email = email.strip().lower()
    with store._LOCK:                       # noqa: SLF001 - this file is part of the store's own tooling
        rows = store.users()
        u = next((x for x in rows if x["email"] == email), None)
        if u:
            u["role"] = "owner"
            store.write("users", rows)
            print(f"{email} is now an owner.")
            return
    if rows:
        raise SystemExit(f"No account for {email}. Create it with:  python admin.py add {email} --role owner")
    store.add_user(email, _ask_password(), email.split("@")[0], role="owner")
    print(f"{email} created as the owner.")


def cmd_passwd(email: str) -> None:
    store.set_password(email, _ask_password(), must_change=False)
    print(f"Password changed for {email.strip().lower()}.")


def cmd_add(email: str, name: str, role: str) -> None:
    from core import engine  # noqa: PLC0415
    roles = [r["id"] for r in engine.run("people.roles")]
    u = store.add_user(email, _ask_password(), name, role if role in roles else engine.run("people.new_account_role"))
    print(f'{u["email"]} added as {u["role"]}.')


def main(argv: list[str]) -> None:
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print(__doc__)
        return
    cmd, rest = argv[0], argv[1:]
    flag = lambda name, default="": (rest[rest.index(name) + 1]           # noqa: E731 - three flags, not a parser
                                     if name in rest and len(rest) > rest.index(name) + 1 else default)
    positional = [a for i, a in enumerate(rest)
                  if not a.startswith("--") and (i == 0 or not rest[i - 1].startswith("--"))]
    try:
        if cmd == "list":
            cmd_list()
        elif cmd == "owner":
            cmd_owner(positional[0])
        elif cmd == "passwd":
            cmd_passwd(positional[0])
        elif cmd == "add":
            cmd_add(positional[0], flag("--name"), flag("--role", "member"))
        else:
            raise SystemExit(f"Unknown command: {cmd}\n{__doc__}")
    except IndexError:
        raise SystemExit(f"{cmd} needs an email address.\n{__doc__}")
    except ValueError as e:
        raise SystemExit(str(e))


if __name__ == "__main__":
    main(sys.argv[1:])
