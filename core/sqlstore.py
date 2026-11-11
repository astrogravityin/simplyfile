"""A domain's high-volume records in SQLite or Postgres, with History - the store a portal uses when JSON stops fitting.

The framework keeps people, organisations and settings in JSON (core/store.py). A domain whose records are many,
relational or money-bearing (orders, carts, price slabs, ledgers) keeps them here instead. Chip store.engine decides where:
  sqlite (the default)  one file per domain, `data/<db>.sqlite3`, Python's own sqlite3, WAL, foreign keys on
  postgres              each db its own schema (store.engine schema_prefix + db) in the database whose connection string is
                        in the environment variable the chip names (url_env) - never in a chip or a file. psycopg 3 is
                        imported only then. `dbs` moves one db at a time.
Every save goes through `save()`, which reads the old row, writes the new one in a transaction, and then tells the same
watchers core/store.py tells - so changelog.py writes History (field, old -> new, when, who) for these rows exactly as for
JSON lists. Name a watch row's pattern `^sql/<db>/<table>$` with list_key "id" in chip changes.watch.

    sqlstore.register("shop", SCHEMA, steps=[(1, "ALTER TABLE ...")])   # once, at import: CREATE TABLE IF NOT EXISTS ...
    sqlstore.save("shop", "orders", {"id": "o1", "org_id": "f1", "stage": "open"})
    sqlstore.rows("shop", "SELECT * FROM orders WHERE org_id = ? AND stage = ?", ("f1", "open"))
    sqlstore.archive("shop", "orders", "o1")                # nothing is deleted: archived_at is set, restore clears it

One SQL for both engines: `?` placeholders (turned into %s for Postgres), COALESCE not IFNULL, LOWER(col) not COLLATE
NOCASE, ON CONFLICT DO NOTHING not INSERT OR IGNORE, json_text() for a JSON field. Chip store.engine sqlite_only lists the
words that fail selfcheck 'store'. Versioned migrations: register(..., steps=[(n, "SQL"), ...]) - each numbered step runs
once, in order, in its own transaction, recorded in the db's _migrations table; a failing step rolls back and stops.
Move a SQLite db into Postgres with `python -m core.sqlstore move <db> --to postgres` (dry run; --apply copies and checks).

Tenant wall: every table that belongs to an organisation carries org_id, and every read the domain makes filters on
it (the domain module's job, as clients._mine is for JSON). Table and column names are checked against IDENT so a
name can never carry SQL; values always travel as parameters.

ponytail: SQLite = one connection per call (short transactions, the file is never held open). Postgres = a few kept
connections (pool_max), since a new one costs a round trip and a login.
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
import re
import sqlite3
import sys
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

from . import engine, store

IDENT = re.compile(r"^[a-z][a-z0-9_]{0,40}$")
PREFIX = re.compile(r"^[a-z0-9_]{0,20}$")
JSON_KEY = re.compile(r"^[\w .-]{1,60}$")
MIGRATIONS = "_migrations"
IntegrityError = sqlite3.IntegrityError     # what a refused save raises on either engine
_SCHEMA: dict[str, str] = {}
_ADD: dict[str, dict] = {}
_STEPS: dict[str, list] = {}
_READY: set = set()
_OVER: dict = {}                             # configure(): a test or the move tool overrides the chip
_POOL: list = []
_POOL_LOCK = threading.Lock()
_COLS: dict = {}                             # (schema, table) -> column names (Postgres; cleared by register)


def cfg() -> dict:
    return engine.run("store.engine") | _OVER


def configure(**over) -> None:
    """Override chip store.engine knobs in this process (tests, the move tool, a benchmark); configure() resets."""
    _OVER.clear()
    _OVER.update(over)
    _READY.clear()
    _TEXT.clear()
    _COLS.clear()
    close_pool()


def _say(key: str, **v) -> str:
    return cfg()["words"][key].format(**v)


def kind(db: str) -> str:
    """'postgres' or 'sqlite' for this db, from chip store.engine."""
    c = cfg()
    return "postgres" if c["engine"] == "postgres" and (not c["dbs"] or db in c["dbs"]) else "sqlite"


def schema(db: str) -> str:
    p = str(cfg()["schema_prefix"] or "")
    if not PREFIX.match(p):
        raise ValueError(f"bad schema_prefix {p!r}")
    return p + db


def path(db: str):
    return store.DATA / f"{db}.sqlite3"


def register(db: str, ddl: str, add: dict | None = None, steps: list | None = None) -> None:
    """The domain's tables, as CREATE TABLE IF NOT EXISTS statements; applied on the first connection.
    `add` = {table: {column: "TYPE DEFAULT ..."}}: columns a later version added - a database made before them gets each
    one once (ALTER TABLE ADD COLUMN), so live data never needs a hand-run migration (2026-11-03, Shoperative's orders
    gained city, pincode and the wallet credit used). Nothing is ever dropped or renamed by `add`.
    `steps` = [(1, "SQL; SQL"), (2, "SQL")...]: versioned migrations for anything `add` cannot do (a rename, a backfill, an
    index, a new table that needs data). Each runs once, in number order, after the DDL and `add`, in its own transaction,
    and is recorded in the db's _migrations table; one that fails rolls back and stops (later steps wait). A step that
    has run is never edited - add the next number."""
    if not IDENT.match(db):
        raise ValueError(f"bad db name {db!r}")
    for table, cols in (add or {}).items():
        _check(table, *cols)
    steps = [(int(n), str(s)) for n, s in (steps or [])]
    if [n for n, _ in steps] != sorted({n for n, _ in steps}) or any(n < 1 or not s.strip() for n, s in steps):
        raise ValueError(f"{db}: migration steps need numbers 1, 2, 3... in order, each once, each with SQL")
    _SCHEMA[db] = ddl
    _ADD[db] = add or {}
    _STEPS[db] = steps
    _READY.clear()
    for k in [k for k in _COLS if k[0].endswith(db)]:
        _COLS.pop(k, None)


# ---- SQL text: one dialect in, the engine's out ----------------------------------------------------------------------

def _outside_quotes(sql: str):
    """(piece, quoted) runs of the SQL text, so a rewrite never touches a string literal."""
    out: list = []
    buf: list[str] = []
    q = False
    for ch in sql:
        if ch == "'":
            if not q and buf:
                out.append(("".join(buf), False))
                buf = []
            buf.append(ch)
            if q:
                out.append(("".join(buf), True))
                buf = []
            q = not q
        else:
            buf.append(ch)
    if buf:
        out.append(("".join(buf), q))
    return out


@functools.lru_cache(maxsize=512)
def _pg_sql(sql: str) -> str:
    """`?` -> %s outside string literals; a literal % doubled (psycopg reads % as a placeholder everywhere)."""
    return "".join(p.replace("%", "%%") if q else p.replace("%", "%%").replace("?", "%s") for p, q in _outside_quotes(sql))


def _pg_ddl(sql: str) -> str:
    """The same DDL on Postgres: column types per chip store.engine pg_types (SQLite INTEGER is 64-bit)."""
    types = cfg()["pg_types"]
    pat = re.compile(r"\b(" + "|".join(map(re.escape, types)) + r")\b", re.I) if types else None
    return "".join(p if q or not pat else pat.sub(lambda m: types[m.group(1).upper()], p) for p, q in _outside_quotes(sql))


def statements(script: str) -> list[str]:
    """A script split on ; outside string literals."""
    out, cur = [], []
    for p, q in _outside_quotes(script):
        if q:
            cur.append(p)
            continue
        parts = p.split(";")
        for i, part in enumerate(parts):
            cur.append(part)
            if i < len(parts) - 1:
                out.append("".join(cur))
                cur = []
    out.append("".join(cur))
    return [s.strip() for s in out if s.strip()]


_TEXT: dict = {}                             # (db key, table, column) -> "fts" / "trgm" / ""


def text_index(db: str, table: str, column: str) -> str:
    """A "word anywhere" index on one text column, made once: SQLite = an FTS5 trigram table kept by triggers ("fts"),
    Postgres = a pg_trgm GIN index, which serves LIKE '%word%' itself ("trgm"). "" = none here (LIKE scans). A table with a
    text column search pages a million rows in ms, not seconds (2026-11-11 W1.1: 100k rows 880 ms -> 174 ms)."""
    _check(table, column)
    k = (_key(db), table, column)
    if k in _TEXT:
        return _TEXT[k]
    fts = f"{table}_fts"
    got = ""
    try:
        with tx(db) as c:
            if isinstance(c, _PG):
                c.execute(f"CREATE INDEX IF NOT EXISTS {table}_{column}_trgm ON {table} USING gin ({column} public.gin_trgm_ops)")
                got = "trgm"
            else:
                new = not c.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (fts,)).fetchone()
                c.executescript(
                    f"CREATE VIRTUAL TABLE IF NOT EXISTS {fts} USING fts5({column}, content='{table}', content_rowid='rowid', tokenize='trigram');"
                    f"CREATE TRIGGER IF NOT EXISTS {fts}_ai AFTER INSERT ON {table} BEGIN INSERT INTO {fts}(rowid, {column}) VALUES (new.rowid, new.{column}); END;"
                    f"CREATE TRIGGER IF NOT EXISTS {fts}_ad AFTER DELETE ON {table} BEGIN INSERT INTO {fts}({fts}, rowid, {column}) VALUES ('delete', old.rowid, old.{column}); END;"
                    f"CREATE TRIGGER IF NOT EXISTS {fts}_au AFTER UPDATE ON {table} BEGIN INSERT INTO {fts}({fts}, rowid, {column}) VALUES ('delete', old.rowid, old.{column}); "
                    f"INSERT INTO {fts}(rowid, {column}) VALUES (new.rowid, new.{column}); END;")
                if new:
                    c.execute(f"INSERT INTO {fts}({fts}) VALUES ('rebuild')")      # rows written before the index
                got = "fts"
    except Exception as e:  # noqa: BLE001 - no FTS5 trigram / no pg_trgm here: LIKE still answers, by a scan
        print(f"[sqlstore] {db}.{table}.{column}: no word index ({str(e).strip()[:120]})")
    _TEXT[k] = got
    return got


def text_match(db: str, table: str, column: str, words: list[str]) -> tuple[str, list]:
    """(" AND ...", args): every word somewhere in `column` (lower-case it when writing) - through text_index, LIKE for the rest."""
    how = text_index(db, table, column)
    words = [w for w in words if w]
    long_ = [w for w in words if len(w) >= 3] if how == "fts" else []     # trigram: three letters or more
    where, args = "", []
    if long_:
        where += f" AND rowid IN (SELECT rowid FROM {table}_fts WHERE {table}_fts MATCH ?)"
        args.append(" AND ".join('"' + w.replace('"', '""') + '"' for w in long_))
    for w in words:
        if w not in long_:
            where += f" AND {column} LIKE ? ESCAPE '!'"
            args.append("%" + w.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%")
    return where, args


def json_text(db: str, col: str, *keys: str) -> str:
    """SQL for one text field inside a JSON text column - json_extract on SQLite, #>> on Postgres."""
    _check(col)
    for k in keys:
        if not JSON_KEY.match(str(k)):
            raise ValueError(f"bad JSON key {k!r}")
    if kind(db) == "postgres":
        return f"({col}::jsonb #>> '{{{','.join(keys)}}}')"
    return "json_extract(" + col + ", '$." + ".".join(f'"{k}"' for k in keys) + "')"


