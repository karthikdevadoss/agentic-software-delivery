"""
Standing Interview acceptance replay -- the six Owner-specified questions plus
the one that must be refused, asserted against the REAL corpus and a REAL model
call, locally or against a deployed host.

WHY THIS EXISTS SEPARATELY FROM test_standing_interview.py
test_standing_interview.py is hermetic: fixture corpus, injected model. It can
prove the leak scanner no longer trips on "the source service" and that
retrieval reserves a slot per employer. It cannot prove that the actual
generic-Kafka question, against the actual 361-chunk corpus, with the actual
model, comes back answered -- and that is precisely the thing that regressed.
Sprint 11's defect was invisible to every hermetic test in the suite and
visible in one real question.

So this is a gate, not a unit test: it costs real model calls, it needs the
real corpus, and it is run deliberately -- before a deploy, and again against
the deployed host afterwards. Exit code 0 means every requirement held.

    python agent/si_acceptance.py                         # local corpus + model
    python agent/si_acceptance.py --base-url https://...  # the deployed host

The SAME assertions run in both modes. A production run that skips the
assertions and just eyeballs three answers is how Sprint 10 nearly reported a
page live on the strength of a status endpoint.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import standing_interview as si


def _hedged(text: str, term: str, window: int = 140) -> bool:
    """True when `term` appears only inside an explicit disclaimer.

    The Owner's requirement is 'no invented RS256/key rotation'. The books
    themselves say the exact JWT algorithm is unknown, so naming RS256 as fact
    is a fabrication -- but a good answer is allowed to say "I can't tell you
    it was RS256 specifically", which is the honesty the surface is built on.
    A flat substring ban would fail the best answer; this checks the sense."""
    low = text.lower()
    hedges = ("can't", "cannot", "can not", "couldn't", "wouldn't", "won't",
              "don't", "do not", "not something", "no detail", "unknown",
              "isn't", "is not", "wasn't", "was not", "never claimed",
              "not claim", "unclear", "uncertain")
    for m in re.finditer(re.escape(term.lower()), low):
        a, b = max(0, m.start() - window), min(len(low), m.end() + window)
        if not any(h in low[a:b] for h in hedges):
            return False
    return True


def _asserted(text: str, term: str, window: int = 60) -> bool:
    """True when `term` is stated as fact somewhere -- i.e. appears without a
    negation in the words just before it. "I don't remember the partition key"
    is honest; "using member ID as a natural partition key" is an invention.
    Narrower than _hedged() on purpose: a hedge elsewhere in the paragraph
    must not launder an assertion (the Owner-rejected answer had both)."""
    low = text.lower()
    negations = ("didn't", "did not", "don't", "do not", "not ", "no ", "never",
                 "wasn't", "was not", "can't", "cannot", "couldn't", "without")
    for m in re.finditer(re.escape(term.lower()), low):
        before = low[max(0, m.start() - window):m.start()]
        if not any(n in before for n in negations):
            return True
    return False


def _all(text: str, *terms: str) -> list[str]:
    low = text.lower()
    return [t for t in terms if t.lower() not in low]


def _any(text: str, *terms: str) -> bool:
    low = text.lower()
    return any(t.lower() in low for t in terms)


def _order(text: str, first: str, then: str) -> bool:
    low = text.lower()
    i, j = low.find(first.lower()), low.find(then.lower())
    return i != -1 and j != -1 and i < j


# --- the requirements, stated as code ---------------------------------------
# Each check returns a list of failure strings. Empty list = requirement met.

def _check_generic_kafka(text):
    bad = []
    missing = _all(text, "bcbsa", "consumer")
    if missing:
        bad.append(f"no BCBSA producer/consumer hands-on (missing {missing})")
    if not _any(text, "producer"):
        bad.append("does not mention the producer side")
    # Sprint 12 FROZEN VOICE SPEC 1: lead with the employer where he USED it.
    # Kafka -> BCBSA first, never NRG first. Asserted on the opening sentence
    # rather than on whole-text ordering, because "BCBSA appears before NRG
    # somewhere" is satisfied by an answer that still opens on an absence.
    first = _sentences(text)[0] if _sentences(text) else ""
    if not _any(first, "bcbsa"):
        bad.append(f"does not open at BCBSA (opens: {first[:80]!r})")
    if _any(first, "nrg", "marsh"):
        bad.append("opens on an employer that did not use Kafka")
    # SPEC 3: the absences are short footnotes, not the body of the answer.
    sents = _sentences(text)
    absence = [x for x in sents if _any(x, "nrg", "marsh")]
    if len(absence) > 3:
        bad.append(f"{len(absence)} sentences about where Kafka was NOT used (max 3)")
    # NOTE the wording accepted here. An earlier version of this check accepted
    # "absence" and "zero" -- the very words the frozen voice spec BANS -- so
    # the content check and the voice check contradicted each other and a
    # correctly-voiced answer failed. These are the plain-speech forms a person
    # actually uses; the audit forms are rejected by _check_voice, not accepted
    # here.
    # Sprint 13 (Owner spec, 2026-09-29): with the attribution matrix putting
    # BCBSA in the lead and NRG marked not-used, the absence is a footnote the
    # answer MAY carry, no longer one it MUST carry. What it must not do is
    # drag in details no book records for this work.
    # Hedge-aware, like the RS256 check: "I didn't set up topics, partitions,
    # consumer groups" is the books' own boundary sentence and is honest;
    # "member ID as the partition key" is an invention. Read the sense.
    if _asserted(text, "partition key"):
        bad.append("asserts a partition key -- not in the hands-on record")
    if _any(text, "member id", "member-id", "memberid"):
        bad.append("mentions member ID as a key -- not in the hands-on record")
    if _any(text, "fhir"):
        bad.append("drags FHIR into a Kafka answer")
    if _ownership_claim(text):
        bad.append("claims to have designed the architecture")
    if _any(text, "jms"):
        bad.append("volunteers JMS")
    # DELIBERATELY NOT an ordering check, and the reason is recorded because the
    # first version of this gate had one and it failed a good answer.
    #
    # The Owner's requirement for this question is content: "BCBSA
    # producer/consumer hands-on + NRG has no Kafka". The NRG-FIRST requirement
    # was stated for the OAuth/JWT question, and it is asserted there. Imposing
    # it here as well penalised a genuinely good answer that opened with the
    # real hands-on experience and then stated the absence -- which is better
    # interview technique for a technology the current employer does not use
    # than opening with "we don't use that". Retrieval still puts the most
    # recent employer's excerpts first; what the model leads with, given both
    # facts, is a judgement this gate does not need to own.
    return bad


_OWNERSHIP = re.compile(
    r"\bI\s+(designed|architected|owned)\s+the\s+(overall|entire|whole|end-to-end|full)"
    r"\s+(\w+\s+){0,2}(architecture|platform|system|layer)\b", re.I)


def _ownership_claim(text: str) -> bool:
    return bool(_OWNERSHIP.search(text))


def _check_generic_oauth(text):
    bad = []
    if not _any(text, "nrg"):
        bad.append("no NRG paragraph")
    if not _order(text, "nrg", "marsh") and _any(text, "marsh"):
        bad.append("NRG is not answered before Marsh")
    if _any(text, "apigee") and not _any(text, "marsh"):
        bad.append("Apigee mentioned without attributing it to Marsh")
    if not _hedged(text, "RS256"):
        bad.append("states RS256 as fact -- not supported by the books")
    if not _hedged(text, "key rotation"):
        bad.append("states a key-rotation policy as fact -- not in the books")
    return bad


def _check_kafka_at_bcbsa(text):
    bad = _all(text, "producer", "consumer")
    bad = [f"missing {b}" for b in bad]
    if not _any(text, "bcbsa", "member", "claims", "coverage"):
        bad.append("not recognisably the BCBSA answer")
    return bad


def _check_kafka_absent_at_nrg(text):
    bad = []
    if not _any(text, "no kafka", "wasn't", "was not", "didn't use", "did not use",
                "not part of", "not used", "never used"):
        bad.append("does not state the absence")
    if not _any(text, "sqs"):
        bad.append("does not name the real async mechanism (SQS)")
    if _any(text, "jms"):
        bad.append("volunteers JMS (Owner rule 2026-09-29)")
    # Q4 in the Owner's spec: "Short."
    if len(text.split()) > 140:
        bad.append(f"an absence answer should be short ({len(text.split())} words)")
    return bad


# --- Sprint 13: the multithreading question that used to refuse ------------
def _check_multithreading(text):
    bad = []
    if not _any(text, "completablefuture", "parallel", "executor", "thread pool", "async"):
        bad.append("no concurrency detail (CompletableFuture / parallel / executor)")
    if not _any(text, "nrg"):
        bad.append("does not place the work at NRG")
    if _ownership_claim(text):
        bad.append("claims to have designed the architecture")
    return bad


# --- Sprint 13: UNSEEN on-book questions. None of these was in any Owner
# packet or prior exam. They prove the MECHANISM (map + rewrite + matrix)
# answers questions nobody tuned for, which is the whole P0. Each check is
# the books' own content, not an invented requirement.
def _check_nrg_async(text):
    bad = []
    if not _any(text, "sqs"):
        bad.append("does not name SQS")
    if not _any(text, "dead-letter", "dead letter", "dlq"):
        bad.append("does not mention the dead-letter queue")
    if _any(text, "jms"):
        bad.append("volunteers JMS (Owner rule 2026-09-29)")
    if _any(text, "kafka") and not _any(text, "didn't use kafka", "did not use kafka",
                                        "not kafka", "no kafka", "wasn't kafka",
                                        "rather than kafka", "instead of kafka",
                                        "kafka wasn't", "kafka was not"):
        bad.append("mentions Kafka at NRG without saying it was not used")
    return bad


def _check_marsh_integration(text):
    bad = []
    if not _any(text, "camel"):
        bad.append("does not mention Apache Camel")
    if not _any(text, "carrier", "insur"):
        bad.append("does not place it in the carrier/insurance integration work")
    if _any(text, "kafka"):
        bad.append("mentions Kafka in a Marsh answer")
    if _ownership_claim(text):
        bad.append("claims to have designed the architecture")
    return bad


def _check_platform_hitl(text):
    bad = []
    if not _any(text, "approv"):
        bad.append("does not describe the approval step")
    if not _any(text, "hash", "no code path", "cannot approve", "can't approve",
                "no way to approve", "not able to approve", "structural"):
        bad.append("does not say how the model is kept from approving its own change")
    return bad


def _check_platform_rag(text):
    # First gate run: the answer described the embedding model, the local
    # index and the scale trade-off -- all on-book -- and failed a clause
    # demanding it ALSO mention the grounding threshold. That clause was mine,
    # not the books'; an assertion I invent is a requirement I invented.
    bad = []
    if not _any(text, "embedding", "retriev", "cosine", "vector", "semantic"):
        bad.append("no retrieval detail")
    return bad


def _check_nrg_lambda(text):
    bad = []
    if not _any(text, "lambda"):
        bad.append("does not mention Lambda")
    if not _any(text, "sam", "openapi", "api gateway"):
        bad.append("no SAM / OpenAPI / API Gateway detail")
    if _any(text, "kubernetes", "terraform"):
        bad.append("names a technology the books say was not used at NRG")
    return bad


def _check_spring_security_nrg(text):
    bad = _all(text, "spring security")
    bad = [f"missing {b}" for b in bad]
    if not _any(text, "jwt", "filter", "access control"):
        bad.append("no hands-on detail (JWT filter / access control)")
    return bad


def _sentences(text: str):
    return si._sentences(text)


def _check_voice(text):
    """Sprint 12. Every answered question runs the same voice assertions, not
    only the one the Owner reported. The banned register and the truncation
    check are the product's own gate (si.voice_violations), re-asserted here
    against the REAL model output -- the hermetic tests prove the checker
    works, and this proves the generator actually satisfies it end to end.

    Sprint 11's lesson applied: an assertion I invent is a requirement I
    invented, so this asserts the Owner's frozen spec and nothing more."""
    bad = ["voice: " + v for v in si.voice_violations(text)]
    # SPEC 8: complete sentences, roughly 6-10 spoken lines. The upper bound is
    # generous on purpose -- the Owner's complaint was a search report, not a
    # long answer, and a hard word cap would start failing good answers.
    words = len(text.split())
    if words < 35:
        bad.append(f"too short to be an interview answer ({words} words)")
    if words > 320:
        bad.append(f"reads as an essay, not spoken ({words} words)")
    return bad


