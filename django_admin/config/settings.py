"""Settings for the LOCAL read-only admin slice (django_admin/).

Honest scope: this runs beside the Starlette API, it is not the product and
not a production IAM/SSO admin. Defaults are for a developer laptop.
"""
import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent
AGENT_DIR = REPO_ROOT / "agent"

# Budget modules (agent/triage_budget.py, agent/si_budget.py) are stdlib-only
# and imported read-only so the limits shown are the real ones on this branch.
if str(AGENT_DIR) not in sys.path:
    sys.path.append(str(AGENT_DIR))

# Dev-only insecure fallback when DJANGO_SECRET_KEY is unset. Never use in a
# shared/hosted environment: with the fallback, DEBUG is still False-by-default
# only if you set it; ALLOWED_HOSTS stays local-only either way.
_env_key = os.environ.get("DJANGO_SECRET_KEY", "")
SECRET_KEY = _env_key or "django-insecure-local-dev-only-do-not-use-elsewhere"
USING_INSECURE_DEV_KEY = not _env_key

DEBUG = os.environ.get("DJANGO_DEBUG", "").lower() in ("1", "true", "yes")
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if h]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "ledger",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]


def _ledger_database() -> dict:
    """The existing ledger (delivery_events). Postgres when
    EVENT_LEDGER_DATABASE_URL is set (same variable agent/event_ledger.py uses),
    opened with default_transaction_read_only=on; otherwise an empty local
    SQLite file, so nothing here ever invents rows."""
    url = os.environ.get("EVENT_LEDGER_DATABASE_URL", "").strip()
    if url.startswith(("postgres://", "postgresql://")):
        p = urlsplit(url)
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(p.path.lstrip("/")),
            "USER": unquote(p.username or ""),
            "PASSWORD": unquote(p.password or ""),
            "HOST": p.hostname or "",
            "PORT": str(p.port or ""),
            "OPTIONS": {"options": "-c default_transaction_read_only=on"},
            "TEST": {"MIRROR": "default"},  # never create test DBs on a real server
        }
    return {"ENGINE": "django.db.backends.sqlite3",
            "NAME": os.environ.get("ADMIN_LEDGER_SQLITE_PATH", str(BASE_DIR / "var" / "ledger.sqlite3"))}


(BASE_DIR / "var").mkdir(exist_ok=True)
DATABASES = {
    # Django's own auth/session tables only. Never holds ledger data.
    "default": {"ENGINE": "django.db.backends.sqlite3",
                "NAME": os.environ.get("ADMIN_AUTH_SQLITE_PATH", str(BASE_DIR / "var" / "admin.sqlite3"))},
    "ledger": _ledger_database(),
}
DATABASE_ROUTERS = ["ledger.routers.LedgerRouter"]

# Optional durable budget store from a *different, unmerged* PR (#53). Read
# only if the file exists; never required, never created.
BUDGET_SQLITE_PATH = os.environ.get("ADMIN_BUDGET_SQLITE_PATH", str(AGENT_DIR / "budget_store.sqlite3"))
EVAL_RESULTS_PATH = os.environ.get("ADMIN_EVAL_RESULTS_PATH", str(AGENT_DIR / "web" / "eval-results.json"))
EVAL_HISTORY_DIR = os.environ.get("ADMIN_EVAL_HISTORY_DIR", str(AGENT_DIR / "web" / "eval-history"))

STATIC_URL = "static/"
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
