"""TEST DATA ONLY. Every ledger row, token count and cost below is a synthetic
test value (source='unit_test_fixture'); none is a production measurement."""
import pytest
from django.contrib.auth import get_user_model
from django.db import connections

DDL = """CREATE TABLE delivery_events (
    event_id TEXT PRIMARY KEY, schema_version INTEGER, timestamp_utc TIMESTAMP NOT NULL,
    event_type TEXT NOT NULL, stage TEXT, status TEXT, session_id TEXT, run_id TEXT,
    requirement_id TEXT, source TEXT, activity_class TEXT, duration_ms REAL, provider TEXT,
    model TEXT, input_tokens INTEGER, output_tokens INTEGER, cache_read_tokens INTEGER,
    cache_write_tokens INTEGER, cost_usd REAL, pricing_version TEXT, evidence_quality TEXT,
    backfill_source TEXT)"""

ROWS = [
    ("test-evt-1", "2026-01-01 00:00:00", "model_call", "test-run-A", "unit_test_fixture", "test-provider", "test-model-x", 100, 50, 0.25),
    ("test-evt-2", "2026-01-01 00:01:00", "model_call", "test-run-A", "unit_test_fixture", "test-provider", "test-model-x", 200, 70, 0.50),
    ("test-evt-3", "2026-01-01 00:02:00", "run_started", "test-run-B", "unit_test_fixture", None, None, None, None, None),
]


@pytest.fixture
def ledger_rows(db):
    pytest.importorskip("django")
    conn = connections["ledger"]
    with conn.cursor() as cur:
        cur.execute(DDL)
        for eid, ts, et, run, src, prov, model, it, ot, cost in ROWS:
            cur.execute(
                "INSERT INTO delivery_events (event_id, schema_version, timestamp_utc, event_type, run_id,"
                " source, provider, model, input_tokens, output_tokens, cost_usd) VALUES (%s,1,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                [eid, ts, et, run, src, prov, model, it, ot, cost])
    return ROWS


@pytest.fixture
def staff_client(db, client):
    u = get_user_model().objects.create_user("test-staff", password="test-pass-not-real", is_staff=True)
    client.force_login(u)
    return client


@pytest.fixture
def superuser_client(db, client):
    u = get_user_model().objects.create_superuser("test-root", password="test-pass-not-real")
    client.force_login(u)
    return client
