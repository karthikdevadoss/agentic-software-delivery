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

import sys
import unittest
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

import interview_walkthrough_data as iwd
import web_server as ws
from starlette.routing import Match, Route

REPO_ROOT = Path(__file__).resolve().parent.parent


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