def _first_person(text: str) -> bool:
    return bool(re.search(r"\b(i|i'm|i'd|i've|my|me|we|our)\b", text, re.I))


# (question, must_be_answered, extra checks, require_first_person)
#
# first_person is per-case on purpose. "Did NRG use Kafka?" is correctly
# answered as a flat statement of fact -- "No, Kafka wasn't used anywhere on
# the NRG project. That was a confirmed absence..." -- which contains no
# pronoun at all and is the right answer. A blanket pronoun check failed that
# answer on the first run of this gate: the same false-positive shape as the
# leak-scanner defect this sprint exists to fix, so it is not repeated here.
CASES = [
    ("explain your experience with kafka", True, _check_generic_kafka, True),
    ("explain your experience in using oauth or jwt", True, _check_generic_oauth, True),
    ("How did you use Kafka at BCBSA?", True, _check_kafka_at_bcbsa, True),
    ("Did NRG use Kafka?", True, _check_kafka_absent_at_nrg, False),
    ("Tell me about Kafka at NRG", True, _check_kafka_absent_at_nrg, False),
    ("How did you use Spring Security at NRG?", True, _check_spring_security_nrg, True),
    # Sprint 13 / Owner Q5: used to refuse -- "multithreading" never appears
    # in the books, which say CompletableFuture / parallel / fan-out. The
    # query rewrite is what makes this answerable; it is asserted here so a
    # regression in the rewrite table fails the gate, not the Owner.
    ("explain your experience with multithreading", True, _check_multithreading, True),
    ("What is the capital of France?", False, None, False),
    # Added Sprint 12: the Owner asked this one on the live page and it was
    # refused by the DECLINE GATE at best_score 0.5204 -- above the 0.50
    # threshold, caught by the second independent signal. That is the only
    # case in the suite that exercises the decline gate against real output,
    # so it belongs here permanently.
    ("what is capital of india", False, None, False),
]

