"""
Tests for Standing Interview v0.

WHAT THESE PROTECT
This surface answers as Karthik, from private material, to someone deciding
whether to hire him. The failure modes that matter are not "it crashed" --
they are "it answered from the model's own knowledge", "it invented an
employer fact", and "it told the interviewer which document it read from".
Each of those is a guard here, and the critical ones are additionally proved
capable of FAILING by seeding the exact defect.

Deliberately hermetic: no model call, no network, no real corpus required. The
model is injected via `create_fn`, and the corpus is a small fixture, so this
runs in the blocking CI set.
"""

import json
import pathlib
import shutil
import tempfile
import unittest
from unittest import mock

import standing_interview as si


def _vec(seed: float, n: int = 8):
    return [seed + i * 0.01 for i in range(n)]


def make_corpus(chunks=None) -> si.Corpus:
    chunks = chunks if chunks is not None else [
        {"book_id": "BOOK-05", "section": "Security", "employer": "NRG",
         "knowledge_type": "system_knowledge", "work_type": "professional",
         "status": "current", "vector": _vec(1.0),
         "text": "The platform validated RS256 JWTs at the edge. Karthik "
                 "implemented the Spring Security filter that verified them."},
        {"book_id": "BOOK-08", "section": "Tooling", "employer": "none",
         "knowledge_type": "personal_hands_on", "work_type": "personal_platform",
         "status": "current", "vector": _vec(2.0),
         "text": "Built an approval-gated write boundary with hash-bound edits."},
    ]
    return si.Corpus({"model_id": "test-model", "chunks": chunks,
                      "source_book_hashes": {"BOOK-05": "abc"}})


class FakeBlock:
    def __init__(self, text):
        self.type, self.text = "text", text


class FakeResponse:
    def __init__(self, text):
        self.content = [FakeBlock(text)]
        self.usage = None


def fake_model(text):
    def create(**kwargs):
        create.last_kwargs = kwargs
        return FakeResponse(text)
    return create


class NoCorpusTestCase(unittest.TestCase):
    """The single most dangerous failure: answering with no corpus loaded.
    That is how a system like this starts inventing employment history."""

    def test_missing_corpus_file_yields_none_not_an_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(si.load_corpus(pathlib.Path(tmp) / "nope.json"))

    def test_corrupt_corpus_is_treated_as_absent_not_as_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "corpus.json"
            p.write_text("{not json", encoding="utf-8")
            self.assertIsNone(si.load_corpus(p))

    def test_empty_corpus_is_treated_as_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "corpus.json"
            p.write_text(json.dumps({"model_id": "m", "chunks": []}), encoding="utf-8")
            self.assertIsNone(si.load_corpus(p))

    def test_no_corpus_refuses_and_never_calls_the_model(self):
        called = []

        def must_not_run(**kwargs):
            called.append(kwargs)
            raise AssertionError("the model was called with no corpus loaded")

        with mock.patch.object(si, "load_corpus", return_value=None):
            out = si.answer("How did you use Spring Security?", create_fn=must_not_run)
        self.assertEqual("no_corpus", out["outcome"])
        self.assertFalse(out["grounded"])
        self.assertEqual(si.NO_CORPUS, out["answer"])
        self.assertEqual([], called)

    def test_status_reports_unloaded_without_leaking_anything(self):
        with mock.patch.object(si, "load_corpus", return_value=None):
            s = si.corpus_status()
        self.assertFalse(s["loaded"])
        self.assertEqual(0, s["chunks"])


