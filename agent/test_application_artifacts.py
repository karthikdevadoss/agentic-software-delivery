"""Artifacts that go to an employer: names, formats, provenance, manifest.

Written for incident INC_2026-10-08 (DEVADOSS storage/incidents/). Every test here
was RED before the fix.

What happened: the tool that baked the Owner's candidate-facing CV and cover-letter
PDFs ran on one person's computer, from `/workspace/cv-out/`, and only its output
was committed. The one committed pipeline, `publish_applications_review.py`, emitted
the internal shortlist filename (`23_nebius-fde-physical-ai-infrastructure.pdf`) and
had no concept of a cover letter at all, and `applications.js` fell back to handing
the user a raw `.md` whenever a cover PDF was missing. Nothing recorded which file
was actually uploaded to a form.

The tests are deliberately broader than the one defect that was noticed. The
Owner's instruction was that a critical bug is tested against every similar
scenario, so each rule is checked on the whole set, on the boundary, and on the
case that would silently pass: a pack with no entry, a key that is too long, a
name that is almost right, an attachment that is a near-miss of the manifest.

No network, no live service. Everything is read off the repository.
"""

from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent
WEB_DIR = AGENT_DIR / "web"
PDF_DIR = WEB_DIR / "applications_pdf"
APPLICATIONS_JSON = WEB_DIR / "applications.json"
APPLICATIONS_JS = WEB_DIR / "applications.js"

CV_PREFIX = "Karthikeyan_Devadoss_CV_"
COVER_PREFIX = "Karthikeyan_Devadoss_CoverLetter_"
#: The Owner's rule, DEVADOSS storage/personal/CONTACT.md: key at most 10 chars.
MAX_KEY = 10


def _js_code_only(text: str) -> str:
    """JavaScript with comments stripped.

    The rules below are about what the page DOES, not about what a comment may
    mention. Explaining why the markdown fallback was removed is part of the fix,
    and a test that forbade naming it would push the history out of the file.
    """
    out, i, n = [], 0, len(text)
    while i < n:
        if text.startswith("//", i):
            end = text.find("\n", i)
            i = n if end == -1 else end
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def _py_code_only(path: Path) -> str:
    """Python source with docstrings and comments removed, via the tokenizer."""
    import io as _io
    import tokenize

    pieces = []
    with open(path, "rb") as handle:
        tokens = list(tokenize.tokenize(handle.readline))
    prev_type = tokenize.INDENT
    for tok in tokens:
        if tok.type == tokenize.COMMENT:
            continue
        if tok.type == tokenize.STRING and prev_type in (
                tokenize.INDENT, tokenize.DEDENT, tokenize.NEWLINE, tokenize.NL,
                tokenize.ENCODING):
            # A bare string in statement position is a docstring.
            prev_type = tok.type
            continue
        pieces.append(tok.string)
        if tok.type not in (tokenize.NL, tokenize.NEWLINE):
            prev_type = tok.type
    return " ".join(pieces)


def _packs() -> list[dict]:
    data = json.loads(APPLICATIONS_JSON.read_text(encoding="utf-8"))
    return data.get("packs") or data.get("applications") or []


class TestTheFixtureIsReal(unittest.TestCase):
    """Guard the inputs first: an empty set would make everything below pass."""

    def test_the_baked_review_data_exists_and_is_not_empty(self):
        self.assertTrue(APPLICATIONS_JSON.is_file(), APPLICATIONS_JSON)
        self.assertGreaterEqual(len(_packs()), 1)

    def test_the_pdf_directory_exists_and_is_not_empty(self):
        self.assertTrue(PDF_DIR.is_dir(), PDF_DIR)
        self.assertTrue(list(PDF_DIR.glob("*.pdf")))


