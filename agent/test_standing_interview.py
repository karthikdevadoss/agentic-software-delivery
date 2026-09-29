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
            # Sprint 13: "what is his salary?" is now refused BEFORE the model by
            # the private-topic gate, so this test -- which is about the DECLINE
            # gate -- asks something the books plausibly cover but the fake
            # model declines anyway. Same mechanism, different question.
            out = si.answer("what was the exact retry policy on that pipeline?",
                            self.corpus, create_fn=model)
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
        # Sprint 13 narrowed these nouns to provenance senses (a real false
        # positive: the deploy gate refused a correct answer about this
        # surface's own retrieval for saying "the knowledge base"). The bare
        # noun is therefore no longer a leak; the citing sense still is, and
        # "excerpt" is unconditional because it has no interview sense.
        for text in ("the document says so", "my notes cover it",
                     "the corpus has it", "the excerpt above", "my knowledge base says"):
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
        # Sprint 11 asserted pure top-k here, which on this fixture returned
        # ONLY NRG material for a question about BCBSA -- documenting the
        # behaviour, not endorsing it. Sprint 13 (Owner: "only where used"):
        # the named employer's material comes first, and it is still not
        # balanced across employers -- Marsh's lower-scoring books stay out.
        self.assertEqual("BCBSA", hits[0]["employer"])
        self.assertNotIn("Marsh", {h["employer"] for h in hits})

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


# The REAL text the Owner clicked Dissatisfied on, 2026-09-27 20:03, verbatim
# from the event ledger. Every new test in this file is anchored to it rather
# than to a paraphrase: this is the answer that has to become impossible.
OLD_KAFKA_GENERIC = (
    "At NRG, Kafka wasn't part of the system at all - it's a confirmed absence, "
    "zero hits across the full file census. The real async mechanism there was "
    "SQS plus a dead-letter queue and one scheduled cron job. At BCBSA, I "
    "directly worked on Kafka producer/consumer application code, propagating "
    "member, coverage and claims changes between backend services. I can speak "
    "to the general engineering concerns - at-least-once delivery meaning "
    "consumers have to handle duplicates, using member ID as a natural "
    "partition key for ordering, idempotency for replayed events, schema "
    "evolution, dead-letter handling. What I can't tell you is the exact retry, "
    "DLQ or offset-handling configuration on that project. I also can't say "
    "which cloud it ran on. I can't speak to what happened when a consumer "
    "failed specifically. At Marsh there's no genuine evidence of Kafka, JMS, "
    "RabbitMQ or ActiveMQ."
)

# The shape the Owner froze, written out so a future change that breaks it
# fails here rather than in production.
#
# SPRINT 15, and this is a deliberate specification change, not a test being
# loosened to go green. The previous frozen shape ended:
#
#     "... I don't have the exact retry, DLQ or offset-handling implementation
#      preserved, and broker administration wasn't mine. Elsewhere Kafka
#      wasn't part of the picture - at NRG the async work was SQS with a
#      dead-letter queue, and at Marsh we didn't use Kafka at all."
#
# Those two sentences ARE the Owner's 2026-09-29 complaint. The three live
# production Kafka answers he rejected say almost exactly that, and they were
# faithful to this fixture -- which is the point. The frozen shape encoded the
# older requirement that an answer state its boundary and footnote the
# employers that did not use the technology. The Owner's later instruction
# supersedes it: state the work, then stop.
#
# Same precedent as the FHIR clause two comments down -- later instruction
# wins, and the fixture moves rather than the gate.
NEW_KAFKA_GENERIC = (
    "My hands-on Kafka experience is from BCBSA. I worked on producer/consumer "
    "application code that propagated member, coverage and claims changes "
    "between backend services, keeping the downstream data current as changes "
    "landed upstream. That was real application-level coding on my end, on the "
    "services that produced and consumed those events."
)
# Sprint 13: the frozen shape used to say "keeping a FHIR-facing normalized data
# view current" -- the Owner's 2026-09-29 Q3 rule is that a Kafka answer does not
# drag FHIR in, so that clause is gone too (later instruction wins).
# Sprint 13: the frozen shape used to end "...didn't use Kafka or JMS at all."
# The Owner's 2026-09-29 rule is that JMS is never volunteered on a question
# that did not ask about it, so the fixture now says only what was asked.


