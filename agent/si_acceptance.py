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
    if not (_any(text, "nrg") and _any(text, "absence", "wasn't used", "was not used",
                                       "no kafka", "not used", "zero")):
        bad.append("does not state the confirmed Kafka absence at NRG")
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
    if not _any(text, "no kafka", "wasn't", "was not", "absence", "not used", "zero"):
        bad.append("does not state the absence")
    if not _any(text, "sqs"):
        bad.append("does not name the real async mechanism (SQS)")
    return bad


def _check_spring_security_nrg(text):
    bad = _all(text, "spring security")
    bad = [f"missing {b}" for b in bad]
    if not _any(text, "jwt", "filter", "access control"):
        bad.append("no hands-on detail (JWT filter / access control)")
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
    ("What is the capital of France?", False, None, False),
]


def ask_local(question: str) -> dict:
    r = si.answer(question)
    return {"answer": r["answer"], "outcome": r["outcome"],
            "grounded": bool(r.get("grounded")), "best_score": r.get("best_score"),
            "leaks": r.get("leaks")}


def ask_remote(base_url: str, question: str) -> dict:
    req = urllib.request.Request(
        base_url.rstrip("/") + "/api/standing-interview/ask",
        data=json.dumps({"question": question}).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run(base_url: str | None) -> int:
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
    for question, must_answer, extra, want_first_person in CASES:
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
                bad.append(f"MUST ANSWER but outcome={outcome}"
                           + (f" leaks={r['leaks']}" if r.get("leaks") else ""))
            else:
                bad += extra(text) if extra else []
                # A leak in a shipped answer is a hard failure, not a warning.
                found = si.leaks(text)
                if found:
                    bad.append(f"leaked source identifier: {found}")
                if want_first_person and not _first_person(text):
                    bad.append("not written in first person")
        else:
            if outcome not in ("ungrounded", "ungrounded_model_declined"):
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
    if failures:
        print("ACCEPTANCE FAILED --", len(failures), "of", len(CASES), "questions")
        for q, bad in failures:
            print("  *", q)
            for b in bad:
                print("      -", b)
        return 1
    print("ACCEPTANCE PASSED --", len(CASES), "of", len(CASES), "questions")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", default=None,
                    help="deployed host; omit to run against the local corpus")
    args = ap.parse_args()
    sys.exit(run(args.base_url))