class TestEveryReviewEntryHasBothPdfs(unittest.TestCase):
    """Rule 1. Both documents, both PDF, both correctly named, both present."""

    def test_every_pack_names_a_cv_and_a_cover_pdf(self):
        missing = [p.get("slug") for p in _packs()
                   if not p.get("cv_pdf") or not p.get("cover_pdf")]
        self.assertEqual([], missing,
                         "packs with no cv_pdf and/or no cover_pdf: " + str(missing))

    def test_both_filenames_end_in_pdf(self):
        for p in _packs():
            with self.subTest(slug=p.get("slug")):
                self.assertTrue(str(p.get("cv_pdf", "")).endswith(".pdf"))
                self.assertTrue(str(p.get("cover_pdf", "")).endswith(".pdf"))

    def test_both_filenames_use_the_owners_naming_rule(self):
        for p in _packs():
            with self.subTest(slug=p.get("slug")):
                self.assertTrue(str(p.get("cv_pdf", "")).startswith(CV_PREFIX),
                                p.get("cv_pdf"))
                self.assertTrue(str(p.get("cover_pdf", "")).startswith(COVER_PREFIX),
                                p.get("cover_pdf"))

    def test_no_filename_leaks_the_internal_shortlist_rank(self):
        """`23_nebius-...pdf` tells a recruiter their position in a private queue,
        and the rank is unstable -- it changed on 2026-10-07 when the posting-date
        ordering moved commercetools from 6th to 9th."""
        rank_prefixed = re.compile(r"^\d{2}_")
        for p in _packs():
            with self.subTest(slug=p.get("slug")):
                self.assertIsNone(rank_prefixed.match(str(p.get("cv_pdf", ""))),
                                  p.get("cv_pdf"))
                self.assertIsNone(rank_prefixed.match(str(p.get("cover_pdf", ""))),
                                  p.get("cover_pdf"))

    def test_both_files_actually_exist_on_disk(self):
        """A Review entry naming a file nobody can download is worse than no
        entry: it reads as ready to send."""
        for p in _packs():
            for field in ("cv_pdf", "cover_pdf"):
                name = str(p.get(field, ""))
                with self.subTest(slug=p.get("slug"), field=field):
                    self.assertTrue((PDF_DIR / name).is_file(),
                                    "named but absent: " + name)

    def test_the_key_is_within_the_length_the_rule_allows(self):
        for p in _packs():
            name = str(p.get("cv_pdf", ""))
            with self.subTest(slug=p.get("slug")):
                key = name[len(CV_PREFIX):-len(".pdf")] if name.startswith(CV_PREFIX) else ""
                self.assertTrue(key, name)
                self.assertLessEqual(len(key), MAX_KEY, key)

    def test_the_cv_and_cover_refer_to_the_same_pack(self):
        """A mismatched pair would send one employer another employer's letter."""
        for p in _packs():
            cv, cover = str(p.get("cv_pdf", "")), str(p.get("cover_pdf", ""))
            with self.subTest(slug=p.get("slug")):
                self.assertEqual(cv[len(CV_PREFIX):], cover[len(COVER_PREFIX):],
                                 "CV and cover letter keys differ: " + cv + " / " + cover)

    def test_no_two_packs_share_a_cv_file(self):
        names = [str(p.get("cv_pdf", "")) for p in _packs()]
        self.assertEqual(len(names), len(set(names)), "duplicate CV filenames: " + str(names))


class TestNoMarkdownIsReachable(unittest.TestCase):
    """Rule 2. A `.md` is not a document an ATS renders, and the page used to
    hand one over whenever a cover PDF was missing."""

    def test_the_review_page_never_offers_a_markdown_download(self):
        js = _js_code_only(APPLICATIONS_JS.read_text(encoding="utf-8"))
        self.assertNotIn("-cover-letter.md", js,
                         "applications.js still builds a .md filename for download")

    def test_the_review_page_has_no_text_download_helper_left_in_use(self):
        """`downloadText` existed only to serve the markdown fallback."""
        js = _js_code_only(APPLICATIONS_JS.read_text(encoding="utf-8"))
        called = re.findall(r"(?<!function )\bdownloadText\s*\(", js)
        self.assertEqual([], called, "downloadText is still called " + str(len(called)) + " time(s)")

    def test_a_pack_without_a_cover_pdf_is_marked_do_not_submit(self):
        """The replacement for the fallback must warn, not fail silently."""
        js = _js_code_only(APPLICATIONS_JS.read_text(encoding="utf-8"))
        self.assertIn("do not submit", js.lower())

    def test_no_pack_record_names_a_markdown_file(self):
        for p in _packs():
            for field in ("cv_pdf", "cover_pdf"):
                with self.subTest(slug=p.get("slug"), field=field):
                    self.assertFalse(str(p.get(field, "")).endswith(".md"))

    def test_the_pdf_route_serves_only_pdf(self):
        """Server side, as well as client side: the route rejects any name that
        is not a .pdf, so a markdown file cannot be fetched directly."""
        server = (AGENT_DIR / "web_server.py").read_text(encoding="utf-8")
        self.assertIn('if not safe.endswith(".pdf"):', server)


