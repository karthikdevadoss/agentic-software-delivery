"""Cost-aware, change-aware test selection.

    python agent/select_tests.py --base origin/master
    python agent/select_tests.py agent/web/style.css agent/web/home.html
    python agent/select_tests.py --stdin < changed_files.txt

Prints one JSON object. Exit 0 when a selection was produced, 2 when the input
could not be bounded (see FAIL-CLOSED below), 1 on a real error.

WHY THIS EXISTS, given that agent/test_impact_analysis.py already selects tests
-----------------------------------------------------------------------------
TIA answers "which suites cover the code that changed?". It has no opinion about
what a suite COSTS, because when it was written every suite was free. That is no
longer true: some suites would call a paid provider, and this project has two
real spend incidents on record. A selector that cannot say "this change needs
zero paid calls" cannot be trusted to keep a CSS tweak from starting a model run.

So this module is a thin cost/classification layer OVER TIA, not a replacement.
It calls tia.analyze() and change_risk.classify_change() for the coverage answer
and adds three things TIA does not have: a change CLASS (eight of them), a
cost_class per suite, and an expected paid-call count that is computed rather
than asserted.

THE ONE RULE THAT IS NOT NEGOTIABLE
----------------------------------
A change consisting only of CSS, images, or purely visual HTML must never select
a paid suite. `test_select_tests.py` asserts this against a real fake CSS diff,
and the assertion is on the OUTPUT of this module, not on a promise in a comment.

FAIL-CLOSED, and what it does NOT mean
--------------------------------------
When TIA cannot bound the change -- an unrecognised path, a pom.xml, a CI
workflow, agent/risk_policy.py -- this module reports change_class UNBOUNDED and
includes the full deterministic release-health suite. It still reports
expected_paid_model_calls: 0. Failing closed means "run more free tests", never
"start spending money because we are unsure". Uncertainty is a reason for
breadth, not for cost.

HOW A PAID SUITE APPEARS
------------------------
A paid suite is never marked as something to execute now. It appears with
disposition REQUIRED_BEFORE_DEPLOY and cost_class "paid", and
`agent/paid_test_guard.py` refuses it at runtime unless both ALLOW_PAID_TESTS and
an explicit positive budget are set. The selector's job is to say a paid suite is
NEEDED; the guard's job is to refuse it until someone authorizes it. Two
separate mechanisms on purpose -- a selector that could also authorize would be
one bug away from authorizing itself.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

import change_risk
import paid_test_guard
import test_impact_analysis as tia

# ---------------------------------------------------------------------------
# CHANGE CLASSES. Ordered most-specific first; the class of a whole changed set
# is the HIGHEST-precedence class any single file in it matches -- the same
# "a change is only as safe as its riskiest file" rule change_risk.py already
# applies to risk, for the same reason. A commit that touches a stylesheet AND
# an agent prompt is a prompt change that happens to include a stylesheet, not a
# visual change.
#
# Each entry: (class name, regex, human reason, needs_paid_evaluation).
# needs_paid_evaluation is the ONLY thing that can put a paid suite in the
# output, and it is true for exactly one class.
# ---------------------------------------------------------------------------
CHANGE_CLASS_RULES = [
    (
        "SECURITY_WRITE_AUTHORITY",
        re.compile(
            r"(^agent/(risk_policy|write_tools|execution_tools|paid_test_guard)\.py$"
            r"|^app/src/main/java/com/example/customer/security/"
            r"|^agent/tools\.py$"
            r"|^authserver/)"
        ),
        "touches a write, authority or security boundary -- the blast radius is "
        "what the system is ALLOWED to do, not what it does",
        False,
    ),
    (
        "PROMPT_MODEL_AGENT",
        re.compile(
            r"(^agent/(agent_loop|standing_interview|si_quality|reasoning_gateway"
            r"|jd_match|ask_codebase|backend_planning|main)\.py$"
            r"|^agent/prompts?/"
            r"|^agent/.*_prompt.*\.(py|txt|md)$"
            r"|^agent/(rag_index|backend_rag_index|eval_runner"
            r"|agent_decision_eval_runner)\.py$)"
        ),
        "changes prompt text, model selection, retrieval, or an agent/tool "
        "schema -- the only class whose correctness a deterministic assertion "
        "cannot fully settle",
        True,
    ),
    (
        "CI_TESTING_INFRA",
        re.compile(
            r"(^\.github/workflows/"
            r"|^playwright\.config\.js$"
            r"|^agent/(ci_python_tests|select_tests|release_health|verify_change"
            r"|test_impact_analysis|change_risk|static_gate)\.py$"
            r"|^package(-lock)?\.json$)"
        ),
        "changes the machinery that decides whether anything else is verified, "
        "so it cannot be verified by that same machinery alone",
        False,
    ),
    (
        "JAVA_BACKEND",
        re.compile(r"(^app/src/|^services/|\.java$|^app/pom\.xml$|pom\.xml$)"),
        "Java/Spring source or build definition",
        False,
    ),
    (
        "PYTHON_APP_LOGIC",
        re.compile(r"^agent/.*\.py$"),
        "deterministic Python application logic",
        False,
    ),
    (
        "FRONTEND_JS",
        re.compile(r"^(agent/web/.*\.js|e2e/.*\.js|app/src/main/resources/static/.*\.js)$"),
        "ordinary frontend JavaScript -- behaviour a browser test can settle",
        False,
    ),
    (
        "STATIC_HTML_COPY",
        re.compile(r"\.html?$"),
        "static HTML / recruiter-facing copy",
        False,
    ),
    (
        "CSS_VISUAL",
        re.compile(r"\.(css|svg|png|jpe?g|gif|webp|avif|ico|woff2?|ttf|otf)$"),
        "stylesheet, font or image -- appearance only, no behaviour and no "
        "model involvement of any kind",
        False,
    ),
]

_CLASS_BY_NAME = {name: (rx, why, paid) for name, rx, why, paid in CHANGE_CLASS_RULES}

# ---------------------------------------------------------------------------
# SUITES. `tags` uses the five names the sprint's own taxonomy fixes:
# quick / full / visual / live / paid. `cost_class` is free or paid, and paid
# means "would reach a provider", not "is slow".
#
# `command` is the real command, quoted rather than described, so a reader can
# run exactly what the selector says without reconstructing it.
# ---------------------------------------------------------------------------
SUITES = {
    "python-hermetic": {
        "command": "python agent/ci_python_tests.py",
        "tags": ["quick", "full"],
        "cost_class": "free",
        "deterministic": True,
        "release_blocking": True,
    },
    "python-quality-monitors": {
        "command": "python agent/ci_python_tests.py  (second, non-blocking pass)",
        "tags": ["full"],
        "cost_class": "free",
        "deterministic": False,
        "release_blocking": False,
    },
    "node-frontend-harnesses": {
        "command": ("node agent/test_trainer_frontend.js && "
                    "node agent/test_usage_frontend.js && "
                    "node agent/test_learn_frontend.js"),
        "tags": ["quick", "full"],
        "cost_class": "free",
        "deterministic": True,
        "release_blocking": True,
    },
    "static-gate": {
        "command": "python agent/static_gate.py",
        "tags": ["quick", "full"],
        "cost_class": "free",
        "deterministic": True,
        "release_blocking": True,
    },
    "config-drift-gate": {
        "command": "python agent/check_config_drift.py",
        "tags": ["quick", "full"],
        "cost_class": "free",
        "deterministic": True,
        "release_blocking": True,
    },
    "java-customer-app": {
        "command": "cd app && ./mvnw test -B",
        "tags": ["full"],
        "cost_class": "free",
        "deterministic": True,
        "release_blocking": True,
    },
    "java-microservices": {
        "command": "cd services/<service> && ./mvnw test -B   (6 services)",
        "tags": ["full"],
        "cost_class": "free",
        "deterministic": True,
        "release_blocking": True,
    },
    "real-topology": {
        "command": ("python services/real-topology-tests/run_real_topology_test.py "
                    "--port-offset 10000"),
        "tags": ["full"],
        "cost_class": "free",
        "deterministic": True,
        "release_blocking": True,
    },
    "playwright-functional": {
        "command": "npx playwright test --reporter=list  (selected specs)",
        "tags": ["full"],
        "cost_class": "free",
        "deterministic": True,
        "release_blocking": True,
    },
    "playwright-visual-pack": {
        "command": "VISUAL_REGRESSION=1 npx playwright test e2e/visual-regression.spec.js",
        "tags": ["visual"],
        "cost_class": "free",
        "deterministic": True,
        "release_blocking": False,
    },
    "rag-mcp-evals": {
        "command": "python agent/eval_runner.py all",
        "tags": ["full"],
        "cost_class": "free",
        "deterministic": True,
        "release_blocking": True,
    },
    "si-answer-quality-paid": {
        "command": ("ALLOW_PAID_TESTS=1 PAID_TEST_BUDGET_USD=<n> "
                    "python agent/si_recapture.py  then the monitor"),
        "tags": ["paid", "live"],
        "cost_class": "paid",
        "deterministic": False,
        "release_blocking": False,
    },
    "workbench-real-acceptance": {
        "command": "npx playwright test e2e/workbench-real-acceptance.spec.js",
        "tags": ["live"],
        "cost_class": "free",
        "deterministic": True,
        "release_blocking": False,
    },
}

# The always-cheap floor. Any non-empty change runs these: they are seconds
# long, they are the gates two real recurring defect classes were caught by
# (file modes/shebangs, Spring profile drift), and nothing is gained by
# reasoning about whether a particular diff could have broken them.
ALWAYS = ["static-gate", "python-hermetic", "python-quality-monitors"]

# What each class adds on top of ALWAYS.
CLASS_TO_SUITES = {
    "CSS_VISUAL": ["playwright-functional", "playwright-visual-pack"],
    "STATIC_HTML_COPY": ["playwright-functional", "playwright-visual-pack"],
    "FRONTEND_JS": ["node-frontend-harnesses", "playwright-functional"],
    "PYTHON_APP_LOGIC": ["playwright-functional", "rag-mcp-evals"],
    "JAVA_BACKEND": ["config-drift-gate", "java-customer-app", "java-microservices",
                     "real-topology"],
    "PROMPT_MODEL_AGENT": ["rag-mcp-evals", "playwright-functional",
                           "si-answer-quality-paid"],
    "CI_TESTING_INFRA": ["node-frontend-harnesses", "config-drift-gate",
                         "java-customer-app", "java-microservices",
                         "playwright-functional", "rag-mcp-evals"],
    "SECURITY_WRITE_AUTHORITY": ["config-drift-gate", "java-customer-app",
                                 "java-microservices", "real-topology",
                                 "playwright-functional", "rag-mcp-evals"],
    # Not a rule-matched class: what an unbounded change gets. Everything free
    # and deterministic, and still no paid suite.
    "UNBOUNDED": ["node-frontend-harnesses", "config-drift-gate",
                  "java-customer-app", "java-microservices", "real-topology",
                  "playwright-functional", "rag-mcp-evals"],
}

_CLASS_PRECEDENCE = [name for name, _, _, _ in CHANGE_CLASS_RULES]


def classify_paths(paths) -> dict:
    """Returns {"change_class", "per_file", "reason", "needs_paid_evaluation"}.

    per_file is every path with the class it matched (or None), so a surprising
    overall class can always be traced to the one file that caused it rather
    than having to be re-derived.
    """
    per_file = {}
    for p in paths:
        norm = p.replace("\\", "/")
        matched = None
        for name, rx, _why, _paid in CHANGE_CLASS_RULES:
            if rx.search(norm):
                matched = name
                break
        per_file[p] = matched

    present = [c for c in _CLASS_PRECEDENCE if c in set(per_file.values())]
    unclassified = sorted(p for p, c in per_file.items() if c is None)

    if not paths:
        return {"change_class": "EMPTY", "per_file": per_file,
                "reason": "no changed files", "needs_paid_evaluation": False,
                "unclassified": []}
    if unclassified:
        return {
            "change_class": "UNBOUNDED", "per_file": per_file,
            "reason": (f"path(s) match no change-class rule: {unclassified}. Failing "
                       f"closed to the full deterministic suite -- breadth, never spend."),
            "needs_paid_evaluation": False, "unclassified": unclassified,
        }
    top = present[0]
    _rx, why, paid = _CLASS_BY_NAME[top]
    reason = why
    if len(present) > 1:
        reason += (f" (highest-precedence of {present}; a mixed change is classified by "
                   f"its riskiest file, never averaged)")
    return {"change_class": top, "per_file": per_file, "reason": reason,
            "needs_paid_evaluation": paid, "unclassified": []}


def select(paths) -> dict:
    paths = [p.replace("\\", "/") for p in paths if p.strip()]
    cls = classify_paths(paths)
    tia_selection = tia.analyze(paths)
    risk_classification = change_risk.classify_change(paths)

    change_class = cls["change_class"]
    if tia_selection.fail_closed and change_class != "EMPTY":
        change_class = "UNBOUNDED"
        cls["reason"] = (
            f"{cls['reason']} -- OVERRIDDEN to UNBOUNDED: test impact analysis "
            f"failed closed ({tia_selection.fail_closed_reason})"
        )
        cls["needs_paid_evaluation"] = False

    wanted = list(ALWAYS) + [s for s in CLASS_TO_SUITES.get(change_class, [])]
    # Preserve declaration order, drop duplicates.
    wanted = [s for i, s in enumerate(wanted) if s not in wanted[:i]]

    guard = paid_test_guard.paid_tests_status()

    included, excluded = [], []
    for name, meta in SUITES.items():
        if name not in wanted:
            excluded.append({
                "suite": name,
                "reason": (f"change_class {change_class} does not touch what this suite "
                           f"covers; nothing in the diff can move its result"),
            })
            continue
        if meta["cost_class"] == "paid":
            included.append({
                "suite": name, "command": meta["command"], "tags": meta["tags"],
                "cost_class": "paid", "disposition": "REQUIRED_BEFORE_DEPLOY",
                "reason": (f"change_class {change_class} changes probabilistic behaviour, so "
                           f"a deterministic assertion cannot settle it. NOT executed by this "
                           f"selection: agent/paid_test_guard.py refuses it until both "
                           f"ALLOW_PAID_TESTS and a positive PAID_TEST_BUDGET_USD are set "
                           f"(currently authorized={guard['authorized']})."),
            })
            continue
        included.append({
            "suite": name, "command": meta["command"], "tags": meta["tags"],
            "cost_class": "free",
            "disposition": "RUN_NOW" if name not in ("playwright-visual-pack",) else "RUN_NOW_NON_BLOCKING",
            "reason": ("always run: seconds long, and the gate two real recurring defect "
                       "classes were caught by" if name in ALWAYS
                       else f"selected by change_class {change_class}"),
        })

    paid_included = [s for s in included if s["cost_class"] == "paid"]
    # Computed, never asserted: a paid suite contributes an expected call count
    # only if it would actually be allowed to run. It currently never is.
    expected_paid_calls = 0
    if paid_included and guard["authorized"]:
        expected_paid_calls = None  # genuinely unknown, and never silently 0

    return {
        "change_class": change_class,
        "change_class_reason": cls["reason"],
        "risk": risk_classification.risk,
        "blast_radius": risk_classification.blast_radius,
        "changed_files": paths,
        "per_file_change_class": cls["per_file"],
        "tia_fail_closed": tia_selection.fail_closed,
        "tia_fail_closed_reason": tia_selection.fail_closed_reason,
        "tia_playwright_specs": sorted(tia_selection.playwright_specs),
        "tia_java_tests": sorted(tia_selection.java_tests),
        "included_suites": included,
        "excluded_suites": sorted(excluded, key=lambda e: e["suite"]),
        "expected_paid_model_calls": expected_paid_calls,
        "max_paid_budget": guard["max_paid_budget"],
        "paid_tests_authorized": guard["authorized"],
        "paid_guard_refusal_reasons": guard["refusal_reasons"],
    }


def _paths_from_base(base: str) -> list:
    out = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        capture_output=True, text=True, check=False,
    )
    if out.returncode != 0:
        raise SystemExit(f"git diff against {base!r} failed: {out.stderr.strip()}")
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="*", help="changed file paths")
    ap.add_argument("--base", help="git ref to diff against instead of listing paths")
    ap.add_argument("--stdin", action="store_true", help="read newline-separated paths from stdin")
    args = ap.parse_args(argv)

    if args.base:
        paths = _paths_from_base(args.base)
    elif args.stdin:
        paths = [line.strip() for line in sys.stdin if line.strip()]
    else:
        paths = args.paths

    result = select(paths)
    print(json.dumps(result, indent=2))
    return 2 if result["change_class"] == "UNBOUNDED" else 0


if __name__ == "__main__":
    sys.exit(main())
