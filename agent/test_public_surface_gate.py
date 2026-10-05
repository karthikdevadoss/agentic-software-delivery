"""Sprint 14 release guards for the recruiter-facing public surface.

Three separate things are guarded here, and they fail for different reasons on
purpose:

1. FORBIDDEN CLAIMS -- the home page and the durable-agent case study must not
   POSITIVELY claim capabilities this platform does not have. The distinction
   that matters is positive claim vs. explicit "not implemented / future work"
   wording: the home page's own "Current scope boundaries" block and the case
   study's "Honest limits" block are *required* to name those absent
   capabilities, so the scan excludes those blocks and checks the rest.

2. PRIVATE SURFACES -- /learn, /jd-match and their APIs must be unreachable in
   a default (production-shaped) process. They are not deleted; they are
   registered only when PRIVATE_SURFACES_ENABLED is set.

3. STRUCTURE AND DEAD LINKS -- the page must actually contain what the release
   contract says it contains, and must not ship a placeholder, a "#" href, a
   rendered TODO or a leftover mockup banner.

These are hermetic: no network, no model, no live database.
"""
import os
import pathlib
import re
import unittest

import proof_registry as pr

WEB_DIR = pathlib.Path(__file__).resolve().parent / "web"
HOME = WEB_DIR / "home.html"
CASE_STUDY = WEB_DIR / "case-study-durable-agent.html"
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _strip_comments(html: str) -> str:
    """HTML comments are not visible to a recruiter and legitimately explain
    engineering decisions (including naming absent capabilities), so they are
    not part of the claim surface."""
    return re.sub(r"<!--.*?-->", " ", html, flags=re.DOTALL)


def _visible_text(html: str) -> str:
    html = _strip_comments(html)
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.DOTALL | re.I)
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.DOTALL | re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", html)


def _drop_paras(html: str, class_name: str) -> str:
    """Remove every <p class="..."> paragraph by class.

    Sprint 18: the per-claim limitation lines are <p class="elimit">, not a
    <div>, so _drop_block below cannot reach them. They are the same CATEGORY
    as the scope block -- text whose entire job is to name what is absent or
    bounded -- and they are therefore excluded from the positive-claim scan for
    the same reason. test_every_limitation_really_is_a_limitation below keeps
    that exclusion honest, exactly as the scope block's own test does.
    """
    pattern = re.compile(
        r'<p class="' + re.escape(class_name) + r'".*?</p>\s*', re.DOTALL)
    return pattern.sub(" ", html)


def _drop_block(html: str, class_name: str) -> str:
    """Remove one <div class="..."> block by class, so its content can be
    excluded from the positive-claim scan."""
    pattern = re.compile(
        r'<div class="' + re.escape(class_name) + r'".*?</div>\s*', re.DOTALL)
    return pattern.sub(" ", html)


# Each entry: (human name, regex matching a POSITIVE claim of the capability).
# Wording is deliberately narrow -- the aim is to catch the page asserting the
# capability, not to ban the word appearing anywhere.
FORBIDDEN_CLAIMS = [
    ("multi-agent orchestration in production", r"\bmulti-?agent\b"),
    ("a second model provider", r"\bsecond (model )?provider\b|\bmulti-?provider\b"),
    ("model routing", r"\bmodel routing\b|\brouting between (models|providers)\b"),
    ("provider failover", r"\bfailover\b"),
    ("a managed vector database", r"\bvector (database|db|store)\b|\bpinecone\b|\bweaviate\b|\bqdrant\b|\bpgvector\b"),
    ("hybrid search", r"\bhybrid (search|retrieval)\b"),
    ("reranking", r"\brerank\w*\b"),
    ("automated deployment / CD", r"\bcontinuous deployment\b|\bautomated deploy\w*\b|\bauto-?deploys?\b"),
    ("Spring AI", r"\bspring ai\b"),
    ("Kafka", r"\bkafka\b"),
    ("Northern Trust", r"\bnorthern trust\b"),
    # Sprint 18: the digit-only version of this pattern was evaded by MY OWN
    # draft lede, which said "Fifteen years of enterprise backend work" -- a
    # figure published nowhere in this repository's claim authority. The regex
    # would have let it through because the numeral was spelled out. It was
    # caught by reading the claim boundary, not by the gate, and that is the gap.
    ("a years-of-experience figure", r"\b\d{1,2}\+?\s*years\b"),
    ("a spelled-out years-of-experience figure",
     r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
     r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)\s*"
     r"(\+|plus)?\s*years\b"),
    ("platform age", r"\b(built|created|running)\s+(it\s+)?(over|for|in)\s+(the\s+)?(past\s+)?\w+\s+(weeks?|months?|years?)\b"),
    ("commit counts", r"\b\d{2,}\s+commits\b"),
    ("raw total test counts as marketing", r"\b\d{3,}\s+tests\b"),
    ("the Standing Interview 15/15 gate", r"\b15\s*/\s*15\b"),
]

DEAD_LINK_MARKERS = [
    (r'href="#"', 'an empty "#" href'),
    (r"TODO", "a rendered TODO"),
    (r"MOCKUP", "a leftover mockup label"),
    (r"FIXME", "a rendered FIXME"),
    (r"Lorem ipsum", "placeholder copy"),
    (r'href="/learn', "a link to Learn (no longer public)"),
    (r'href="/jd-match', "a link to JD Match (no longer public)"),
]