class GroundingTestCase(unittest.TestCase):
    def setUp(self):
        self.corpus = make_corpus()

    def test_below_threshold_refuses_and_does_not_call_the_model(self):
        called = []

        def must_not_run(**kwargs):
            called.append(kwargs)
            raise AssertionError("model called for an ungrounded question")

        with mock.patch.object(si, "retrieve", return_value=[]):
            out = si.answer("What is the capital of France?", self.corpus,
                            create_fn=must_not_run)
        self.assertEqual("ungrounded", out["outcome"])
        self.assertEqual(si.REFUSAL, out["answer"])
        self.assertEqual([], called)

    def test_a_weak_hit_below_threshold_still_refuses(self):
        weak = [dict(self.corpus.chunks[0], score=si.GROUNDING_THRESHOLD - 0.01)]
        with mock.patch.object(si, "retrieve", return_value=weak):
            out = si.answer("something only vaguely related", self.corpus,
                            create_fn=fake_model("should never be used"))
        self.assertEqual("ungrounded", out["outcome"])
        self.assertEqual(si.REFUSAL, out["answer"])

    def test_a_strong_hit_is_answered_from_the_excerpts(self):
        strong = [dict(self.corpus.chunks[0], score=0.81)]
        model = fake_model("I implemented the Spring Security filter that verified "
                           "the RS256 tokens. I didn't design the issuer.")
        with mock.patch.object(si, "retrieve", return_value=strong):
            out = si.answer("How did you use Spring Security?", self.corpus,
                            create_fn=model)
        self.assertEqual("answered", out["outcome"])
        self.assertTrue(out["grounded"])
        self.assertIn("Spring Security filter", out["answer"])

    def test_the_excerpts_are_actually_put_in_front_of_the_model(self):
        """Grounding is only real if the retrieved text reaches the prompt."""
        strong = [dict(self.corpus.chunks[0], score=0.81)]
        model = fake_model("ok")
        with mock.patch.object(si, "retrieve", return_value=strong):
            si.answer("How did you use Spring Security?", self.corpus, create_fn=model)
        sent = model.last_kwargs["messages"][0]["content"]
        self.assertIn("RS256", sent)
        self.assertIn("Spring Security filter", sent)

    def test_the_system_prompt_forbids_outside_knowledge_and_sources(self):
        strong = [dict(self.corpus.chunks[0], score=0.81)]
        model = fake_model("ok")
        with mock.patch.object(si, "retrieve", return_value=strong):
            si.answer("q", self.corpus, create_fn=model)
        sysmsg = model.last_kwargs["system"]
        self.assertIn("ONLY the supplied excerpts", sysmsg)
        self.assertIn("Never mention where the information came from", sysmsg)
        self.assertIn("first person", sysmsg.lower())

    def test_empty_question_refuses(self):
        out = si.answer("   ", self.corpus, create_fn=fake_model("x"))
        self.assertEqual("empty", out["outcome"])


class ModelDeclineTestCase(unittest.TestCase):
    """The gate added on 2026-09-27 after the real end-to-end acceptance check.

    Retrieval cleared the threshold for "what is Karthik's home address and
    salary?" (0.6816 -- the words match career text even though the answer is
    not in it). The model correctly declined, but the SYSTEM recorded
    outcome=answered, so the question was never logged for review. A polite
    non-answer that never reaches the review queue is exactly the coverage
    signal v0 exists to collect, thrown away."""

    def setUp(self):
        self.corpus = make_corpus()
        self.strong = [dict(self.corpus.chunks[0], score=0.82)]

    def test_a_declining_answer_becomes_a_refusal_and_is_flagged_ungrounded(self):
        model = fake_model("I don't have that detail - it's not something I worked on.")
        with mock.patch.object(si, "retrieve", return_value=self.strong):
            out = si.answer("what is his salary?", self.corpus, create_fn=model)
        self.assertEqual("ungrounded_model_declined", out["outcome"])
        self.assertFalse(out["grounded"])
        self.assertEqual(si.REFUSAL, out["answer"])

    def test_the_declining_reply_is_kept_for_review_not_discarded(self):
        model = fake_model("I don't have that detail.")
        with mock.patch.object(si, "retrieve", return_value=self.strong):
            out = si.answer("q", self.corpus, create_fn=model)
        self.assertIn("model_reply", out)

    def test_an_honest_caveat_LATE_in_a_good_answer_is_not_a_refusal(self):
        """The failure mode of this gate is over-firing. A grounded answer that
        ends with an honest limit must still count as answered -- that phrasing
        is exactly the tone the system prompt asks for."""
        model = fake_model(
            "I implemented the Spring Security filter that validated the RS256 "
            "tokens at the edge, and wired it into the aggregator services. "
            "I don't have the exact key-rotation detail though.")
        with mock.patch.object(si, "retrieve", return_value=self.strong):
            out = si.answer("q", self.corpus, create_fn=model)
        self.assertEqual("answered", out["outcome"])
        self.assertTrue(out["grounded"])

    def test_every_decline_marker_is_detected_at_the_opening(self):
        for marker in si.DECLINE_MARKERS:
            self.assertTrue(si._model_declined(marker.capitalize() + " that."), marker)

    def test_the_threshold_is_above_the_measured_nonsense_score(self):
        """0.4491 was the real cosine for 'what is the capital of France?'
        against the 361-chunk corpus. The threshold must stay above it."""
        self.assertGreater(si.GROUNDING_THRESHOLD, 0.4491)
        self.assertLess(si.GROUNDING_THRESHOLD, 0.6915)   # and below a real question