# ---- Postgres ---------------------------------------------------------------------------------------------------------

def _driver():
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as e:
        raise RuntimeError(_say("no_driver")) from e
    return psycopg, dict_row


class _PG:
    """A Postgres connection that speaks like sqlite3's: execute / executemany / executescript with ? placeholders,
    rows as dicts, a refused write as IntegrityError."""

    def __init__(self, conn, sch: str):
        self.conn, self.schema = conn, sch

    def execute(self, sql: str, args=()):
        psycopg, _ = _driver()
        try:
            return self.conn.execute(_pg_sql(sql), tuple(args))
        except psycopg.IntegrityError as e:
            raise IntegrityError(str(e).strip()) from e

    def executemany(self, sql: str, seq):
        psycopg, _ = _driver()
        try:
            with self.conn.cursor() as cur:
                cur.executemany(_pg_sql(sql), [tuple(a) for a in seq])
        except psycopg.IntegrityError as e:
            raise IntegrityError(str(e).strip()) from e

    def executescript(self, script: str) -> None:
        for s in statements(script):
            self.execute(s)


def _pg_open(db: str) -> _PG:
    psycopg, dict_row = _driver()
    c, sch = cfg(), schema(db)
    conn = None
    with _POOL_LOCK:
        while _POOL and conn is None:
            x = _POOL.pop()
            conn = x if not x.closed and x.info.transaction_status == psycopg.pq.TransactionStatus.IDLE else None
    if conn is None:
        url = os.environ.get(str(c["url_env"]))
        if not url:
            raise RuntimeError(_say("no_url", env=c["url_env"]))
        conn = psycopg.connect(url, autocommit=True, row_factory=dict_row, connect_timeout=int(c["connect_timeout_s"]),
                               options=f"-c statement_timeout={int(c['statement_timeout_ms'])}")
    if getattr(conn, "_sqlstore_schema", None) != sch:
        conn.execute(f"SET search_path TO {sch}")
        conn._sqlstore_schema = sch          # noqa: SLF001 - the schema this kept connection points at
    return _PG(conn, sch)


def _pg_release(c: _PG) -> None:
    psycopg, _ = _driver()
    ok = not c.conn.closed and c.conn.info.transaction_status == psycopg.pq.TransactionStatus.IDLE
    with _POOL_LOCK:
        if ok and len(_POOL) < int(cfg()["pool_max"]):
            _POOL.append(c.conn)
            return
    c.conn.close()