class VoiceGateTestCase(unittest.TestCase):
    """Sprint 12. The Owner's complaint was not that the answer was wrong -- it
    was factually fine -- but that it read like a search report. Every
    assertion here is one clause of the frozen voice spec."""

    def test_the_exact_text_the_owner_rejected_is_now_rejected(self):
        bad = si.voice_violations(OLD_KAFKA_GENERIC)
        self.assertTrue(bad, "the Owner-rejected answer passes the voice gate")
        # Not just "something fired" -- the specific things he named.
        joined = " | ".join(bad).lower()
        for expected in ("census", "hits", "confirmed absence", "partition key",
                         "delivery guarantee", "schema evolution", "cron",
                         "evidence"):
            self.assertIn(expected, joined, f"did not catch: {expected}")

    def test_the_frozen_shape_passes(self):
        self.assertEqual([], si.voice_violations(NEW_KAFKA_GENERIC),
                         "the Owner's own specified shape is being rejected")

    def test_a_truncated_answer_is_rejected(self):
        self.assertIn("stops mid-sentence",
                      si.voice_violations("At BCBSA I wrote the producer code and then I"))
        self.assertNotIn("stops mid-sentence", si.voice_violations(NEW_KAFKA_GENERIC))

    def test_closing_punctuation_inside_a_quote_still_counts_as_finished(self):
        self.assertEqual([], si.voice_violations(
            "At BCBSA I wrote the producers. The team called it \"the feed.\""))

    def test_an_essay_about_what_he_cannot_say_is_rejected(self):
        essay = ("I can't tell you the topic names. I can't recall the retry "
                 "settings. I don't have the offsets. I cannot say which cloud.")
        bad = si.voice_violations(essay)
        self.assertTrue(any("cannot say" in b for b in bad), bad)
        # Sprint 15: still flagged for opening on a limitation, but reworded and
        # reclassified as SOFT -- it triggers a retry rather than refusing the
        # question outright, because where a caveat SITS is a style problem and
        # a refusal replaces a real answer with nothing. The check is unchanged;
        # only the message it reports is.
        self.assertTrue(
            any("opens the answer instead of the work" in b for b in bad), bad)
        self.assertTrue(
            any(b.startswith(si.SOFT_VIOLATION) for b in bad),
            f"the opening-caveat violation must be retryable, not a refusal: {bad}")

    def test_ONE_uncertainty_line_is_allowed_because_honesty_is_the_point(self):
        ok = ("At BCBSA I wrote the Kafka producer and consumer code for member "
              "and coverage changes. I don't have the exact retry or DLQ "
              "settings for that project. Broker administration wasn't mine.")
        self.assertEqual([], si.voice_violations(ok),
                         "a single honest limit must not be penalised")

    def test_search_talk_is_banned_but_real_search_work_is_not(self):
        self.assertTrue(si.voice_violations(
            "JMS showed up in searches but it wasn't real usage."))
        self.assertEqual([], si.voice_violations(
            "I built the customer search endpoint and we used Elasticsearch "
            "behind the product search feature on that site."))

    def test_the_audit_register_is_caught_in_the_shapes_it_actually_appeared_in(self):
        """Verbatim from the FIRST live answer the gate let through. Each of
        these passed every pattern that existed at the time, because those
        patterns looked for the word "evidence" and the model had moved on to
        other wording. A banned-phrase list is finished by reading real output,
        not by reasoning about it."""
        for real in ("At Marsh there was no genuine Kafka or JMS usage either.",
                     "A single SQS mention showed up in some filing material "
                     "but got rejected."):
            self.assertTrue(si.voice_violations(real), f"still passes: {real!r}")

    def test_absence_is_never_dressed_up_as_an_audit_finding(self):
        """Six real runs of "Tell me about Kafka at NRG" produced one answer
        saying "it's a clean absence across the codebase". Same register,
        different adjective -- the third time this sprint that widening one
        word simply moved the model to the next one."""
        for adj in ("confirmed", "comprehensive", "clean", "clear", "complete", "total"):
            self.assertTrue(si.voice_violations(f"It was a {adj} absence there."), adj)
        self.assertEqual([], si.voice_violations("We didn't use it there."))

    def test_closing_those_gaps_did_not_break_plain_speech(self):
        self.assertEqual([], si.voice_violations(
            "At Marsh we didn't use Kafka or JMS at all. The async work there "
            "was a different shape entirely."))

    def test_every_banned_phrase_has_a_human_readable_reason(self):
        for rx, why in si._VOICE_BANNED:
            self.assertTrue(why and why[0].islower(), why)
            self.assertNotIn("regex", why.lower())

    def test_the_voice_gate_is_separate_from_the_leak_gate(self):
        """They have opposite failure costs -- a leak must refuse immediately, a
        voice violation gets one retry first. Merging them is how the Sprint 11
        false positive stayed invisible."""
        self.assertEqual([], si.leaks(OLD_KAFKA_GENERIC),
                         "the old answer leaked nothing -- it was only badly voiced")
        self.assertTrue(si.voice_violations(OLD_KAFKA_GENERIC))


