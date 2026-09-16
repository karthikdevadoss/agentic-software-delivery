"""
Regression coverage for docs/INTERVIEW_WALKTHROUGH.yaml and its loader
(agent/interview_walkthrough_data.py). Same link-integrity discipline as
agent/test_showcase_data.py's AEQ-022 regression test: every URL that
agent/web/showcase.js actually renders as a clickable link must resolve to
a real destination (a genuine absolute https:// URL, or a real registered
app route via Starlette's own route-matching, not string comparison), and
every doc_path referenced must be a real file that exists in this repo --
this whole feature exists specifically to surface those files, so a
dangling reference here would be the exact kind of silent drift this
project's own testing-strategy Skill warns against.

Run: python agent/test_interview_walkthrough_data.py
"""

import subprocess
import sys
import unittest
from pathlib import Path
from urllib.parse import urlparse

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

import interview_walkthrough_data as iwd
import web_server as ws
from starlette.routing import Match, Route

REPO_ROOT = Path(__file__).resolve().parent.parent


def _raw_stories():
    """The pre-resolution YAML (commit/source_paths as written, before
    interview_walkthrough_data resolves them into plain url items) -- used
    to verify against real git/filesystem state independently of the
    loader's own resolution logic, the same "don't just trust your own
    code" discipline as test_showcase_data.py."""
    raw = yaml.safe_load(iwd.WALKTHROUGH_PATH.read_text(encoding="utf-8")) or {}
    return raw.get("stories", [])