class ForbiddenClaimTestCase(unittest.TestCase):
    """The claim surface is the visible text MINUS the blocks whose whole job
    is to name what is absent."""

    def _claim_surface(self, path: pathlib.Path, *exclude_classes: str) -> str:
        html = path.read_text(encoding="utf-8")
        # Sprint 18: per-claim limitations first, then the named blocks.
        html = _drop_paras(html, "elimit")
        for cls in exclude_classes:
            html = _drop_block(html, cls)
        return _visible_text(html).lower()

    def test_home_page_makes_no_forbidden_positive_claim(self):
        surface = self._claim_surface(HOME, "scope")
        for name, pattern in FORBIDDEN_CLAIMS:
            with self.subTest(claim=name):
                m = re.search(pattern, surface, re.I)
                detail = repr(m.group(0)) if m else ""
                self.assertIsNone(
                    m, f"home.html positively claims {name}: {detail} "
                       f"(negated/future wording belongs in the scope-boundaries block or in a per-claim limitation)")

    def test_case_study_makes_no_forbidden_positive_claim(self):
        surface = self._claim_surface(CASE_STUDY, "caveat")
        for name, pattern in FORBIDDEN_CLAIMS:
            with self.subTest(claim=name):
                m = re.search(pattern, surface, re.I)
                detail = repr(m.group(0)) if m else ""
                self.assertIsNone(
                    m, f"case study positively claims {name}: {detail}")

    def test_the_scope_block_really_does_name_the_absent_capabilities(self):
        """The exclusion above is only safe if the excluded block is actually
        doing its job. If someone deletes the scope block, the forbidden-claim
        test would start passing vacuously -- this stops that."""
        text = _visible_text(HOME.read_text(encoding="utf-8")).lower()
        for needle in ("one model provider", "vector database",
                       "manually triggered", "future work"):
            self.assertIn(needle, text,
                          f"the scope-boundaries block must still state {needle!r}")

    # Markers that turn a mention of an absent capability into a disclaimer.
    # "rather than X" / "no X" / "does not use X" / "X remains future work".
    NEGATION_MARKERS = (
        "rather than", "instead of", "does not", "do not", "not ", "no ",
        "without", "remain future work", "remains future work", "future work",
        "has not", "have not", "never",
    )

    def _block(self, path: pathlib.Path, class_name: str) -> str:
        html = _strip_comments(path.read_text(encoding="utf-8"))
        m = re.search(r'<div class="' + re.escape(class_name) + r'".*?</div>',
                      html, re.DOTALL)
        self.assertIsNotNone(m, f"{path.name} has no .{class_name} block")
        return _visible_text(m.group(0)).lower()

    def test_scope_block_mentions_absent_capabilities_only_as_disclaimers(self):
        """Seeded mutation M1 (2026-09-29) proved the wholesale exclusion of the
        scope block let an affirmative overclaim hide inside it.

        Scoping is per SENTENCE, not per character window. English puts the
        disclaimer on either side of the capability -- "rather than a managed
        vector database" (before) and "hybrid retrieval remain future work"
        (after) -- so a directional window gets one of them wrong. A sentence
        is the unit that actually carries the negation."""
        for path, cls in ((HOME, "scope"), (CASE_STUDY, "caveat")):
            block = self._block(path, cls)
            for sentence in re.split(r"(?<=[.!?])\s+", block):
                has_marker = any(mark in sentence for mark in self.NEGATION_MARKERS)
                for name, pattern in FORBIDDEN_CLAIMS:
                    m = re.search(pattern, sentence, re.I)
                    if not m:
                        continue
                    with self.subTest(page=path.name, claim=name, sentence=sentence[:70]):
                        self.assertTrue(
                            has_marker,
                            f"{path.name}'s .{cls} block names {name} "
                            f"({m.group(0)!r}) in a sentence with no negation or "
                            f"contrast marker, which reads as a positive claim: "
                            f"{sentence.strip()!r}")

    def test_scope_block_cannot_be_silently_deleted(self):
        """If the scope block vanished, the main forbidden-claim scan would
        start passing vacuously. This fails loudly instead."""
        block = self._block(HOME, "scope")
        self.assertGreater(len(block), 120,
                           "the scope-boundaries block must still carry real content")

    def test_case_study_keeps_an_honest_limits_section(self):
        text = _visible_text(CASE_STUDY.read_text(encoding="utf-8")).lower()
        self.assertIn("honest limits", text)
        self.assertIn("not an employer production system", text)

    def test_neither_page_implies_employer_scale_for_the_personal_platform(self):
        for path in (HOME, CASE_STUDY):
            text = _visible_text(path.read_text(encoding="utf-8")).lower()
            with self.subTest(page=path.name):
                # NRG may be named as the current engagement; what must never
                # appear is the platform being attributed to it.
                self.assertNotRegex(
                    text, r"nrg'?s? (ai )?(platform|system)\b",
                    "the AI platform must never be described as NRG's")

    def test_home_states_the_nrg_separation_explicitly(self):
        text = _visible_text(HOME.read_text(encoding="utf-8")).lower()
        self.assertIn("not an nrg product", text,
                      "the hero must keep the explicit NRG separation sentence")


class DeadLinkAndPlaceholderTestCase(unittest.TestCase):
    def test_no_placeholder_or_dead_link_markers(self):
        for path in (HOME, CASE_STUDY):
            html = _strip_comments(path.read_text(encoding="utf-8"))
            for pattern, description in DEAD_LINK_MARKERS:
                with self.subTest(page=path.name, marker=description):
                    self.assertNotRegex(html, pattern,
                                        f"{path.name} contains {description}")

    def test_every_internal_link_targets_a_registered_route_or_real_anchor(self):
        """A link to a route the server does not serve is a dead link even
        though nothing in the HTML looks wrong."""
        import web_server
        served = set()
        for route in web_server.routes:
            path = getattr(route, "path", None)
            if path:
                served.add(path)
        # routes with path params that the home page links into
        served.add("/showcase/senior-java-ai-transformation")

        for path in (HOME, CASE_STUDY):
            html = _strip_comments(path.read_text(encoding="utf-8"))
            for href in re.findall(r'href="(/[^"#]*)(?:#[^"]*)?"', html):
                with self.subTest(page=path.name, href=href):
                    self.assertIn(
                        href, served,
                        f"{path.name} links to {href}, which no route serves")

    def test_workbench_anchor_target_actually_exists(self):
        """The first proof card deep-links into Workbench. An anchor that does
        not exist scrolls nowhere and silently breaks the claim's destination."""
        home = HOME.read_text(encoding="utf-8")
        anchors = re.findall(r'href="/workbench#([^"]+)"', home)
        if anchors:
            workbench = (WEB_DIR / "workbench.html").read_text(encoding="utf-8")
            for anchor in anchors:
                with self.subTest(anchor=anchor):
                    self.assertRegex(
                        workbench, r'id="' + re.escape(anchor) + r'"',
                        f'workbench.html has no element with id="{anchor}"')


