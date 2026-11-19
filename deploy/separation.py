"""deploy/deploy.sh asks this before a deploy / init of a test target: is it really apart from prod? (gap audit C1-14)

    python deploy/separation.py <repo folder> <target>     exit 0 = separate (or not a guarded target), 1 = refused
    python deploy/separation.py --selftest                 the bites (selfcheck part deploy runs it)

Staging runs on the same VPS by the same script. Nothing stopped it from pointing at prod's data folder, database, mail
account, sign-in key or seal key, or from holding live payment keys - a test then writes real records or charges real
cards. Which targets are guarded, which settings may never be equal, where each target's settings are read from and
every sentence: chip deploy.separation. Folders and services: chip deploy.settings (DEPLOY_BASE / DEPLOY_SERVICE for the
target deployed, DEPLOY_<AGAINST>_BASE / _SERVICE for the other - the dry-run harness uses those).
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import settings as deploy_settings  # noqa: E402

CHIP = "deploy.separation"
_ENV_LINE = re.compile(r"^\s*(?:Environment=)?\"?([A-Za-z_][A-Za-z0-9_]*)=(.*?)\"?\s*$")


def _read_env(paths: list[str], unread: list[str]) -> dict:
    """KEY=VALUE and systemd Environment=KEY=VALUE lines of every file that exists; a later file wins (as systemd reads them)."""
    out: dict = {}
    for pattern in paths:
        for f in sorted(glob.glob(pattern)) if any(ch in pattern for ch in "*?[") else [pattern]:
            if not os.path.isfile(f):
                continue
            try:
                text = Path(f).read_text(encoding="utf-8")
            except OSError:
                unread.append(f)
                continue
            for line in text.splitlines():
                m = _ENV_LINE.match(line)
                if m and not line.lstrip().startswith(("#", "[")):
                    out[m.group(1)] = m.group(2).strip().strip('"')
    return out


def _side(c: dict, base: str, service: str, unread: list[str]) -> dict:
    files = [f.format(base=base, service=service, unit_dir=c["unit_dir"]) for f in c["env_files"]]
    env = _read_env(files, unread)
    data = Path(env.get(c["data_env"]) or Path(base) / "data")
    seal = Path(env.get(c["seal_file_env"]) or data.parent / c["seal_key_file"])
    smtp: dict = {}
    sp = data / c["smtp_file"]
    try:
        got = json.loads(sp.read_text(encoding="utf-8")) if sp.is_file() else {}
        smtp = got if isinstance(got, dict) else {}
    except OSError:
        unread.append(str(sp))
    except ValueError:
        smtp = {}
    seal_hash = ""
    try:
        seal_hash = hashlib.sha256(seal.read_bytes().strip()).hexdigest() if seal.is_file() else ""
    except OSError:
        unread.append(str(seal))
    return {"env": env, "data": os.path.normcase(os.path.realpath(data)), "seal": seal_hash,
            "smtp": tuple(str(smtp.get(k) or "").strip().lower() for k in c["smtp_fields"])}


def problems(c: dict, target: str, mine: dict, theirs: dict, unread: list[str]) -> list[str]:
    w, against = c["words"], c["against"]

    def same(what: str) -> str:
        return w["same"].format(target=target, against=against, what=what)
    bad = [w["unread"].format(path=p) for p in unread]
    if mine["data"] == theirs["data"]:
        bad.append(same(f"{c['data_env']} {mine['data']}"))
    names = set(c["same_refused"]) | {n for n in mine["env"] if n.startswith(tuple(c["same_refused_prefixes"]))}
    for n in sorted(names):
        v = mine["env"].get(n)
        if v and v == theirs["env"].get(n):
            bad.append(same(n))
    if mine["seal"] and mine["seal"] == theirs["seal"]:
        bad.append(same(c["seal_key_file"]))
    if all(mine["smtp"]) and mine["smtp"] == theirs["smtp"]:
        bad.append(same(c["smtp_file"]))
    for n, v in sorted(mine["env"].items()):
        if any(m in v for m in c["live_marks"]):
            bad.append(w["live"].format(target=target, name=n))
    return bad


def check(repo: Path, target: str) -> tuple[list[str], str]:
    c = deploy_settings._chip(repo, CHIP)  # noqa: SLF001 - the deploy folder's own reader
    if target not in c["guarded"]:
        return [], ""
    mine_s = deploy_settings.settings(repo, target)
    other = dict(deploy_settings._chip(repo)["targets"][c["against"]])  # noqa: SLF001
    for k in ("base", "service"):
        other[k] = os.environ.get(f"DEPLOY_{c['against'].upper()}_{k.upper()}") or other[k]
    unread: list[str] = []
    mine = _side(c, str(mine_s["base"]), str(mine_s["service"]), unread)
    theirs = _side(c, str(other["base"]), str(other["service"]), unread)
    bad = problems(c, target, mine, theirs, unread)
    head = c["words"]["refused" if bad else "ok"].format(target=target, against=c["against"])
    return bad, head


def _selftest() -> None:
    """Bites: each way staging can point at prod, put in once, must be refused; two apart targets pass."""
    import tempfile  # noqa: PLC0415
    c = deploy_settings._chip(Path(__file__).resolve().parent.parent, CHIP)  # noqa: SLF001
    live = "rzp_" + "live_"                                  # built, so no key scanner sees a key here
    with tempfile.TemporaryDirectory() as t:
        prod, stag = Path(t, "prod"), Path(t, "staging")
        for b in (prod, stag):
            (b / "data").mkdir(parents=True)
        (prod / "portal.env").write_text(f"PORTAL_DATABASE_URL=postgresql://p/db\nCRED_PAY_KEY_ID={live}P1\nCRED_MAIL_TOKEN=tok-prod-1\n", encoding="utf-8")
        (prod / "data" / c["smtp_file"]).write_text(json.dumps({"host": "smtp.x.org", "username": "prod@x.org"}), encoding="utf-8")
        (prod / c["seal_key_file"]).write_text("k-prod", encoding="utf-8")

        def run(env: str = "", smtp: dict | None = None, seal: str = "k-stag") -> list[str]:
            (stag / "portal.env").write_text(env, encoding="utf-8")
            mail = smtp or {"host": "smtp.x.org", "username": "test@x.org"}
            (stag / "data" / c["smtp_file"]).write_text(json.dumps(mail), encoding="utf-8")
            (stag / c["seal_key_file"]).write_text(seal, encoding="utf-8")
            u: list[str] = []
            return problems(c, "staging", _side(c, str(stag), "s", u), _side(c, str(prod), "p", u), u)

        ok = run("PORTAL_DATABASE_URL=postgresql://s/db\nCRED_PAY_KEY_ID=" + "rzp_" + "test_S1\n")
        assert ok == [], f"two apart targets were refused: {ok}"
        # each case: the reason that must be named (a case caught only by a side effect does not count)
        bites = {c["data_env"]: run(f"{c['data_env']}={prod / 'data'}\n"),
                 "PORTAL_DATABASE_URL": run("PORTAL_DATABASE_URL=postgresql://p/db\n"),
                 "CRED_MAIL_TOKEN": run("CRED_MAIL_TOKEN=tok-prod-1\n"),
                 "CRED_SHOP_SECRET": run("CRED_SHOP_SECRET=" + "sk_" + "live_9\n"),
                 c["smtp_file"]: run(smtp={"host": "SMTP.x.org", "username": "prod@x.org"}),
                 c["seal_key_file"]: run(seal="k-prod")}
        for what, bad in bites.items():
            assert any(what in b for b in bad), f"staging pointing at prod ({what}) was not refused (deploy/separation.py, chip {CHIP}): {bad}"
    print("  separation: staging pointing at prod's data, database, credentials, mail or seal key, or a live key, is refused")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--selftest"]:
        _selftest()
        sys.exit(0)
    found, line = check(Path(sys.argv[1]).resolve(), sys.argv[2] if len(sys.argv) > 2 else "")
    if line:
        print(line)
    for b in found:
        print("  - " + b)
    sys.exit(1 if found else 0)