class LeakGuardTestCase(unittest.TestCase):
    """A prompt instruction is advisory. This is the control."""

    LEAKY = [
        "According to the document, I used Spring Security.",
        "As Book 6 records, I implemented the filter.",
        "See BOOK-05 for the details.",
        "My notes say I wrote the filter.",
        "It's in books/derived/BOOK-05.md.",
        "Ganesha has the full record.",
        "The corpus says I used RS256.",
    ]
    CLEAN = [
        "I implemented the Spring Security filter that validated RS256 tokens.",
        "I didn't design the issuer; I implemented the filter against it.",
        "I don't have that detail.",
        # VERBATIM from a real generated answer, 2026-09-27. This exact sentence
        # was the whole reason the Owner saw "explain your experience with kafka"
        # refuse: the leak scanner matched "the source" inside ordinary backend
        # English and threw away the best answer the system produces.
        "That let the receiving side stay current without the source service "
        "having to synchronously coordinate with every consumer.",
        "The source system was slower and batch-updated.",
        "We treated that service as the source of truth.",
        "I read the source code for the filter before changing it.",
    ]

    def test_every_leaky_phrasing_is_detected(self):
        for text in self.LEAKY:
            self.assertTrue(si.leaks(text), f"leak not detected: {text!r}")

    def test_clean_answers_are_not_falsely_flagged(self):
        for text in self.CLEAN:
            self.assertEqual([], si.leaks(text), f"false positive on: {text!r}")

    def test_a_leaking_answer_is_blocked_and_replaced_with_the_refusal(self):
        strong = [dict(make_corpus().chunks[0], score=0.81)]
        model = fake_model("According to the document, I used Spring Security.")
        with mock.patch.object(si, "retrieve", return_value=strong):
            out = si.answer("q", make_corpus(), create_fn=model)
        self.assertEqual("leak_blocked", out["outcome"])
        self.assertEqual(si.REFUSAL, out["answer"])
        self.assertTrue(out["leaks"])

    def test_no_pantheon_name_can_reach_the_interviewer(self):
        for name in ("Krishna", "Vishnu", "Shiva", "Rudra", "Yamaraj",
                     "Brahma", "Ganesha", "Shakti"):
            self.assertTrue(si.leaks(f"I asked {name} about it."), name)


