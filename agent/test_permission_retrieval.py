"""
Tests for document-level permissions in retrieval (agent/permission_retrieval.py)
and their wiring into Ask the Codebase and the eval runner.

Real calls against the real built curated index plus the fake fixture docs.
Needs the prebuilt index (python agent/backend_rag_index.py), like test_ask_codebase.

Run: python agent/test_permission_retrieval.py
"""

import hashlib
import unittest

import ask_codebase as ac
import eval_runner
import permission_retrieval as pr

COMP = "agent/fixtures/permission_docs/compensation-bands-fixture.md"
RUNBOOK = "agent/fixtures/permission_docs/payments-reconciliation-runbook.md"
FAQ = "agent/fixtures/permission_docs/onboarding-faq.md"
SALARY_Q = "What is the salary band for a Level 3 engineer and how are compensation review decisions made?"
RUNBOOK_Q = "How do I rerun the nightly payments reconciliation job with the ledger repair flag?"


def paths(results):
    return [r["source_path"] for r in results]


class WithheldNotOutrankedTestCase(unittest.TestCase):
    def test_closest_match_is_forbidden_and_withheld_from_public(self):
        # Proof the forbidden doc IS the closest match: a private caller gets it at rank 1.
        self.assertEqual(paths(pr.search(SALARY_Q, "private", top_k=1)), [COMP])
        public = pr.search(SALARY_Q, "public", top_k=10)
        self.assertNotIn(COMP, paths(public))
        self.assertTrue(all(r["access_level"] == "public" for r in public))

    def test_eng_internal_sees_runbook_but_not_private(self):
        self.assertEqual(paths(pr.search(RUNBOOK_Q, "eng-internal", top_k=1)), [RUNBOOK])
        self.assertNotIn(COMP, paths(pr.search(SALARY_Q, "eng-internal", top_k=10)))
        self.assertNotIn(RUNBOOK, paths(pr.search(RUNBOOK_Q, "public", top_k=10)))

    def test_authorized_roles_still_retrieve(self):
        self.assertEqual(paths(pr.search(SALARY_Q, "private", top_k=1)), [COMP])
        self.assertEqual(paths(pr.search("How do I request a laptop from the IT helpdesk?", "public", top_k=1)), [FAQ])

    def test_forbidden_content_text_never_in_public_results_at_any_top_k(self):
        for r in pr.search(SALARY_Q, "public", top_k=1000):
            self.assertNotIn("FIXTURE-BAND-A", r["content"])
            self.assertNotIn("vault://fixture", r["content"])


class DenyByDefaultTestCase(unittest.TestCase):
    def test_missing_unknown_or_malformed_roles_get_nothing(self):
        for role in (None, "", "admin", "PRIVATE", "Public", 3, ["private"], {"r": "private"}):
            self.assertEqual(pr.allowed_levels(role), frozenset(), role)
            self.assertEqual(pr.search(SALARY_Q, role), [], role)

    def test_ask_denies_rather_than_downgrading(self):
        for role in (None, "admin"):
            out = ac.ask(SALARY_Q, role=role)
            self.assertEqual(out["status"], "ROLE_DENIED")
            self.assertEqual(out["evidence"], [])


class AskCodebaseWiringTestCase(unittest.TestCase):
    def test_default_role_is_public_and_leaks_nothing(self):
        out = ac.ask(SALARY_Q)
        self.assertNotIn(COMP, [e["source_path"] for e in out["evidence"]])
        self.assertTrue(all(e["access_level"] == "public" for e in out["evidence"]))

    def test_private_role_gets_labelled_fixture_with_no_github_link(self):
        out = ac.ask(SALARY_Q, role="private")
        top = out["evidence"][0]
        self.assertEqual(top["source_path"], COMP)
        self.assertEqual((top["access_level"], top["source"]), ("private", "notion-standin"))
        self.assertIsNone(top["source_url"])

    def test_public_endpoint_hardwires_public_role(self):
        # Read the source (web_server needs optional deps that may be absent)
        # so this gate always runs. The endpoint must pass a literal "public".
        from pathlib import Path
        src = (Path(__file__).resolve().parent / "web_server.py").read_text(encoding="utf-8")
        body = src.split("async def ask_codebase_api", 1)[1].split("\nasync def ", 1)[0]
        self.assertIn('ask_codebase.ask, query, "public"', body)
        self.assertNotIn("headers", body.split("result =")[0].split("query =", 1)[1].split("#")[0])


class FixtureMetadataTestCase(unittest.TestCase):
    def test_every_fixture_has_a_valid_level_and_a_real_content_hash(self):
        for d in pr.FIXTURE_DOCUMENTS:
            self.assertIn(d.access_level, pr.ACCESS_LEVELS)
            data = (pr.FIXTURE_DIR / d.filename).read_bytes()
            self.assertEqual(pr.fixture_content_hash(d), hashlib.sha256(data).hexdigest())
            self.assertIn(b"FIXTURE", data)  # clearly labelled as fake

    def test_every_level_has_at_least_one_fixture(self):
        self.assertEqual({d.access_level for d in pr.FIXTURE_DOCUMENTS}, set(pr.ACCESS_LEVELS))


class PermissionEvalGateTestCase(unittest.TestCase):
    def test_permission_eval_passes_with_zero_leaks(self):
        report = eval_runner.run_permission_eval()
        failures = [c for c in report["per_case"] if not c["passed"]]
        self.assertEqual(failures, [])
        self.assertGreaterEqual(report["summary"]["cases"], 10)

    def test_permission_eval_goes_red_when_the_filter_is_broken(self):
        from unittest import mock
        everything = frozenset(pr.ACCESS_LEVELS)
        with mock.patch.object(pr, "allowed_levels", lambda role: everything):
            report = eval_runner.run_permission_eval()
        self.assertGreater(report["summary"]["leaks_or_failures"], 0)


if __name__ == "__main__":
    unittest.main()
