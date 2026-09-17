"""
Regression coverage for the Showcase navigation-link-integrity defect
(AEQ-022): showcases/senior-java-ai-transformation/showcase.yaml's
"AI Engineering Quality Ledger" secondary_evidence entry used a bare
repo-relative path ("docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml") as a
rendered <a href> on the /showcase/{slug} page. A relative href resolves
against the CURRENT page URL, so on /showcase/<slug> it resolved to
/showcase/docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml -- a path with no
matching server route -- and returned 404. Every other link in the same
list was a genuine absolute https:// URL; nothing validated that this one
was too, and no test or Playwright spec covered the Showcase page's links
at all (unlike Learn/Usage/Workbench, which do).

Generalized invariant enforced here: every URL rendered as a clickable
link from a showcase manifest (primary_demo.url, secondary_evidence[].url,
production_urls.*) must be either a genuine absolute http(s) URL, or an
absolute app path ("/...") that actually matches a real GET route
registered in agent/web_server.py's own route table -- checked via
Starlette's own real route-matching logic, not string comparison. A bare
relative path (the exact defect class above) always fails this check.

Run: python agent/test_showcase_data.py
"""

import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml

import showcase_data
import web_server as ws
from starlette.routing import Match, Route

REPO_ROOT = Path(__file__).resolve().parent.parent
REAL_SHOWCASE_SLUG = "senior-java-ai-transformation"


def _registered_get_routes():
    return [r for r in ws.routes if isinstance(r, Route) and "GET" in (r.methods or set())]


def _internal_path_is_routable(path: str) -> bool:
    """True if `path` matches a real registered GET route, using
    Starlette's own Route.matches() -- the same mechanism that decides a
    real incoming request, not a hand-rolled string comparison."""
    scope = {"type": "http", "method": "GET", "path": path}
    for route in _registered_get_routes():
        match, _ = route.matches(scope)
        if match == Match.FULL:
            return True
    return False


def classify_link(url: str) -> str:
    """Returns 'ABSOLUTE_EXTERNAL', 'VALID_INTERNAL_ROUTE',
    'BROKEN_INTERNAL_ROUTE', or 'BARE_RELATIVE_PATH' (the AEQ-022 defect
    class -- always invalid as a rendered href)."""
    parsed = urlparse(url)
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return "ABSOLUTE_EXTERNAL"
    if url.startswith("/"):
        return "VALID_INTERNAL_ROUTE" if _internal_path_is_routable(parsed.path) else "BROKEN_INTERNAL_ROUTE"
    return "BARE_RELATIVE_PATH"


def _rendered_link_urls(showcase: dict):
    """Every URL this project's showcase.js actually renders as a
    clickable <a href> -- mirrors renderEvidence()/renderNav() in
    agent/web/showcase.js exactly, so this test covers what a real
    visitor can actually click, not the full manifest schema."""
    urls = []
    primary_demo_url = (showcase.get("primary_demo") or {}).get("url")
    if primary_demo_url:
        urls.append(("primary_demo.url", primary_demo_url))
    for item in showcase.get("secondary_evidence") or []:
        urls.append((f"secondary_evidence[{item.get('name')!r}]", item["url"]))
    customer_app_url = (showcase.get("production_urls") or {}).get("customer_app")
    if customer_app_url:
        urls.append(("production_urls.customer_app", customer_app_url))
    return urls


class ShowcaseLinkIntegrityTestCase(unittest.TestCase):
    def test_at_least_one_showcase_exists(self):
        self.assertGreater(len(showcase_data.list_showcase_slugs()), 0)

    def test_every_rendered_showcase_link_resolves_to_a_real_destination(self):
        broken = []
        for slug in showcase_data.list_showcase_slugs():
            showcase = showcase_data.load_showcase(slug)
            for field, url in _rendered_link_urls(showcase):
                classification = classify_link(url)
                if classification in ("BROKEN_INTERNAL_ROUTE", "BARE_RELATIVE_PATH"):
                    broken.append(f"{slug}.{field} = {url!r} ({classification})")
        self.assertEqual(
            broken, [],
            "Showcase link(s) will not resolve to a real destination for a "
            "site visitor -- fix the URL in showcases/<slug>/showcase.yaml "
            "to a genuine absolute https:// URL or a real registered app "
            "route:\n" + "\n".join(broken),
        )

    def test_classify_link_rejects_a_bare_repo_relative_path(self):
        # The exact literal shape of the original AEQ-022 defect.
        self.assertEqual(
            classify_link("docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml"),
            "BARE_RELATIVE_PATH",
        )

    def test_classify_link_accepts_a_real_absolute_url(self):
        self.assertEqual(
            classify_link("https://github.com/karthikdevadoss/agentic-software-delivery"),
            "ABSOLUTE_EXTERNAL",
        )

    def test_classify_link_accepts_a_real_registered_internal_route(self):
        self.assertEqual(classify_link("/dashboard"), "VALID_INTERNAL_ROUTE")

    def test_classify_link_rejects_an_unregistered_internal_route(self):
        self.assertEqual(classify_link("/this-route-does-not-exist"), "BROKEN_INTERNAL_ROUTE")