def close_pool() -> None:
    with _POOL_LOCK:
        while _POOL:
            _POOL.pop().close()


@contextmanager
def _pg_tx(c: _PG, lock: str = ""):
    with c.conn.transaction():
        if lock:
            c.execute("SELECT pg_advisory_xact_lock(hashtext(?))", (lock,))
        yield c


# ---- one transaction, either engine ------------------------------------------------------------------------------------

def _columns(db: str, c, table: str) -> set:
    if isinstance(c, _PG):
        k = (c.schema, table)
        if k not in _COLS:
            _COLS[k] = {r["name"] for r in c.execute("SELECT column_name AS name FROM information_schema.columns "
                                                     "WHERE table_schema = ? AND table_name = ?", (c.schema, table))}
        return _COLS[k]
    return {r["name"] for r in c.execute(f"PRAGMA table_info({table})")}


def _ready(db: str, c) -> None:
    """The registered DDL, the `add` columns, then every migration step not yet run."""
    if isinstance(c, _PG):
        with _pg_tx(c, f"{c.schema}.ddl"):
            c.execute(f"CREATE SCHEMA IF NOT EXISTS {c.schema}")
            for s in statements(_SCHEMA.get(db) or ""):
                c.execute(_pg_ddl(s))
            for table, cols in _ADD.get(db, {}).items():
                _COLS.pop((c.schema, table), None)
                have = _columns(db, c, table)
                for col, decl in cols.items():
                    if col not in have:
                        c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {_pg_ddl(decl)}")
                _COLS.pop((c.schema, table), None)
    else:
        c.execute("PRAGMA journal_mode=WAL")
        if _SCHEMA.get(db):
            c.executescript(_SCHEMA[db])
        for table, cols in _ADD.get(db, {}).items():
            have = _columns(db, c, table)
            for col, decl in cols.items():
                if col not in have:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
        c.commit()
    _migrate(db, c)


def _step_hash(sql: str) -> str:
    return hashlib.sha256(sql.strip().encode("utf-8")).hexdigest()[:16]


def _migrate(db: str, c) -> None:
    steps = _STEPS.get(db) or []
    if not steps:
        return
    pg = isinstance(c, _PG)
    make = f"CREATE TABLE IF NOT EXISTS {MIGRATIONS} (n INTEGER PRIMARY KEY, sql_hash TEXT NOT NULL, applied_at TEXT NOT NULL)"
    if pg:
        with _pg_tx(c, f"{c.schema}.migrations"):
            c.execute(_pg_ddl(make))
    else:
        c.execute(make)
        c.commit()
    for n, sql in steps:
        try:
            if pg:
                with _pg_tx(c, f"{c.schema}.migrations"):
                    _step(db, c, n, sql, pg)
            else:
                c.execute("BEGIN IMMEDIATE")     # the write lock first, so two processes never run one step twice
                try:
                    _step(db, c, n, sql, pg)
                    c.commit()
                except BaseException:
                    c.rollback()
                    raise
        except Exception as e:  # noqa: BLE001 - named, then raised: the db is not used until the step is fixed
            raise RuntimeError(_say("step_failed", db=db, n=n, why=str(e).strip()[:300])) from e


def _step(db: str, c, n: int, sql: str, pg: bool) -> None:
    done = c.execute(f"SELECT sql_hash FROM {MIGRATIONS} WHERE n = ?", (n,)).fetchone()
    if done:
        if done["sql_hash"] != _step_hash(sql):
            print(_say("step_edited", db=db, n=n), file=sys.stderr)
        return
    for s in statements(sql):
        c.execute(_pg_ddl(s) if pg else s)
    c.execute(f"INSERT INTO {MIGRATIONS} (n, sql_hash, applied_at) VALUES (?, ?, ?)",
              (n, _step_hash(sql), datetime.now(timezone.utc).isoformat(timespec="seconds")))
    if pg:
        _COLS.clear()


def _key(db: str) -> str:
    """What 'this db is ready' is kept by: a SQLite db per file, so a test or tool that points store.DATA at another folder
    gets its tables made there too (2026-11-11: a ready mark kept by name alone skipped the DDL in a fresh folder)."""
    return db if kind(db) == "postgres" else str(path(db))


@contextmanager
def tx(db: str):
    """One transaction: committed on success, rolled back on any error, and the file (or kept connection) let go afterwards."""
    if kind(db) == "postgres":
        c = _pg_open(db)
        try:
            if _key(db) not in _READY:
                _ready(db, c)
                _READY.add(_key(db))
            with _pg_tx(c):
                yield c
        finally:
            _pg_release(c)
        return
    store.DATA.mkdir(parents=True, exist_ok=True)
    s = sqlite3.connect(path(db), timeout=float(cfg()["sqlite_timeout_s"]))
    s.row_factory = sqlite3.Row
    try:
        s.execute("PRAGMA foreign_keys=ON")
        if _key(db) not in _READY:
            _ready(db, s)
            _READY.add(_key(db))
        with s:
            yield s
    finally:
        s.close()


def rows(db: str, sql: str, args: tuple = ()) -> list[dict]:
    with tx(db) as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def one(db: str, sql: str, args: tuple = ()) -> dict | None:
    r = rows(db, sql, args)
    return r[0] if r else None


def migrations(db: str) -> list[dict]:
    """The steps this db has run: n, sql_hash, applied_at."""
    with tx(db) as c:
        if not _STEPS.get(db):
            return []
        return [dict(r) for r in c.execute(f"SELECT n, sql_hash, applied_at FROM {MIGRATIONS} ORDER BY n").fetchall()]


def _check(*names: str) -> None:
    for n in names:
        if not IDENT.match(n):
            raise ValueError(f"bad table or column name {n!r}")


def get(db: str, table: str, rid: str, key: str = "id") -> dict | None:
    _check(table, key)
    return one(db, f"SELECT * FROM {table} WHERE {key} = ?", (rid,))


def save(db: str, table: str, row: dict, key: str = "id") -> dict:
    """Insert or update one row by its key, then tell the watchers (History) the old and the new row."""
    _check(table, key, *row)
    if not row.get(key):
        raise ValueError(f"{table}: a row needs its {key}")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with tx(db) as c:
        cols = _columns(db, c, table)
        old = c.execute(f"SELECT * FROM {table} WHERE {key} = ?", (row[key],)).fetchone()
        old = dict(old) if old else None
        new = (old or {}) | dict(row) | ({"updated_at": now} if "updated_at" in cols else {})   # a partial save keeps the rest
        if old is None and "created_at" in cols:
            new.setdefault("created_at", now)
        names = list(new)
        c.execute(f"INSERT INTO {table} ({', '.join(names)}) VALUES ({', '.join('?' * len(names))}) "
                  f"ON CONFLICT({key}) DO UPDATE SET {', '.join(f'{n} = excluded.{n}' for n in names if n != key)}",
                  tuple(new[n] for n in names))
        stored = dict(c.execute(f"SELECT * FROM {table} WHERE {key} = ?", (new[key],)).fetchone())
    _tell(f"sql/{db}/{table}", [old] if old else [], [stored])
    return stored


