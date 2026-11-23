import json
from pathlib import Path

import pytest
from django.contrib import admin
from django.urls import reverse

from ledger.models import LedgerEvent, ReadOnlyError

DB = pytest.mark.django_db(databases=["default", "ledger"])
REPO = Path(__file__).resolve().parents[2]


def test_project_loads_and_model_registered():
    from django.apps import apps
    assert apps.is_installed("ledger")
    assert LedgerEvent in admin.site._registry
    assert LedgerEvent._meta.managed is False
    assert LedgerEvent._meta.db_table == "delivery_events"


def test_env_ledger_url_cannot_leak_into_tests():
    from django.conf import settings
    assert settings.DATABASES["ledger"]["ENGINE"].endswith("sqlite3")


@DB
def test_ledger_rows_appear_in_admin_changelist(superuser_client, ledger_rows):
    r = superuser_client.get(reverse("admin:ledger_ledgerevent_changelist"))
    assert r.status_code == 200
    body = r.content.decode()
    assert "test-run-A" in body and "test-run-B" in body


@DB
def test_admin_offers_no_writes(superuser_client, ledger_rows):
    r = superuser_client.get(reverse("admin:ledger_ledgerevent_changelist"))
    assert reverse("admin:ledger_ledgerevent_add") not in r.content.decode()
    assert superuser_client.get(reverse("admin:ledger_ledgerevent_add")).status_code == 403
    assert superuser_client.post(reverse("admin:ledger_ledgerevent_delete", args=["test-evt-1"])).status_code == 403
    assert superuser_client.post(reverse("admin:ledger_ledgerevent_change", args=["test-evt-1"]),
                                 {"run_id": "hacked"}).status_code == 403
    assert LedgerEvent.objects.get(pk="test-evt-1").run_id == "test-run-A"


@DB
def test_model_level_writes_refused(ledger_rows):
    with pytest.raises(ReadOnlyError):
        LedgerEvent(event_id="x", timestamp_utc="2026-01-01T00:00:00Z", event_type="t").save()
    with pytest.raises(ReadOnlyError):
        LedgerEvent.objects.get(pk="test-evt-1").delete()


@DB
def test_spend_page_sums_fixture_rows(staff_client, ledger_rows):
    r = staff_client.get(reverse("spend"))
    assert r.status_code == 200
    assert r.context["totals"] == {"input_tokens": 300, "output_tokens": 120, "cost_usd": 0.75}
    assert r.context["event_count"] == 3


@DB
def test_spend_page_honest_when_ledger_table_missing(staff_client):
    r = staff_client.get(reverse("spend"))  # no table created in this test
    assert r.status_code == 200
    assert "not reachable or table missing" in r.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["index", "spend", "budgets", "evals"])
def test_views_require_staff(client, name):
    r = client.get(reverse(name))
    assert r.status_code == 302 and "login" in r["Location"]


@pytest.mark.django_db
def test_eval_page_shows_committed_scores(staff_client):
    committed = json.loads((REPO / "agent" / "web" / "eval-results.json").read_text())
    body = staff_client.get(reverse("evals")).content.decode()
    assert committed["commit_sha"] in body
    for m in committed["metrics"]:
        assert m["label"] in body and str(m["score"]) in body


@pytest.mark.django_db
def test_eval_page_with_labelled_fixture_and_history(staff_client, settings, tmp_path):
    fx = tmp_path / "r.json"
    fx.write_text(json.dumps({"generated_at": "TEST-FIXTURE", "commit_sha": "test-fixture-sha", "overall_passed": True,
                              "metrics": [{"label": "TEST metric", "score": 0.123, "threshold": 0.1, "comparator": ">=", "passed": True}]}))
    hist = tmp_path / "hist"; hist.mkdir(); (hist / "2026-test.json").write_text("{}")
    settings.EVAL_RESULTS_PATH = str(fx); settings.EVAL_HISTORY_DIR = str(hist)
    body = staff_client.get(reverse("evals")).content.decode()
    assert "0.123" in body and "2026-test.json" in body


@pytest.mark.django_db
def test_eval_history_absent_is_stated_not_invented(staff_client, settings, tmp_path):
    settings.EVAL_HISTORY_DIR = str(tmp_path / "nope")
    body = staff_client.get(reverse("evals")).content.decode()
    assert "No eval-history directory" in body and "none is invented" in body


@pytest.mark.django_db
def test_budget_page_in_memory_honesty_without_durable_file(staff_client, settings, tmp_path):
    settings.BUDGET_SQLITE_PATH = str(tmp_path / "missing.sqlite3")
    body = staff_client.get(reverse("budgets")).content.decode()
    assert "reset on restart" in body
    assert "No durable budget store file" in body
    import si_budget, triage_budget
    assert str(triage_budget.DEFAULT_DAILY_MAX) in body
    assert str(si_budget.SI_DAILY_MAX_ANSWERS) in body


@pytest.mark.django_db
def test_budget_page_reads_optional_sqlite_without_assuming_schema(staff_client, settings, tmp_path):
    import sqlite3
    p = tmp_path / "b.sqlite3"
    c = sqlite3.connect(p); c.execute("CREATE TABLE test_table (a)"); c.execute("INSERT INTO test_table VALUES (1)"); c.commit(); c.close()
    settings.BUDGET_SQLITE_PATH = str(p)
    body = staff_client.get(reverse("budgets")).content.decode()
    assert "test_table" in body and "1 row(s)" in body


@pytest.mark.django_db
def test_budget_page_survives_corrupt_file(staff_client, settings, tmp_path):
    p = tmp_path / "bad.sqlite3"; p.write_bytes(b"not a database" * 50)
    settings.BUDGET_SQLITE_PATH = str(p)
    r = staff_client.get(reverse("budgets"))
    assert r.status_code == 200 and "Could not read it" in r.content.decode()
