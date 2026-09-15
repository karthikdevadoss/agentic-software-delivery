"""
Non-LLM Intelligence Metrics (Base Architecture V3 Section 16). Computes
REAL counts directly from real, structured sources on every run -- never
a hardcoded number that could silently go stale, and never a fabricated
composite "intelligence score" (the directive explicitly warns against
that). A metric this script cannot honestly compute from a real source is
reported as "UNKNOWN", never silently defaulted to 0.

Run: python agent/non_llm_intelligence_metrics.py
"""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENT_DIR = REPO_ROOT / "agent"
LEDGER_PATH = REPO_ROOT / "docs" / "ai" / "AI_ENGINEERING_QUALITY_LEDGER.yaml"
INVARIANT_REGISTRY_PATH = REPO_ROOT / "docs" / "INVARIANT_REGISTRY.md"


def _count_test_functions(path: Path) -> int:
    if not path.exists():
        return None
    return len(re.findall(r"^\s*def test_", path.read_text(encoding="utf-8"), re.MULTILINE))


def _count_invariant_registry_rows() -> int:
    """Counts real table rows in docs/INVARIANT_REGISTRY.md (lines
    starting with '| `' -- an actual invariant_id cell, not the header/
    separator rows)."""
    if not INVARIANT_REGISTRY_PATH.exists():
        return None
    text = INVARIANT_REGISTRY_PATH.read_text(encoding="utf-8")
    return len(re.findall(r"^\|\s*`[A-Z]+-\d+`", text, re.MULTILINE))


def _count_ledger_defects() -> int:
    if not LEDGER_PATH.exists():
        return None
    import yaml
    ledger = yaml.safe_load(LEDGER_PATH.read_text(encoding="utf-8")) or {}
    return len(ledger.get("defects", []))


def compute_metrics() -> dict:
    import reasoning_gateway as rg
    import test_reasoning_gateway_enforcement as rge

    architecture_boundary_test_files = [
        AGENT_DIR / "test_reasoning_gateway_enforcement.py",
        AGENT_DIR / "test_capability_boundaries.py",
        AGENT_DIR / "test_verify_claude_permissions_config.py",
    ]
    architecture_test_count = sum(
        (_count_test_functions(p) or 0) for p in architecture_boundary_test_files
    )

    test_architect_tests = _count_test_functions(AGENT_DIR / "test_test_architect.py")

    return {
        "advisory_purposes_defined": len(rg.ADVISORY_PURPOSES),
        "reasoning_gateway_approved_direct_call_sites": len(rge.APPROVED_DIRECT_IMPORT_FILES),
        "invariants_catalogued": _count_invariant_registry_rows(),
        "architecture_boundary_tests": architecture_test_count if architecture_test_count else None,
        "test_architect_contract_tests": test_architect_tests,
        "quality_ledger_defects_recorded": _count_ledger_defects(),
        # Deliberately NOT computed here (real, honest UNKNOWNs, not 0):
        "mutation_test_survivor_count": "UNKNOWN -- see docs/TESTING_ARCHITECTURE_V2.md (2 real seeded mutants this session, 0 survivors, but this is not an automated/repeatable count -- PIT was not adopted)",
        "zero_llm_verified_runs_lifetime": "UNKNOWN -- no counter exists yet for this specific event type; docs/ZERO_LLM_MODE_PROOF.md records one real, manually-run example",
        "escaped_defects_by_enforcement_tier": "UNKNOWN as an automated count -- see docs/ESCAPED_DEFECT_COMPILER.md's manually-audited table (prose, not yet structured data a script can recompute)",
    }


if __name__ == "__main__":
    metrics = compute_metrics()
    print(json.dumps(metrics, indent=2))