# Sprint 13: unseen set. NOT the product, NOT hard-coded -- see the checks'
# own comment. Reported under its own heading so a reader can tell "the exam
# passed" from "questions nobody tuned for passed".
UNSEEN_CASES = [
    ("How did you handle async processing or messaging at NRG?", True, _check_nrg_async, True),
    ("Tell me about your integration work at Marsh", True, _check_marsh_integration, True),
    ("How does the human approval step work on your platform?", True, _check_platform_hitl, True),
    ("How does your RAG retrieval work in the Standing Interview?", True, _check_platform_rag, True),
    ("Tell me about your AWS Lambda work", True, _check_nrg_lambda, True),
    # Off-book: not in any book. Refusing is the correct outcome.
    ("What is your salary expectation and home address?", False, None, False),
]


# --- the gate proves itself ---------------------------------------------------
# A gate is only worth its exit code if it has been seen rejecting the real bad
# output. Sprint 11 proved the previous version of this file red by running it
# against the pre-fix module; that is no longer possible for the Sprint 12
# checks, because they call si.voice_violations() which did not exist then --
# importing the old module just raises AttributeError, which proves nothing.
#
# So the known-bad case is pinned here instead, verbatim from the event ledger:
# the answer the Owner clicked Dissatisfied on at 2026-09-27 20:03. --selftest
# asserts every check rejects it, and it runs on every real gate invocation, so
# it cannot rot the way a one-off shell demonstration does.
OWNER_REJECTED_KAFKA_ANSWER = (
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
    "which cloud it ran on. At Marsh there's no genuine evidence of Kafka, JMS, "
    "RabbitMQ or ActiveMQ."
)


