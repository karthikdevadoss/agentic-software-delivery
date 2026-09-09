"""
Deterministic, server-side risk/complexity classification for trainer-
submitted requirements. The LLM never decides its own authority — this
module runs BEFORE any agent/tool call, on the raw requirement text, and
its decision is a hard gate: BLOCK means the agent loop is never even
started for that requirement.

Two-layer defense, not one:
  1. This module (text-level) decides whether to attempt the change at all.
  2. write_tools.ALLOWED_WRITE_PREFIXES/EXTENSIONS (file-level) independently
     rejects any proposed file outside the safe scope, even if this
     module's classification was wrong or too permissive — see
     trainer_tools.py's auto-approval, which re-checks scope itself
     rather than trusting the text-level classification alone.

Deliberately simple and over-inclusive on the BLOCK side: a keyword-based
denylist plus a length/vagueness heuristic. Not a machine-learned
classifier — a classifier that can't explain *why* it blocked something
is not acceptable for a production-authority gate.
"""

import re

# Any of these appearing anywhere in the requirement forces BLOCKED,
# regardless of how small the rest of the request sounds. Deliberately
# broad and over-inclusive — false positives (blocking something actually
# safe) are the acceptable failure mode here, not false negatives.
BLOCK_KEYWORDS = [
    "auth", "login", "password", "secret", "credential", "api key", "apikey",
    "oauth", "jwt", "token", "session", "security", "encrypt", "permission",
    "role", "admin", "payment", "billing", "credit card", "stripe", "money",
    "delete", "drop table", "truncate", "migration", "schema change",
    "database schema", "alter table", "production data",
    "infrastructure", "dependency", "pom.xml", "upgrade spring",
    "upgrade java", "version bump", "shell", "subprocess", "exec(",
    "eval(", "os.system", ".env", "environment variable", "ci/cd",
    "github action", "git history", "force push", "rebase", "reset --hard",
    "vercel", "railway account", "railway.json", "dns", "domain",
    "microservice", "multi-service", "kafka", "redis", "postgres",
    "docker", "kubernetes", "aws", "cloud config", "refactor the entire",
    "rewrite the entire", "redesign the architecture", "new service",
]

# Requirements this short/vague rarely give the agent enough to safely
# scope a change to 1-3 files — treated as MEDIUM complexity at minimum,
# not auto-executed, even with no blocked keywords.
MIN_WORDS_FOR_TINY = 4

COMPLEXITY_LARGE_WORDS = 60
COMPLEXITY_MEDIUM_WORDS = 25

SUGGESTED_ALTERNATIVES = [
    'Add a small "Agent Demo" status badge near the page title',
    "Add a read-only customer-count endpoint and show the count on the page",
    "Change the wording of the Create Customer success message",
    'Add a small "Powered by Agentic Delivery" footer line to the page',
]


def _matched_block_keywords(text: str) -> list:
    lowered = text.lower()
    return [kw for kw in BLOCK_KEYWORDS if kw in lowered]


def _complexity(text: str) -> str:
    words = len(text.split())
    if words > COMPLEXITY_LARGE_WORDS:
        return "LARGE"
    if words > COMPLEXITY_MEDIUM_WORDS:
        return "MEDIUM"
    if words < MIN_WORDS_FOR_TINY:
        return "MEDIUM"  # too vague to scope confidently, not because it's big
    return "TINY" if words <= 12 else "SMALL"


def classify(requirement: str) -> dict:
    """Returns a decision dict; never raises. `decision` is either
    'auto' (safe to attempt automatically) or 'blocked' (must not run the
    agent loop for this requirement at all)."""
    requirement = (requirement or "").strip()

    if not requirement:
        return {
            "complexity": "N/A", "risk": "N/A", "decision": "blocked",
            "reason": "Empty requirement.",
            "matched_keywords": [], "suggested_alternatives": SUGGESTED_ALTERNATIVES,
        }

    matched = _matched_block_keywords(requirement)
    complexity = _complexity(requirement)

    if matched:
        return {
            "complexity": complexity, "risk": "HIGH", "decision": "blocked",
            "reason": f"Contains a term outside the demo's safe boundary: {', '.join(matched[:3])}.",
            "matched_keywords": matched, "suggested_alternatives": SUGGESTED_ALTERNATIVES,
        }

    if complexity in ("MEDIUM", "LARGE"):
        reason = (
            "Requirement is too long/ambiguous to confidently scope to a tiny, reversible change."
            if complexity == "MEDIUM" else
            "Requirement reads as a larger feature, not a small bounded demo change."
        )
        return {
            "complexity": complexity, "risk": "MEDIUM", "decision": "blocked",
            "reason": reason,
            "matched_keywords": [], "suggested_alternatives": SUGGESTED_ALTERNATIVES,
        }

    return {
        "complexity": complexity, "risk": "LOW", "decision": "auto",
        "reason": "No blocked terms found; requirement is short and specific enough to scope to a small, reversible change.",
        "matched_keywords": [], "suggested_alternatives": [],
    }
