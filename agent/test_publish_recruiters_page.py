"""Tests for the /recruiters page builder and its published data.

Hermetic: no network, no model, no git refs (CI checkouts are shallow, so
the "live vs pending deploy" decision, which reads origin/master, is tested
with injected fakes; the published file is re-checked against the working
tree only).
"""
import json
import pathlib
import re
import tempfile
import unittest

import publish_recruiters_page as prp
import test_public_surface_gate as surface

WEB = prp.WEB_DIR
SERVED = {"/eval": "eval.html", "/workbench": "workbench.html", "/triage": "triage.html"}


def _classify(url, production=frozenset({"/workbench"}), master=(), head=()):
    return prp.classify_link(url, served=SERVED, production=set(production), branch="feature-x",
                             exists_on_master=lambda rel: rel in master,
                             exists_on_head=lambda rel: rel in head)


class ClassifyLinkTestCase(unittest.TestCase):
    def test_route_served_in_production_is_live(self):
        self.assertEqual(_classify("/workbench")["status"], "live")

    def test_route_only_on_this_branch_is_pending_with_source_fallback(self):
        rec = _classify("/eval")
        self.assertEqual(rec["status"], "pending_deploy")
        self.assertEqual(rec["fallback_url"], prp.REPO_URL + "/blob/feature-x/agent/web/eval.html")

    def test_unserved_route_is_rejected(self):
        with self.assertRaises(prp.LinkError):
            _classify("/no-such-page")

    def test_anchor_must_exist_in_the_served_page(self):
        self.assertEqual(_classify("/workbench#verified-run-panel")["status"], "live")
        with self.assertRaises(prp.LinkError):
            _classify("/workbench#no-such-anchor")

    def test_repo_file_on_master_is_source(self):
        rec = _classify(prp.MASTER_BLOB + "agent/x.py", master={"agent/x.py"})
        self.assertEqual(rec, {"url": prp.MASTER_BLOB + "agent/x.py", "status": "source"})

    def test_repo_file_only_on_this_branch_is_rewritten_to_the_branch(self):
        rec = _classify(prp.MASTER_BLOB + "agent/y.py", head={"agent/y.py"})
        self.assertEqual(rec["status"], "source_pending")
        self.assertEqual(rec["url"], prp.REPO_URL + "/blob/feature-x/agent/y.py")

    def test_missing_repo_file_is_rejected(self):
        with self.assertRaises(prp.LinkError):
            _classify(prp.MASTER_BLOB + "agent/gone.py")

    def test_plain_http_and_relative_links_are_rejected(self):
        for url in ("http://example.com", "recruiters.html"):
            with self.subTest(url=url), self.assertRaises(prp.LinkError):
                _classify(url)


class MetricsTestCase(unittest.TestCase):
    def _triage(self, skipped, needs_docker):
        return {"generated_at": "t", "commit_sha": "c", "scenarios": [
            {"java_integration_tests": [{"needs_docker": False, "result": {"tests": 5, "failures": 0, "errors": 0, "skipped": 0}}]},
            {"java_integration_tests": [{"needs_docker": needs_docker, "result": {"tests": 2, "failures": 0, "errors": 1, "skipped": skipped}}]},
        ]}

    def test_triage_totals_are_summed(self):
        m = prp.triage_metrics(self._triage(1, True))
        self.assertEqual((m["java_tests"], m["java_failed"], m["java_skipped"], m["java_passed"]), (7, 1, 1, 5))
        self.assertIn("Docker", m["skip_reason"])

    def test_skip_reason_only_claimed_when_every_skip_needs_docker(self):
        self.assertIsNone(prp.triage_metrics(self._triage(1, False))["skip_reason"])

    def test_case_study_banner_is_parsed_and_required(self):
        html = '<dl class="banner"><div><dt>A</dt><dd>1<small>x</small></dd></div><div><dt>B</dt><dd>2<small>y</small></dd></div><div><dt>C</dt><dd>3<small>z</small></dd></div></dl>'
        self.assertEqual(prp.case_study_metrics(html)["banner"][1], {"label": "B", "value": "2", "note": "y"})
        with self.assertRaises(ValueError):
            prp.case_study_metrics("<p>no banner</p>")


class QuotesTestCase(unittest.TestCase):
    SOURCE = {"postings": [{"id": "p1"}], "requirements": [{"id": "r", "asked_by": {"p1": "Build  agents\nthat act"}}], "gaps": []}

    def test_verbatim_quote_passes_after_whitespace_normalisation(self):
        with tempfile.TemporaryDirectory() as d:
            pathlib.Path(d, "p1.txt").write_text("We want you to build agents that act&nbsp;well.", encoding="utf-8")
            self.assertEqual(prp.verify_quotes(self.SOURCE, pathlib.Path(d)), 1)

    def test_paraphrased_quote_fails(self):
        with tempfile.TemporaryDirectory() as d:
            pathlib.Path(d, "p1.txt").write_text("We want you to build systems.", encoding="utf-8")
            with self.assertRaises(ValueError):
                prp.verify_quotes(self.SOURCE, pathlib.Path(d))

    def test_quote_for_unknown_posting_is_rejected(self):
        bad = {"postings": [{"id": "p1"}], "requirements": [{"id": "r", "asked_by": {"zz": "q"}}], "gaps": []}
        with self.assertRaises(ValueError):
            prp.validate_source(bad)