class VoiceRetryTestCase(unittest.TestCase):
    """The retry is the whole reason the gate can afford to be strict. Without
    it, one banned phrase in an otherwise perfect answer becomes a refusal --
    which is precisely the Sprint 11 defect this project already paid for."""

    def setUp(self):
        self.corpus = make_corpus()
        self.strong = [dict(self.corpus.chunks[0], score=0.81, employer="BCBSA")]

    def _two_replies(self, first, second):
        calls = []

        def create(**kwargs):
            calls.append(kwargs)
            return FakeResponse(first if len(calls) == 1 else second)
        create.calls = calls
        return create

    def test_a_voice_violation_is_retried_not_refused(self):
        model = self._two_replies(
            "At BCBSA we used member ID as the partition key for ordering.",
            NEW_KAFKA_GENERIC)
        with mock.patch.object(si, "retrieve", return_value=self.strong):
            out = si.answer("explain your experience with kafka",
                            self.corpus, create_fn=model)
        self.assertEqual("answered", out["outcome"])
        self.assertEqual(NEW_KAFKA_GENERIC, out["answer"])
        self.assertEqual(2, len(model.calls), "the retry did not happen")

    def test_the_retry_is_told_what_was_wrong_not_just_asked_again(self):
        model = self._two_replies(
            "At BCBSA we used member ID as the partition key for ordering.",
            NEW_KAFKA_GENERIC)
        with mock.patch.object(si, "retrieve", return_value=self.strong):
            si.answer("q", self.corpus, create_fn=model)
        retry_prompt = str(model.calls[1])
        self.assertIn("partition key", retry_prompt,
                      "the retry repeats the rules instead of naming the failure")

    def test_two_bad_attempts_refuse_and_are_logged_under_their_own_outcome(self):
        model = self._two_replies(
            "Zero hits across the full file census at NRG.",
            "Still a confirmed absence, zero hits across the census.")
        with mock.patch.object(si, "retrieve", return_value=self.strong):
            out = si.answer("q", self.corpus, create_fn=model)
        self.assertEqual("voice_rejected", out["outcome"])
        self.assertEqual(si.REFUSAL, out["answer"])
        self.assertTrue(out["voice_violations"])
        self.assertTrue(out["retry_violations"])

    def test_a_clean_first_attempt_costs_exactly_one_model_call(self):
        model = self._two_replies(NEW_KAFKA_GENERIC, "should never be used")
        with mock.patch.object(si, "retrieve", return_value=self.strong):
            out = si.answer("q", self.corpus, create_fn=model)
        self.assertEqual("answered", out["outcome"])
        self.assertEqual(1, len(model.calls),
                         "a good answer must not pay for a retry")

    def test_a_retry_that_leaks_is_refused_rather_than_shipped(self):
        """The retry output goes through the leak scan too. Without this the
        voice fix would have opened a hole in the confidentiality control."""
        model = self._two_replies(
            "Zero hits across the census.",
            "According to the document, I wrote the producer code at BCBSA.")
        with mock.patch.object(si, "retrieve", return_value=self.strong):
            out = si.answer("q", self.corpus, create_fn=model)
        self.assertEqual("voice_rejected", out["outcome"])
        self.assertEqual(si.REFUSAL, out["answer"])

    def test_the_answer_token_budget_fits_the_required_length(self):
        """400 tokens truncated real multi-employer answers mid-sentence. The
        spec asks for 6-10 finished spoken lines, so the budget is part of the
        contract, not a tuning detail."""
        self.assertGreaterEqual(si.MAX_ANSWER_TOKENS, 600)
        model = self._two_replies(NEW_KAFKA_GENERIC, "x")
        with mock.patch.object(si, "retrieve", return_value=self.strong):
            si.answer("q", self.corpus, create_fn=model)
        self.assertEqual(si.MAX_ANSWER_TOKENS, model.calls[0]["max_tokens"])


class VoiceSpecInPromptTestCase(unittest.TestCase):
    """The prompt is not the control -- voice_violations() is -- but the prompt
    is what makes the control pass on the first attempt instead of the second,
    and a trace proved the ordering could only be fixed there."""

    def test_the_prompt_says_to_lead_with_where_the_work_happened(self):
        low = si.SYSTEM_PROMPT.lower()
        self.assertIn("lead with where you actually used it", low)
        self.assertIn("not the most recent one", low)

    def test_the_prompt_forbids_repeating_audit_language(self):
        low = si.SYSTEM_PROMPT.lower()
        for phrase in ("census", "zero hits", "confirmed absence"):
            self.assertIn(phrase, low, f"prompt does not name {phrase!r}")
        self.assertIn("translate it", low)

    def test_the_prompt_forbids_reciting_preparation_material_as_memory(self):
        low = si.SYSTEM_PROMPT.lower()
        self.assertIn("preparation material, not memory", low)
        self.assertIn("delivery guarantees", low)

    def test_the_prompt_forbids_volunteering_a_limitation(self):
        """Sprint 15. This used to assert the prompt CAPPED limitation talk at
        "at most one short" sentence. That cap was the defect: measured over 57
        real production answers, a permitted sentence read as a required one
        and produced 37 volunteered negatives across 21 of them. The budget is
        now zero, so the assertion is on the stronger rule -- and on the
        absence of the old permissive wording, since leaving that in place
        anywhere in the prompt would reinstate the behaviour."""
        low = si.SYSTEM_PROMPT.lower()
        self.assertIn("do not volunteer a limitation", low)
        self.assertIn("the correct number of volunteered limitations is zero", low)
        for reinstates_the_defect in (
            "at most one short",
            "then the boundary of it in one sentence",
            "an absence gets one closing",
            "say where else it did or did not come up",
            "and you say so in one clause",
        ):
            self.assertNotIn(
                reinstates_the_defect, low,
                f"the prompt still invites a volunteered limitation: "
                f"{reinstates_the_defect!r}")


if __name__ == "__main__":
    unittest.main(verbosity=2)

# ======================================================================
# Sprint 13 / BL-090 -- the "any on-book question" mechanism.
# Three parts, each a real mechanism rather than a hard-coded exam answer:
#   (A) the standing career map is in front of the model on EVERY generate;
#   (B) interviewer English is rewritten into the books' own vocabulary
#       before retrieval;
#   (C) the books' attribution matrix decides which employer leads and
#       which employers get no paragraph at all.
# Every test below was observed FAILING against the pre-Sprint-13 module
# (AttributeError / AssertionError) before the implementation existed.
# ======================================================================

ATTRIBUTION_FIXTURE = {
    "BCBSA": [
        {"tech": "Kafka producer/consumer", "classification": "HANDS-ON",
         "bucket": "HANDS_ON", "interpretation": "Explicitly confirmed application-side work."},
        {"tech": "FHIR objects/resources", "classification": "HANDS-ON",
         "bucket": "HANDS_ON", "interpretation": ""},
    ],
    "NRG Energy": [
        {"tech": "Kafka", "classification": "NOT USED at NRG",
         "bucket": "NOT_USED", "interpretation": "Confirmed absent."},
        {"tech": "FusionAuth / JWT", "classification": "HANDS-ON",
         "bucket": "HANDS_ON", "interpretation": "Repeated real JWT/security commits."},
        {"tech": "SQS / DLQ", "classification": "USED/EXPOSED / system knowledge",
         "bucket": "USED", "interpretation": ""},
    ],
    "Marsh": [
        {"tech": "OAuth/JWT", "classification": "USED/EXPOSED",
         "bucket": "USED", "interpretation": "Worked behind/through secured API boundary."},
    ],
}

