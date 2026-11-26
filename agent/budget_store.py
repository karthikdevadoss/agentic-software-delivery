"""Durable counter store for budgets and rate limits (SQLite).

WHY THIS EXISTS
agent/triage_budget.py and agent/si_budget.py used to keep their counters in
process memory, so a restart (or a second replica) started from zero and the
"daily cap" was really "per process per day". This module is the one durable
place those counters now live, together with the platform-wide gateway policy
(agent/gateway_budget.py). Every row is one RESERVATION: written when a call
is attempted, before the provider is contacted, because a call that fails
half-way can still be billed.

WHY SQLite AND NOT THE EVENT LEDGER (Postgres)
The event ledger (agent/event_ledger.py) is the right place for the *record*
of what was spent: it is append-only, best-effort (it falls back to a local
spool when Postgres is unreachable) and written after the fact. A cap needs
the opposite properties -- a synchronous, atomic check-and-insert that works
with no network and no running Postgres. SQLite gives that (BEGIN IMMEDIATE
serialises writers, WAL keeps readers unblocked) and lets the tests prove a
restart without infrastructure. The two are complementary: the ledger is the
audit trail, this store is the enforcement state.

HONEST LIMITS
  * Durable across a PROCESS restart on the same filesystem. On a host whose
    disk is replaced on each deploy (Railway without a mounted volume) the
    file is replaced too, so durability there needs BUDGET_DB_PATH pointed at
    a persistent volume. Nothing about production is changed by this module.
  * One file means one host. Two replicas on separate disks do not share
    counters.

POSTGRES BACKEND (2026-11-26)
Set BUDGET_DATABASE_URL and the same `transaction()` interface runs on
Postgres instead, so caps survive a redeploy and are shared by replicas.
Writers are serialised with a transaction-scoped advisory lock, the Postgres
equivalent of SQLite's BEGIN IMMEDIATE: two callers can never both see room
under a cap. The trade-off the SQLite design avoided is now explicit: if
Postgres cannot be reached, transaction() raises StoreUnavailable and every
caller REFUSES the billed call (fail closed). A cap that cannot be checked is
treated as reached, never as absent. Unset, nothing changes: SQLite as before.
  * Dollar amounts are reservations (a worst-case estimate) until a real
    usage figure settles them; see gateway_budget.py.
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

_DEFAULT_PATH = Path(__file__).resolve().parent / ".budget" / "budget.sqlite3"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS budget_ledger (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      REAL    NOT NULL,            -- wall clock; survives a restart
    day     TEXT    NOT NULL,            -- UTC YYYY-MM-DD
    scope   TEXT    NOT NULL,            -- 'gateway' | 'triage' | 'si'
    visitor TEXT,
    run_id  TEXT,
    usd     REAL    NOT NULL DEFAULT 0,  -- reserved estimate, then actual
    settled INTEGER NOT NULL DEFAULT 0   -- 1 once usd is a real measured cost
);
CREATE INDEX IF NOT EXISTS budget_scope_day ON budget_ledger (scope, day);
CREATE INDEX IF NOT EXISTS budget_scope_ts ON budget_ledger (scope, ts);
"""

_init_lock = threading.Lock()
_initialised: set[str] = set()

_PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS budget_ledger (
    id      BIGSERIAL PRIMARY KEY,
    ts      DOUBLE PRECISION NOT NULL,
    day     TEXT    NOT NULL,
    scope   TEXT    NOT NULL,
    visitor TEXT,
    run_id  TEXT,
    usd     DOUBLE PRECISION NOT NULL DEFAULT 0,
    settled INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS budget_scope_day ON budget_ledger (scope, day);
CREATE INDEX IF NOT EXISTS budget_scope_ts ON budget_ledger (scope, ts);
"""
# Arbitrary fixed key for pg_advisory_xact_lock; "budget" in ASCII.
_PG_LOCK_KEY = 0x627564676574


class StoreUnavailable(RuntimeError):
    """The configured budget store cannot be reached. Callers must refuse
    the billed call: a cap that cannot be checked counts as reached."""


def pg_url() -> str:
    return os.environ.get("BUDGET_DATABASE_URL", "").strip()


def backend() -> str:
    return "postgres" if pg_url() else "sqlite"


def db_path() -> str:
    return os.environ.get("BUDGET_DB_PATH", "").strip() or str(_DEFAULT_PATH)


def _connect() -> sqlite3.Connection:
    path = db_path()
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    with _init_lock:
        if path not in _initialised:
            if path != ":memory:":
                conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(_SCHEMA)
            _initialised.add(path)
    return conn


class _PgConn:
    """Adapts a psycopg2 cursor to the sqlite3 `execute(...).fetchone()` shape
    Tx uses, translating `?` placeholders to `%s`."""

    def __init__(self, cur):
        self._cur = cur

    def execute(self, sql, params=()):
        self._cur.execute(sql.replace("?", "%s"), params)
        return self._cur


class Tx:
    """Operations valid inside one atomic transaction (SQLite or Postgres)."""

    def __init__(self, conn, pg: bool = False):
        self._c = conn
        self._pg = pg

    def count(self, scope: str, day: str, visitor: str | None = None) -> int:
        if visitor is None:
            row = self._c.execute(
                "SELECT COUNT(*) FROM budget_ledger WHERE scope=? AND day=?",
                (scope, day)).fetchone()
        else:
            row = self._c.execute(
                "SELECT COUNT(*) FROM budget_ledger WHERE scope=? AND day=? AND visitor=?",
                (scope, day, visitor)).fetchone()
        return int(row[0])

    def count_since(self, scope: str, since_ts: float) -> int:
        return int(self._c.execute(
            "SELECT COUNT(*) FROM budget_ledger WHERE scope=? AND ts>=?",
            (scope, since_ts)).fetchone()[0])

    def usd(self, scope: str, day: str, run_id: str | None = None) -> float:
        if run_id is None:
            row = self._c.execute(
                "SELECT COALESCE(SUM(usd),0) FROM budget_ledger WHERE scope=? AND day=?",
                (scope, day)).fetchone()
        else:   # per-run totals are not day-bound: a run is one unit of work
            row = self._c.execute(
                "SELECT COALESCE(SUM(usd),0) FROM budget_ledger WHERE scope=? AND run_id=?",
                (scope, run_id)).fetchone()
        return float(row[0])

    def last_ts(self, scope: str, visitor: str) -> float | None:
        row = self._c.execute(
            "SELECT MAX(ts) FROM budget_ledger WHERE scope=? AND visitor=?",
            (scope, visitor)).fetchone()
        return None if row[0] is None else float(row[0])

    def distinct_visitors(self, scope: str, day: str) -> int:
        return int(self._c.execute(
            "SELECT COUNT(DISTINCT visitor) FROM budget_ledger "
            "WHERE scope=? AND day=? AND visitor IS NOT NULL", (scope, day)).fetchone()[0])

    def insert(self, scope: str, day: str, ts: float, visitor: str | None = None,
               run_id: str | None = None, usd: float = 0.0) -> int:
        sql = "INSERT INTO budget_ledger (ts, day, scope, visitor, run_id, usd) VALUES (?,?,?,?,?,?)"
        params = (ts, day, scope, visitor, run_id, usd)
        if self._pg:
            return int(self._c.execute(sql + " RETURNING id", params).fetchone()[0])
        return int(self._c.execute(sql, params).lastrowid)

    def settle(self, row_id: int, usd: float) -> None:
        self._c.execute("UPDATE budget_ledger SET usd=?, settled=1 WHERE id=?", (usd, row_id))


def _pg_connect():
    try:
        import psycopg2
        conn = psycopg2.connect(
            pg_url(), connect_timeout=5,
            options="-c statement_timeout=5000 -c idle_in_transaction_session_timeout=15000")
    except Exception as exc:  # noqa: BLE001 - any failure to reach the store is the same refusal
        raise StoreUnavailable(f"budget store (postgres) unreachable: {type(exc).__name__}") from exc
    key = pg_url()
    with _init_lock:
        if key not in _initialised:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_xact_lock(%s)", (_PG_LOCK_KEY,))
                    cur.execute(_PG_SCHEMA)
                conn.commit()
            except Exception as exc:  # noqa: BLE001
                conn.close()
                raise StoreUnavailable(f"budget store (postgres) schema setup failed: {type(exc).__name__}") from exc
            _initialised.add(key)
    return conn


@contextmanager
def _pg_transaction():
    conn = _pg_connect()
    try:
        cur = conn.cursor()
        try:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (_PG_LOCK_KEY,))
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            raise StoreUnavailable(f"budget store (postgres) lock failed: {type(exc).__name__}") from exc
        try:
            yield Tx(_PgConn(cur), pg=True)
        except BaseException:
            conn.rollback()
            raise
        conn.commit()
    finally:
        conn.close()


@contextmanager
def transaction():
    """Atomic check-then-reserve. SQLite: BEGIN IMMEDIATE takes the write
    lock up front. Postgres: a transaction-scoped advisory lock does the same.
    Either way two concurrent callers cannot both see room under a cap and
    both reserve it."""
    if pg_url():
        with _pg_transaction() as tx:
            yield tx
        return
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield Tx(conn)
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        conn.execute("COMMIT")
    finally:
        conn.close()


def now() -> float:
    return time.time()


def clear_scope(scope: str) -> None:
    """Test helper: delete one scope's rows."""
    with transaction() as tx:
        tx._c.execute("DELETE FROM budget_ledger WHERE scope=?", (scope,))