def selftest() -> int:
    """Assert this gate rejects the real answer the Owner rejected."""
    print("=" * 74)
    print("GATE SELFTEST -- the verbatim Owner-rejected generic-Kafka answer")
    print("=" * 74)
    failures = []

    voice = _check_voice(OWNER_REJECTED_KAFKA_ANSWER)
    print("\n_check_voice ->")
    for v in voice:
        print("   ", v)
    if not voice:
        failures.append("_check_voice ACCEPTED the Owner-rejected answer")
    else:
        joined = " | ".join(voice).lower()
        # The specific things the Owner named, not merely "something fired".
        for clause in ("census", "hits", "confirmed absence", "partition key",
                       "delivery guarantee", "schema evolution", "cron", "evidence"):
            if clause not in joined:
                failures.append(f"_check_voice missed the banned clause: {clause}")

    kafka = _check_generic_kafka(OWNER_REJECTED_KAFKA_ANSWER)
    print("\n_check_generic_kafka ->")
    for v in kafka:
        print("   ", v)
    if not any("open" in v for v in kafka):
        failures.append("_check_generic_kafka did not catch the NRG-first opening")
    if not any("partition" in v for v in kafka):
        failures.append("_check_generic_kafka did not catch the partition key")
    if not any("JMS" in v for v in kafka):
        failures.append("_check_generic_kafka did not catch the volunteered JMS")

    print("\n" + "=" * 74)
    if failures:
        print("SELFTEST FAILED -- this gate cannot be trusted:")
        for f in failures:
            print("  -", f)
        return 1
    print("SELFTEST PASSED -- the gate rejects the known-bad answer")
    return 0