class HomePageStructureTestCase(unittest.TestCase):
    def setUp(self):
        self.html = HOME.read_text(encoding="utf-8")
        self.text = _visible_text(self.html)

    def test_identity_is_present_and_correct(self):
        self.assertIn("Karthikeyan Devadoss", self.text)
        self.assertIn("Berlin", self.text)

    def test_exactly_three_proof_cards(self):
        cards = re.findall(r'<article class="pcard">', self.html)
        self.assertEqual(len(cards), 3,
                         f"the release contract specifies exactly three proof cards, found {len(cards)}")

    def test_the_evidence_rows_match_the_registry_exactly(self):
        """Sprint 18: the row count used to be hardcoded at six. It is now
        whatever docs/PUBLIC_PROOF_SURFACE.yaml declares PRIMARY, because the
        registry became the single source of truth for what the page claims --
        and a contract duplicated in two places is a contract that will drift.
        This still asserts a declared contract; the declaration just moved to
        where the claims themselves live."""
        rows = re.findall(r'<div class="erow">', self.html)
        expected = pr.public_entries(tier="PRIMARY")
        self.assertEqual(
            len(rows), len(expected),
            f"the registry declares {len(expected)} PRIMARY capabilities but the page "
            f"renders {len(rows)} evidence rows -- run "
            "python agent/build_proof_surface.py --write")
        for entry in expected:
            with self.subTest(capability=entry["capability_id"]):
                self.assertIn(
                    entry["headline"], self.text,
                    f"{entry['capability_id']} is declared PRIMARY but its headline is "
                    "not on the page")

    def test_every_evidence_row_has_a_status_a_limitation_and_a_link(self):
        blocks = re.findall(r'<div class="erow">(.*?)</div>\s*</div>', self.html, re.DOTALL)
        self.assertEqual(len(blocks), len(pr.public_entries(tier="PRIMARY")))
        for i, block in enumerate(blocks, 1):
            with self.subTest(row=i):
                self.assertRegex(block, r'<p class="estat[^"]*">\s*\S',
                                 f"evidence row {i} has no verification status")
                # Sprint 18: new contract. A claim without its boundary next to
                # it is the failure mode this sprint exists to remove -- a
                # limitation collected in a footer nobody reaches is not a
                # limitation, it is a disclaimer.
                self.assertRegex(block, r'<p class="elimit">\s*\S',
                                 f"evidence row {i} states no limitation")
                self.assertRegex(block, r'<a href="[^"]+"',
                                 f"evidence row {i} has no evidence link")

    def test_every_status_label_is_a_published_vocabulary_value(self):
        """Free-prose statuses ("Running in production", "Measured on every
        build", "Implemented and tested") were what the page used before. They
        read fine and meant nothing checkable. Four values, and only four."""
        labels = {
            meta["label"]
            for meta in pr.load_surface()["status_vocabulary"].values()
        }
        rendered = re.findall(r'<p class="estat[^"]*">([^<]+)</p>', self.html)
        self.assertTrue(rendered, "no status labels rendered at all")
        for label in rendered:
            with self.subTest(label=label):
                self.assertIn(label.strip(), labels,
                              f"{label.strip()!r} is not one of the four published statuses")

    def test_every_limitation_really_is_a_limitation(self):
        """Keeps the positive-claim scan's exclusion honest. _drop_paras removes
        the limitation lines before scanning for overclaims, which is only safe
        while those lines genuinely carry bounding language. If a limitation
        were ever rewritten into marketing, this fails and the exclusion stops
        hiding it."""
        bounding = re.compile(
            r"\bnot\b|\bno\b|\bonly\b|\bnever\b|\brather than\b|\bunproven\b|"
            r"\bpaused\b|\bscoped\b|\blocal(ly)?\b|\bunavailable\b|\bwithout\b",
            re.I)
        limitations = re.findall(r'<p class="elimit">(.*?)</p>', self.html, re.DOTALL)
        self.assertEqual(len(limitations), len(pr.public_entries(tier="PRIMARY")))
        for text in limitations:
            visible = _visible_text(text).strip()
            with self.subTest(limitation=visible[:60]):
                self.assertGreater(len(visible), 40,
                                   "a one-word limitation is decoration, not a boundary")
                self.assertRegex(visible, bounding,
                                 "this limitation contains no bounding language, so "
                                 "excluding it from the overclaim scan would hide a claim")

    def test_the_paused_experiment_is_not_presented_as_live_on_the_home_page(self):
        """The single most likely future overclaim on this page: the Deep
        Consensus row is the most impressive engineering on it and its product
        thesis failed."""
        block = re.search(
            r'<div class="erow">(?:(?!</div>\s*</div>).)*?'
            r'An experiment that failed its own test.*?</div>\s*</div>',
            self.html, re.DOTALL)
        self.assertIsNotNone(block, "the paused-experiment evidence row is missing")
        row = block.group(0)
        self.assertIn("st-experimental-paused", row,
                      "the paused experiment must carry the experimental/paused status")
        for forbidden in ("st-live-verified", "Running in production"):
            self.assertNotIn(forbidden, row)
        visible = _visible_text(row).lower()
        self.assertIn("unproven", visible,
                      "the row must say the product thesis is unproven")

    def test_mcp_is_not_presented_as_a_hosted_production_service(self):
        """Independently reverified 2026-09-29: agent/mcp_server.py is a stdio
        server for local clients and is NOT served by the deployed web app.

        Sprint 18 merged the standalone MCP row into the retrieval capability
        the registry already bundles it with (rag-mcp-embeddings), so this no
        longer looks for a row called "MCP server". It asserts the property that
        actually matters and that survives the row being reorganised: the page
        must disclose that MCP runs locally, and must not place MCP inside a
        Live row."""
        self.assertIn("runs locally", self.text,
                      "the page no longer discloses that the MCP server is local-only")
        block = re.search(
            r'<div class="erow">(?:(?!</div>\s*</div>).)*?'
            r'Model Context Protocol.*?</div>\s*</div>', self.html, re.DOTALL)
        self.assertIsNotNone(block, "no row mentions the Model Context Protocol")
        self.assertNotIn("st-live-verified", block.group(0),
                         "MCP runs locally over stdio; its row must not read as Live")

    def test_no_internal_identifiers_or_raw_paths_are_rendered(self):
        for bad in ("AEQ-", "BL-0", "PORTFOLIO_CAPABILITIES", "C:\\", "/home/", "docs/"):
            with self.subTest(marker=bad):
                self.assertNotIn(bad, self.text,
                                 f"internal identifier or raw path {bad!r} is visible to the reader")

    def test_footer_cookie_wording_is_precise(self):
        self.assertIn("sets no cookies and uses no analytics or third-party trackers", self.text)
        for overreach in ("no tracking", "no logging", "Impressum not required", "no server logs"):
            with self.subTest(phrase=overreach):
                self.assertNotIn(overreach, self.text)

    def test_employer_list_is_exactly_the_three_approved(self):
        self.assertIn("NRG Energy", self.text)
        self.assertIn("Blue Cross Blue Shield Association", self.text)
        self.assertIn("Marsh", self.text)


