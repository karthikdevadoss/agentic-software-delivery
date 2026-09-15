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

import sys
import unittest
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

import showcase_data
import web_server as ws
from starlette.routing import Match, Route


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


if __name__ == "__main__":
    unittest.main()