def ask_local(question: str) -> dict:
    r = si.answer(question)
    return {"answer": r["answer"], "outcome": r["outcome"],
            "grounded": bool(r.get("grounded")), "best_score": r.get("best_score"),
            "leaks": r.get("leaks"), "voice_violations": r.get("voice_violations"),
            "retry_violations": r.get("retry_violations")}


def ask_remote(base_url: str, question: str) -> dict:
    req = urllib.request.Request(
        base_url.rstrip("/") + "/api/standing-interview/ask",
        data=json.dumps({"question": question}).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run(base_url: str | None) -> int:
    # Never report a green suite from a gate that has not just proven it can go
    # red. This costs no model calls and takes milliseconds.
    if selftest() != 0:
        return 1

    where = base_url or "local corpus + local model"
    print("=" * 74)
    print("STANDING INTERVIEW ACCEPTANCE --", where)
    print("=" * 74)

    if base_url:
        status = json.loads(urllib.request.urlopen(
            base_url.rstrip("/") + "/api/standing-interview/status", timeout=60
        ).read().decode("utf-8"))
    else:
        status = si.corpus_status()
    print("status:", json.dumps(status))
    if not status.get("loaded"):
        print("\nFAIL: the corpus is not loaded -- nothing below can be trusted.")
        return 1

    failures = []
    for label, cases in (("REGRESSION EXAM", CASES), ("UNSEEN ON-BOOK CHECKS", UNSEEN_CASES)):
      print("\n" + "#" * 74)
      print("#", label, "--", len(cases), "questions")
      print("#" * 74)
      for question, must_answer, extra, want_first_person in cases:
        r = ask_remote(base_url, question) if base_url else ask_local(question)
        text, outcome = r.get("answer", ""), r.get("outcome")
        print("\n" + "-" * 74)
        print("Q :", question)
        print("  outcome:", outcome, " grounded:", r.get("grounded"),
              "" if r.get("best_score") is None else " best=%.4f" % r["best_score"])
        print("  A:", text.replace("\n", " ")[:400])

        bad = []
        if must_answer:
            if outcome != "answered":
                detail = ""
                if r.get("leaks"):
                    detail = f" leaks={r['leaks']}"
                elif r.get("voice_violations"):
                    detail = (f" voice={r['voice_violations']}"
                              f" retry={r.get('retry_violations')}")
                bad.append(f"MUST ANSWER but outcome={outcome}{detail}")
            else:
                bad += extra(text) if extra else []
                bad += _check_voice(text)
                # A leak in a shipped answer is a hard failure, not a warning.
                found = si.leaks(text)
                if found:
                    bad.append(f"leaked source identifier: {found}")
                if want_first_person and not _first_person(text):
                    bad.append("not written in first person")
        else:
            if outcome not in ("ungrounded", "ungrounded_model_declined", "private_topic"):
                bad.append(f"MUST REFUSE but outcome={outcome}")
            if text.strip() != si.REFUSAL:
                bad.append("refusal text is not the standard single line")
            if _any(text, "paris"):
                bad.append("answered from world knowledge")

        if bad:
            for b in bad:
                print("  FAIL:", b)
            failures.append((question, bad))
        else:
            print("  OK")

    print("\n" + "=" * 74)
    total = len(CASES) + len(UNSEEN_CASES)
    if failures:
        print("ACCEPTANCE FAILED --", len(failures), "of", total, "questions")
        for q, bad in failures:
            print("  *", q)
            for b in bad:
                print("      -", b)
        return 1
    print("ACCEPTANCE PASSED --", total, "of", total, "questions",
          f"({len(CASES)} exam + {len(UNSEEN_CASES)} unseen)")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", default=None,
                    help="deployed host; omit to run against the local corpus")
    ap.add_argument("--selftest", action="store_true",
                    help="only assert the gate rejects the known-bad answer")
    args = ap.parse_args()
    sys.exit(selftest() if args.selftest else run(args.base_url))