class PrivateSurfaceGateTestCase(unittest.TestCase):
    """Learn and JD Match must 404 in a production-shaped process, while their
    implementation, datasets and tests remain untouched."""

    def _client_without_flag(self):
        import importlib
        import web_server
        previous = os.environ.pop("PRIVATE_SURFACES_ENABLED", None)
        module = importlib.reload(web_server)
        self.addCleanup(lambda: self._restore(previous))
        self.assertFalse(module.PRIVATE_SURFACES_ENABLED)
        from starlette.testclient import TestClient
        return TestClient(module.app)

    @staticmethod
    def _restore(previous):
        import importlib
        import web_server
        if previous is not None:
            os.environ["PRIVATE_SURFACES_ENABLED"] = previous
        else:
            os.environ.pop("PRIVATE_SURFACES_ENABLED", None)
        importlib.reload(web_server)

    def test_learn_and_jd_match_are_not_publicly_reachable(self):
        client = self._client_without_flag()
        # The .html/.js/.css/.json forms matter as much as the clean URLs:
        # the app ends in a StaticFiles mount, so a file in agent/web/ is a
        # public URL unless something shadows it. Removing the routes alone
        # left /learn.html serving a full page (found 2026-09-29).
        for path in ("/learn", "/learn/java-core", "/jd-match",
                     "/api/jd-match/sample", "/api/learn/tree",
                     "/learn.html", "/jd-match.html",
                     "/learn.js", "/learn.css", "/jd-match.js", "/jd-match.css",
                     "/learn-data.json", "/learn-tree.json", "/learn-deep-topics.json"):
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 404,
                                 f"{path} must not be reachable on the public deployment")

    def test_the_implementations_were_not_deleted(self):
        """The Owner's instruction was to unpublish, not to remove."""
        for module in ("jd_match.py", "learn_data.py"):
            candidate = pathlib.Path(__file__).resolve().parent / module
            if module == "learn_data.py" and not candidate.exists():
                continue          # learn's loader may live under another name
            with self.subTest(module=module):
                self.assertTrue(candidate.exists(), f"{module} must still exist")
        self.assertTrue((WEB_DIR / "jd-match.html").exists())
        self.assertTrue((WEB_DIR / "learn.html").exists())
        self.assertTrue((pathlib.Path(__file__).resolve().parent / "evals" / "jd_match_dataset.json").exists())

    def test_public_pages_are_still_served(self):
        client = self._client_without_flag()
        for path in ("/", "/workbench", "/case-study/durable-agent", "/triage",
                     "/ask-codebase", "/usage", "/standing-interview",
                     "/showcase/senior-java-ai-transformation", "/dashboard"):
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 200, f"{path} must still serve")

    def test_root_serves_the_home_page_not_the_workbench(self):
        client = self._client_without_flag()
        body = client.get("/").text
        self.assertIn("Karthikeyan Devadoss", body)
        self.assertNotIn("What would you like to change?", body,
                         '"/" must no longer serve the Workbench form')

    def test_case_study_route_serves_the_case_study(self):
        client = self._client_without_flag()
        body = client.get("/case-study/durable-agent").text
        self.assertIn("halfway through an AI-written change", body)


class CustomerAppReturnPathTestCase(unittest.TestCase):
    def test_customer_app_offers_a_way_back_to_the_portfolio(self):
        """Found by the Sprint 14 product review: the separately deployed Java
        app rendered zero navigation links, so a recruiter who opened it was
        stranded with no route back."""
        index = REPO_ROOT / "app" / "src" / "main" / "resources" / "static" / "index.html"
        html = index.read_text(encoding="utf-8")
        self.assertIn('id="back-to-portfolio"', html,
                      "the customer app must carry a Back to Portfolio link")
        self.assertIn("Back to Portfolio", html)
        self.assertRegex(html, r'href="https://agentic-platform-backend-production\.up\.railway\.app/"',
                         "the return link must point at the portfolio home page")