class AEQ026RequirementMappingTestCase(unittest.TestCase):
    """AEQ-026: job_requirements_addressed and selected_capabilities used
    to be two parallel flat lists paired by ARRAY POSITION in
    showcase.js's renderRequirementMap() -- silently wrong the moment the
    two lists' lengths/order diverged (13 capabilities vs. 8 requirements
    in the real manifest: Redis paired with "Testing discipline," and 5
    capabilities all incorrectly inherited the last requirement's text).
    selected_capabilities is now a list of {id, addresses_requirement}
    entries -- each capability names its own real requirement explicitly,
    so position can no longer matter. These tests prove that mechanically,
    not just for today's specific real content."""

    def test_every_addresses_requirement_value_matches_a_real_named_requirement_or_is_none(self):
        showcase = showcase_data.load_showcase(REAL_SHOWCASE_SLUG)
        self.assertEqual(
            showcase["unresolved_requirement_texts"], [],
            "A capability's addresses_requirement doesn't exactly match any "
            "entry in job_requirements_addressed -- real drift, not a typo test.",
        )

    def test_the_exact_original_mispairings_are_fixed(self):
        """The literal, real defect the Owner observed: redis-cache was
        rendered against "Testing discipline," and test-impact-analysis
        against the LLM/agentic-AI requirement -- pure positional
        coincidence, not an intentional editorial choice."""
        showcase = showcase_data.load_showcase(REAL_SHOWCASE_SLUG)
        by_id = {c["id"]: c for c in showcase["capabilities"]}
        self.assertIsNone(
            by_id["redis-cache"]["addresses_requirement"],
            "redis-cache must not be paired with any named requirement -- "
            "it's real additional evidence, not evidence for \"Testing discipline\".",
        )
        self.assertIn(
            "Testing discipline", by_id["test-impact-analysis"]["addresses_requirement"] or "",
            "test-impact-analysis is a testing capability -- it must map to the "
            "testing requirement, not the LLM/agentic-AI requirement.",
        )

    def test_no_capability_silently_inherits_the_last_requirement(self):
        """The other half of the original defect: capabilities beyond the
        requirement list's length used to all fall back to reqs[-1]
        ("root-cause real production incidents"). Only capabilities that
        genuinely, individually address that requirement may still show
        it -- and never as an accidental side effect of list length."""
        showcase = showcase_data.load_showcase(REAL_SHOWCASE_SLUG)
        root_cause_req = "Ability to root-cause real production incidents from evidence, not guesses"
        paired_with_root_cause = {
            c["id"] for c in showcase["capabilities"] if c["addresses_requirement"] == root_cause_req
        }
        # Real, deliberate pairings only -- not every capability the old
        # positional bug incorrectly roped in (rag-mcp-embeddings,
        # independent-qa-evaluator, workbench-live-delivery-ui must NOT
        # appear here; they never genuinely addressed this requirement).
        self.assertEqual(paired_with_root_cause, {"durable-event-ledger", "production-deployment-verification"})

    def test_mapping_mechanism_is_position_independent_not_just_todays_content(self):
        """Isolated fixture, decoupled from the real manifest's specific
        content: builds a manifest whose capability order is the REVERSE
        of its requirement order, and proves each capability still
        resolves to the exact requirement it names -- not the requirement
        at its matching list index. This is the actual regression
        coverage the Owner asked for: reordering or adding to either list
        can never again silently desynchronize the pairing."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            showcases_dir = tmp_path / "showcases"
            slug_dir = showcases_dir / "fixture-slug"
            slug_dir.mkdir(parents=True)
            capabilities_path = tmp_path / "capabilities.yaml"

            capabilities_path.write_text(yaml.dump({
                "capabilities": [
                    {"id": "cap-a", "display_name": "Capability A", "production_state": "PRODUCTION_ACTIVE", "engineering_problem_solved": "A"},
                    {"id": "cap-b", "display_name": "Capability B", "production_state": "PRODUCTION_ACTIVE", "engineering_problem_solved": "B"},
                    {"id": "cap-c", "display_name": "Capability C", "production_state": "PRODUCTION_ACTIVE", "engineering_problem_solved": "C"},
                ]
            }), encoding="utf-8")

            # Capability order is deliberately the REVERSE of requirement
            # order -- if anything still zipped by position, cap-c (index 0
            # here) would wrongly resolve to req-1 (index 0 in the
            # requirement list) instead of its actually-declared req-3.
            (slug_dir / "showcase.yaml").write_text(yaml.dump({
                "slug": "fixture-slug",
                "job_requirements_addressed": ["req-1", "req-2", "req-3"],
                "selected_capabilities": [
                    {"id": "cap-c", "addresses_requirement": "req-3"},
                    {"id": "cap-b", "addresses_requirement": "req-2"},
                    {"id": "cap-a", "addresses_requirement": "req-1"},
                ],
            }), encoding="utf-8")

            with mock.patch.object(showcase_data, "SHOWCASES_DIR", showcases_dir), \
                 mock.patch.object(showcase_data, "CAPABILITIES_PATH", capabilities_path):
                showcase = showcase_data.load_showcase("fixture-slug")

            by_id = {c["id"]: c["addresses_requirement"] for c in showcase["capabilities"]}
            self.assertEqual(by_id, {"cap-c": "req-3", "cap-b": "req-2", "cap-a": "req-1"})
            self.assertEqual(showcase["unresolved_requirement_texts"], [])

    def test_a_typo_in_addresses_requirement_is_reported_not_silently_mismatched(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            showcases_dir = tmp_path / "showcases"
            slug_dir = showcases_dir / "fixture-slug"
            slug_dir.mkdir(parents=True)
            capabilities_path = tmp_path / "capabilities.yaml"
            capabilities_path.write_text(yaml.dump({
                "capabilities": [{"id": "cap-a", "display_name": "A", "production_state": "PRODUCTION_ACTIVE", "engineering_problem_solved": "A"}]
            }), encoding="utf-8")
            (slug_dir / "showcase.yaml").write_text(yaml.dump({
                "slug": "fixture-slug",
                "job_requirements_addressed": ["The real requirement text"],
                "selected_capabilities": [{"id": "cap-a", "addresses_requirement": "The real requirement txet"}],  # typo
            }), encoding="utf-8")

            with mock.patch.object(showcase_data, "SHOWCASES_DIR", showcases_dir), \
                 mock.patch.object(showcase_data, "CAPABILITIES_PATH", capabilities_path):
                showcase = showcase_data.load_showcase("fixture-slug")

            self.assertEqual(len(showcase["unresolved_requirement_texts"]), 1)
            self.assertIn("cap-a", showcase["unresolved_requirement_texts"][0])


class ShowcaseFreshnessTestCase(unittest.TestCase):
    """D: `last_verified` must not silently go stale relative to real
    content changes -- no rule enforced this before (checked directly:
    docs/DECISIONS.md's "Standards freshness" table only covers external
    technology choices, not this field). This makes it a real, checkable
    invariant instead of a field nobody re-visits."""

    def test_last_verified_is_not_older_than_the_latest_commit_touching_showcase_content(self):
        showcase = showcase_data.load_showcase(REAL_SHOWCASE_SLUG)
        last_verified = date.fromisoformat(showcase["last_verified"])

        relevant_paths = [
            "showcases/senior-java-ai-transformation/showcase.yaml",
            "docs/PORTFOLIO_CAPABILITIES.yaml",
            "docs/INTERVIEW_WALKTHROUGH.yaml",
        ]
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--"] + relevant_paths,
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        committed_date_str = result.stdout.strip()
        if not committed_date_str:
            self.skipTest("No git history for showcase-relevant files in this checkout (e.g. a shallow clone).")
        latest_relevant_commit_date = date.fromisoformat(committed_date_str)

        self.assertGreaterEqual(
            last_verified, latest_relevant_commit_date,
            f"last_verified ({last_verified}) is older than the latest real commit "
            f"touching showcase-relevant content ({latest_relevant_commit_date}) -- "
            "bump last_verified in showcases/senior-java-ai-transformation/showcase.yaml.",
        )


if __name__ == "__main__":
    unittest.main()