def _real_commit_exists(sha: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-t", sha],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "commit"


def _registered_get_routes():
    return [r for r in ws.routes if isinstance(r, Route) and "GET" in (r.methods or set())]


def _internal_path_is_routable(path: str) -> bool:
    scope = {"type": "http", "method": "GET", "path": path}
    for route in _registered_get_routes():
        match, _ = route.matches(scope)
        if match == Match.FULL:
            return True
    return False


def classify_link(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return "ABSOLUTE_EXTERNAL"
    if url.startswith("/"):
        return "VALID_INTERNAL_ROUTE" if _internal_path_is_routable(parsed.path) else "BROKEN_INTERNAL_ROUTE"
    return "BARE_RELATIVE_PATH"


def _rendered_link_urls(walkthrough: dict):
    """Mirrors exactly what agent/web/showcase.js renders as a clickable
    href from walkthrough data: path.start_link, story.live_demo.url
    (featured and compact), and story.real_evidence[].url (featured only).
    story.doc_path is NOT a rendered href directly -- showcase.js builds
    the GitHub blob URL from it -- so it's checked separately below as a
    real on-disk file, which is the property that actually matters for it."""
    urls = []
    for path in walkthrough.get("paths", []):
        if path.get("start_link"):
            urls.append((f"paths[{path['id']}].start_link", path["start_link"]))
        for story in path.get("stories", []):
            live_demo = story.get("live_demo") or {}
            if live_demo.get("url"):
                urls.append((f"stories[{story['id']}].live_demo.url", live_demo["url"]))
            for item in story.get("real_evidence") or []:
                if item.get("url"):
                    urls.append((f"stories[{story['id']}].real_evidence[{item.get('label')!r}]", item["url"]))
    return urls


class InterviewWalkthroughLoaderTestCase(unittest.TestCase):
    def test_loads_at_least_three_paths(self):
        data = iwd.load_interview_walkthrough()
        self.assertGreaterEqual(len(data["paths"]), 3)

    def test_every_path_has_at_least_one_story(self):
        data = iwd.load_interview_walkthrough()
        for path in data["paths"]:
            self.assertGreater(len(path["stories"]), 0, f"{path['id']} has no resolved stories")

    def test_no_unresolved_story_ids(self):
        data = iwd.load_interview_walkthrough()
        for path in data["paths"]:
            self.assertEqual(path["unresolved_story_ids"], [], f"{path['id']} references a story id that doesn't exist")

    def test_no_unresolved_capability_ids(self):
        data = iwd.load_interview_walkthrough()
        for path in data["paths"]:
            self.assertEqual(path["unresolved_capability_ids"], [], f"{path['id']} references a capability id not in the registry")

    def test_at_least_one_featured_story_per_path(self):
        data = iwd.load_interview_walkthrough()
        for path in data["paths"]:
            featured = [s for s in path["stories"] if s.get("featured")]
            self.assertGreater(len(featured), 0, f"{path['id']} has no featured (deep) story")

    def test_featured_stories_carry_the_full_structured_breakdown(self):
        data = iwd.load_interview_walkthrough()
        required_fields = [
            "business_problem", "engineering_requirement", "design_decision",
            "implementation", "runtime_details", "testing", "failure_mode",
            "verification", "how_to_explain",
        ]
        for story in data["stories"]:
            if not story.get("featured"):
                continue
            for field in required_fields:
                self.assertIn(field, story, f"featured story {story['id']!r} missing {field!r}")
            for key in ("why", "what", "how", "tradeoff", "failure", "verification"):
                self.assertIn(key, story["how_to_explain"], f"{story['id']!r}.how_to_explain missing {key!r}")

    def test_every_story_doc_path_exists_as_a_real_file(self):
        data = iwd.load_interview_walkthrough()
        missing = []
        for story in data["stories"]:
            doc_path = story.get("doc_path")
            if doc_path and not (REPO_ROOT / doc_path).exists():
                missing.append(f"{story['id']}: {doc_path}")
        self.assertEqual(missing, [], "Story references a doc_path with no real file on disk:\n" + "\n".join(missing))

    def test_every_real_evidence_item_has_a_url_after_resolution(self):
        """Hard regression gate for the original gap: a plain-text
        `value:` evidence item (un-clickable) must never survive
        resolution -- every item real_evidence renders must carry a real
        url by the time showcase.js sees it."""
        data = iwd.load_interview_walkthrough()
        unlinked = []
        for story in data["stories"]:
            for item in story.get("real_evidence", []):
                if not item.get("url"):
                    unlinked.append(f"{story['id']}: {item}")
        self.assertEqual(unlinked, [], "Evidence item(s) with no resolved url (un-clickable):\n" + "\n".join(unlinked))

    def test_every_commit_reference_is_a_real_commit_and_resolves_correctly(self):
        found_any = False
        for story in _raw_stories():
            for item in story.get("real_evidence", []):
                sha = item.get("commit")
                if not sha:
                    continue
                found_any = True
                self.assertTrue(_real_commit_exists(sha), f"{story['id']}: {sha!r} is not a real commit in this repo")
        self.assertTrue(found_any, "No commit-typed evidence items found -- test would pass vacuously")

        # Cross-check: the loader's resolved URL actually points at that
        # same real sha, not a typo'd or stale one.
        data = iwd.load_interview_walkthrough()
        for story in data["stories"]:
            for item in story["real_evidence"]:
                if "commit" not in str(item.get("label", "")).lower():
                    continue
                self.assertIn("/commit/", item["url"])

    def test_every_source_path_reference_is_a_real_file_or_directory(self):
        found_any = False
        for story in _raw_stories():
            for item in story.get("real_evidence", []):
                for path in item.get("source_paths") or []:
                    found_any = True
                    self.assertTrue(
                        (REPO_ROOT / path).exists(),
                        f"{story['id']}: source_paths entry {path!r} does not exist on disk",
                    )
        self.assertTrue(found_any, "No source_paths-typed evidence items found -- test would pass vacuously")

    def test_source_paths_resolve_to_one_evidence_item_per_path(self):
        """The exact original defect this closes: a comma-joined string of
        4 file paths rendered as ONE inert evidence line -- must now be 4
        separate clickable items."""
        data = iwd.load_interview_walkthrough()
        pipeline_story = next(s for s in data["stories"] if s["id"] == "agentic-delivery-pipeline")
        source_urls = [e["url"] for e in pipeline_story["real_evidence"] if e["label"].startswith("Source:")]
        self.assertEqual(len(source_urls), 4)
        for url in source_urls:
            self.assertTrue(url.startswith("https://github.com/karthikdevadoss/agentic-software-delivery/blob/master/agent/"))

    def test_at_scale_present_for_stories_with_real_scale_content_absent_otherwise(self):
        data = iwd.load_interview_walkthrough()
        by_id = {s["id"]: s for s in data["stories"]}
        expected_present = [
            "postgres-bytea-incident", "plan-enrollment-idempotency",
            "appointment-resilience", "agentic-delivery-pipeline",
        ]
        for story_id in expected_present:
            self.assertTrue(by_id[story_id].get("at_scale"), f"{story_id} should have real at_scale content")
        # observability-production-debugging's own doc has no "What
        # Changes at 10x Scale" section (confirmed by direct grep of
        # docs/interview-scenarios/09-observability-production-debugging.md)
        # -- must stay honestly absent, never fabricated to fill the field.
        self.assertNotIn("at_scale", by_id["observability-production-debugging"])


class InterviewWalkthroughLinkIntegrityTestCase(unittest.TestCase):
    def test_every_rendered_link_resolves_to_a_real_destination(self):
        data = iwd.load_interview_walkthrough()
        broken = []
        for field, url in _rendered_link_urls(data):
            classification = classify_link(url)
            if classification in ("BROKEN_INTERNAL_ROUTE", "BARE_RELATIVE_PATH"):
                broken.append(f"{field} = {url!r} ({classification})")
        self.assertEqual(
            broken, [],
            "Interview Walkthrough link(s) will not resolve to a real destination:\n" + "\n".join(broken),
        )


if __name__ == "__main__":
    unittest.main()