class OneApprovalStoryTestCase(unittest.TestCase):
    """Sprint 19 (2026-10-05, Owner-authorized): the public pages tell ONE
    approval story, and it is the true one.

    The truth, read out of agent/risk_policy.py, agent/write_tools.py and
    agent/web_server.py: a DETERMINISTIC policy -- not the model, not a person
    -- decides whether a requirement is inside a narrow pre-declared band.
    Inside it, the Workbench applies the change with no approval event at all.
    Outside it, nothing is applied without a person, and that approval is bound
    by hash to the exact content approved. Triage is a third surface and is
    always gated by an admin approval.

    Two opposite false claims are therefore both forbidden: "every change
    needs a person" (the home page's generated evidence row said exactly this
    before Sprint 19) and "the model approves itself" (the Workbench tagline
    implied this before Sprint 17). These checks are hermetic twins of
    e2e/copy-contract.spec.js, so release health catches the regression
    without a browser.
    """

    PROOF = WEB_DIR / "proof.html"
    WORKBENCH = WEB_DIR / "workbench.html"
    USAGE = WEB_DIR / "usage.html"
    STANDING_INTERVIEW = WEB_DIR / "standing-interview.html"

    EVERY_CHANGE_NEEDS_A_PERSON = [
        r"applied only after a person approves",
        r"every (change|write|requirement) (requires|needs) (a )?(human|person)",
        r"nothing (is|gets) applied without (a )?(human|person)",
    ]

    def _text(self, path):
        return _visible_text(path.read_text(encoding="utf-8"))

    def test_home_and_proof_do_not_claim_every_change_needs_a_person(self):
        for path in (HOME, self.PROOF):
            body = self._text(path)
            for pattern in self.EVERY_CHANGE_NEEDS_A_PERSON:
                self.assertIsNone(
                    re.search(pattern, body, re.I),
                    f"{path.name} says every change needs a person ({pattern!r}); "
                    "the Workbench auto path applies small changes with no "
                    "approval event, so this is a false claim",
                )

    def test_home_states_what_decides_and_that_the_auto_path_is_real(self):
        body = self._text(HOME)
        self.assertRegex(body, r"deterministic",
                         "say WHAT decides, not only that the model does not")
        self.assertRegex(
            body, r"(without|with no) (a )?(person|human)",
            "the bounded auto path is real and the home page must say so, or "
            "a technical interviewer catches the false modesty in one question",
        )

    def test_home_headline_is_senior_backend_and_agentic_ai(self):
        """Owner decision 2026-10-05: the headline stays Senior Backend /
        Agentic AI. Sprint 18 had changed it; this pins the decision."""
        html = HOME.read_text(encoding="utf-8")
        role = re.search(r'<p class="role">(.*?)</p>', html, re.DOTALL)
        self.assertIsNotNone(role, "the home page must carry a <p class=\"role\"> headline")
        self.assertIn("Senior Backend / Software Engineer", role.group(1))
        self.assertIn("Agentic AI", role.group(1))

    def test_workbench_tells_the_same_story(self):
        body = self._text(self.WORKBENCH)
        for forbidden in (r"no human approval needed", r"preview tier", r"self-approv",
                          r"the (model|agent|AI|LLM) approves"):
            self.assertIsNone(re.search(forbidden, body, re.I),
                              f"Workbench copy matched {forbidden!r}")
        self.assertRegex(body, r"deterministic", "the truthful claim must be present")
        self.assertRegex(body, r"automatic", "the auto path is real and should be stated")
        self.assertIsNone(re.search(r"every (change|write|requirement) requires (a )?human", body, re.I))

    def test_target_app_environment_label_is_truthful(self):
        import web_server as ws
        self.assertRegex(ws.TARGET_APPLICATION["environment"], r"Live demo app \(not NRG\)",
                         '"Production Demo" is two words that contradict each other')

    def test_standing_interview_names_the_candidate(self):
        self.assertIn("Karthikeyan Devadoss", self._text(self.STANDING_INTERVIEW))

    def test_usage_names_its_own_spend_and_keeps_dashboard_below_the_fold(self):
        html = self.USAGE.read_text(encoding="utf-8")
        body = _visible_text(html)
        self.assertRegex(body, r"this platform's own metered spend")
        self.assertRegex(body, r"not NRG|not any employer")
        fold = re.search(r'<p class="fold-actions">.*?</p>', html, re.DOTALL)
        self.assertIsNotNone(fold)
        self.assertNotIn('href="/dashboard"', fold.group(0),
                         "Dashboard is deliberately not a first-screen action; it stays "
                         "linked further down the page (usage.js)")


class MainLandmarkTestCase(unittest.TestCase):
    """OWNER_DECISIONS_PENDING.md item 6: three public pages had no <main>
    landmark, so a screen-reader user could not skip to content. Exactly one
    per page, because two landmarks of the same kind need distinguishing labels
    and none of these pages has a reason for two."""

    PAGES = {
        "home": HOME,
        "case-study": CASE_STUDY,
        "proof": WEB_DIR / "proof.html",
    }

    def test_each_public_page_has_exactly_one_main_landmark(self):
        for name, path in self.PAGES.items():
            html = _strip_comments(path.read_text(encoding="utf-8"))
            # Markup only: a <style> or <script> block may legitimately mention
            # the landmark in a CSS comment (case-study does), and that is not
            # a landmark.
            html = re.sub(r"<style.*?</style>", " ", html, flags=re.DOTALL | re.I)
            html = re.sub(r"<script.*?</script>", " ", html, flags=re.DOTALL | re.I)
            count = len(re.findall(r"<main\b", html))
            self.assertEqual(count, 1, f"{name}: expected exactly one <main>, found {count}")