def archive(db: str, table: str, rid: str, on: bool = True, key: str = "id") -> dict | None:
    """Archive (or restore) - the row stays, History records it."""
    r = get(db, table, rid, key)
    if not r:
        return None
    return save(db, table, {key: rid, "archived_at": datetime.now(timezone.utc).isoformat(timespec="seconds") if on else None}, key)


def _tell(name: str, old, new) -> None:
    for pat, fn in store.WATCHERS:
        if pat.search(name):
            try:
                fn(name, old, new)
            except Exception as e:  # noqa: BLE001 - a broken watcher never breaks the save it watches (as core/store.py)
                print(f"[sqlstore] watcher on {name}: {e}")


# ---- the move tool: a SQLite db into Postgres, checked ----------------------------------------------------------------

def _norm(v) -> str:
    if v is None:
        return "\x00"
    if isinstance(v, bytes | bytearray | memoryview):
        return bytes(v).hex()
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, dict | list):                 # a JSON value (Postgres jsonb), compared by content
        return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return str(v)


def _table_sum(cur, table: str) -> tuple[int, str]:
    return _digest(cur.execute(f"SELECT * FROM {table}"))


def _digest(rows) -> tuple[int, str]:
    """(rows, checksum): sha256 over every row's sorted per-row digest, so order never matters."""
    names = None
    digests = []
    for r in rows:
        d = dict(r)
        names = names or sorted(d)
        digests.append(hashlib.sha256("\x1f".join(_norm(d[k]) for k in names).encode("utf-8")).hexdigest())
    return len(digests), hashlib.sha256("".join(sorted(digests)).encode()).hexdigest()[:16]


def _fk_order(src, tables: list[str]) -> list[str]:
    """Parents before children, so foreign keys hold while copying."""
    deps = {t: {r["table"] for r in src.execute(f"PRAGMA foreign_key_list({t})")} & set(tables) - {t} for t in tables}
    out: list[str] = []
    while deps:
        free = sorted(t for t, d in deps.items() if not d - set(out))
        if not free:
            free = sorted(deps)[:1]
        for t in free:
            out.append(t)
            deps.pop(t)
    return out


