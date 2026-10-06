import ast
import textwrap
import unittest

from classify_test_oracles import classify_test_function, classify_file

import tempfile
from pathlib import Path


def _func(src: str) -> ast.FunctionDef:
    tree = ast.parse(textwrap.dedent(src))
    return tree.body[0]


class ClassifyTestFunctionTestCase(unittest.TestCase):
    def test_no_assertions_is_unclassified(self):
        node = _func("""
            def test_nothing(self):
                x = 1
        """)
        result = classify_test_function(node)
        self.assertEqual(result["category"], "UNCLASSIFIED")

    def test_assert_not_in_is_safety_invariant(self):
        node = _func("""
            def test_no_secret_leaks(self):
                self.assertNotIn("SECRET_KEY", response.text)
        """)
        result = classify_test_function(node)
        self.assertEqual(result["category"], "SAFETY_INVARIANT")

    def test_assert_raises_is_safety_invariant(self):
        node = _func("""
            def test_rejects_unauthorized(self):
                with self.assertRaises(PermissionError):
                    call_protected_action()
        """)
        result = classify_test_function(node)
        self.assertEqual(result["category"], "SAFETY_INVARIANT")

    def test_assert_equal_to_a_labelled_value_is_correctness_labelled(self):
        node = _func("""
            def test_known_answer(self):
                self.assertEqual(compute_total(cart), 42.50)
        """)
        result = classify_test_function(node)
        self.assertEqual(result["category"], "CORRECTNESS_LABELLED")

    def test_assert_equal_to_true_is_not_correctness_labelled(self):
        # Equality to a trivial literal (True/False/None/0/"") is plumbing-
        # flavoured, not a "known right answer" in the SI audit's sense.
        node = _func("""
            def test_flag_is_set(self):
                self.assertEqual(result.ok, True)
        """)
        result = classify_test_function(node)
        self.assertNotEqual(result["category"], "CORRECTNESS_LABELLED")

    def test_assert_true_alone_is_plumbing(self):
        node = _func("""
            def test_mechanism_ran(self):
                self.assertTrue(mock_fn.called)
        """)
        result = classify_test_function(node)
        self.assertEqual(result["category"], "PLUMBING")

    def test_human_review_keyword_wins(self):
        node = _func("""
            def test_dissatisfied_row_recorded(self):
                self.assertEqual(len(review_queue.dissatisfied_rows), 1)
        """)
        result = classify_test_function(node)
        self.assertEqual(result["category"], "HUMAN_REVIEWED")

    def test_safety_invariant_takes_priority_over_correctness(self):
        # A test with BOTH an exclusionary assertion and an equality
        # assertion is classified SAFETY_INVARIANT first, matching the SI
        # audit's own precedence (safety dominates when both are present).
        node = _func("""
            def test_mixed(self):
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("forbidden_field", response.json())
        """)
        result = classify_test_function(node)
        self.assertEqual(result["category"], "SAFETY_INVARIANT")


class ClassifyFileTestCase(unittest.TestCase):
    def test_classifies_every_test_method_in_a_real_temp_file(self):
        src = textwrap.dedent("""
            import unittest
            class SomeTestCase(unittest.TestCase):
                def test_a(self):
                    self.assertNotIn("x", "abc")
                def test_b(self):
                    self.assertEqual(add(2, 2), 4)
                def setUp(self):
                    pass
        """)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "test_fixture_module.py"
            p.write_text(src, encoding="utf-8")
            results = classify_file(p)
        names = {r["test"] for r in results}
        self.assertEqual(names, {"test_a", "test_b"})
        by_name = {r["test"]: r for r in results}
        self.assertEqual(by_name["test_a"]["category"], "SAFETY_INVARIANT")
        self.assertEqual(by_name["test_b"]["category"], "CORRECTNESS_LABELLED")
        self.assertEqual(by_name["test_a"]["class"], "SomeTestCase")

    def test_a_file_that_fails_to_parse_is_reported_not_silently_dropped(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "test_broken.py"
            p.write_text("def test_x(:\n  pass", encoding="utf-8")
            results = classify_file(p)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["category"], "UNCLASSIFIED")
        self.assertIn("failed to parse", results[0]["reason"])


if __name__ == "__main__":
    unittest.main()