# ---------------------------------------------------------------------------
# Sprint 20 (2026-10-05): the guard covers every recruiter-visible page (BL-163),
# and three copy promises a hiring manager reads (BL-167, BL-157, BL-101).
# ---------------------------------------------------------------------------

#: Every recruiter-visible HTML page under agent/web. The shells (usage,
#: dashboard, showcase, ask-codebase) render their claims from JS; their static
#: text is scanned here and the rendered text is covered by the Playwright
#: copy contract. Standing Interview's sample questions are prompts a visitor
#: may ask, not claims the platform makes, so that block is excluded by class.
PUBLIC_PAGES = {
    "home": (WEB_DIR / "home.html", ("scope",)),
    "case-study": (WEB_DIR / "case-study-durable-agent.html", ("caveat",)),
    # proof.html states each limitation in <p class="lim1"> and in a
    # <div class="disclose"> block: the same category as home's scope block.
    "proof": (WEB_DIR / "proof.html", ("scope", "caveat", "p:lim1", "dd:Limitation in full")),
    "workbench": (WEB_DIR / "workbench.html", ("caveat",)),
    "triage-a": (WEB_DIR / "triage.html", ("caveat",)),
    "triage-b": (WEB_DIR / "triage-b.html", ("caveat",)),
    "triage-c": (WEB_DIR / "triage-c.html", ("caveat",)),
    "usage": (WEB_DIR / "usage.html", ("caveat",)),
    "standing-interview": (WEB_DIR / "standing-interview.html", ("caveat", "si-samples")),
    "showcase": (WEB_DIR / "showcase.html", ("caveat",)),
    "ask-codebase": (WEB_DIR / "ask-codebase.html", ("caveat",)),
    "dashboard": (WEB_DIR / "dashboard.html", ("caveat",)),
}


class WholeSurfaceForbiddenClaimTestCase(ForbiddenClaimTestCase):
    """BL-163: the forbidden-claim scan covered two pages. Now every page."""

    def test_every_recruiter_visible_page_makes_no_forbidden_positive_claim(self):
        for name, (path, excluded) in PUBLIC_PAGES.items():
            self.assertTrue(path.is_file(), f"{name}: {path} is missing")
            html = path.read_text(encoding="utf-8")
            html = _drop_paras(html, "elimit")
            for cls in excluded:
                if cls.startswith("p:"):
                    html = _drop_paras(html, cls[2:])
                elif cls.startswith("dd:"):
                    # <dt>Limitation in full</dt><dd>...</dd>: a limitation by name.
                    html = re.sub(r"<dt>" + re.escape(cls[3:]) + r"</dt>\s*<dd>.*?</dd>",
                                  " ", html, flags=re.DOTALL)
                else:
                    html = _drop_block(html, cls)
            surface = _visible_text(html).lower()
            for claim, pattern in FORBIDDEN_CLAIMS:
                with self.subTest(page=name, claim=claim):
                    m = re.search(pattern, surface, re.I)
                    detail = repr(m.group(0)) if m else ""
                    self.assertIsNone(
                        m, f"{path.name} positively claims {claim}: {detail}")

    def test_no_public_page_carries_a_dead_link_marker(self):
        for name, (path, _excluded) in PUBLIC_PAGES.items():
            html = _strip_comments(path.read_text(encoding="utf-8"))
            # A hidden anchor whose href is filled in client-side (the Workbench
            # verified-run link) is not a dead link a visitor can click.
            html = re.sub(r"<a\b[^>]*\bhidden\b[^>]*>.*?</a>", " ", html, flags=re.DOTALL)
            for pattern, what in DEAD_LINK_MARKERS:
                with self.subTest(page=name, marker=what):
                    self.assertIsNone(re.search(pattern, html), f"{path.name} carries {what}")


class HiringManagerCopyTestCase(unittest.TestCase):
    """Three copy promises, checked on the static files (hermetic twins of the
    Playwright assertions in e2e/public-copy-sprint20.spec.js)."""

    def _text(self, path):
        return _visible_text(_strip_comments(path.read_text(encoding="utf-8")))

    def test_home_explains_the_standing_interview_before_the_click(self):
        text = self._text(WEB_DIR / "home.html")
        self.assertIn("Standing Interview", text)
        self.assertRegex(text, r"(?i)written record|recorded engineering knowledge")
        self.assertIn('href="/standing-interview"', (WEB_DIR / "home.html").read_text(encoding="utf-8"))

    def test_dashboard_is_scoped_as_the_full_inventory_for_engineers(self):
        text = self._text(WEB_DIR / "dashboard.html")
        self.assertRegex(text, r"(?i)full (evidence )?inventory")
        self.assertRegex(text, r"(?i)written for engineers")

    def test_workbench_says_which_stages_code_decides(self):
        text = self._text(WEB_DIR / "workbench.html")
        self.assertRegex(text, r"(?i)decided by (deterministic )?code")
        self.assertRegex(text, r"(?i)proposed by (a|the) model")
        script = (WEB_DIR / "workbench.js").read_text(encoding="utf-8")
        self.assertNotRegex(script, r"(?i)preview tier",
                            "the tier wording the Owner removed from the page must not survive in a stage detail")

    def test_every_triage_page_tells_the_one_story(self):
        for name in ("triage.html", "triage-b.html", "triage-c.html"):
            with self.subTest(page=name):
                text = self._text(WEB_DIR / name)
                self.assertRegex(text, r"(?i)why three scenarios")
                self.assertRegex(text, r"(?i)never reads a ticket")
                self.assertIn("Human Approval Required", text, "the approval gate is not to be touched")

    def test_standing_interview_thread_is_a_live_region(self):
        html = (WEB_DIR / "standing-interview.html").read_text(encoding="utf-8")
        self.assertRegex(html, r'id="si-thread"[^>]*aria-live="polite"|aria-live="polite"[^>]*id="si-thread"')
        self.assertEqual(1, html.count("<main"), "one main landmark")