# ------------------------------------------------------------ published data

DATA = json.loads((WEB / "recruiters.json").read_text(encoding="utf-8"))
SOURCE = prp.yaml.safe_load(prp.SOURCE_PATH.read_text(encoding="utf-8"))


def _non_quote_strings(node, path=""):
    """Every string in the published data except the posting quotes and the
    posting list (company names and job titles are the employers' words)."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "quote" or k in ("postings", "inputs", "link_check", "quotes_verified"):
                continue
            yield from _non_quote_strings(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _non_quote_strings(v, f"{path}[{i}]")
    elif isinstance(node, str):
        yield path, node


# Owner-confirmed date phrases (2026-10-06) that may carry a calendar year.
# Everything else is scanned with them removed, so a degree year, a career
# start year or any other year still fails.
OWNER_CONFIRMED_DATE_PHRASES = ("since early 2026",)


def _without_confirmed_dates(text):
    for phrase in OWNER_CONFIRMED_DATE_PHRASES:
        text = re.sub(re.escape(phrase), "", text, flags=re.I)
    return text


EXTRA_FORBIDDEN = [
    ("a money amount", r"[€$£]\s?\d|\d\s?k?\s?(€|£|\$|eur\b|usd\b|gbp\b)|\bper (hour|year|annum)\b|/hour\b"),
    ("salary", r"\bsalar(y|ies)\b"),
    ("notice period", r"\bnotice\b"),
    ("a year (degree or career dates)", r"\b(19|20)\d{2}\b(?!-\d{2}-\d{2})"),
    ("an every-change-needs-approval claim", r"\bevery (change|write)\b[^.]*\bapprov"),
]


class PublishedRecruitersDataTestCase(unittest.TestCase):
    def test_snapshot_is_fresh(self):
        self.assertEqual(DATA["inputs"], prp.compute_input_hashes(),
                         "recruiters.json is stale: run `python publish_recruiters_page.py` on a clean tree")

    def test_quotes_were_verified_against_this_exact_source(self):
        qv = DATA["quotes_verified"]
        self.assertIsNotNone(qv, "quotes were never verified against captured posting text")
        self.assertEqual(qv["source_sha256"], prp.compute_input_hashes()["agent/recruiters_source.yaml"])
        self.assertEqual(qv["quotes"], sum(1 for _ in prp.iter_quotes(SOURCE)))

    def test_counts_are_computed_from_the_quotes(self):
        for r in DATA["requirements"] + DATA["gaps"]:
            with self.subTest(item=r["title"]):
                self.assertEqual(r["asked_count"], len(r["asked_by"]))
                self.assertLessEqual(r["asked_count"], DATA["postings_total"])
        self.assertEqual(DATA["postings_total"], len(DATA["postings"]))

    def test_numbers_match_the_published_snapshots(self):
        snaps = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in prp.SNAPSHOTS.items()}
        self.assertEqual(DATA["metrics"]["eval"], prp.eval_metrics(snaps["eval"]))
        self.assertEqual(DATA["metrics"]["triage"], prp.triage_metrics(snaps["triage"]))
        self.assertEqual(DATA["metrics"]["ask"], prp.ask_metrics(snaps["ask"]))
        self.assertEqual(DATA["metrics"]["case_study"],
                         prp.case_study_metrics(prp.CASE_STUDY_PATH.read_text(encoding="utf-8")))

    def _all_links(self):
        for r in DATA["requirements"]:
            for e in r["evidence"]:
                yield e
        yield from DATA["profile"]["links"]
        for h in DATA["headline"]:
            yield h["link"]
        yield from DATA["postings"]

    def test_every_internal_link_is_served_and_every_repo_link_exists_on_this_tree(self):
        served = prp.served_routes()
        for rec in self._all_links():
            url = rec["url"]
            with self.subTest(url=url):
                if url.startswith("/"):
                    path, _, anchor = url.partition("#")
                    self.assertIn(path, served)
                    if anchor:
                        self.assertIn(f'id="{anchor}"', (WEB / served[path]).read_text(encoding="utf-8"))
                    self.assertIn(rec["status"], ("live", "pending_deploy"))
                    if rec["status"] == "pending_deploy":
                        self.assertTrue(rec["fallback_url"].startswith(prp.REPO_URL + "/blob/"))
                        rel = rec["fallback_url"].split("/blob/", 1)[1].split("/", 2)[-1]
                        self.assertTrue((prp.REPO_ROOT / rel).exists(), rel)
                elif url.startswith(prp.REPO_URL + "/blob/"):
                    rel = re.sub(r"^.*?/blob/(master|mahadeva/[^/]+)/", "", url)
                    self.assertTrue((prp.REPO_ROOT / rel).exists(), f"{rel} not in this tree")
                else:
                    self.assertTrue(url.startswith("https://"))

    def test_unmerged_pages_are_never_linked_as_live_without_a_fallback(self):
        statuses = {e["url"]: e for r in DATA["requirements"] for e in r["evidence"]}
        for route in ("/eval", "/triage/evidence", "/ask-codebase/examples"):
            with self.subTest(route=route):
                self.assertIn(route, statuses)
                rec = statuses[route]
                self.assertTrue(rec["status"] == "live" or rec.get("fallback_url"),
                                f"{route} is neither live nor carries a fallback")

    def test_no_forbidden_claim_outside_posting_quotes(self):
        page_text = surface._visible_text((WEB / "recruiters.html").read_text(encoding="utf-8"))
        js = (WEB / "recruiters.js").read_text(encoding="utf-8")
        js_strings = " ".join(re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', js))
        surfaces = list(_non_quote_strings(DATA)) + [("recruiters.html", page_text), ("recruiters.js strings", js_strings)]
        for name, pattern in surface.FORBIDDEN_CLAIMS + EXTRA_FORBIDDEN:
            for where, text in surfaces:
                with self.subTest(claim=name, where=where):
                    self.assertNotRegex(_without_confirmed_dates(text).lower(), pattern,
                                        f"{where} makes a forbidden claim: {name}")

    def test_quote_exemption_is_needed_and_scoped_to_quotes(self):
        quotes = [q for _, _, q in prp.iter_quotes(SOURCE)]
        multi = r"\bmulti-?agent\b"
        self.assertTrue(any(re.search(multi, q, re.I) for q in quotes),
                        "no quote needs the exemption any more; drop it")
        for where, text in _non_quote_strings(DATA):
            self.assertNotRegex(text.lower(), multi, where)

    def test_profile_never_carries_an_architect_title_or_a_year(self):
        p = DATA["profile"]
        for field in ("name", "headline", "location", "work_mode", "languages", "education", "nrg"):
            with self.subTest(field=field):
                self.assertNotRegex(p[field].lower(), r"\barchitects?\b")
                self.assertNotRegex(_without_confirmed_dates(p[field]), r"\b(19|20)\d{2}\b")
        self.assertEqual(p["headline"], "AI solution architecture and engineering")
        self.assertIn("since early 2026", p["nrg"].lower())
        self.assertIn("initial core AI team", p["nrg"])
        self.assertNotRegex(p["education"], r"\d")
        self.assertEqual(p["education"], "B.E. Computer Science, Madras University")
        self.assertIn("German A1–A2", p["languages"])
        self.assertIn("not an NRG product", p["nrg"])

    def test_every_requirement_has_evidence_and_an_honest_limit_and_gaps_exist(self):
        for r in DATA["requirements"]:
            with self.subTest(req=r["id"]):
                self.assertTrue(r["evidence"])
                self.assertGreater(len(r["limits"]), 20)
        self.assertGreaterEqual(len(DATA["gaps"]), 5)

    def test_postings_have_https_urls_and_the_access_date(self):
        self.assertEqual(DATA["postings_accessed"], "2026-10-06")
        self.assertEqual(len(DATA["postings"]), 13)
        for p in DATA["postings"]:
            self.assertTrue(p["url"].startswith("https://"), p["url"])


class RecruitersPageArtifactTestCase(unittest.TestCase):
    def test_route_serves_the_page(self):
        self.assertEqual(prp.served_routes().get("/recruiters"), "recruiters.html")

    def test_page_loads_its_own_assets_and_no_web_fonts(self):
        html = (WEB / "recruiters.html").read_text(encoding="utf-8")
        for ref in ("/recruiters.css", "/recruiters.js", "/nav.js", 'id="top-nav"'):
            self.assertIn(ref, html)
        for path in ("recruiters.html", "recruiters.css"):
            self.assertNotIn("fonts.googleapis", (WEB / path).read_text(encoding="utf-8"))

    def test_page_is_in_the_top_nav_as_for_recruiters(self):
        # Automation Sprint 4: the Owner approved the nav entry.
        self.assertIn('{ href: "/recruiters", label: "For Recruiters" }', (WEB / "nav.js").read_text(encoding="utf-8"))

    def test_no_placeholder_or_dead_link_markers(self):
        for path in ("recruiters.html", "recruiters.js"):
            text = surface._strip_comments((WEB / path).read_text(encoding="utf-8"))
            for pattern, description in surface.DEAD_LINK_MARKERS:
                with self.subTest(file=path, marker=description):
                    self.assertNotRegex(text, pattern)

    def test_js_renders_numbers_from_the_data_not_literals(self):
        js = (WEB / "recruiters.js").read_text(encoding="utf-8")
        for literal in ("0.833", "22 / 22", "18 of 20", '"13"'):
            self.assertNotIn(literal, js)


if __name__ == "__main__":
    unittest.main()