CAREER_MAP_FIXTURE = (
    "I am a senior Java backend developer. Right now I work at NRG Energy as a "
    "Senior Backend Developer; before that BCBSA; before that Marsh. "
    "We did not use Kafka at NRG; the async work ran on SQS with dead-letter "
    "queues and some scheduled jobs. " * 6
)


def make_corpus_v2(chunks=None, attribution=None, career_map=CAREER_MAP_FIXTURE):
    c = make_corpus(chunks)
    data = {"format_version": 2, "model_id": "test-model",
            "chunks": c.chunks, "source_book_hashes": {"BOOK-05": "abc"},
            "career_map": career_map,
            "attribution": ATTRIBUTION_FIXTURE if attribution is None else attribution}
    return si.Corpus(data)


class QueryRewriteTestCase(unittest.TestCase):
    """(B) The rewrite table exists so 'multithreading' can find a chunk that
    only ever says 'CompletableFuture'. Every expansion term was taken from
    the books' own wording, never from the public web."""

    def test_multithreading_is_rewritten_into_the_books_vocabulary(self):
        q = "explain your experience with multithreading"
        out = si.rewrite_query(q)
        self.assertIn(q, out)
        for term in ("CompletableFuture", "ExecutorService", "parallel"):
            self.assertIn(term, out)

    def test_kafka_jwt_and_nrg_async_each_expand(self):
        self.assertIn("consumer", si.rewrite_query("what did you do with Kafka?"))
        self.assertIn("producer", si.rewrite_query("what did you do with Kafka?"))
        self.assertIn("OAuth2", si.rewrite_query("tell me about JWT"))
        self.assertIn("Spring Security", si.rewrite_query("tell me about JWT"))
        out = si.rewrite_query("how did you do messaging at NRG?")
        self.assertIn("SQS", out)
        self.assertIn("dead-letter", out)

    def test_a_question_with_no_family_is_returned_unchanged(self):
        q = "what was the hardest bug you fixed?"
        self.assertEqual(si.rewrite_query(q), q)

    def test_the_rewrite_never_adds_an_employer_name(self):
        # Employer routing is the attribution matrix's job, not the rewrite's.
        for q in ("kafka", "jwt", "multithreading", "messaging", "async"):
            out = si.rewrite_query(q).lower()
            for emp in ("nrg", "bcbsa", "marsh"):
                self.assertNotIn(emp, out.replace(q, ""))

    def test_families_are_reported_so_attribution_can_look_them_up(self):
        fams = si.rewrite_families("explain your experience with kafka")
        self.assertIn("kafka", fams)
        self.assertEqual(si.rewrite_families("hardest bug"), [])


class AttributionTestCase(unittest.TestCase):
    """(C) The books' own 'Personal classification' tables decide who leads."""

    def test_kafka_leads_with_the_hands_on_employer_and_excludes_not_used(self):
        corpus = make_corpus_v2()
        a = si.attribution_for("explain your experience with kafka", corpus)
        self.assertEqual(a["lead"], ["BCBSA"])
        self.assertIn("NRG Energy", a["not_used"])
        self.assertNotIn("Marsh", a["lead"])

    def test_a_topic_no_matrix_records_yields_no_policy_rather_than_a_guess(self):
        corpus = make_corpus_v2()
        a = si.attribution_for("what was the hardest bug you fixed?", corpus)
        self.assertEqual(a, {})

    def test_jwt_has_two_evidenced_homes_and_the_hands_on_one_leads(self):
        corpus = make_corpus_v2()
        a = si.attribution_for("explain your experience in using oauth or jwt", corpus)
        self.assertEqual(a["lead"], ["NRG Energy"])
        self.assertIn("Marsh", a["used"])

    def test_a_corpus_without_a_matrix_falls_back_to_no_policy(self):
        corpus = make_corpus_v2(attribution={})
        self.assertEqual(si.attribution_for("kafka", corpus), {})

    def test_the_policy_line_names_the_lead_and_forbids_a_tour(self):
        corpus = make_corpus_v2()
        a = si.attribution_for("explain your experience with kafka", corpus)
        line = si.attribution_line(a, "explain your experience with kafka")
        self.assertIn("BCBSA", line)
        self.assertIn("NRG Energy", line)
        # Sprint 15 (SI-03): the line used to append "not used at NRG Energy"
        # to the same speakable list as everything else, and the model duly
        # spoke it -- the Kafka answers volunteered an absence about employers
        # nobody had asked about. The employer must still be NAMED, so no work
        # is ever claimed there; it is now framed as a constraint on claims
        # rather than as content to recite.
        low = line.lower()
        self.assertIn("nrg energy", low,
                      "the employer with no record must still be named")
        self.assertRegex(low, r"no record|not used|did not use")
        self.assertIn("never claim work there", low)
        self.assertRegex(
            low, r"do not say so|unless the question asks",
            "naming the absent employer must not double as permission to "
            "recite it")
        self.assertNotIn("Marsh", line)          # nothing recorded -> not mentioned

    def test_naming_an_employer_or_asking_career_wide_lifts_the_exclusion(self):
        corpus = make_corpus_v2()
        self.assertTrue(si.attribution_for("did NRG use kafka?", corpus)["employer_named"])
        self.assertTrue(si.attribution_for("did you use kafka anywhere?", corpus)["career_wide"])
        self.assertFalse(si.attribution_for("explain your experience with kafka", corpus)["career_wide"])