# ---------------------------------------------------------------------------
# Flow 4 (2026-10-05): triage step 6 reports the real fixApplied switch, and the
# README matches the served site.
# ---------------------------------------------------------------------------

class TriageStepSixMatchesTheSwitchTestCase(unittest.TestCase):
    """After approval each triage page re-runs the reproduction, and the
    reproduction result carries the scenario's real `fixApplied` switch. Step 6
    must report that switch, and may call the incident resolved only when the
    switch is on AND the re-run shows the defect gone. Source-level check on the
    three handlers, because the real backend is not reachable from a unit test."""

    PAGES = ("triage.js", "triage-b.js", "triage-c.js")

    def test_the_verdict_reads_the_switch_and_the_outcome(self):
        for name in self.PAGES:
            with self.subTest(page=name):
                src = (WEB_DIR / name).read_text(encoding="utf-8")
                handler = src[src.index('"/api/triage/scenario-'):]
                handler = handler[handler.index("approve"):]
                self.assertIn("rerun.fixApplied", handler,
                              name + ": step 6 does not read the real fixApplied switch after approval")
                self.assertIn("STILL REPRODUCES", src,
                              name + ": no branch for a re-run that still shows the defect")
                self.assertIn("SWITCH OFF", src,
                              name + ": no branch for an approval that did not turn the switch on")
                self.assertNotRegex(
                    src, r"innerHTML = `<p class=\"hint\">Fix applied and re-verified\.</p>`;",
                    name + ": prints 'Fix applied and re-verified' unconditionally")
                self.assertRegex(src, r"verdict \$\{", name + ": the verdict class must be chosen at run time")