def move(db: str, to: str = "postgres", apply: bool = False, say=print) -> dict:
    """Copy every table of data/<db>.sqlite3 into Postgres schema prefix+db, then check rows and checksums match - all
    in one Postgres transaction, so a mismatch keeps nothing. Refuses a target that already holds rows. Dry run unless apply."""
    if to != "postgres" or not IDENT.match(db):
        raise ValueError("usage: python -m core.sqlstore move <db> --to postgres [--apply]")
    src_path = path(db)
    if not src_path.is_file():
        say(_say("no_file", path=src_path))
        return {"ok": False, "why": "no_file"}
    src = sqlite3.connect(src_path)
    src.row_factory = sqlite3.Row
    try:
        tables = [r["name"] for r in src.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        # 2026-11-11: an FTS5 word index (text_index) is a VIRTUAL table plus shadow tables <name>_data/_idx/... - SQLite's own
        # machinery, never data. Postgres makes its own index (pg_trgm) on first use, so neither is copied.
        virt = [r["name"] for r in src.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND sql LIKE 'CREATE VIRTUAL TABLE%'")]
        tables = [t for t in tables if not any(t == v or t.startswith(v + "_") for v in virt)]
        tables = _fk_order(src, tables)
        made = {r["name"]: r["sql"] for r in src.execute("SELECT name, sql FROM sqlite_master WHERE type = 'table'")}
        idx = [r["sql"] for r in src.execute("SELECT sql FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL")]
        before = {t: _table_sum(src, t) for t in tables}
        kept = {k: _OVER[k] for k in ("engine", "dbs") if k in _OVER}
        _OVER.update(engine="postgres", dbs=[db])
        c = _pg_open(db)
        try:
            sch = c.schema
            have = [r["t"] for r in c.execute("SELECT table_name AS t FROM information_schema.tables WHERE table_schema = ?", (sch,))]
            busy = [f"{t} {n}" for t in have if (n := c.execute(f"SELECT COUNT(*) AS n FROM {sch}.{t}").fetchone()["n"])]
            say(_say("plan", db=db, tables=len(tables), rows=sum(n for n, _ in before.values()), schema=sch))
            for t in tables:
                say(_say("table", table=t, rows=before[t][0]))
            if busy:
                say(_say("target_busy", schema=sch, busy=", ".join(busy)))
                return {"ok": False, "why": "target_busy", "busy": busy}
            if not apply:
                say(_say("dry"))
                return {"ok": True, "dry": True, "tables": {t: before[t][0] for t in tables}}
            batch = int(cfg()["move_batch"])
            bad = []
            try:
                with _pg_tx(c, f"{sch}.ddl"):
                    c.execute(f"CREATE SCHEMA IF NOT EXISTS {sch}")
                    for t in tables:
                        c.execute(_pg_ddl(re.sub(r"^\s*CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?", "CREATE TABLE IF NOT EXISTS ", made[t], flags=re.I)))
                    for t in tables:
                        cur = src.execute(f"SELECT * FROM {t}")
                        names = [d[0] for d in cur.description]
                        ins = f"INSERT INTO {t} ({', '.join(names)}) VALUES ({', '.join('?' * len(names))})"
                        while chunk := cur.fetchmany(batch):
                            c.executemany(ins, [tuple(r) for r in chunk])
                    for s in idx:
                        c.execute(re.sub(r"^\s*CREATE\s+(UNIQUE\s+)?INDEX\s+(IF\s+NOT\s+EXISTS\s+)?", lambda m: f"CREATE {m.group(1) or ''}INDEX IF NOT EXISTS ", s, flags=re.I))
                    for t in tables:
                        after = _table_sum(c.conn.cursor(), t)
                        if after == before[t]:
                            say(_say("checked", table=t, rows=after[0], sum=after[1]))
                        else:
                            bad.append(t)
                            say(_say("mismatch", table=t, a_rows=before[t][0], a_sum=before[t][1], b_rows=after[0], b_sum=after[1]))
                    if bad:
                        raise _Mismatch()
            except _Mismatch:
                return {"ok": False, "why": "mismatch", "tables": bad}
            say(_say("done", db=db))
            return {"ok": True, "dry": False, "tables": {t: before[t][0] for t in tables}}
        finally:
            _pg_release(c)
    finally:
        src.close()
        if "kept" in locals():
            _OVER.pop("engine", None)
            _OVER.pop("dbs", None)
            _OVER.update(kept)
        _READY.clear()


class _Mismatch(Exception):
    pass


# ---- the move tool, from MySQL / MariaDB: a database another product kept, into Postgres, checked ----------------------

def _mysql_open():
    try:
        import pymysql
        import pymysql.cursors
    except ImportError as e:
        raise RuntimeError(_say("no_mysql_driver")) from e
    from urllib.parse import unquote, urlparse
    env = str(cfg()["mysql_url_env"])
    url = os.environ.get(env)
    if not url:
        raise RuntimeError(_say("no_mysql_url", env=env))
    u = urlparse(url)
    return pymysql.connect(host=u.hostname, port=u.port or 3306, user=unquote(u.username or ""), password=unquote(u.password or ""),
                           database=u.path.lstrip("/"), charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
                           connect_timeout=int(cfg()["connect_timeout_s"]))


def _mysql_shape(src) -> dict:
    """Every table of the MySQL database: columns (Postgres type, null, default, identity), primary key, indexes and
    foreign keys - read from information_schema, never parsed from DDL text."""
    types = cfg()["mysql_types"]
    cur = src.cursor()
    cur.execute("SELECT TABLE_NAME AS t FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE' ORDER BY 1")
    shape = {}
    for t in [r["t"] for r in cur.fetchall()]:
        if not IDENT.match(t):
            raise ValueError(_say("mysql_name", name=t))
        cur.execute("SELECT COLUMN_NAME AS c, DATA_TYPE AS dt, COLUMN_TYPE AS ct, IS_NULLABLE AS nul, COLUMN_DEFAULT AS d, EXTRA AS x, "
                    "NUMERIC_PRECISION AS p, NUMERIC_SCALE AS s FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s ORDER BY ORDINAL_POSITION", (t,))
        found = cur.fetchall()
        try:                                          # MariaDB keeps JSON as LONGTEXT CHECK (json_valid(`col`))
            cur.execute("SELECT CHECK_CLAUSE AS k FROM information_schema.CHECK_CONSTRAINTS "
                        "WHERE CONSTRAINT_SCHEMA = DATABASE() AND TABLE_NAME = %s", (t,))
            jsons = {m for r in cur.fetchall() for m in re.findall(r"json_valid\(`(\w+)`\)", r["k"] or "")}
        except Exception:  # noqa: BLE001 - MySQL 8 has no TABLE_NAME there; its JSON columns say json already
            jsons = set()
        cols = []
        for c in found:
            if c["c"] in jsons:
                c["dt"] = "json"
            if not IDENT.match(c["c"]):
                raise ValueError(_say("mysql_name", name=f"{t}.{c['c']}"))
            dt = c["dt"].lower()
            key = f"{dt} unsigned" if "unsigned" in c["ct"].lower() and f"{dt} unsigned" in types else dt
            if key not in types:
                raise ValueError(_say("mysql_type", table=t, column=c["c"], type=c["ct"]))
            cols.append({"name": c["c"], "dt": dt, "pg": types[key].format(p=c["p"] or 10, s=c["s"] or 0),
                         "null": c["nul"] == "YES", "default": c["d"], "identity": "auto_increment" in (c["x"] or "").lower()})
        cur.execute("SELECT INDEX_NAME AS i, NON_UNIQUE AS nu, COLUMN_NAME AS c FROM information_schema.STATISTICS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s ORDER BY INDEX_NAME, SEQ_IN_INDEX", (t,))
        idx: dict = {}
        for r in cur.fetchall():
            idx.setdefault(r["i"], {"unique": not int(r["nu"]), "cols": []})["cols"].append(r["c"])
        cur.execute("SELECT CONSTRAINT_NAME AS n, COLUMN_NAME AS c, REFERENCED_TABLE_NAME AS rt, REFERENCED_COLUMN_NAME AS rc "
                    "FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s "
                    "AND REFERENCED_TABLE_NAME IS NOT NULL ORDER BY CONSTRAINT_NAME, ORDINAL_POSITION", (t,))
        fks: dict = {}
        for r in cur.fetchall():
            f = fks.setdefault(r["n"], {"table": r["rt"], "cols": [], "refs": []})
            f["cols"].append(r["c"])
            f["refs"].append(r["rc"])
        shape[t] = {"cols": cols, "pk": idx.pop("PRIMARY", {}).get("cols", []), "idx": idx, "fks": list(fks.values())}
    return shape


def _mysql_default(d) -> str:
    """A MySQL column default as Postgres SQL, or "" when there is none (the app gives the value)."""
    if d is None or str(d).upper() == "NULL":
        return ""
    v = str(d)
    if v.lower().startswith("current_timestamp"):
        return "CURRENT_TIMESTAMP"
    if re.fullmatch(r"-?\d+(\.\d+)?", v):
        return v
    if len(v) >= 2 and v[0] == v[-1] == "'":       # MariaDB quotes a text default; MySQL does not
        v = v[1:-1].replace("''", "'")
    return "'" + v.replace("'", "''") + "'"


def _mysql_value(col: dict, v, table: str):
    """One MySQL value as Postgres takes it (and as the checksum compares it)."""
    import datetime as _dt
    if v is None:
        return None
    if col["dt"] == "bit" and isinstance(v, bytes | bytearray):
        return int.from_bytes(v, "big")
    if col["dt"] == "json" and isinstance(v, str):
        return json.loads(v)
    if isinstance(v, _dt.timedelta):              # MySQL TIME comes back as a duration
        sec = int(v.total_seconds())
        return _dt.time(sec // 3600 % 24, sec // 60 % 60, sec % 60)
    if col["dt"] in ("date", "datetime", "timestamp") and isinstance(v, str) and v.startswith("0000-00-00"):
        raise ValueError(_say("mysql_zero_date", table=table, column=col["name"], value=v))
    return v


def _pg_ident(*parts: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", "_".join(parts).lower())[:63]


def move_mysql(db: str, apply: bool = False, say=print) -> dict:
    """Copy every table of a MySQL / MariaDB database (its connection string in the variable chip store.engine
    mysql_url_env names) into Postgres schema prefix+db: columns typed by chip mysql_types, primary keys, AUTO_INCREMENT as
    an identity that continues after the highest id, indexes, then foreign keys - and check rows and checksums per table,
    all in one Postgres transaction, so a mismatch keeps nothing. Refuses a target that already holds rows. Dry run unless apply."""
    if not IDENT.match(db):
        raise ValueError("usage: python -m core.sqlstore move <db> --from mysql --to postgres [--apply]")
    src = _mysql_open()
    kept = {k: _OVER[k] for k in ("engine", "dbs") if k in _OVER}
    try:
        shape = _mysql_shape(src)
        cur = src.cursor()
        cur.execute("SELECT DATABASE() AS d")
        source = cur.fetchone()["d"]
        deps = {t: {f["table"] for f in v["fks"]} & set(shape) - {t} for t, v in shape.items()}
        order: list[str] = []
        while deps:                                   # parents before children
            free = sorted(t for t, d in deps.items() if not d - set(order)) or sorted(deps)[:1]
            for t in free:
                order.append(t)
                deps.pop(t)

        def read(t):
            cols = {col["name"]: col for col in shape[t]["cols"]}
            rc = src.cursor()
            rc.execute(f"SELECT * FROM `{t}`")
            while chunk := rc.fetchmany(int(cfg()["move_batch"])):
                yield from ({k: _mysql_value(cols[k], v, t) for k, v in r.items()} for r in chunk)

        before = {t: _digest(read(t)) for t in order}
        _OVER.update(engine="postgres", dbs=[db])
        c = _pg_open(db)
        try:
            sch = c.schema
            have = [r["t"] for r in c.execute("SELECT table_name AS t FROM information_schema.tables WHERE table_schema = ?", (sch,))]
            busy = [f"{t} {n}" for t in have if (n := c.execute(f"SELECT COUNT(*) AS n FROM {sch}.{t}").fetchone()["n"])]
            say(_say("mysql_plan", db=db, tables=len(order), rows=sum(n for n, _ in before.values()), source=source, schema=sch))
            for t in order:
                say(_say("table", table=t, rows=before[t][0]))
            if busy:
                say(_say("target_busy", schema=sch, busy=", ".join(busy)))
                return {"ok": False, "why": "target_busy", "busy": busy}
            if not apply:
                say(_say("dry"))
                return {"ok": True, "dry": True, "tables": {t: before[t][0] for t in order}}
            bad = []
            batch = int(cfg()["move_batch"])
            try:
                with _pg_tx(c, f"{sch}.ddl"):
                    c.execute(f"CREATE SCHEMA IF NOT EXISTS {sch}")
                    for t in order:
                        defs = []
                        for col in shape[t]["cols"]:
                            d = "" if col["identity"] else _mysql_default(col["default"])
                            defs.append(f"{col['name']} {col['pg']}" + (" GENERATED BY DEFAULT AS IDENTITY" if col["identity"] else "")
                                        + ("" if col["null"] else " NOT NULL") + (f" DEFAULT {d}" if d else ""))
                        if shape[t]["pk"]:
                            defs.append(f"PRIMARY KEY ({', '.join(shape[t]['pk'])})")
                        c.execute(f"CREATE TABLE IF NOT EXISTS {t} ({', '.join(defs)})")
                    for t in order:
                        names = [col["name"] for col in shape[t]["cols"]]
                        jcols = {col["name"] for col in shape[t]["cols"] if col["pg"] == "JSONB"}
                        ins = f"INSERT INTO {t} ({', '.join(names)}) OVERRIDING SYSTEM VALUE VALUES ({', '.join('?' * len(names))})"
                        rows = read(t)
                        while chunk := [r for _, r in zip(range(batch), rows, strict=False)]:
                            c.executemany(ins, [tuple(json.dumps(r[n]) if n in jcols and r[n] is not None else r[n] for n in names) for r in chunk])
                        for col in shape[t]["cols"]:
                            if col["identity"]:      # the next id continues after the highest copied one
                                c.execute(f"SELECT setval(pg_get_serial_sequence('{t}', '{col['name']}'), "
                                          f"COALESCE((SELECT MAX({col['name']}) FROM {t}), 0) + 1, false)")
                    for t in order:
                        for name, ix in shape[t]["idx"].items():
                            c.execute(f"CREATE {'UNIQUE ' if ix['unique'] else ''}INDEX IF NOT EXISTS {_pg_ident(sch, t, name)} ON {t} ({', '.join(ix['cols'])})")
                        for i, f in enumerate(shape[t]["fks"]):
                            c.execute(f"ALTER TABLE {t} ADD CONSTRAINT {_pg_ident(t, 'fk', str(i))} FOREIGN KEY ({', '.join(f['cols'])}) "
                                      f"REFERENCES {f['table']} ({', '.join(f['refs'])})")
                    for t in order:
                        after = _table_sum(c.conn.cursor(), t)
                        if after == before[t]:
                            say(_say("checked", table=t, rows=after[0], sum=after[1]))
                        else:
                            bad.append(t)
                            say(_say("mismatch", table=t, a_rows=before[t][0], a_sum=before[t][1], b_rows=after[0], b_sum=after[1]))
                    if bad:
                        raise _Mismatch()
            except _Mismatch:
                return {"ok": False, "why": "mismatch", "tables": bad}
            say(_say("mysql_done", env=cfg()["url_env"]))
            return {"ok": True, "dry": False, "tables": {t: before[t][0] for t in order}}
        finally:
            _pg_release(c)
    finally:
        src.close()
        _OVER.pop("engine", None)
        _OVER.pop("dbs", None)
        _OVER.update(kept)
        _READY.clear()


# ---- self-check: the same assertions on SQLite always, and on Postgres when its variable is set -------------------------

def selfcheck_migrations():
    """Steps run once, in order; a new step runs alone; a failing step rolls back and stops; bad numbering is refused."""
    ddl = "CREATE TABLE IF NOT EXISTS m0 (id TEXT PRIMARY KEY);"
    s1 = [(1, "CREATE TABLE IF NOT EXISTS m1 (id TEXT PRIMARY KEY, n INTEGER)"), (2, "INSERT INTO m1 (id, n) VALUES ('a', 1)")]
    register("selfmig", ddl, steps=s1)
    assert get("selfmig", "m1", "a")["n"] == 1 and [m["n"] for m in migrations("selfmig")] == [1, 2], "steps 1-2 not applied"
    s2 = s1 + [(3, "UPDATE m1 SET n = n + 1; INSERT INTO m0 (id) VALUES ('z')")]
    register("selfmig", ddl, steps=s2)
    assert get("selfmig", "m1", "a")["n"] == 2, "step 3 not applied"
    register("selfmig", ddl, steps=s2)
    register("selfmig", ddl, steps=s2)
    assert get("selfmig", "m1", "a")["n"] == 2 and one("selfmig", "SELECT COUNT(*) AS k FROM m0")["k"] == 1, "a step ran twice"
    assert [m["n"] for m in migrations("selfmig")] == [1, 2, 3], "every step is recorded once"
    s3 = s2 + [(4, "INSERT INTO m1 (id, n) VALUES ('b', 1); INSERT INTO no_such_table (id) VALUES ('x')"), (5, "UPDATE m1 SET n = 99")]
    register("selfmig", ddl, steps=s3)
    try:
        get("selfmig", "m1", "a")
        raise AssertionError("a failing step did not stop")
    except RuntimeError:
        pass
    register("selfmig", ddl, steps=s2)
    assert get("selfmig", "m1", "b") is None and get("selfmig", "m1", "a")["n"] == 2, "a failing step was not rolled back, or a later one ran"
    assert [m["n"] for m in migrations("selfmig")] == [1, 2, 3], "a failing step was recorded"
    for bad in ([(2, "SELECT 1"), (1, "SELECT 1")], [(1, "SELECT 1"), (1, "SELECT 2")], [(0, "SELECT 1")], [(1, " ")]):
        try:
            register("selfmig", ddl, steps=bad)
            raise AssertionError(f"bad steps {bad} not refused")
        except ValueError:
            pass
    register("selfmig", ddl, add={"m1": {"city": "TEXT NOT NULL DEFAULT ''"}}, steps=s2)
    assert get("selfmig", "m1", "a")["city"] == "", "add and steps together"


def _assertions():
    register("demo", """CREATE TABLE IF NOT EXISTS parent (id TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, org_id TEXT NOT NULL, parent_id TEXT REFERENCES parent(id),
          stage TEXT, paise INTEGER CHECK (paise >= 0), archived_at TEXT, created_at TEXT, updated_at TEXT);""")
    seen = []
    store.watch(r"^sql/demo/orders$", lambda n, o, w: seen.append((n, o, w)))
    a = save("demo", "orders", {"id": "o1", "org_id": "f1", "stage": "open", "paise": 4800})
    assert a["created_at"] and seen[-1][1] == [] and seen[-1][2][0]["stage"] == "open", "a new row tells History with no old row"
    b = save("demo", "orders", {"id": "o1", "org_id": "f1", "stage": "confirmed", "paise": 4800})
    assert seen[-1][1][0]["stage"] == "open" and seen[-1][2][0]["stage"] == "confirmed", "an update tells old and new"
    assert b["created_at"] == a["created_at"], "created_at survives an update"
    archive("demo", "orders", "o1")
    assert get("demo", "orders", "o1")["archived_at"], "archive keeps the row"
    archive("demo", "orders", "o1", on=False)
    assert get("demo", "orders", "o1")["archived_at"] is None, "restore clears it"
    for bad in ({"id": "o2", "org_id": "f1", "paise": -1}, {"id": "o3", "org_id": "f1", "parent_id": "nope"}, {"id": "o4"}):
        try:
            save("demo", "orders", bad)
        except IntegrityError:
            continue
        raise AssertionError(f"constraint not enforced for {bad}")
    assert get("demo", "orders", "o2") is None, "a refused save leaves nothing behind"
    for bad_name in ("orders; DROP TABLE orders", "Orders", "1x"):
        try:
            get("demo", bad_name, "o1")
        except ValueError:
            continue
        raise AssertionError(f"identifier {bad_name!r} not refused")
    assert rows("demo", "SELECT COUNT(*) AS n FROM orders WHERE org_id = ?", ("f1",))[0]["n"] == 1
    assert one("demo", "SELECT COALESCE(archived_at, '') AS a, 'it''s 100% ?' AS lit FROM orders WHERE id = ?", ("o1",)) == \
        {"a": "", "lit": "it's 100% ?"}, "a literal ? or % or quote survives the placeholder rewrite"
    save("demo", "orders", {"id": "o5", "org_id": "f1", "stage": '{"2026-27": {"stage": "done"}}'})
    assert one("demo", f"SELECT {json_text('demo', 'stage', '2026-27', 'stage')} AS s FROM orders WHERE id = ?", ("o5",))["s"] == "done", "json_text"
    register("selftext", "CREATE TABLE IF NOT EXISTS t (id TEXT PRIMARY KEY, body TEXT NOT NULL DEFAULT '')")
    for i, b in (("a1", "rate 50% off"), ("b1", "rate 50 percent"), ("c1", "ok")):
        save("selftext", "t", {"id": i, "body": b})
    for words, want in ((["50%"], ["a1"]), (["rate", "off"], ["a1"]), (["ok"], ["c1"]), (["50"], ["a1", "b1"]), (["zzz"], [])):
        w, a = text_match("selftext", "t", "body", words)
        assert [r["id"] for r in rows("selftext", "SELECT id FROM t WHERE 1 = 1" + w + " ORDER BY id", tuple(a))] == want, (words, w)
    save("selftext", "t", {"id": "c1", "body": "now about rates"})
    w, a = text_match("selftext", "t", "body", ["rates"])
    assert [r["id"] for r in rows("selftext", "SELECT id FROM t WHERE 1 = 1" + w, tuple(a))] == ["c1"], "the word index follows an update"
    assert text_index("selftext", "t", "body") in ("fts", "trgm"), "no word index made"
    big = save("demo", "orders", {"id": "o6", "org_id": "f1", "paise": 5_000_000_000})
    assert big["paise"] == 5_000_000_000, "an INTEGER holds 64 bits on both engines"
    _ddl = "CREATE TABLE IF NOT EXISTS later (id TEXT PRIMARY KEY, archived_at TEXT, created_at TEXT, updated_at TEXT);"
    register("selfchk2", _ddl)
    save("selfchk2", "later", {"id": "a"})
    register("selfchk2", _ddl, add={"later": {"city": "TEXT NOT NULL DEFAULT ''"}})   # a later version's column
    assert get("selfchk2", "later", "a")["city"] == "" and save("selfchk2", "later", {"id": "a", "city": "Pune"})["city"] == "Pune", "column not added in place"
    register("selfchk2", _ddl, add={"later": {"city": "TEXT NOT NULL DEFAULT ''"}})
    assert get("selfchk2", "later", "a")["city"] == "Pune", "adding again must change nothing"
    selfcheck_migrations()


MYSQL_SAMPLE = """DROP TABLE IF EXISTS order_lines; DROP TABLE IF EXISTS orders; DROP TABLE IF EXISTS customers;
CREATE TABLE customers (id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY, name VARCHAR(80) NOT NULL, city VARCHAR(40) DEFAULT 'Pune',
  vip TINYINT(1) NOT NULL DEFAULT 0, flags BIT(8), born DATE, opens TIME, made DATETIME DEFAULT CURRENT_TIMESTAMP, UNIQUE KEY u_name (name));
CREATE TABLE orders (id BIGINT AUTO_INCREMENT PRIMARY KEY, customer_id INT UNSIGNED NOT NULL, total DECIMAL(12,2) NOT NULL,
  ratio DOUBLE, stage ENUM('open','paid') NOT NULL DEFAULT 'open', meta JSON, note LONGTEXT, pic BLOB, big BIGINT UNSIGNED,
  KEY k_stage (stage, customer_id), CONSTRAINT fk_c FOREIGN KEY (customer_id) REFERENCES customers (id));
CREATE TABLE order_lines (order_id BIGINT NOT NULL, n SMALLINT NOT NULL, qty INT NOT NULL, PRIMARY KEY (order_id, n),
  CONSTRAINT fk_o FOREIGN KEY (order_id) REFERENCES orders (id));
INSERT INTO customers (name, city, vip, flags, born, opens) VALUES ('Asha Demo', NULL, 1, b'00000101', '1980-03-03', '09:30:00'),
  ('Ravi O''Demo', 'Chennai', 0, NULL, NULL, NULL), ('Meena 名前 ✓', DEFAULT, 0, b'11111111', '2001-12-31', '23:59:59');
INSERT INTO orders (customer_id, total, ratio, stage, meta, note, pic, big) VALUES
  (1, 1234.50, 0.1, 'paid', '{"b": 2, "a": [1, "x"]}', 'it''s 100% ?', x'00ff10', 18446744073709551615),
  (2, 0.00, NULL, 'open', NULL, NULL, NULL, NULL), (3, 99.99, 2.5e10, 'open', '[]', 'line1\\nline2', x'', 0);
INSERT INTO order_lines VALUES (1, 1, 2), (1, 2, 1), (3, 1, 5);"""


def selfcheck_mysql():
    """A MySQL shop (unsigned, bit, enum, JSON, unicode, quotes, blobs, a composite key, foreign keys) moved into Postgres:
    dry run writes nothing, apply copies and checks, ids continue, keys hold, a second move is refused."""
    src = _mysql_open()
    try:
        with src.cursor() as cur:
            for s_ in statements(MYSQL_SAMPLE):
                cur.execute(s_)
        src.commit()
    finally:
        src.close()
    quiet = lambda s_: None  # noqa: E731
    r = move_mysql("mysqlshop", apply=False, say=quiet)
    assert r["ok"] and r["dry"] and r["tables"] == {"customers": 3, "orders": 3, "order_lines": 3}, r
    assert not rows("mysqlshop", "SELECT table_name FROM information_schema.tables WHERE table_schema = ?", (schema("mysqlshop"),)), "a dry run wrote"
    r = move_mysql("mysqlshop", apply=True, say=quiet)
    assert r["ok"] and not r["dry"], r
    o = one("mysqlshop", "SELECT * FROM orders WHERE id = 1")
    assert o["meta"] == {"a": [1, "x"], "b": 2} and o["note"] == "it's 100% ?" and bytes(o["pic"]) == b"\x00\xff\x10" and int(o["big"]) == 18446744073709551615, o
    assert one("mysqlshop", "SELECT name, flags, city FROM customers WHERE id = 3") == {"name": "Meena 名前 ✓", "flags": 255, "city": "Pune"}
    assert save("mysqlshop", "customers", {"id": 4, "name": "New After Move"})["vip"] == 0, "a default came across"
    with tx("mysqlshop") as c:
        c.execute("INSERT INTO orders (customer_id, total) VALUES (4, 1)")
        assert c.execute("SELECT MAX(id) AS m FROM orders").fetchone()["m"] == 4, "ids continue after the highest copied one"
    for bad in ({"order_id": 99, "n": 1, "qty": 1}, {"order_id": 1, "n": 1, "qty": 9}):
        try:
            with tx("mysqlshop") as c:
                c.execute("INSERT INTO order_lines (order_id, n, qty) VALUES (?, ?, ?)", (bad["order_id"], bad["n"], bad["qty"]))
            raise AssertionError(f"foreign key or composite key not enforced: {bad}")
        except IntegrityError:
            pass
    assert move_mysql("mysqlshop", apply=True, say=quiet)["why"] == "target_busy", "a moved schema was overwritten"


def _pg_drop(prefix: str) -> None:
    c = _pg_open("demo")
    try:
        for r in c.execute("SELECT schema_name AS s FROM information_schema.schemata WHERE schema_name LIKE ?", (prefix + "%",)).fetchall():
            c.execute(f"DROP SCHEMA {r['s']} CASCADE")
    finally:
        _pg_release(c)


def _selfcheck() -> None:
    import secrets
    import tempfile
    from pathlib import Path

    assert _pg_sql("SELECT ? , '?', 'a%' WHERE x LIKE ?") == "SELECT %s , '?', 'a%%' WHERE x LIKE %s", _pg_sql("SELECT ? , '?', 'a%' WHERE x LIKE ?")
    assert statements("CREATE TABLE a (x TEXT DEFAULT ';'); ; INSERT INTO a VALUES ('b;c')") == ["CREATE TABLE a (x TEXT DEFAULT ';')", "INSERT INTO a VALUES ('b;c')"]
    assert cfg()["engine"] == "sqlite" or os.environ.get(cfg()["url_env"]), "chip store.engine says postgres but its variable is not set"
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as t:
        store.DATA = Path(t)
        configure(engine="sqlite")
        _assertions()
        assert kind("demo") == "sqlite" and path("demo").is_file(), "SQLite keeps one file per db"
        print("sqlstore self-check OK (sqlite)")
        env = cfg()["url_env"]
        if not os.environ.get(env):
            print(f"sqlstore: Postgres part skipped ({env} not set)")
            return
        prefix = f"chk{secrets.token_hex(3)}_"
        configure(engine="postgres", schema_prefix=prefix)
        try:
            _assertions()
            assert kind("demo") == "postgres"
            configure(engine="postgres", schema_prefix=prefix + "mv_")      # the move tool: SQLite file -> Postgres, checked
            r = move("demo", apply=False, say=lambda s: None)
            assert r["ok"] and r["dry"] and r["tables"]["orders"] == 3, r
            r = move("selftext", apply=False, say=lambda s: None)             # a db with an FTS5 word index (text_index)
            assert r["ok"] and set(r["tables"]) == {"t"}, ("the SQLite word index (virtual + shadow tables) is not data", r)
            assert move("demo", apply=True, say=lambda s: None)["ok"], "move did not apply"
            assert rows("demo", "SELECT COUNT(*) AS n FROM orders")[0]["n"] == 3, "moved rows are not read back"
            assert move("demo", apply=True, say=lambda s: None)["why"] == "target_busy", "a non-empty target was overwritten"
            print("sqlstore self-check OK (postgres)")
            if os.environ.get(cfg()["mysql_url_env"]):
                configure(engine="postgres", schema_prefix=prefix + "my_")
                selfcheck_mysql()
                print("sqlstore self-check OK (mysql -> postgres)")
            else:
                print(f"sqlstore: MySQL move part skipped ({cfg()['mysql_url_env']} not set)")
        finally:
            configure(engine="postgres", schema_prefix=prefix)
            _pg_drop(prefix)
            configure()


if __name__ == "__main__":
    if sys.argv[1:2] == ["move"]:
        a = sys.argv[2:]
        if not a or "--to" not in a:
            raise SystemExit("usage: python -m core.sqlstore move <db> --to postgres [--apply]")
        frm = a[a.index("--from") + 1] if "--from" in a and a.index("--from") + 1 < len(a) else "sqlite"
        res = move_mysql(a[0], apply="--apply" in a) if frm == "mysql" else move(a[0], to=a[a.index("--to") + 1], apply="--apply" in a)
        raise SystemExit(0 if res.get("ok") else 1)
    _selfcheck()