class RoutingTestCase(unittest.TestCase):
    def test_backend_question_routes_to_the_employer_books(self):
        self.assertEqual("career", si.route("How did you use Spring Security at NRG?"))
        self.assertEqual({f"BOOK-0{i}" for i in range(1, 7)},
                         si._allowed_books("career"))

    def test_ai_question_routes_to_the_platform_books(self):
        self.assertEqual("ai", si.route("How does your RAG retrieval work?"))
        self.assertEqual({"BOOK-07", "BOOK-08"}, si._allowed_books("ai"))

    def test_mixed_question_searches_everything_rather_than_guessing(self):
        self.assertEqual("both", si.route("How do you use an LLM agent to change Java code?"))
        self.assertIsNone(si._allowed_books("both"))

    def test_an_unrecognised_question_searches_everything_not_nothing(self):
        """Routing must never be the thing that causes a false refusal."""
        self.assertEqual("both", si.route("what did you find hardest"))
        self.assertIsNone(si._allowed_books(si.route("what did you find hardest")))

    def test_routing_actually_filters_the_retrieved_set(self):
        corpus = make_corpus()
        hits = si.retrieve("Spring Security at NRG", corpus,
                           embed_query=lambda q: _vec(1.0))
        self.assertTrue(hits)
        self.assertTrue(all(h["book_id"].startswith("BOOK-0") and
                            h["book_id"] <= "BOOK-06" for h in hits),
                        "a career question reached the personal-platform books")


class ModelMismatchTestCase(unittest.TestCase):
    def test_a_different_embedding_model_yields_no_hits_rather_than_nonsense(self):
        corpus = make_corpus()
        fake_embeddings = mock.Mock()
        fake_embeddings.model_id.return_value = "some-other-model"
        with mock.patch.dict("sys.modules", {"embeddings": fake_embeddings}):
            hits = si.retrieve("anything", corpus)
        self.assertEqual([], hits)


class DeploymentWiringTestCase(unittest.TestCase):
    """The corpus reaches the container by being present in the working
    directory at `railway up` time while absent from git. Both halves of that
    have to stay true, and both are one careless edit away from breaking."""

    REPO = pathlib.Path(__file__).resolve().parent.parent

    def test_the_corpus_path_is_not_dockerignored(self):
        di = self.REPO / ".dockerignore"
        if not di.exists():
            self.skipTest("no .dockerignore")
        for line in di.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                self.assertNotIn("si_corpus", line,
                                 "agent/.si_corpus/ is dockerignored -- the image "
                                 "would build with no corpus and never answer")

    def test_the_corpus_is_NOT_gitignored_or_the_upload_silently_drops_it(self):
        """The inverse of what this asserted until 2026-09-27, and the reason
        two production deploys shipped an empty corpus.

        `railway up` respects .gitignore. While agent/.si_corpus/ was ignored,
        the corpus was silently excluded from the upload and production reported
        {"loaded": false}. A .railwayignore did not override it. The corpus must
        therefore be UNTRACKED-BUT-NOT-IGNORED. If anyone re-adds it to
        .gitignore to 'protect the public repo', Standing Interview stops
        working in production with no error -- this test is what says so."""
        import subprocess
        r = subprocess.run(["git", "check-ignore", "agent/.si_corpus/corpus.json"],
                           cwd=str(self.REPO), capture_output=True, text=True)
        self.assertNotEqual(0, r.returncode,
                            "agent/.si_corpus/ is gitignored again -- `railway up` will drop "
                            "the corpus and Standing Interview will report loaded:false in "
                            "production. Keep it untracked instead; git add -A is already "
                            "hard-denied in .claude/settings.json.")

    def test_no_railwayignore_exists_to_confuse_the_upload_rules(self):
        """One rule, not two. A .railwayignore is used INSTEAD of .gitignore by
        Railway, so having both makes upload behaviour depend on which file a
        reader happens to check -- and it did not actually override .gitignore
        when tried on 2026-09-27."""
        self.assertFalse((self.REPO / ".railwayignore").exists(),
                         ".railwayignore is back; it did not work and it splits the rules")

    def test_no_book_text_is_committed_anywhere_in_this_repo(self):
        import subprocess
        r = subprocess.run(["git", "ls-files", "agent/.si_corpus"],
                           cwd=str(self.REPO), capture_output=True, text=True)
        self.assertEqual("", r.stdout.strip(),
                         "corpus files are tracked in the public repository")