class OnlyWhereUsedRetrievalTestCase(unittest.TestCase):
    """Retrieval for a generic question fills its slots from the employers
    where the matrix says the work happened. Sprint 11's employer balancing
    stays as the fallback when the matrix has nothing to say."""

    def _corpus(self):
        chunks = [
            {"book_id": "BOOK-04", "section": "Kafka", "employer": "BCBSA",
             "knowledge_type": "personal_hands_on", "work_type": "professional",
             "status": "current", "vector": _vec(1.0),
             "text": "I wrote the Kafka producer and consumer application code."},
            {"book_id": "BOOK-05", "section": "Messaging", "employer": "NRG",
             "knowledge_type": "system_knowledge", "work_type": "professional",
             "status": "current", "vector": _vec(1.0),
             "text": "Kafka is absent from the NRG project; async is SQS/DLQ."},
            {"book_id": "BOOK-01", "section": "Messaging", "employer": "Marsh",
             "knowledge_type": "system_knowledge", "work_type": "professional",
             "status": "current", "vector": _vec(1.0),
             "text": "No Marsh messaging platform is established."},
        ]
        return make_corpus_v2(chunks)

    def test_a_generic_kafka_question_retrieves_only_the_hands_on_employer(self):
        corpus = self._corpus()
        hits = si.retrieve("explain your experience with kafka", corpus,
                           embed_query=lambda q: _vec(1.0))
        self.assertTrue(hits)
        self.assertEqual({h["employer"] for h in hits}, {"BCBSA"})

    def test_a_career_wide_question_keeps_every_employer(self):
        corpus = self._corpus()
        hits = si.retrieve("did you use kafka anywhere in your career?", corpus,
                           embed_query=lambda q: _vec(1.0))
        self.assertEqual({h["employer"] for h in hits}, {"BCBSA", "NRG Energy", "Marsh"})

    def test_naming_the_absent_employer_still_retrieves_it(self):
        corpus = self._corpus()
        hits = si.retrieve("Did NRG use Kafka?", corpus, embed_query=lambda q: _vec(1.0))
        self.assertIn("NRG Energy", {h["employer"] for h in hits})

    def test_naming_an_employer_puts_that_employers_chunks_first(self):
        # "How did you use Spring Security at NRG?" measured on the real corpus
        # returned Marsh, Marsh, NRG, ... -- the named employer third. The
        # prompt says "answer only about that employer", so retrieval should
        # put that employer's material first rather than rely on the model
        # to skip past two paragraphs of somebody else's.
        chunks = self._corpus().chunks
        chunks[1] = dict(chunks[1], vector=_vec(0.9))      # NRG scores LOWER
        corpus = make_corpus_v2(chunks)
        hits = si.retrieve("Did NRG use Kafka?", corpus, embed_query=lambda q: _vec(1.0))
        self.assertEqual(hits[0]["employer"], "NRG Energy")
        self.assertGreater(len(hits), 1, "named-first must not starve the answer")

    def test_no_matrix_means_the_old_balancing_still_applies(self):
        corpus = make_corpus_v2(self._corpus().chunks, attribution={})
        hits = si.retrieve("explain your experience with kafka", corpus,
                           embed_query=lambda q: _vec(1.0))
        self.assertEqual({h["employer"] for h in hits}, {"BCBSA", "NRG Energy", "Marsh"})


class CareerMapTestCase(unittest.TestCase):
    """(A) The map is in front of the model on every successful generate, and
    a corpus without one is not a corpus."""

    def test_the_map_is_in_the_system_prompt_of_every_generate(self):
        corpus = make_corpus_v2()
        create = fake_model("At NRG I implemented the Spring Security filter that verified them. "
                            "That is where it stopped; the platform team owned the issuer.")
        strong = [dict(corpus.chunks[0], score=0.9, employer="NRG Energy")]
        with mock.patch.object(si, "retrieve", return_value=strong):
            r = si.answer("How did you use Spring Security at NRG?", corpus, create_fn=create)
        self.assertEqual(r["outcome"], "answered")
        self.assertIn(CAREER_MAP_FIXTURE[:60], create.last_kwargs["system"])

    def test_a_v1_corpus_without_a_map_is_treated_as_no_corpus(self):
        d = tempfile.mkdtemp()
        try:
            path = pathlib.Path(d) / "corpus.json"
            path.write_text(json.dumps({"format_version": 1, "model_id": "m",
                                        "chunks": [{"book_id": "BOOK-05", "text": "x",
                                                    "vector": [1.0]}]}), encoding="utf-8")
            self.assertIsNone(si.load_corpus(path))
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_status_reports_the_map_without_revealing_it(self):
        s = si.corpus_status(make_corpus_v2())
        self.assertTrue(s["career_map"])
        self.assertNotIn("NRG", json.dumps(s))

    def test_the_real_map_if_present_passes_the_leak_and_voice_gates(self):
        corpus = si.load_corpus()
        if corpus is None:
            self.skipTest("no real corpus on this machine")
        self.assertEqual(si.leaks(corpus.career_map), [])
        # The map is written in the voice the answers must have; a banned
        # phrase in it would teach the model the audit register.
        self.assertEqual([v for v in si.voice_violations(corpus.career_map)
                          if not v.startswith("spends")], [])


