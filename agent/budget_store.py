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
    counters; sharing them needs a Postgres-backed implementation of the same
    `transaction()` interface, which is not built here.
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


class Tx:
    """Operations valid inside one atomic transaction."""

    def __init__(self, conn: sqlite3.Connection):
        self._c = conn

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
        cur = self._c.execute(
            "INSERT INTO budget_ledger (ts, day, scope, visitor, run_id, usd) VALUES (?,?,?,?,?,?)",
            (ts, day, scope, visitor, run_id, usd))
        return int(cur.lastrowid)

    def settle(self, row_id: int, usd: float) -> None:
        self._c.execute("UPDATE budget_ledger SET usd=?, settled=1 WHERE id=?", (usd, row_id))


@contextmanager
def transaction():
    """Atomic check-then-reserve: BEGIN IMMEDIATE takes the write lock up
    front, so two concurrent callers cannot both see room under a cap and
    both reserve it."""
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