class LeakFalsePositiveTestCase(unittest.TestCase):
    """Sprint 11. The leak scanner is a REFUSAL trigger, so a false positive is
    not cosmetic -- it silently converts a correct, grounded, well-attributed
    answer into "I don't have a grounded answer for that one", and the operator
    then sees an unexplained refusal in the review queue with a HIGH retrieval
    score beside it. That is exactly what happened to the generic Kafka
    question (best_score 0.7332, outcome leak_blocked).

    Both halves are pinned here: the engineering senses of "source" must pass,
    and the provenance senses must still be blocked. Narrowing a control
    without a test on the part that was narrowed away is how a control quietly
    stops working."""

    ENGINEERING_SENSES_MUST_PASS = [
        "the source service published the event",
        "the source system is batch-updated",
        "that service was our source of truth",
        "I changed the source code, not the config",
        "we read from the source table nightly",
        "my source control history shows the commits",
    ]

    PROVENANCE_SENSES_MUST_STILL_BLOCK = [
        "The sources say I used RS256.",
        "My source says the filter was mine.",
        "The source states that Kafka was absent.",
        "My sources mention a DLQ.",
        "The source material describes the JWT flow.",
        "My source document has the sequence diagram.",
        "According to my source, it was Apigee.",
    ]

    def test_ordinary_backend_english_about_a_source_system_is_not_a_leak(self):
        for text in self.ENGINEERING_SENSES_MUST_PASS:
            self.assertEqual([], si.leaks(text), f"false positive on: {text!r}")

    def test_provenance_uses_of_source_are_still_blocked(self):
        for text in self.PROVENANCE_SENSES_MUST_STILL_BLOCK:
            self.assertTrue(si.leaks(text), f"leak NOT detected: {text!r}")

    def test_the_other_provenance_words_were_not_touched_by_the_narrowing(self):
        for text in ("the document says so", "my notes cover it",
                     "the corpus has it", "the excerpt above", "my knowledge base"):
            self.assertTrue(si.leaks(text), text)


