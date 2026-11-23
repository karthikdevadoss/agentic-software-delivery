# django_admin — local read-only admin slice

A small Django project that runs **beside** the Starlette API (`agent/web_server.py`).
It is a local admin/inspection slice. It is **not** a rewrite of the platform, not
the public product, and **not** a production IAM/SSO admin. Nothing here is deployed
or wired into Railway.

## What it shows
| Page | Source | Notes |
|---|---|---|
| `/admin/` → *ledger events* | existing Postgres `delivery_events` (`infra/event-ledger/schema.sql`) via an **unmanaged** model | list/filter/search; no add/change/delete; `payload` JSONB deliberately not mapped |
| `/spend/` | same table, real `cost_usd` + token columns | NULL shown as "n/a", not 0. Rows whose cost exists only inside `payload` (pre-column history) are not counted |
| `/budgets/` | `agent/triage_budget.py`, `agent/si_budget.py` limits; optional SQLite file | counters live in the Starlette process's memory and **reset on restart**; this process can't see them, so only limits are shown |
| `/evals/` | committed `agent/web/eval-results.json`; `agent/web/eval-history/` if present | point-in-time snapshot. If no history dir exists, the page says so |

## Run it
```bash
cd django_admin
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate --database default      # Django auth/session tables only (local SQLite in var/)
python manage.py createsuperuser                 # local dev login; choose your own password, never commit one
python manage.py runserver 8001                  # Starlette keeps its own port; this is separate
```
Then open http://127.0.0.1:8001/ (log in with the superuser).

## Configuration (env vars)
- `EVENT_LEDGER_DATABASE_URL` — same variable `agent/event_ledger.py` uses. When set (postgres://…), the ledger alias connects with `default_transaction_read_only=on`. When unset, the ledger alias is an empty local SQLite file and `/spend/` says the table is missing. No rows are ever invented.
- `DJANGO_SECRET_KEY` — if unset, an **insecure dev-only key** is used (flag `USING_INSECURE_DEV_KEY`). Set a real one for anything beyond localhost.
- `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS` — default off / localhost only.
- `ADMIN_BUDGET_SQLITE_PATH` — optional durable budget SQLite file (default `agent/budget_store.sqlite3`, the path assumed for the unmerged budget-store PR #53 — **unverified**). Missing file is fine; if present it is opened `mode=ro` and only table names + row counts are listed (no schema assumed).
- `ADMIN_EVAL_RESULTS_PATH`, `ADMIN_EVAL_HISTORY_DIR` — override eval locations.

## Tests (hermetic: in-memory SQLite, no Postgres, no network)
```bash
cd django_admin && python -m pytest -q
```
`config/test_settings.py` forces SQLite even if `EVENT_LEDGER_DATABASE_URL` is set in your shell. Ledger rows in tests are synthetic (`source='unit_test_fixture'`, ids `test-*`), not production data.

## Assumptions and honest limits
- Read-only is enforced three ways: admin permissions deny add/change/delete (403), the model's `save()`/`delete()` raise, and the Postgres session is read-only. Django's own **Users/Groups** admin is still editable (needed to manage local logins).
- The Django `ledger` app maps only the columns it displays; if `schema.sql` changes, update `ledger/models.py`.
- No migrations for the ledger (`managed=False`, router blocks migrate). The existing `ensure_schema()` remains the only schema owner.
- Eval history and the durable budget store come from other, unmerged PRs (#51, #53); this branch does not include them.
- Not tested against a live Postgres in this slice (SQLite only); the Postgres settings branch is unexercised.
- Not load-, security- or accessibility-reviewed; local use only.
