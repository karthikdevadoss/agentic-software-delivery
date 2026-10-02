"""Generate docs/testing-matrix.json from the real suite declarations.

Generated rather than hand-written on purpose: agent/select_tests.py already
holds the authoritative tags and cost classes, and a second hand-maintained copy
would drift from it within a sprint. The extra per-suite prose that only belongs
in the matrix (purpose, layer, known limitations) lives here.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[0]
# Resolve the repo root from the actual git checkout rather than from this
# script's location, which sits in a scratch directory.
REPO = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, check=True,
                           cwd=r"C:\Users\Hemapriya\agentic-software-delivery"
                           ).stdout.strip())
sys.path.insert(0, str(REPO / "agent"))

import select_tests  # noqa: E402
import ci_python_tests  # noqa: E402
import test_impact_analysis as tia  # noqa: E402

# Per-suite prose that has no home in select_tests.py. Keys must match
# select_tests.SUITES exactly; a mismatch fails loudly below rather than
# silently producing a matrix with holes.
DETAIL = {
    "python-hermetic": {
        "purpose": "Deterministic correctness of every Python module in agent/ that can run without live infrastructure.",
        "layer": "unit + module integration",
        "change_classes": ["ALL"],
        "requires_network": False,
        "requires_model": False,
        "known_limitations": [
            "Ten modules are excluded because they need live infrastructure this suite does not hold (real Postgres, the deployed Railway apps, a spawned web_server subprocess, a JDK, this developer machine's ~/.claude/settings.json). All ten are printed with their individual reason on every run.",
            "Three hermetic modules need the RAG indexes on disk, which are gitignored build output. They fail on a fresh checkout until `python rag_index.py` and `python backend_rag_index.py` have been run once.",
            "No coverage measurement and no mutation score.",
        ],
    },
    "python-quality-monitors": {
        "purpose": "Standing Interview answer quality, scored against a real captured sample of production answers.",
        "layer": "AI quality monitor",
        "change_classes": ["PROMPT_MODEL_AGENT"],
        "requires_network": False,
        "requires_model": False,
        "known_limitations": [
            "KNOWN RED on question m ('describe a technical disagreement'), 2 of 3 captured draws not answered. Tracked as SI-19/BL-149.",
            "Three draws per question cannot separate a fixed defect from an unlucky sample. Repeated stochastic trials are backlog.",
            "Of the two failing draws, m/2 is outcome=no_model (the model was never called) and only m/3 is a real decline. They are different causes sharing one assertion.",
            "Scores an archive, so it says nothing about what production would answer today.",
        ],
    },
    "node-frontend-harnesses": {
        "purpose": "Deterministic assertions over the rendered HTML the Usage, Workbench and Learn renderers produce, without a browser.",
        "layer": "frontend unit",
        "change_classes": ["FRONTEND_JS", "STATIC_HTML_COPY", "CI_TESTING_INFRA"],
        "requires_network": False,
        "requires_model": False,
        "known_limitations": [
            "Asserts strings in generated HTML, not layout or appearance. It cannot see that an element renders off screen.",
            "Covers three renderers. Triage, Showcase, Ask Codebase and Standing Interview have no equivalent harness.",
        ],
    },
    "static-gate": {
        "purpose": "Non-source artefact properties a judgement call keeps getting wrong: file mode bits, shebangs, and a literal '--' inside an XML/HTML comment.",
        "layer": "static",
        "change_classes": ["ALL"],
        "requires_network": False,
        "requires_model": False,
        "known_limitations": [
            "Reads committed content via `git show HEAD:<path>`, so a fix in the working tree does not clear it until committed. That is deliberate (it checks what is actually committed) and surprising the first time.",
            "Its unqualified-framework-@Bean check is ADVISORY only and currently reports 12 findings; it does not gate.",
        ],
    },
    "config-drift-gate": {
        "purpose": "A property key present in one Spring profile file and missing from another -- the Owner's real NRG stage-versus-prod incident class.",
        "layer": "static",
        "change_classes": ["JAVA_BACKEND", "CI_TESTING_INFRA", "SECURITY_WRITE_AUTHORITY"],
        "requires_network": False,
        "requires_model": False,
        "known_limitations": [
            "Compares key presence, not values, so a key present in both files with a wrong value passes.",
        ],
    },
    "java-customer-app": {
        "purpose": "The real Spring Boot application the Workbench pipeline mutates: unit tests plus real Postgres integration tests via Testcontainers.",
        "layer": "unit + integration",
        "change_classes": ["JAVA_BACKEND", "SECURITY_WRITE_AUTHORITY", "CI_TESTING_INFRA"],
        "requires_network": False,
        "requires_model": False,
        "known_limitations": [
            "The Testcontainers Postgres tests SKIP on this developer machine, which has no Docker (docs/DECISIONS.md). They only really run in CI.",
            "The Dockerfile build is likewise CI-only, and is the only place app/Dockerfile is proven to build at all.",
        ],
    },
    "java-microservices": {
        "purpose": "Each of the six services as an independent Maven project, so one service's failure does not obscure the other five.",
        "layer": "unit + integration",
        "change_classes": ["JAVA_BACKEND", "CI_TESTING_INFRA"],
        "requires_network": False,
        "requires_model": False,
        "known_limitations": [
            "billing-service's Redis-backed tests are disabledWithoutDocker and skip locally.",
            "Tests each service in isolation. Nothing here exercises them together -- that is the real-topology tier.",
        ],
    },
    "real-topology": {
        "purpose": "Four real JVM service processes started and coordinated together: real Eureka registration, real gateway routing, a real cross-service enrolment.",
        "layer": "multi-process system",
        "change_classes": ["JAVA_BACKEND", "SECURITY_WRITE_AUTHORITY", "CI_TESTING_INFRA"],
        "requires_network": False,
        "requires_model": False,
        "known_limitations": [
            "Heavy: four concurrent JVMs and several minutes. Not part of a local pre-commit check.",
            "Gating since BL-056, after three consecutive clean local runs. Its history includes a real drift between two features built the same night (ACT-015), which is the reason it exists.",
        ],
    },
    "playwright-functional": {
        "purpose": "Real-browser coverage of the recruiter paths: the public pages render their own real content, links resolve, overflow and console errors at four widths, third-party network behaviour, and the public copy claims.",
        "layer": "end-to-end browser",
        "change_classes": ["CSS_VISUAL", "STATIC_HTML_COPY", "FRONTEND_JS", "PYTHON_APP_LOGIC", "CI_TESTING_INFRA", "SECURITY_WRITE_AUTHORITY"],
        "requires_network": False,
        "requires_model": False,
        "known_limitations": [
            "NON-BLOCKING in CI until five consecutive green runs on master. Promotion criterion is written into .github/workflows/ci.yml.",
            "Five specs fail on this laptop for environment reasons proven pre-existing in Sprint 16 (no ledger data, no verified run, Customer App not running). They pass in production.",
            "Chromium only. No Firefox, no WebKit, no real device.",
            "It measures geometry and content. It does not measure whether a page looks good.",
        ],
    },
    "playwright-visual-pack": {
        "purpose": "Screenshot comparison against an accepted baseline, to catch unintended visual change from a stylesheet edit that moved a page nobody was looking at.",
        "layer": "end-to-end browser (visual)",
        "change_classes": ["CSS_VISUAL", "STATIC_HTML_COPY"],
        "requires_network": False,
        "requires_model": False,
        "known_limitations": [
            "GATED OFF behind VISUAL_REGRESSION=1 and NOT release-blocking: the Owner has not accepted the baseline. Promotion criterion is his acceptance.",
            "Catches CHANGE, never first-time ugliness. A baseline of an ugly page is an ugly baseline, faithfully defended.",
            "/usage and /dashboard are captured to a bounded height because their length tracks how much real history the environment holds (6,759px against production, 69,830px against this laptop).",
            "Masked regions are no longer protected. Masks are element-scoped and listed per page for exactly that reason.",
        ],
    },
    "rag-mcp-evals": {
        "purpose": "Retrieval and routing quality against recorded thresholds, using deterministic oracles and no model call.",
        "layer": "AI evaluation (deterministic)",
        "change_classes": ["PROMPT_MODEL_AGENT", "PYTHON_APP_LOGIC", "CI_TESTING_INFRA"],
        "requires_network": False,
        "requires_model": False,
        "known_limitations": [
            "Deterministic oracles only. No LLM-as-judge anywhere, by decision.",
            "The eval set is small and hand-built. A dataset of 20-50+ real failures is backlog.",
        ],
    },
    "si-answer-quality-paid": {
        "purpose": "Re-run the audit's questions against live production to produce a fresh capture -- the only evidence that can settle whether a specification change actually changed model behaviour.",
        "layer": "AI evaluation (live, paid)",
        "change_classes": ["PROMPT_MODEL_AGENT"],
        "requires_network": True,
        "requires_model": True,
        "known_limitations": [
            "REFUSED by default. Requires BOTH ALLOW_PAID_TESTS=1 and a positive PAID_TEST_BUDGET_USD, and refuses before any provider client is constructed.",
            "Approximately $0.023 per request from the audit's real measured total, so the default 18-request run is roughly $0.41. That figure is CALCULATED from real captured data, not an actual figure for any future run.",
            "The deployed per-visitor spend cap can 429 this script mid-capture, producing an incomplete capture. It raises rather than storing a refusal as an answer.",
        ],
    },
    "workbench-real-acceptance": {
        "purpose": "The actual public Workbench journey end to end for real: submit a supported requirement, watch it reach COMPLETED, confirm the change in real production, reset, confirm the baseline is restored.",
        "layer": "end-to-end production acceptance",
        "change_classes": [],
        "requires_network": True,
        "requires_model": False,
        "known_limitations": [
            "Commits, pushes and DEPLOYS a real change to the production Customer App. Operator-initiated only -- deliberately unmapped in the TIA so no file edit can trigger it.",
            "Costs no model tokens (the public path is deterministic) but does consume a real deployment.",
        ],
    },
}


def main() -> int:
    suites = select_tests.SUITES
    missing = sorted(set(suites) - set(DETAIL))
    extra = sorted(set(DETAIL) - set(suites))
    if missing or extra:
        raise SystemExit(
            f"matrix/suite mismatch. Missing detail for {missing}; "
            f"detail for unknown suite {extra}. Fix rather than generating a "
            f"matrix with holes in it."
        )

    entries = []
    for name, meta in suites.items():
        d = DETAIL[name]
        paid = meta["cost_class"] == "paid"
        entries.append({
            "name": name,
            "purpose": d["purpose"],
            "layer": d["layer"],
            "command": meta["command"],
            "trigger_change_classes": d["change_classes"],
            "tags": meta["tags"],
            "determinism": "deterministic" if meta["deterministic"] else "stochastic",
            "release_blocking": meta["release_blocking"],
            "requires_network": d["requires_network"],
            "requires_model": d["requires_model"],
            "expected_paid_model_calls": "unknown until authorized" if paid else 0,
            "cost_class": meta["cost_class"],
            "known_limitations": d["known_limitations"],
        })

    matrix = {
        "_purpose": (
            "One machine-readable record of every major test suite in this "
            "repository: what it is for, what triggers it, whether it blocks a "
            "release, and what it costs. The prose companion is docs/TESTING.md."
        ),
        "_generated_by": "agent-side script; regenerate rather than hand-editing",
        "_authoritative_source": (
            "tags, cost_class, release_blocking and command are read from "
            "agent/select_tests.py's SUITES at generation time, so this file "
            "cannot drift from the selector that actually runs."
        ),
        "_determinism_note": (
            "'stochastic' does not mean the CODE is non-deterministic. Both "
            "stochastic entries here run deterministic code over a captured "
            "sample of MODEL OUTPUT -- what varies is the subject, not the "
            "measurement. That distinction is what decides release_blocking."
        ),
        "_release_health_definition": (
            "release_blocking: true means a failure means this branch cannot "
            "truthfully be called green. Two properties are required: the same "
            "input gives the same verdict every run, AND the thing measured is a "
            "property of this repository's code."
        ),
        "_paid_guard": (
            "Any suite with cost_class 'paid' requires BOTH ALLOW_PAID_TESTS=1 "
            "AND a positive PAID_TEST_BUDGET_USD, enforced by "
            "agent/paid_test_guard.py before any provider client is constructed. "
            "Sprint 17 never set it; its recorded paid call count is 0."
        ),
        "_local_entry_point": "python agent/release_health.py",
        "_change_classes": {
            name: {"reason": why, "needs_paid_evaluation": paid}
            for name, _rx, why, paid in select_tests.CHANGE_CLASS_RULES
        },
        "_python_module_buckets": {
            "hermetic_blocking": len(ci_python_tests.HERMETIC_MODULES),
            "quality_monitors": ci_python_tests.QUALITY_MONITOR_MODULES,
            "live_infrastructure_excluded": ci_python_tests.LIVE_INFRA_MODULES,
            "pending_owner_decision": ci_python_tests.PENDING_OWNER_DECISION,
            "min_expected_tests": ci_python_tests.MIN_EXPECTED_TESTS,
        },
        "_playwright_specs_intentionally_unmapped": tia.INTENTIONALLY_UNMAPPED_SPECS,
        "suites": entries,
    }

    out = REPO / "docs" / "testing-matrix.json"
    out.write_text(json.dumps(matrix, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(REPO)} with {len(entries)} suites")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