class AnswerPolicyGateTestCase(unittest.TestCase):
    """The audit family is banned as a FAMILY, and two Owner rules are code."""

    def test_the_audit_register_family_is_banned(self):
        for text in ("Per my knowledge cutoff, Kafka was not used.",
                     "The documents say we used SQS.",
                     "A full file census found nothing.",
                     "The record shows no Kafka."):
            self.assertTrue(si.voice_violations(text + " That is all."), text)

    def test_jms_is_never_volunteered(self):
        text = "We didn't use Kafka at NRG. We didn't use JMS either. Async ran on SQS."
        v = si.voice_violations(text, question="Did NRG use Kafka?")
        self.assertTrue(any("JMS" in x for x in v), v)

    def test_jms_may_be_answered_when_it_is_asked_about(self):
        text = "We didn't use JMS at NRG. The async work ran on SQS with a dead-letter queue."
        v = si.voice_violations(text, question="Did you use JMS at NRG?")
        self.assertFalse(any("JMS" in x for x in v), v)

    def test_architecture_ownership_claims_are_rejected(self):
        self.assertTrue(si.voice_violations(
            "I designed the overall architecture of the NRG platform. It worked."))
        self.assertTrue(si.voice_violations(
            "I architected the entire serverless layer myself. It worked."))
        self.assertEqual(si.voice_violations(
            "I implemented the JWT filter within the architecture the lead designed. "
            "That is where my part stopped."), [])

    def test_the_system_prompt_carries_the_only_where_used_policy(self):
        corpus = make_corpus_v2()
        create = fake_model("At BCBSA I wrote the Kafka producer and consumer code. "
                            "That is where it stopped.")
        strong = [dict(corpus.chunks[0], score=0.9, employer="BCBSA")]
        with mock.patch.object(si, "retrieve", return_value=strong):
            si.answer("explain your experience with kafka", corpus, create_fn=create)
        sent = create.last_kwargs["messages"][0]["content"] + create.last_kwargs["system"]
        self.assertIn("BCBSA", sent)
        self.assertRegex(sent, r"(?i)do not (give|write) .*paragraph")


class PrivateTopicGateTestCase(unittest.TestCase):
    """Sprint 13, from the first real gate run: "What is your salary
    expectation and home address?" scored 0.5725 (above threshold) and the
    model DEFLECTED politely instead of declining. Private topics are refused
    in code, before any model call."""

    def test_salary_and_address_are_refused_without_calling_the_model(self):
        corpus = make_corpus_v2()
        create = fake_model("should never be called")
        calls = []
        def spy(**kw):
            calls.append(kw); return create(**kw)
        with mock.patch.object(si, "retrieve", side_effect=AssertionError("retrieval must not run")):
            r = si.answer("What is your salary expectation and home address?", corpus, create_fn=spy)
        self.assertEqual(r["outcome"], "private_topic")
        self.assertEqual(r["answer"], si.REFUSAL)
        self.assertEqual(calls, [])

    def test_the_gate_is_narrow_enough_for_ordinary_career_questions(self):
        for q in ("How did you use Spring Security at NRG?",
                  "What did you pay attention to when logging PHI?",   # 'pay' as a verb
                  "Tell me about the account-mapping queue",
                  "Are you open to relocating to Munich?"):            # logistics: NOT gated (Owner decision open)
            self.assertFalse(si.is_private_topic(q), q)

    def test_each_private_shape_is_caught(self):
        for q in ("what is your current salary?", "expected compensation?",
                  "what's your day rate", "give me your phone number",
                  "what is your home address", "how old are you", "are you married?",
                  "passport number please"):
            self.assertTrue(si.is_private_topic(q), q)

    def test_a_polite_deflection_from_the_model_is_still_a_refusal(self):
        # If a private question ever slipped past the regex, the decline gate
        # must catch the deflection shape the model actually produced.
        self.assertTrue(si._model_declined(
            "I'm not going to share my home address in this context, but happy "
            "to talk through salary expectations directly."))


class NotesCitationTestCase(unittest.TestCase):
    def test_citing_the_projects_own_notes_is_a_voice_violation(self):
        v = si.voice_violations("I built a local index. The project's own notes are "
                               "explicit that it is sized for this repo. That is all.")
        self.assertTrue(any("notes" in x for x in v), v)

    def test_plain_speech_about_documentation_work_is_not(self):
        self.assertEqual(si.voice_violations(
            "I wrote the documentation for the carrier mappings and reviewed it "
            "with the architect. That is where my part stopped."), [])


class PassiveVoiceRuleTestCase(unittest.TestCase):
    def test_the_prompt_forbids_converting_team_work_into_i_built_it(self):
        self.assertRegex(si.SYSTEM_PROMPT, r"(?i)do not convert it into")
        self.assertRegex(si.SYSTEM_PROMPT, r"(?i)neighbouring\s+technology")


class NeighbourTechnologyTestCase(unittest.TestCase):
    """Sprint 13, gate runs 1 and 2: FHIR kept entering the Kafka answer."""

    def test_fhir_in_a_kafka_answer_is_a_violation(self):
        v = si.voice_violations("At BCBSA I wrote the Kafka producer code that kept the "
                               "FHIR-facing view current. That is where it stopped.",
                               question="explain your experience with kafka")
        self.assertTrue(any("FHIR" in x for x in v), v)

    def test_fhir_in_a_fhir_answer_is_not(self):
        v = si.voice_violations("At BCBSA I worked directly with FHIR resource objects in "
                               "Java. That is where it stopped.",
                               question="tell me about your FHIR work")
        self.assertFalse(any("FHIR" in x for x in v), v)

    def test_acord_is_allowed_in_an_integration_answer(self):
        # The Camel/carrier family rewrites to ACORD, so it is not a neighbour.
        v = si.voice_violations("At Marsh I mapped carrier payloads into the ACORD-oriented "
                               "model with Camel routes. That is where it stopped.",
                               question="Tell me about your integration work at Marsh")
        self.assertFalse(any("ACORD" in x for x in v), v)

    def test_a_question_about_no_technology_has_no_neighbours(self):
        self.assertEqual(si.neighbour_violations("We used DB2 and FHIR there.",
                                                 "what was your hardest week?"), [])


