"""Naming standards the self-check holds every portal to (owner 2026-11-12, "Yes, A and B" on the VS standards review).

Every rule is chip standards.naming; this file only reads text and answers with problems in plain words.

  db_problems(module, text)    tables made by CREATE TABLE in a .py file: snake_case, plural, fixed words singular (_log),
                               no abbreviated prefixes, primary key `id`, a link column `<singular table>_id`, yes/no columns
                               is_ / has_, snapshot tables `_backup_<project>_<YYYYMMDD>_<table>`
  doc_problems(names)          document file names `<project>-<topic_words>-vM_m.md` / `-YYYYMMDD.md`, a kind word last
  exception_problems(text)     every `# EXCEPTION:` block fills Standard, This project uses, Reason, Owner, Revisit
  env_problems(read, listed)   every environment variable the code reads is named in .env.example

Data kinds (where each lives): master data (people, firms, lookups) in the store or a `<thing>_master` table; transactions
as plain plural tables (`orders`); configuration in CHIPS, never a table; logs as `<thing>_log` (History, the ledger).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from core import engine

TABLE = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*\((.*?)\)\s*(?:WITHOUT\s+ROWID\s*)?;", re.I | re.S)
REF = re.compile(r"REFERENCES\s+([A-Za-z_][A-Za-z0-9_]*)", re.I)
ENV_READ = re.compile(r"""(?<!del )os\.environ(?:\.get\(\s*["']([A-Z][A-Z0-9_]+)["']|\[\s*["']([A-Z][A-Z0-9_]+)["']\s*\](?!\s*=[^=]))|os\.getenv\(\s*["']([A-Z][A-Z0-9_]+)["']""")


def K() -> dict:
    return engine.run("standards.naming")


def _parts(body: str) -> list[str]:
    """The column / constraint lines of a CREATE TABLE body, split on commas outside brackets."""
    out, depth, cur = [], 0, ""
    for ch in body:
        depth += (ch == "(") - (ch == ")")
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    return [p for p in [*out, cur.strip()] if p]


def singular(name: str, k: dict | None = None) -> str:
    for end, to in (k or K())["singular_rules"]:
        if name.endswith(end):
            return name[: len(name) - len(end)] + to
    return name


def table_problems(table: str, body: str, k: dict | None = None) -> list[str]:
    k = k or K()
    if table.startswith("_backup_"):
        return [] if re.fullmatch(k["backup_pattern"], table) else [f"{table}: snapshot name (want _backup_<project>_<YYYYMMDD>_<table>)"]
    bad = []
    if not re.fullmatch(k["name_pattern"], table):
        bad.append(f"{table}: not snake_case")
    if any(table.endswith(s) for s in k["banned_suffixes"]):
        bad.append(f"{table}: fixed word in the plural (write it singular)")
    elif not (any(table.endswith(s) for s in k["singular_suffixes"]) or any(table.endswith(e) for e in k["plural_endings"])):
        bad.append(f"{table}: not plural")
    bad += [f"{table}: abbreviated prefix {p}" for p in k["banned_prefixes"] if table.startswith(p)]
    pk = []
    for part in _parts(body):
        words = part.split()
        if not words:
            continue
        head = words[0].upper()
        if head in ("PRIMARY", "UNIQUE", "FOREIGN", "CHECK", "CONSTRAINT"):
            m = re.match(r"PRIMARY\s+KEY\s*\(([^)]*)\)", part, re.I)
            if m:
                pk = [c.strip() for c in m.group(1).split(",")]
            continue
        col = words[0].strip('"')
        if not re.fullmatch(k["name_pattern"], col):
            bad.append(f"{table}.{col}: not snake_case")
        if re.search(r"\bPRIMARY\s+KEY\b", part, re.I):
            pk = [col]
        ref = REF.search(part)
        if ref and col != singular(ref.group(1), k) + k["fk_suffix"]:
            bad.append(f"{table}.{col}: link to {ref.group(1)} (want {singular(ref.group(1), k)}{k['fk_suffix']})")
        if len(words) > 1 and words[1].upper() in k["bool_types"] and not any(col.startswith(p) for p in k["bool_prefixes"]):
            bad.append(f"{table}.{col}: yes/no column (want {' / '.join(k['bool_prefixes'])})")
    if len(pk) != 1:
        bad.append(f"{table}: no single-column primary key")
    elif pk[0] != k["pk_name"]:
        bad.append(f"{table}: primary key '{pk[0]}' (want '{k['pk_name']}')")
    return bad


def db_problems(module: str, text: str, k: dict | None = None) -> list[str]:
    """`module: problem` for every table a .py file creates; the caller drops chip db_known (the shrinking list)."""
    k = k or K()
    return [f"{module}: {p}" for t, body in TABLE.findall(text) for p in table_problems(t, body, k)]


def stale_backups(tables: list[str], today: datetime | None = None, k: dict | None = None) -> list[str]:
    """Snapshot tables older than backup_keep_days - each was meant to be deleted."""
    k, today = k or K(), today or datetime.now(timezone.utc)
    out = []
    for t in tables:
        m = re.match(r"^_backup_[a-z0-9]+_([0-9]{8})_", t)
        if m and (today - datetime.strptime(m.group(1), "%Y%m%d").replace(tzinfo=timezone.utc)).days > int(k["backup_keep_days"]):
            out.append(t)
    return out


def doc_problems(names: list[str], k: dict | None = None) -> list[str]:
    k = k or K()
    bad = []
    for n in names:
        if n in k["doc_exempt"] or not n.endswith(".md"):
            continue
        if not re.fullmatch(k["doc_pattern"], n):
            bad.append(f"{n}: want <project>-<topic_words>-vM_m.md or -YYYYMMDD.md")
        elif n.split("-")[1].split("_")[-1] not in k["doc_kinds"]:
            bad.append(f"{n}: the last topic word says its kind ({', '.join(k['doc_kinds'])})")
    return bad


def exception_problems(text: str, k: dict | None = None) -> list[str]:
    """Each '# EXCEPTION: <what>' block fills every field on the lines under it."""
    k = k or K()
    bad, lines = [], text.splitlines()
    for i, line in enumerate(lines):
        if not line.strip().startswith(k["exception_marker"]):
            continue
        what = line.strip()[len(k["exception_marker"]):].strip() or f"line {i + 1}"
        block = {}
        for nxt in lines[i + 1: i + 1 + 2 * len(k["exception_fields"])]:
            m = re.match(r"^\s*#\s*([^:]+):\s*(.*)$", nxt)
            if not m or m.group(1).strip() == k["exception_marker"].lstrip("# ").rstrip(":"):
                break
            block[m.group(1).strip()] = m.group(2).strip()
        bad += [f"exception '{what}': {f} is empty" for f in k["exception_fields"] if not block.get(f)]
    return bad


def env_read(text: str) -> set[str]:
    return {a or b or c for a, b, c in ENV_READ.findall(text)}


def env_problems(read: set[str], listed_text: str, k: dict | None = None) -> list[str]:
    k = k or K()
    listed = {ln.split("=", 1)[0].strip() for ln in listed_text.splitlines() if "=" in ln and not ln.lstrip().startswith("#")}
    return sorted(f"{v}: read by the code but not in {k['env_file']}" for v in read - listed - set(k["env_ignore"]))


def selftest() -> None:
    k = K()
    assert not table_problems("orders", "id TEXT PRIMARY KEY, customer_id TEXT REFERENCES customers(id), is_paid BOOLEAN", k)
    assert table_problems("order", "id TEXT PRIMARY KEY", k) == ["order: not plural"]
    assert table_problems("audit_logs", "id TEXT PRIMARY KEY", k) == ["audit_logs: fixed word in the plural (write it singular)"]
    assert not table_problems("audit_log", "id TEXT PRIMARY KEY", k) and not table_problems("pipeline_config", "id TEXT PRIMARY KEY", k)
    assert "cfg_items: abbreviated prefix cfg_" in table_problems("cfg_items", "id TEXT PRIMARY KEY", k)
    assert table_problems("orders", "order_id TEXT PRIMARY KEY", k) == ["orders: primary key 'order_id' (want 'id')"]
    assert table_problems("lines", "id TEXT PRIMARY KEY, ord TEXT REFERENCES orders(id)", k) == ["lines.ord: link to orders (want order_id)"]
    assert table_problems("cities", "id TEXT PRIMARY KEY, country_id TEXT REFERENCES countries(id)", k) == []
    assert table_problems("users", "id TEXT PRIMARY KEY, active BOOLEAN", k)[0].startswith("users.active: yes/no")
    assert table_problems("pairs", "a TEXT, b TEXT, PRIMARY KEY (a, b)", k) == ["pairs: no single-column primary key"]
    assert not table_problems("_backup_cf_20261112_orders", "x", k) and table_problems("_backup_orders", "x", k)
    assert stale_backups(["_backup_cf_20200101_orders", "_backup_cf_29990101_orders"], k=k) == ["_backup_cf_20200101_orders"]
    assert db_problems("m", 'x = """CREATE TABLE IF NOT EXISTS thing (id TEXT PRIMARY KEY);"""', k) == ["m: thing: not plural"]
    assert not doc_problems(["dt-framework_overview-v1_0.md", "dt-merge_review-20261104.md", "README.md"], k)
    assert doc_problems(["FRAMEWORK.md"], k) and doc_problems(["dt-framework-v1_0.md"], k) and doc_problems(["dt-x_plan-v1.0.md"], k)
    ok = "# EXCEPTION: storage\n# Standard: a\n# This project uses: b\n# Reason: c\n# Owner: d\n# Revisit: e\n"
    assert not exception_problems(ok, k)
    assert exception_problems(ok.replace("# Reason: c", "# Reason:"), k) == ["exception 'storage': Reason is empty"]
    assert env_read('os.environ.get("A_B") os.environ["CC"] os.getenv("D_E") os.environ["SET_ONLY"] = "x" del os.environ["GONE"]') == {"A_B", "CC", "D_E"}
    assert env_problems({"AA", "PATH"}, "# c\nB=1\n", k) == ["AA: read by the code but not in .env.example"]


if __name__ == "__main__":
    selftest()
    print("core.standards OK")
