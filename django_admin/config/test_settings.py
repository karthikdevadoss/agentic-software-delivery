"""Hermetic test settings: forces SQLite for the ledger alias even if
EVENT_LEDGER_DATABASE_URL is set in the developer's shell, so tests can never
touch a real Postgres ledger."""
import os

os.environ.pop("EVENT_LEDGER_DATABASE_URL", None)

from .settings import *  # noqa: E402,F401,F403

DATABASES = {
    "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"},
    "ledger": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"},
}