class ReadmeMatchesTheSiteTestCase(unittest.TestCase):
    """Every route in the README's public-pages table is served, every
    navigation destination appears in that table, and the README describes the
    generated block the way the files are actually built."""

    def _readme(self):
        return (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    def _readme_routes(self):
        return set(re.findall(r"^\| `(/[^`]*)` \|", self._readme(), re.M))

    def test_every_readme_route_is_served(self):
        import web_server as ws
        from starlette.testclient import TestClient
        client = TestClient(ws.app)
        for route in sorted(self._readme_routes()):
            with self.subTest(route=route):
                self.assertEqual(200, client.get(route).status_code, route)

    def test_every_nav_destination_is_in_the_readme(self):
        nav = (WEB_DIR / "nav.js").read_text(encoding="utf-8")
        destinations = set(re.findall(r'href: "(/[^"]*)"', nav))
        self.assertEqual(set(), destinations - self._readme_routes(),
                         "nav destinations the README does not list")

    def test_readme_describes_the_generated_block_as_it_is(self):
        """Only the proof-rows block is generated; the rest of home.html is copy
        that Sprints 19 and 20 edited by hand. The README must not say the whole
        file is generated."""
        home = (WEB_DIR / "home.html").read_text(encoding="utf-8")
        self.assertIn("GENERATED:proof-rows:start", home)
        text = self._readme()
        self.assertIn("proof-rows", text)
        self.assertNotIn("`home.html` and `proof.html` are generated from the registry below and must not be hand-edited",
                         text)

    def test_readme_carries_no_retired_wording(self):
        text = self._readme()
        for stale in ("Week 1 Baseline", "agent only plans", "Production Demo", "preview tier"):
            self.assertNotIn(stale, text)


# ---------------------------------------------------------------------------
# Flow 5 (2026-10-05): the first screen names the three public operations, and
# the Workbench says before the click that a submission can deploy to the demo.
# ---------------------------------------------------------------------------

class FirstScreenOperationsTestCase(unittest.TestCase):
    """The three public operations are the tiles with a backend action behind
    them: the Workbench, Ask the Codebase, and Triage. Nothing new is added; the
    header names what the tiles below already offer."""

    def test_the_header_names_the_three_operations(self):
        html = (WEB_DIR / "home.html").read_text(encoding="utf-8")
        header = html[html.index("<header>"):html.index("</header>")]
        ops = re.search(r'<p class="ops">(.*?)</p>', header, re.S)
        self.assertIsNotNone(ops, "no operations line in the header")
        text = _visible_text(ops.group(0))
        for name in ("Workbench", "Ask the Codebase", "Triage"):
            self.assertIn(name, text)
        self.assertNotIn("Standing Interview", text, "not an operation on the first screen")

    def test_the_operations_line_links_only_to_existing_tiles(self):
        html = (WEB_DIR / "home.html").read_text(encoding="utf-8")
        ops = re.search(r'<p class="ops">(.*?)</p>', html, re.S).group(1)
        tiles = html[html.index('<div class="tiles">'):]
        for href in re.findall(r'href="([^"]+)"', ops):
            self.assertIn('href="' + href + '"', tiles, href + " is not one of the tiles")


class WorkbenchSaysItDeploysTestCase(unittest.TestCase):
    """A submission inside the deterministic band is applied and deployed to the
    demo app with no further click. The page says so next to the submit control,
    before the click, in the words the auto path already uses."""

    def test_the_requirement_panel_says_so_before_the_click(self):
        html = (WEB_DIR / "workbench.html").read_text(encoding="utf-8")
        panel = html[html.index('id="requirement-panel"'):html.index("</section>", html.index('id="requirement-panel"'))]
        text = _visible_text(panel)
        self.assertRegex(text, r"(?i)deploy\w* to the (live )?demo app")
        self.assertRegex(text, r"(?i)no further (click|approval)")
        self.assertIn('id="submit-btn"', panel)


# ---------------------------------------------------------------------------
# Night queue (2026-10-05), items 40, 51, 52, 93, 127, 128, 129.
# ---------------------------------------------------------------------------

class SkillLinesTestCase(unittest.TestCase):
    """Item 40: the enterprise line names the hands-on tools the Owner's own
    records already show, and none the records mark NOT USED."""

    def _skills(self):
        html = (WEB_DIR / "home.html").read_text(encoding="utf-8")
        match = re.search(r'<p class="skills">(.*?)</p>', html, re.S)
        self.assertIsNotNone(match, "no skills line on the home page")
        return _visible_text(match.group(1))

    def test_the_confirmed_tools_are_named(self):
        text = self._skills()
        for tool in ("Java", "Spring Boot", "REST", "GraphQL", "SOAP", "Apache Camel",
                     "FHIR", "AWS Lambda", "JWT", "Dynatrace"):
            with self.subTest(tool=tool):
                self.assertIn(tool, text)

    def test_nothing_the_records_mark_not_used_appears(self):
        text = self._skills()
        for absent in ("Kubernetes", "Terraform", "Resilience4j", "Hystrix", "JMS", "Redis",
                       "Kafka"):
            with self.subTest(absent=absent):
                self.assertNotIn(absent, text)

    def test_the_line_claims_no_years_and_no_metric(self):
        text = self._skills()
        self.assertIsNone(re.search(r"\b\d+\+?\s*years\b", text, re.I))
        self.assertIsNone(re.search(r"\b\d{2,}\b", text))


class OnePagerTestCase(unittest.TestCase):
    """Item 51: a recruiter one-pager that tells the one approval story."""

    PAGE = WEB_DIR / "one-pager.html"

    def test_the_page_exists_and_is_served(self):
        self.assertTrue(self.PAGE.is_file())
        import web_server as ws
        from starlette.testclient import TestClient
        self.assertEqual(200, TestClient(ws.app).get("/one-pager").status_code)

    def test_it_does_not_say_every_change_needs_a_person(self):
        body = _visible_text(_strip_comments(self.PAGE.read_text(encoding="utf-8")))
        self.assertIsNone(re.search(r"every (change|write|requirement) requires (a )?human", body, re.I))
        self.assertIsNone(re.search(r"every change needs (a )?(person|human)", body, re.I))

    def test_it_tells_both_halves_of_the_approval_story(self):
        body = _visible_text(_strip_comments(self.PAGE.read_text(encoding="utf-8")))
        self.assertRegex(body, r"(?i)deterministic")
        self.assertRegex(body, r"(?i)without a person|with no further click|no approval event")
        self.assertRegex(body, r"(?i)waits for|needs a person|human approval")
        self.assertNotRegex(body, r"(?i)self-approv")

    def test_it_makes_no_forbidden_claim(self):
        surface = _visible_text(_strip_comments(self.PAGE.read_text(encoding="utf-8"))).lower()
        for name, pattern in FORBIDDEN_CLAIMS:
            with self.subTest(claim=name):
                self.assertIsNone(re.search(pattern, surface, re.I))

    def test_it_is_in_the_readme_page_table(self):
        text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("`/one-pager`", text)


class StandingInterviewCorpusClaimTestCase(unittest.TestCase):
    """Item 93: the page must not suggest the private records are public."""

    PAGE = WEB_DIR / "standing-interview.html"

    def test_the_page_says_the_records_are_not_public(self):
        body = _visible_text(_strip_comments(self.PAGE.read_text(encoding="utf-8")))
        self.assertRegex(body, r"(?i)not public|private")
        self.assertRegex(body, r"(?i)(records|notes|knowledge).{0,80}(not public|private)")

    def test_it_does_not_offer_the_records_for_download_or_browsing(self):
        html = self.PAGE.read_text(encoding="utf-8")
        for forbidden in ("download", "browse the corpus", "view the corpus", "the full corpus is"):
            self.assertNotIn(forbidden, html.lower())


class WorkbenchAndTriageAndDashboardStayTestCase(unittest.TestCase):
    """Items 127, 128, 129: three things that must not drift back."""

    def test_the_workbench_still_warns_before_a_deploying_click(self):
        html = (WEB_DIR / "workbench.html").read_text(encoding="utf-8")
        panel = html[html.index('id="requirement-panel"'):]
        panel = panel[:panel.index("</section>")]
        text = _visible_text(panel)
        self.assertRegex(text, r"(?i)deploy\w* to the (live )?demo app")
        self.assertRegex(text, r"(?i)no further (click|approval)")

    def test_promote_is_the_only_promote_step_on_each_triage_page(self):
        for name in ("triage.html", "triage-b.html", "triage-c.html"):
            with self.subTest(page=name):
                html = (WEB_DIR / name).read_text(encoding="utf-8")
                self.assertEqual(1, html.count('id="step-promote"'))
                self.assertEqual(1, html.count('id="promote-btn"'))
                self.assertEqual(1, html.count("PROMOTE TO PRODUCTION"))

    def test_the_dashboard_link_is_not_a_first_screen_action_on_usage(self):
        html = (WEB_DIR / "usage.html").read_text(encoding="utf-8")
        fold = re.search(r'<p class="fold-actions">.*?</p>', html, re.DOTALL)
        self.assertIsNotNone(fold)
        self.assertNotIn('href="/dashboard"', fold.group(0))
        script = (WEB_DIR / "usage.js").read_text(encoding="utf-8")
        link_at = script.index('href="/dashboard"')
        # It must sit inside a collapsed <details>, whichever one: the nearest
        # preceding <details> must not have been closed before the link.
        opened_at = script.rfind("<details", 0, link_at)
        self.assertGreater(opened_at, -1, "the Dashboard link is not inside any details block")
        self.assertNotIn("</details>", script[opened_at:link_at],
                         "the Dashboard link sits outside the collapsed block")

if __name__ == "__main__":
    unittest.main()