class LeakRetryTestCase(unittest.TestCase):
    """An extension-only leak earns one retry; the retry is fully re-scanned.
    A book/path/name leak still refuses immediately."""

    def setUp(self):
        self.corpus = make_corpus_v2()
        self.strong = [dict(self.corpus.chunks[1], score=0.85, employer=None)]

    def _two(self, first, second):
        calls = []
        def create(**kw):
            calls.append(kw); return FakeResponse(first if len(calls) == 1 else second)
        create.calls = calls
        return create

    def test_a_filename_leak_is_retried_and_the_clean_retry_ships(self):
        model = self._two("The hash is checked in write_tools.py before apply. Done.",
                          "The hash is checked again right before the write. Done.")
        with mock.patch.object(si, "retrieve", return_value=self.strong):
            out = si.answer("How does the approval step work?", self.corpus, create_fn=model)
        self.assertEqual(out["outcome"], "answered")
        self.assertTrue(out["leak_retried"])
        self.assertEqual(si.leaks(out["answer"]), [])
        self.assertEqual(len(model.calls), 2)

    def test_a_retry_that_still_leaks_is_refused(self):
        model = self._two("See write_tools.py. Done.", "It lives in apply_edit.py. Done.")
        with mock.patch.object(si, "retrieve", return_value=self.strong):
            out = si.answer("How does the approval step work?", self.corpus, create_fn=model)
        self.assertEqual(out["outcome"], "leak_blocked")
        self.assertEqual(out["answer"], si.REFUSAL)
        self.assertTrue(out["leak_retried"])

    def test_a_book_identifier_leak_is_never_retried(self):
        model = self._two("According to the document, BOOK-05 says so. Done.",
                          "should never be used")
        with mock.patch.object(si, "retrieve", return_value=self.strong):
            out = si.answer("How does the approval step work?", self.corpus, create_fn=model)
        self.assertEqual(out["outcome"], "leak_blocked")
        self.assertEqual(len(model.calls), 1, "a confidentiality leak must not be retried")

    def test_the_retry_output_still_passes_the_voice_gate(self):
        model = self._two("See write_tools.py. Done.",
                          "Zero hits across the census, but the hash is checked. Done.")
        with mock.patch.object(si, "retrieve", return_value=self.strong):
            out = si.answer("How does the approval step work?", self.corpus, create_fn=model)
        self.assertNotEqual(out["outcome"], "answered")


class ProvenanceNarrowingTestCase(unittest.TestCase):
    """Sprint 13, gate run 4 (the deploy script's own local gate): a correct
    answer about this surface's own retrieval was refused because it said
    "the knowledge base"/"my notes" as the SUBJECT. Pinned from both sides,
    as Sprint 11 pinned `source`: the senses that must pass AND the senses
    that must still be blocked."""

    CLEAN = (
        # verbatim from the real replay, 2026-09-29
        "The retrieval in this interview surface runs locally against my own notes.",
        # the product's own refusal line
        si.NO_CORPUS,
        "Retrieval runs over the corpus with cosine similarity and a grounding threshold.",
        "This surface retrieves from a private knowledge base before anything reaches you.",
    )
    LEAKY = (
        "My notes say I used Kafka at BCBSA.",
        "The document describes the JWT flow in detail.",
        "In the corpus there is a section on FusionAuth.",
        "The knowledge base lists SQS and a dead-letter queue.",
        "According to my notes, we used Camel.",
        "Per the excerpts, it was Oracle.",
    )

    def test_describing_the_mechanism_is_not_a_leak(self):
        for text in self.CLEAN:
            self.assertEqual(si.leaks(text), [], text)

    def test_citing_where_it_was_read_is_still_a_leak(self):
        for text in self.LEAKY:
            self.assertTrue(si.leaks(text), text)

    def test_a_refused_answer_keeps_the_model_text_for_review(self):
        corpus = make_corpus_v2()
        strong = [dict(corpus.chunks[1], score=0.85, employer=None)]
        model = fake_model("My notes say the hash is checked twice. Done.")
        with mock.patch.object(si, "retrieve", return_value=strong):
            out = si.answer("How does the approval step work?", corpus, create_fn=model)
        self.assertEqual(out["outcome"], "leak_blocked")
        self.assertIn("My notes say", out["model_reply"])
        self.assertEqual(out["answer"], si.REFUSAL)


