#!/usr/bin/env python3
"""Live production check for the platform backend.

WHY THIS EXISTS (2026-11-26)
The PR 64 deploy (25 Nov) went out with plain `railway up` instead of
scripts/deploy_platform_with_si_corpus.sh, so the container shipped without
the Standing Interview corpus. Every page still returned 200, the nav entry
hid itself, and the full test run reported green -- the failure was silent.
The CV names Standing Interview as a live product surface, so "loads but
cannot answer" is a real defect, not a cosmetic one.

This script checks what a visitor would check, against the LIVE site:
  * every public page and probe answers 200
  * the security headers added in PR 63 are present
  * Standing Interview reports loaded:true with a non-zero chunk count
  * the gateway budget endpoint answers with its caps
It makes NO model calls and costs nothing. Exit code 0 = all good, 1 = at
least one failure (each failure is printed).

Run:  python scripts/live_check.py
      python scripts/live_check.py --base https://agentic-platform-backend-production.up.railway.app
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

DEFAULT_BASES = (
    "https://agentic.karthikdevadoss.com",
    "https://agentic-platform-backend-production.up.railway.app",
)

PAGES = (
    "/",
    "/workbench",
    "/triage",
    "/ask-codebase",
    "/eval",
    "/usage",
    "/dashboard",
    "/standing-interview",
    "/showcase/senior-java-ai-transformation",
    "/case-study/durable-agent",
    "/interviewer",
    "/kraken",
    "/ai-usage",
    "/recruiters",
    "/healthz",
    "/readyz",
)

REQUIRED_HEADERS = (
    "content-security-policy",
    "strict-transport-security",
    "x-content-type-options",
    "x-frame-options",
    "referrer-policy",
)


def fetch(url: str, timeout: float = 30.0):
    """Return (status, headers_lowercased, body_text). Never raises on HTTP errors."""
    req = urllib.request.Request(url, headers={"User-Agent": "platform-live-check"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, ""
    except Exception as e:  # network error, timeout, TLS
        return 0, {}, f"{type(e).__name__}: {e}"


def check_base(base: str, fetch_fn=fetch) -> list[str]:
    base = base.rstrip("/")
    failures: list[str] = []

    for path in PAGES:
        status, headers, body = fetch_fn(base + path)
        if status != 200:
            failures.append(f"{base}{path}: HTTP {status} {body[:120]}".rstrip())
            continue
        if path == "/":
            missing = [h for h in REQUIRED_HEADERS if h not in headers]
            if missing:
                failures.append(f"{base}/: missing security headers {missing}")

    status, _, body = fetch_fn(base + "/api/standing-interview/status")
    try:
        si = json.loads(body) if status == 200 else {}
    except ValueError:
        si = {}
    if not si.get("loaded") or not si.get("chunks"):
        failures.append(
            f"{base}: Standing Interview has NO knowledge base "
            f"(status={status}, loaded={si.get('loaded')}, chunks={si.get('chunks')}, "
            f"reason={si.get('reason')!r}). Redeploy with "
            f"scripts/deploy_platform_with_si_corpus.sh"
        )

    status, _, body = fetch_fn(base + "/api/github-knowledge")
    try:
        gh = json.loads(body) if status == 200 else {}
    except ValueError:
        gh = {}
    if not gh.get("documents"):
        failures.append(f"{base}: GitHub knowledge index is empty (status={status}, "
                        f"source={gh.get('source')}, last_error={gh.get('last_error')!r})")

    status, _, body = fetch_fn(base + "/api/budget")
    try:
        budget = json.loads(body) if status == 200 else {}
    except ValueError:
        budget = {}
    if "daily_usd_cap" not in (budget.get("gateway") or {}):
        failures.append(f"{base}/api/budget: gateway caps not reported (HTTP {status})")

    return failures


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", action="append", help="base URL (repeatable); default: both live addresses")
    args = ap.parse_args(argv)
    failures: list[str] = []
    for base in args.base or DEFAULT_BASES:
        found = check_base(base)
        print(f"{'PASS' if not found else 'FAIL'}  {base}")
        failures += found
    for f in failures:
        print(f"  - {f}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