class TestTheGeneratorIsInTheRepository(unittest.TestCase):
    """Rule 3, and the root cause. The tool that makes an artifact an employer
    sees must be committed, or nobody but its author can reproduce or review it.
    """

    GENERATOR = AGENT_DIR / "build_application_pdfs.py"

    def test_the_generator_is_committed(self):
        self.assertTrue(self.GENERATOR.is_file(),
                        "no committed generator at " + str(self.GENERATOR))

    def test_the_generator_uses_no_absolute_workspace_paths(self):
        """The original ran from /workspace/cv-out on one person's computer.
        A repo-relative generator is the whole point of committing it."""
        code = _py_code_only(self.GENERATOR)
        for bad in ("/workspace/", "C:\\Users\\", "/home/"):
            with self.subTest(path=bad):
                self.assertNotIn(bad, code)

    def test_no_shipped_application_module_hardcodes_an_absolute_path(self):
        """The same rule across every module that touches a submit artifact,
        not only the generator -- the incident came from one tool, but the rule
        is about the class."""
        for name in ("build_application_pdfs.py", "pack_pdf_names.py",
                     "submit_manifest.py", "publish_applications_review.py"):
            code = _py_code_only(AGENT_DIR / name)
            for bad in ("/workspace/", "C:\\Users\\", "/home/"):
                with self.subTest(module=name, path=bad):
                    self.assertNotIn(bad, code)

    #: The live page and the committed generator disagree about exactly two
    #: packs, and the disagreement is deliberate rather than a fault.
    #:
    #: `applications.json` was baked on 2026-10-06. On 2026-10-07 the Owner
    #: authorised swapping Cursor's Solutions Architect out for LangChain --
    #: APPLY_LOG_2026-10-07.md records the Cursor ATS as a 404, and the generator
    #: carries the newer list. The page has simply not been rebuilt since.
    #:
    #: Pinned in BOTH directions. A third entry means a new, unrecorded drift.
    #: Rebuilding the page is what clears it, and doing so is a visible change to
    #: what the Owner sees, so it waits for his yes rather than happening as a
    #: side effect of a test.
    KNOWN_PAGE_DRIFT = {
        "on_page_not_in_generator": {"cursor-solutions-architect-central-europe"},
        "in_generator_not_on_page": {"langchain-deployed-architect-amsterdam"},
    }

    def test_the_page_and_the_generator_differ_only_where_recorded(self):
        import build_application_pdfs as gen

        buildable = {pack["role_slug"] for pack in gen.PACKS}
        on_page = {p.get("slug") for p in _packs()}
        self.assertEqual(self.KNOWN_PAGE_DRIFT["on_page_not_in_generator"],
                         on_page - buildable)
        self.assertEqual(self.KNOWN_PAGE_DRIFT["in_generator_not_on_page"],
                         buildable - on_page)

    def test_every_other_pack_on_the_page_is_buildable(self):
        """The drift above aside, nothing the page offers is unreproducible."""
        import build_application_pdfs as gen

        buildable = {pack["role_slug"] for pack in gen.PACKS}
        on_page = {p.get("slug") for p in _packs()}
        unexplained = (on_page - buildable) - self.KNOWN_PAGE_DRIFT["on_page_not_in_generator"]
        self.assertEqual(set(), unexplained,
                         "on the Review page, not buildable, not recorded: " + str(unexplained))

    def test_the_generator_reports_no_missing_inputs(self):
        """`--check` is the contract: every input it needs is in this repo.

        This is the test the incident turns on. It was impossible to satisfy
        until the 2026-10-08 handover committed the generator, and it stayed red
        afterwards until cv_v1.html -- dropped by a .gitignore "build/" rule --
        was force-added to DEVADOSS main.
        """
        import build_application_pdfs as gen

        self.assertEqual([], gen.missing_inputs())

    def test_the_generator_needs_no_sibling_checkout(self):
        """Its pack inputs are vendored here, not read from the DEVADOSS repo."""
        import build_application_pdfs as gen

        for root in (gen.GOV50, gen.GOV10, gen.COVERS, gen.TEMPLATE):
            with self.subTest(path=str(root)):
                self.assertTrue(str(root).startswith(str(AGENT_DIR)), str(root))

    def test_the_generator_shells_out_to_no_uncommitted_helper_binary(self):
        """It used to call poppler's pdfinfo and pdftotext to verify its own
        output -- a second pair of tools nobody committed, absent on Windows.
        Chrome is the one external binary left, and it is passed in explicitly."""
        code = _py_code_only(self.GENERATOR)
        for binary in ("pdfinfo", "pdftotext", "wkhtmltopdf", "pandoc"):
            with self.subTest(binary=binary):
                self.assertNotIn(binary, code)