class DeployMarkerTestCase(unittest.TestCase):
    """Sprint 13 real incident: the remote gate ran against the OLD container
    during Railway's cutover. The status endpoint reports the upload's marker
    so the deploy script can wait for the new container specifically."""

    def test_status_reports_the_marker_when_present(self):
        d = tempfile.mkdtemp()
        try:
            marker = pathlib.Path(d) / "deploy_marker.txt"
            marker.write_text("deploy-20260929T230000Z-eb1aeec\n", encoding="utf-8")
            with mock.patch.object(si, "DEPLOY_MARKER_PATH", marker):
                s = si.corpus_status(make_corpus_v2())
            self.assertEqual(s["deploy_marker"], "deploy-20260929T230000Z-eb1aeec")
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_status_reports_none_without_a_marker(self):
        with mock.patch.object(si, "DEPLOY_MARKER_PATH", pathlib.Path("/nonexistent/marker.txt")):
            self.assertIsNone(si.corpus_status(make_corpus_v2())["deploy_marker"])

    def test_the_deploy_script_gates_on_the_marker_not_on_loaded_true(self):
        script = (pathlib.Path(__file__).resolve().parent.parent / "scripts"
                  / "deploy_platform_with_si_corpus.sh").read_text(encoding="utf-8")
        self.assertIn("deploy_marker.txt", script)
        self.assertIn("matches >= 3", script)
        self.assertNotIn("grep -q '\"loaded\":true'", script)


class QuestionAwareLeakTestCase(unittest.TestCase):
    """Post-cutover remote gate: "the corpus holds ..." is the ANSWER to a
    question about retrieval, and a citation for any other question."""

    TEXT = "The corpus holds a few hundred embedded chunks and the index is local JSON with cosine similarity."

    def test_describing_the_corpus_is_allowed_when_asked_about_retrieval(self):
        self.assertEqual(si.leaks(self.TEXT, "How does your RAG retrieval work in the Standing Interview?"), [])

    def test_the_same_sentence_is_a_leak_on_a_career_question(self):
        self.assertTrue(si.leaks(self.TEXT, "explain your experience with kafka"))
        self.assertTrue(si.leaks(self.TEXT))

    def test_the_exemption_covers_only_the_provenance_verb_pattern(self):
        q = "How does your RAG retrieval work?"
        self.assertTrue(si.leaks("BOOK-05 lists the chunks.", q))
        self.assertTrue(si.leaks("According to the document, retrieval is local.", q))
        self.assertTrue(si.leaks("The excerpt above explains it.", q))
        self.assertTrue(si.leaks("It is in rag_index.py.", q))


class NeighbourRetryTestCase(unittest.TestCase):
    """Deploy attempt 5, generic Kafka question: FHIR on the first attempt,
    DB2 on the retry. The retry must be told the whole neighbour list."""

    def test_the_retry_is_told_every_neighbour_not_just_the_one_caught(self):
        corpus = make_corpus_v2()
        strong = [dict(corpus.chunks[0], score=0.85, employer="BCBSA")]
        calls = []
        def model(**kw):
            calls.append(kw)
            return FakeResponse("At BCBSA I wrote the Kafka producer code for the FHIR layer. Done."
                                if len(calls) == 1 else
                                "At BCBSA I wrote the Kafka producer and consumer code. Done.")
        with mock.patch.object(si, "retrieve", return_value=strong):
            out = si.answer("explain your experience with kafka", corpus, create_fn=model)
        self.assertEqual(out["outcome"], "answered")
        retry_prompt = calls[1]["messages"][0]["content"]
        for name in ("FHIR", "DB2", "Oracle", "DynamoDB", "ACORD"):
            self.assertIn(name, retry_prompt)

    def test_the_prompt_carries_the_worked_example(self):
        self.assertIn("FHIR-normalized", si.SYSTEM_PROMPT)
        self.assertIn("DB2-backed", si.SYSTEM_PROMPT)


class SubstringSenseTestCase(unittest.TestCase):
    """Deploy attempt 7: "not a substring check" is engineering vocabulary
    from the platform book; "just a substring match inside base64 tokens" is
    the JMS audit narrative. Pinned both ways."""

    def test_engineering_sense_passes(self):
        text = ("The test verifies it with an exact set-membership check, not a "
                "substring check, so a renamed tool cannot slip through. That is all.")
        self.assertFalse(any("substring" in v for v in si.voice_violations(text)), si.voice_violations(text))

    def test_audit_narrative_sense_is_still_banned(self):
        for text in ("JMS turned up but it was just a substring match inside base64 tokens. Done.",
                     "That was a substring hit, not real usage. Done."):
            self.assertTrue(any("substring" in v for v in si.voice_violations(text)), text)

    def test_the_retry_is_told_to_open_on_the_work(self):
        corpus = make_corpus_v2()
        strong = [dict(corpus.chunks[0], score=0.85, employer="NRG Energy")]
        calls = []
        def model(**kw):
            calls.append(kw)
            return FakeResponse("Zero hits across the census. Done." if len(calls) == 1
                                else "At NRG I implemented the filter. Done.")
        with mock.patch.object(si, "retrieve", return_value=strong):
            si.answer("How did you use Spring Security at NRG?", corpus, create_fn=model)
        self.assertIn("Open on the work", calls[1]["messages"][0]["content"])


class QaFoundRegisterTestCase(unittest.TestCase):
    """Independent QA (2026-09-29) read a fresh answer the gate had not
    sampled and found the audit register in two new shapes."""

    def test_the_two_shapes_qa_found_are_now_caught(self):
        for text in ("There was also a confirmed real async flow in the dashboard. Done.",
                     "Kafka never came up anywhere in that codebase. Done.",
                     "It shows up nowhere in the repository. Done."):
            self.assertTrue(si.voice_violations(text), text)

    def test_plain_speech_about_the_same_facts_passes(self):
        for text in ("We did parallelize the dashboard fan-out with CompletableFuture. Done.",
                     "We didn't use Kafka at NRG; the async work ran on SQS. Done.",
                     "The topic came up in a design review and we chose SQS. Done."):
            self.assertEqual([v for v in si.voice_violations(text) if "search talk" in v or "confirmed real" in v], [], text)