class EmployerCoverageTestCase(unittest.TestCase):
    """Sprint 11, Owner-reported: "explain your experience in using oauth or
    jwt" produced one mashed paragraph with no employer attached to any claim.
    The cause was RETRIEVAL, not wording -- 5 of the 6 real chunks came from a
    single employer's books, so the other employers' material was never in
    front of the model at all. A prompt cannot attribute what it was not given.

    The fixture scores the books so that pure cosine top-k would return ONLY
    the most recent employer, which is the real failure shape inverted."""

    BOOK_SCORES = {"BOOK-05": 0.90, "BOOK-06": 0.89,      # NRG
                   "BOOK-03": 0.80, "BOOK-04": 0.79,      # BCBSA
                   "BOOK-01": 0.70, "BOOK-02": 0.69}      # Marsh

    def setUp(self):
        self.scores = dict(self.BOOK_SCORES)
        self._real_cosine = si._cosine
        # A chunk's vector IS its score here, and cosine just reads it. Honest
        # about what it is: this test is about slot allocation, not vector maths.
        si._cosine = lambda qv, cv: cv[0]

    def tearDown(self):
        si._cosine = self._real_cosine

    def _corpus(self):
        chunks = [{"book_id": b, "section": f"s{i}", "employer": "x",
                   "knowledge_type": "system_knowledge", "work_type": "professional",
                   "status": "current", "vector": [self.scores[b]],
                   "text": f"{b} chunk {i} kafka oauth jwt"}
                  for b in self.scores for i in range(3)]
        return si.Corpus({"model_id": "test-model", "chunks": chunks,
                          "source_book_hashes": {}})

    def _retrieve(self, question):
        return si.retrieve(question, self._corpus(), embed_query=lambda q: [1.0])

    def test_a_generic_question_retrieves_from_every_employer_not_just_the_top(self):
        hits = self._retrieve("explain your experience in using oauth or jwt")
        employers = [h["employer"] for h in hits]
        for expected in ("NRG Energy", "BCBSA", "Marsh"):
            self.assertIn(expected, employers,
                          f"{expected} absent -> the answer cannot attribute it")

    def test_the_most_recent_employer_comes_first(self):
        hits = self._retrieve("explain your experience with kafka")
        self.assertEqual("NRG Energy", hits[0]["employer"])
        first_of = {}
        for n, h in enumerate(hits):
            first_of.setdefault(h["employer"], n)
        self.assertLess(first_of["NRG Energy"], first_of["BCBSA"])
        self.assertLess(first_of["BCBSA"], first_of["Marsh"])

    def test_a_question_that_names_an_employer_is_NOT_balanced(self):
        q = "How did you use Kafka at BCBSA?"
        self.assertTrue(si.names_employer(q))
        self.assertFalse(si.names_employer("explain your experience with kafka"))
        hits = self._retrieve(q)
        # pure top-k over this fixture -> the highest-scoring books only
        self.assertEqual({"NRG Energy"}, {h["employer"] for h in hits})

    def test_an_employer_below_the_grounding_threshold_is_left_out(self):
        self.scores["BOOK-01"] = self.scores["BOOK-02"] = 0.20
        hits = self._retrieve("explain your experience with kafka")
        employers = [h["employer"] for h in hits]
        # Both halves, deliberately. Asserting only the absence would pass
        # vacuously against code that labels nothing at all -- which is exactly
        # how it behaved before this sprint, and exactly the vacuous-test shape
        # Sprint 9's retro found and swore off.
        self.assertIn("BCBSA", employers, "balancing stopped working entirely")
        self.assertNotIn("Marsh", employers,
                         "an irrelevant employer must not be dragged in")

    def test_every_hit_carries_an_employer_label_for_the_prompt(self):
        hits = self._retrieve("explain your experience with kafka")
        prompt = si.build_user_prompt("q", hits)
        for expected in ("NRG Energy", "BCBSA", "Marsh"):
            self.assertIn(expected, prompt,
                          "the model cannot attribute an unlabelled excerpt")

    def test_the_grounding_gate_reads_the_best_score_not_the_first_hit(self):
        """Balanced retrieval returns hits in EMPLOYER order, so hits[0] is no
        longer the maximum. Reading the gate off position 0 would start
        refusing answerable questions -- this fails if that is reintroduced."""
        chunk = self._corpus().chunks[0]
        out_of_order = [dict(chunk, score=0.20, employer="NRG Energy"),
                        dict(chunk, score=0.90, employer="BCBSA")]
        with mock.patch.object(si, "retrieve", return_value=out_of_order):
            out = si.answer("q", self._corpus(),
                            create_fn=fake_model("I wrote the producer code."))
        self.assertEqual("answered", out["outcome"])
        self.assertAlmostEqual(0.90, out["best_score"])

    def test_the_book_to_employer_map_covers_all_six_career_books(self):
        mapped = set()
        for _name, books in si.EMPLOYER_BOOKS:
            mapped |= set(books)
        self.assertEqual({f"BOOK-0{i}" for i in range(1, 7)}, mapped)
        self.assertIsNone(si.employer_for_book("BOOK-07"))
        self.assertIsNone(si.employer_for_book("BOOK-08"))

    def test_the_system_prompt_forbids_blending_two_employers(self):
        low = si.SYSTEM_PROMPT.lower()
        self.assertIn("one employer at a time", low)
        self.assertIn("never blend", low)
        self.assertIn("confirmed absence", low)


if __name__ == "__main__":
    unittest.main(verbosity=2)
