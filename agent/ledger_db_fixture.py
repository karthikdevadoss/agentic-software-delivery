"""
Test fixture for the Postgres event ledger (agent/event_ledger.py).

WHY THIS EXISTS (Automation Sprint 8, 2026-10-06): test_event_ledger.py was
never run in CI. It needs a real Postgres, CI held none, so the module sat in
ci_python_tests.LIVE_INFRA_MODULES and 27 of its 42 tests only ever ran on a
machine that happened to hold EVENT_LEDGER_DATABASE_URL. This module gives
those tests a database without weakening a single assertion:

1. TEMP DATABASE (what CI uses). If EVENT_LEDGER_TEST_SERVER_URL points at a
   Postgres server (any database on it, e.g. .../postgres), setUpModule()
   creates a fresh, uniquely named database (ledger_test_<hex>), points
   EVENT_LEDGER_DATABASE_URL at it for the duration of the module, and
   tearDownModule() drops it again. ensure_schema() builds the real schema
   from schema.sql, so the tests run against the real DDL on an empty ledger.
   CI provides the server as a postgres service container.

2. EXISTING DATABASE (the old local behaviour, unchanged). If only
   EVENT_LEDGER_DATABASE_URL is set, the tests use it as they always did.

3. NO DATABASE. If neither is set, or the server is unreachable, every test
   that needs the database is SKIPPED with the reason, and the tests that
   patch the network boundary (outage spool, redaction, envelope, timezone
   windows, stale sync lock, the concurrent ensure_schema lock) still run.

   EXCEPT when EVENT_LEDGER_REQUIRE_DB=1 (set in CI). Then "no database" is a
   hard FAILURE, never a skip: a CI job that silently skipped every real
   ledger test would read green having proven nothing -- the same false-green
   family ci_python_tests.py exists to prevent.

Usage in a test module:

    from ledger_db_fixture import needs_ledger_db, setUpModule, tearDownModule

    @needs_ledger_db            # on a TestCase class: guards every test via setUp
    class RealInsertTestCase(unittest.TestCase): ...

    @needs_ledger_db            # or on a single test method
    def test_real_thing(self): ...

Works the same under `python -m unittest` and pytest (pytest runs unittest
classes and honours setUpModule/tearDownModule and SkipTest).
"""

import functools
import os
import unittest
import uuid
from urllib.parse import urlsplit, urlunsplit

SERVER_URL_ENV = "EVENT_LEDGER_TEST_SERVER_URL"
LEDGER_URL_ENV = "EVENT_LEDGER_DATABASE_URL"
REQUIRE_ENV = "EVENT_LEDGER_REQUIRE_DB"

_state = {
    "checked": False,
    "available": False,
    "reason": "not checked yet",
    "temp_db": None,          # name of the temp database we created, if any
    "server_url": None,
    "previous_ledger_url": None,
    "had_previous_ledger_url": False,
}


def _require_db() -> bool:
    return os.environ.get(REQUIRE_ENV, "").strip() in ("1", "true", "yes")


def _with_database(url: str, dbname: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, "/" + dbname, parts.query, parts.fragment))


def _probe(url: str):
    """Return (ok, reason). One short connection, SELECT 1, closed."""
    try:
        import psycopg2
    except ImportError as exc:  # pragma: no cover - psycopg2 is pinned in requirements
        return False, f"psycopg2 not importable: {exc}"
    try:
        conn = psycopg2.connect(url, connect_timeout=3)
    except Exception as exc:
        return False, f"Postgres not reachable: {type(exc).__name__}: {str(exc).strip()[:200]}"
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    finally:
        conn.close()
    return True, "reachable"


def _admin_execute(server_url: str, sql: str):
    import psycopg2
    conn = psycopg2.connect(server_url, connect_timeout=5)
    try:
        conn.autocommit = True  # CREATE/DROP DATABASE cannot run in a transaction
        with conn.cursor() as cur:
            cur.execute(sql)
    finally:
        conn.close()


def _reset_ledger_module_state():
    """event_ledger caches 'schema already created' per process; a new
    database needs the real DDL run again."""
    try:
        import event_ledger
    except ImportError:
        return
    event_ledger._schema_ready = False


def setUpModule():
    """Decide once per test module whether a real ledger database exists,
    creating a temp database first when a test server is configured."""
    _state["checked"] = True
    server_url = os.environ.get(SERVER_URL_ENV, "").strip()
    if server_url:
        ok, reason = _probe(server_url)
        if not ok:
            _state["available"], _state["reason"] = False, f"{SERVER_URL_ENV}: {reason}"
            return
        dbname = f"ledger_test_{uuid.uuid4().hex[:12]}"
        _admin_execute(server_url, f'CREATE DATABASE "{dbname}"')
        _state["temp_db"] = dbname
        _state["server_url"] = server_url
        _state["had_previous_ledger_url"] = LEDGER_URL_ENV in os.environ
        _state["previous_ledger_url"] = os.environ.get(LEDGER_URL_ENV)
        os.environ[LEDGER_URL_ENV] = _with_database(server_url, dbname)
        _reset_ledger_module_state()
        ok, reason = _probe(os.environ[LEDGER_URL_ENV])
        _state["available"] = ok
        _state["reason"] = f"temp database {dbname}: {reason}"
        return

    ledger_url = os.environ.get(LEDGER_URL_ENV, "").strip()
    if not ledger_url:
        _state["available"] = False
        _state["reason"] = f"neither {SERVER_URL_ENV} nor {LEDGER_URL_ENV} is set"
        return
    ok, reason = _probe(ledger_url)
    _state["available"], _state["reason"] = ok, f"{LEDGER_URL_ENV}: {reason}"


def tearDownModule():
    dbname = _state.get("temp_db")
    if not dbname:
        return
    if _state["had_previous_ledger_url"]:
        os.environ[LEDGER_URL_ENV] = _state["previous_ledger_url"]
    else:
        os.environ.pop(LEDGER_URL_ENV, None)
    _reset_ledger_module_state()
    # FORCE closes any connection a test left open (PostgreSQL 13+).
    _admin_execute(_state["server_url"], f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)')
    _state["temp_db"] = None


def ledger_db_available() -> bool:
    if not _state["checked"]:
        setUpModule()
    return _state["available"]


def ledger_db_reason() -> str:
    return _state["reason"]


def check_ledger_db(testcase=None):
    """Skip (or, with EVENT_LEDGER_REQUIRE_DB=1, fail) when no database."""
    if ledger_db_available():
        return
    message = f"no event-ledger database: {ledger_db_reason()}"
    if _require_db():
        raise AssertionError(
            f"{message}. {REQUIRE_ENV}=1 is set, so this is a failure, not a skip "
            "(a skipped real-ledger suite must never read as green in CI).")
    raise unittest.SkipTest(message)


def needs_ledger_db(obj):
    """Mark a TestCase class or a single test method as needing the real
    Postgres ledger. On a class the check runs in setUp, before any
    per-class setUp that itself opens a connection."""
    if isinstance(obj, type) and issubclass(obj, unittest.TestCase):
        original_setup = obj.setUp

        @functools.wraps(original_setup)
        def setUp(self, *args, **kwargs):
            check_ledger_db(self)
            return original_setup(self, *args, **kwargs)

        obj.setUp = setUp
        return obj

    @functools.wraps(obj)
    def wrapper(self, *args, **kwargs):
        check_ledger_db(self)
        return obj(self, *args, **kwargs)

    return wrapper
