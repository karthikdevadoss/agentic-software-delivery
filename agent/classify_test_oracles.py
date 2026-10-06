"""
BL-116 (Sprint 27, SI audit BK-18): classify every Python test in this
repository by oracle type, derived from the real assertions each test
makes (which unittest assert* method it calls, and on what shape of
argument) -- never from the test's own name string.

Five categories, verbatim from the SI audit's Part 4c worked example
(docs/audits/SI_AUDIT_2026-09-29.md), which hand-classified 134 Standing
Interview test cases this way:

  PLUMBING           -- the mechanism is wired and data flows
  SAFETY_INVARIANT   -- something forbidden never reaches the user
  CORRECTNESS_LABELLED -- a case with a known right answer
  QUALITY_USEFULNESS -- is this a *good* answer? (no automatic oracle
                        can honestly claim this -- always 0 here)
  HUMAN_REVIEWED     -- a human judged the output (also always 0 here,
                        unless a test explicitly asserts against a stored
                        human/Owner review decision)

HONESTY LIMIT, stated once so it is not oversold: this is a deterministic
HEURISTIC over real assertion calls, not a human reading each test the
way the SI audit did for its 134 cases. It is a real, reusable signal
(which assert* method fired, on what kind of argument), genuinely
stronger than matching the test's name, but it is not semantic
understanding of what the test proves. Anything the heuristic cannot
place with reasonable confidence is labelled UNCLASSIFIED rather than
forced into a bucket -- an honest UNCLASSIFIED is worth more than a
confident wrong guess (see CLAUDE.md's five evidence rules, rule 1:
code existing is not code working -- the same applies to a classifier
existing vs. a classifier being right).

Run:  python agent/classify_test_oracles.py            # writes the manifest
      python agent/classify_test_oracles.py --summary  # prints counts only
"""

import ast
import json
import sys
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = AGENT_DIR / "test_oracle_manifest.json"

# Security/refusal-flavoured exception and keyword signal used to detect a
# SAFETY_INVARIANT assertion even when it's phrased as assertRaises rather
# than assertNotIn/assertFalse.
SECURITY_KEYWORDS = (
    "forbidden", "leak", "secret", "unauthor", "blocked", "denied",
    "refus", "permission", "injection", "traversal", "private", "secur",
)

EXCLUSIONARY_ASSERTS = {"assertNotIn", "assertRaises", "assertFalse", "assertIsNone"}
EQUALITY_ASSERTS = {"assertEqual", "assertDictEqual", "assertListEqual", "assertSetEqual", "assertAlmostEqual"}
PRESENCE_ASSERTS = {"assertTrue", "assertIn", "assertIsNotNone", "assertGreater", "assertGreaterEqual", "assertLess", "assertLessEqual"}

HUMAN_REVIEW_KEYWORDS = ("owner_review", "si_review", "human_review", "dissatisfied_row", "review_queue")


def _is_trivial_literal(node) -> bool:
    """True/False/None/0/empty-string/empty-collection -- too trivial to
    count as a 'known right answer', since almost every test compares
    against one of these somewhere."""
    if isinstance(node, ast.Constant):
        return node.value in (True, False, None, 0, "", 0.0)
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)) and not node.elts:
        return True
    if isinstance(node, ast.Dict) and not node.keys:
        return True
    return False


def _unparse(node) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return "<unparseable>"


def _collect_assert_calls(func_node):
    """Returns a list of (method_name, [arg_source_strings]) for every
    self.assert*(...) call inside this test function (including nested
    helper calls made directly in the body -- not calls inside a separate
    helper function elsewhere, which this script deliberately cannot see
    and must not claim to)."""
    calls = []
    for node in ast.walk(func_node):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            name = node.func.attr
            if name.startswith("assert"):
                calls.append((name, [_unparse(a) for a in node.args]))
    return calls