class TestTheSubmitManifest(unittest.TestCase):
    """Rule 4. What was uploaded is recorded, and an attachment that is not the
    recorded file is refused rather than sent."""

    def test_the_manifest_module_is_committed(self):
        self.assertTrue((AGENT_DIR / "submit_manifest.py").is_file())

    def test_a_manifest_entry_records_both_files_with_sha256(self):
        import submit_manifest as sm

        entry = sm.build_entry(
            slug="tavily-forward-deployed-engineer-enterprise",
            cv_path=PDF_DIR / (CV_PREFIX + "tavily.pdf"),
            cover_path=PDF_DIR / (COVER_PREFIX + "tavily.pdf"),
            submitted_by="test", submitted_at_berlin="8 October 2026, 02:00 Berlin",
            url="https://example.invalid/jobs/1")
        self.assertEqual(entry["cv"]["name"], CV_PREFIX + "tavily.pdf")
        self.assertEqual(entry["cover"]["name"], COVER_PREFIX + "tavily.pdf")
        for half in ("cv", "cover"):
            with self.subTest(half=half):
                self.assertRegex(entry[half]["sha256"], r"^[0-9a-f]{64}$")

    def test_the_recorded_sha256_is_the_real_digest(self):
        import submit_manifest as sm

        path = PDF_DIR / (CV_PREFIX + "tavily.pdf")
        entry = sm.build_entry(
            slug="x", cv_path=path, cover_path=path,
            submitted_by="test", submitted_at_berlin="t", url="u")
        expected = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(expected, entry["cv"]["sha256"])

    def test_an_attachment_matching_the_manifest_is_allowed(self):
        import submit_manifest as sm

        path = PDF_DIR / (CV_PREFIX + "tavily.pdf")
        entry = sm.build_entry(slug="x", cv_path=path, cover_path=path,
                               submitted_by="t", submitted_at_berlin="t", url="u")
        self.assertTrue(sm.attachment_allowed(entry, path))

    def test_an_attachment_that_is_not_the_manifest_file_is_refused(self):
        """The near-miss case: same pack, right-looking name, different bytes."""
        import submit_manifest as sm

        path = PDF_DIR / (CV_PREFIX + "tavily.pdf")
        other = PDF_DIR / (CV_PREFIX + "oyster.pdf")
        entry = sm.build_entry(slug="x", cv_path=path, cover_path=path,
                               submitted_by="t", submitted_at_berlin="t", url="u")
        self.assertFalse(sm.attachment_allowed(entry, other))

    def test_a_markdown_attachment_is_refused_outright(self):
        import submit_manifest as sm

        path = PDF_DIR / (CV_PREFIX + "tavily.pdf")
        entry = sm.build_entry(slug="x", cv_path=path, cover_path=path,
                               submitted_by="t", submitted_at_berlin="t", url="u")
        with self.assertRaises(sm.AttachmentRefused):
            sm.assert_attachment_allowed(entry, AGENT_DIR / "test_application_artifacts.py")

    def test_the_manifest_records_the_unknowns_rather_than_omitting_them(self):
        """The incident was partly that absent facts looked like absent fields.
        A manifest entry states "not recorded" explicitly."""
        import submit_manifest as sm

        path = PDF_DIR / (CV_PREFIX + "tavily.pdf")
        entry = sm.build_entry(slug="x", cv_path=path, cover_path=path,
                               submitted_by="t", submitted_at_berlin="t", url="u")
        for field in ("form_fields", "salary_stated", "screenshot", "tokens_used"):
            with self.subTest(field=field):
                self.assertEqual("not recorded", entry["unknowns"][field])


class TestThePublisherItselfIsCompliant(unittest.TestCase):
    """The latent bug, guarded at its source.

    The live applications.json happens to be correct because a person baked it by
    hand. Running the committed publisher would have overwritten it with
    rank-prefixed names and no cover letter, and every test above would have gone
    red only AFTER that damage was done. These call the publisher's own naming
    path directly, so the publisher cannot regress the page in the first place.
    """

    def test_the_publisher_emits_a_compliant_pair_for_every_mapped_pack(self):
        import publish_applications_review as pub
        from pack_pdf_names import PACK_KEYS

        for slug in sorted(PACK_KEYS):
            with self.subTest(slug=slug):
                try:
                    fields = pub._artifact_fields(slug)
                except Exception as exc:                       # noqa: BLE001
                    # A pack with no baked pair must RAISE, not emit a bad name.
                    self.assertIn("missing baked PDFs", str(exc), str(exc))
                    continue
                self.assertTrue(fields["cv_pdf"].startswith(CV_PREFIX))
                self.assertTrue(fields["cover_pdf"].startswith(COVER_PREFIX))
                self.assertIn(fields["cv_pdf"], fields["pdfs"])
                self.assertIn(fields["cover_pdf"], fields["pdfs"])

    def test_the_publisher_refuses_an_unmapped_pack_rather_than_inventing_a_name(self):
        import publish_applications_review as pub
        from pack_pdf_names import PackArtifactError

        with self.assertRaises(PackArtifactError):
            pub._artifact_fields("some-pack-nobody-mapped")

    def test_the_publisher_no_longer_builds_a_rank_prefixed_filename(self):
        code = _py_code_only(AGENT_DIR / "publish_applications_review.py")
        self.assertNotIn('{i:02d}_', code)
        self.assertNotIn("%02d_", code)


if __name__ == "__main__":
    unittest.main()