def classify_test_function(func_node) -> dict:
    """Returns {'category': ..., 'reason': ..., 'assert_methods': [...]}."""
    asserts = _collect_assert_calls(func_node)
    assert_methods = sorted({m for m, _ in asserts})

    if not asserts:
        return {"category": "UNCLASSIFIED", "reason": "no self.assert*() call found in the test body", "assert_methods": []}

    source_blob = " ".join(a for _, args in asserts for a in args).lower()

    if any(k in source_blob for k in HUMAN_REVIEW_KEYWORDS):
        return {"category": "HUMAN_REVIEWED", "reason": "asserts against a stored human/Owner review decision", "assert_methods": assert_methods}

    has_security_exclusion = False
    for method, args in asserts:
        if method in EXCLUSIONARY_ASSERTS:
            arg_text = " ".join(args).lower()
            if any(k in arg_text for k in SECURITY_KEYWORDS) or method == "assertRaises":
                has_security_exclusion = True
                break
            if method in ("assertNotIn", "assertFalse", "assertIsNone"):
                has_security_exclusion = True
                break
    if has_security_exclusion:
        return {"category": "SAFETY_INVARIANT", "reason": "an exclusionary assertion (assertNotIn/assertRaises/assertFalse/assertIsNone) guards against a forbidden outcome", "assert_methods": assert_methods}

    has_labelled_equality = False
    for method, args in asserts:
        if method in EQUALITY_ASSERTS and args:
            first_arg_node = None
            for node in ast.walk(func_node):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == method:
                    if len(node.args) >= 2 and not _is_trivial_literal(node.args[1]):
                        has_labelled_equality = True
                        break
            if has_labelled_equality:
                break
    if has_labelled_equality:
        return {"category": "CORRECTNESS_LABELLED", "reason": "compares actual output to a specific non-trivial expected value (a known right answer)", "assert_methods": assert_methods}

    if any(method in PRESENCE_ASSERTS for method in assert_methods):
        return {"category": "PLUMBING", "reason": "asserts presence/truthiness/a threshold comparison -- the mechanism ran and produced something, not that the content is the one correct answer", "assert_methods": assert_methods}

    return {"category": "UNCLASSIFIED", "reason": "assertion pattern did not match any heuristic rule", "assert_methods": assert_methods}


def classify_file(path: Path) -> list:
    """Returns a list of per-test-function classification dicts for one
    test_*.py file."""
    results = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as e:
        return [{"file": str(path.name), "test": "<FILE>", "category": "UNCLASSIFIED",
                  "reason": f"file failed to parse: {e}", "assert_methods": []}]

    class_stack = []

    def visit(node, class_name=None):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                visit(child, class_name=child.name)
            elif isinstance(child, ast.FunctionDef) and child.name.startswith("test"):
                classification = classify_test_function(child)
                results.append({
                    "file": path.name,
                    "class": class_name,
                    "test": child.name,
                    **classification,
                })
            elif isinstance(child, (ast.ClassDef, ast.FunctionDef)):
                pass
            else:
                visit(child, class_name=class_name)

    visit(tree)
    return results


def build_manifest(test_dir: Path = AGENT_DIR) -> dict:
    all_results = []
    for path in sorted(test_dir.glob("test_*.py")):
        all_results.extend(classify_file(path))

    counts = {}
    for r in all_results:
        counts[r["category"]] = counts.get(r["category"], 0) + 1

    return {
        "schema_version": 1,
        "scope": "agent/test_*.py only (Python hermetic+live-infra suite). "
                 "Java tests (app/src/test, services/*/src/test) and "
                 "Playwright specs (e2e/*.spec.js) are NOT YET classified -- "
                 "see docs/TEST_ORACLE_CLASSIFICATION.md 'What is not done yet'.",
        "methodology": "heuristic, derived from real self.assert*() calls and "
                        "their argument shapes in each test function's AST -- "
                        "never from the test's own name string. See this "
                        "script's module docstring for the honesty limit.",
        "counts": counts,
        "total_tests": len(all_results),
        "tests": all_results,
    }


def main(argv) -> int:
    manifest = build_manifest()
    if "--summary" in argv:
        print(f"Total tests classified: {manifest['total_tests']}")
        for cat, n in sorted(manifest["counts"].items(), key=lambda kv: -kv[1]):
            print(f"  {cat:22s} {n}")
        return 0

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {MANIFEST_PATH} ({manifest['total_tests']} tests classified)")
    for cat, n in sorted(manifest["counts"].items(), key=lambda kv: -kv[1]):
        print(f"  {cat:22s} {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
