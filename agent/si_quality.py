"""Answer-quality oracle for the Standing Interview.

Why this file exists
--------------------
The 2026-09-29 SI audit (docs/audits/SI_AUDIT_2026-09-29.md) established two
facts that together explain how a 117/117-green sprint shipped answers the
Owner rejected:

  * 39% of answered production questions volunteered at least one negative
    nobody asked for -- 38 of them across 22 of 57 answers.
  * Every shipped gate accepted every one of those answers. The leak scan, the
    voice gate, the neighbour check and the acceptance gate all returned empty
    for all six answers the Owner objected to. Nothing in the suite was
    looking at answer quality: 0 of 134 test cases addressed it.

So this module measures the thing the Owner actually complained about. It is
deliberately a SEPARATE oracle from the runtime gates in standing_interview.py
-- a gate that ships inside `answer()` is under pressure to be permissive, and
the audit showed what that produces.

What it checks
--------------
1. UNSOLICITED NEGATIVES (the Owner's complaint). A sentence is a negative if
   it states an absence, a scope limit, a recall limit or an ownership
   disclaimer. It is UNSOLICITED unless the question actually invited it. The
   budget is zero.
2. TENSE. NRG is current employment; BCBSA and Marsh are past. An answer that
   frames NRG in the past tense says he has left a job he still holds. Live
   answers are already correct here, so this is a regression guard.
3. OVER-REFUSAL. Every existing refusal test proves a refusal *happens*; none
   proves a legitimate question is *not* refused. Question m -- "describe a
   technical disagreement and how you resolved it" -- was refused on all three
   production draws while passing every shipped test.

Honest limits, stated rather than buried
----------------------------------------
This is regex-based and shares the convergence problem the audit describes for
the shipped ban list. The difference is that it classifies a RELATION (was
this asked for?) rather than a vocabulary, so the categories stay stable even
where the patterns are incomplete. Its precision was established by hand: the
audit's version produced 45 raw hits over 63 real answers, all 45 were
inspected individually, and 7 were its own false positives. The two hardenings
that inspection produced ARE applied here (see `_is_product_refusal` and the
`outcome` guard). Its RECALL is still UNVERIFIED -- it has never been measured
against an Owner-labelled key, because none exists yet. Treat a clean result
as "no known-bad shape found", never as "this answer is good".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Sentence segmentation
# --------------------------------------------------------------------------
# Deliberately simple. The audit's taxonomy is sentence-scoped, and a
# paragraph-scoped check is exactly the mistake that let two seeded mutations
# through in Sprint 14: a negation buried in a long block was excluded
# wholesale because the block as a whole looked fine.
_ABBREV = re.compile(r"\b(?:e\.g|i\.e|etc|vs|Mr|Mrs|Dr|Inc|Ltd|Co)\.$", re.I)


def split_sentences(text: str) -> list[str]:
    """Split prose into sentences without swallowing decimals or abbreviations."""
    if not text:
        return []
    # Protect decimals (0.39) and version numbers (v5.50.2) from the splitter.
    guarded = re.sub(r"(\d)\.(\d)", r"\1<DOT>\2", text)
    parts = re.split(r"(?<=[.!?])[\s\n]+", guarded)
    out: list[str] = []
    for part in parts:
        piece = part.replace("<DOT>", ".").strip()
        if not piece:
            continue
        if out and _ABBREV.search(out[-1]):
            out[-1] = out[-1] + " " + piece
        else:
            out.append(piece)
    return out


# --------------------------------------------------------------------------
# The four negative categories (Appendix C, carried forward)
# --------------------------------------------------------------------------
ABSENCE = "ABSENCE"
SCOPE_LIMIT = "SCOPE_LIMIT"
RECALL_LIMIT = "RECALL_LIMIT"
OWNERSHIP_DISCLAIMER = "OWNERSHIP_DISCLAIMER"

_NEG_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (ABSENCE, re.compile(
        r"\b(did ?n[o']t|didn.t|never|no|wasn.t|weren.t|was not|were not)\s+"
        r"(\w+\s+){0,3}(use|used|using|part of|in the stack|involved|come up|there)\b", re.I)),
    (ABSENCE, re.compile(
        r"\b(wasn.t|was not|isn.t|is not|weren.t)\s+(\w+\s+){0,3}(part of|in|on)\s+"
        r"(the|that|my|our)\s+(stack|system|platform|estate|project)\b", re.I)),
    (ABSENCE, re.compile(r"\bno\s+\w+\s+(at|in|on)\s+(NRG|BCBSA|Marsh)\b", re.I)),
    (SCOPE_LIMIT, re.compile(
        r"\bI\s+(did ?n[o']t|didn.t|was ?n[o']t|wasn.t)\s+(\w+\s+){0,3}"
        r"(administer|set up|own|run|operate|configure|manage|design|handle|do)\b", re.I)),
    (SCOPE_LIMIT, re.compile(
        r"\b(outside|beyond)\s+(what|the scope of what)\s+I\s+(touched|did|owned|worked)", re.I)),
    (SCOPE_LIMIT, re.compile(
        r"\b(someone else.s responsibility|handled by others|was not mine|wasn.t mine|"
        r"not my (job|responsibility)|that side was outside)\b", re.I)),
    (RECALL_LIMIT, re.compile(
        r"\bI\s+(do ?n[o']t|don.t|can.t|cannot|could ?n[o']t|couldn.t)\s+"
        r"(\w+\s+){0,3}(have|remember|recall|retain|speak to|tell you|say)\b", re.I)),
    (RECALL_LIMIT, re.compile(r"\bI\s+don.t\s+have\b", re.I)),
    (OWNERSHIP_DISCLAIMER, re.compile(
        r"\b(came from the (technical )?architect|rather than owning it|"
        r"implementing within that design|implemented within that design|"
        r"I was implementing within|within a design (that )?(a|the) (lead|architect))\b", re.I)),
]

# --------------------------------------------------------------------------
# Hardening 1: the product's own refusal lines are not model misbehaviour
# --------------------------------------------------------------------------
# Six of the audit detector's 45 raw hits were the product's standard refusal
# line on rows that were never answered, and one was question r's correct
# prompt-injection refusal. Counting a correct refusal as a quality defect
# would push the system toward answering things it should decline -- the exact
# opposite of what is wanted.
_PRODUCT_REFUSAL_MARKERS = (
    "i don't have anything recorded",
    "i don't have that recorded",
    "isn't something i have recorded",
    "not something i've recorded",
    "i'm not going to share",
    "i won't share",
    "that's not something i'll discuss",
    "outside what this interview covers",
    "i'd rather discuss that directly",
    # Question r's correct prompt-injection refusal. The audit's detector
    # counted this as a quality defect; it is the opposite -- the system
    # refusing to leak on demand is it working.
    "private notes to hand over",
    "not internal instructions",
    "my answers here are meant to reflect actual work experience",
)


def _is_product_refusal(sentence: str) -> bool:
    low = sentence.lower()
    return any(marker in low for marker in _PRODUCT_REFUSAL_MARKERS)


# --------------------------------------------------------------------------
# Was the negative actually invited by the question?
# --------------------------------------------------------------------------
# The audit hard-coded the solicited questions as {n, o, v}. A shipped gate
# cannot do that -- it sees questions it has never been shown -- so this is
# computed from the question text instead.

# "Have you used Terraform?", "Do you have experience with Docker?": a yes/no
# capability probe, where delimiting the experience IS the answer.
#
# This must be anchored to a leading auxiliary verb. A first attempt also
# matched the bare phrase "experience with", which silently swallowed
# "explain your experience with Kafka" -- one of the six answers the Owner
# objected to -- and excused its volunteered absence as solicited. The test
# that names the specific offending sentences is what caught it. An
# open-ended "explain/tell me about/describe" question is NOT a probe.
_CAPABILITY_PROBE = re.compile(
    r"^\s*(have|has|had|do|does|did|are|is|was|were|can|could|ever)\s+you\b", re.I)

# Questions that ask about a limit outright.
_ASKS_LIMIT = re.compile(
    r"\b(limitation|limitations|weakness|weaknesses|gap|gaps|shortcoming|"
    r"what\s+(don.t|do not|didn.t|did not|can.t|cannot|haven.t|have not)\s+you|"
    r"what\s+are\s+you\s+not|gotchas?|drawback)\b", re.I)

# Questions that ask about ownership or scope directly.
_ASKS_OWNERSHIP = re.compile(
    r"\b(did you (own|design|architect|build it yourself)|was (it|that) yours|"
    r"whose (design|decision|call)|who (owned|designed|decided)|"
    r"how much of (it|that) (was|did) you|what was your (role|part|contribution)|"
    r"were you responsible)\b", re.I)

# Questions that invite a recall limit.
_ASKS_RECALL = re.compile(
    r"\b(do you remember|can you recall|how well do you remember)\b", re.I)

# Does the sentence talk about the speaker's own experience, rather than
# stating a neutral fact about a system? Used to keep architectural
# descriptions out of the ABSENCE category.
_ABOUT_SPEAKER = re.compile(
    r"\b(I|I'm|I've|I'd|my|we|we're|we've|our|us|NRG|BCBSA|Marsh)\b")


def _question_subjects(question: str) -> set[str]:
    """Technology/employer tokens the question is actually about.

    Used to separate "you asked about Kafka and I'm telling you I didn't use
    it" (a direct answer) from "you asked about Kafka and I'm volunteering
    that I also didn't use it at two other employers" (unsolicited).
    """
    tokens = re.findall(r"\b[A-Za-z][A-Za-z0-9+./#-]{1,}\b", question or "")
    stop = {
        "what", "how", "why", "when", "where", "who", "which", "tell", "me",
        "about", "your", "you", "did", "do", "does", "have", "has", "was",
        "were", "is", "are", "the", "a", "an", "at", "in", "on", "with", "of",
        "and", "or", "for", "to", "from", "it", "that", "this", "explain",
        "describe", "walk", "through", "any", "experience", "work", "worked",
        "working", "use", "used", "using", "ever", "some", "more", "detail",
        "right", "now", "still", "my", "our", "their", "his", "her", "them",
    }
    return {t.lower() for t in tokens if t.lower() not in stop and len(t) > 2}


def _mentions_subject(sentence: str, subjects: set[str]) -> bool:
    low = sentence.lower()
    return any(re.search(r"\b" + re.escape(s) + r"\b", low) for s in subjects)


@dataclass
class Negative:
    category: str
    sentence: str
    solicited: bool
    reason: str


@dataclass
class QualityReport:
    question: str
    outcome: str
    negatives: list[Negative] = field(default_factory=list)
    tense_errors: list[str] = field(default_factory=list)
    over_refusal: str | None = None

    @property
    def unsolicited(self) -> list[Negative]:
        return [n for n in self.negatives if not n.solicited]

    @property
    def solicited(self) -> list[Negative]:
        return [n for n in self.negatives if n.solicited]

    @property
    def ok(self) -> bool:
        return not self.unsolicited and not self.tense_errors and not self.over_refusal

    def describe(self) -> str:
        bits = []
        for n in self.unsolicited:
            bits.append(f"    [{n.category}] {n.sentence[:120]}")
        for t in self.tense_errors:
            bits.append(f"    [TENSE] {t[:120]}")
        if self.over_refusal:
            bits.append(f"    [OVER-REFUSAL] {self.over_refusal}")
        return "\n".join(bits)


# --------------------------------------------------------------------------
# Tense
# --------------------------------------------------------------------------
# NRG is current employment; BCBSA and Marsh are past. Only EMPLOYMENT framing
# is checked -- "At NRG I built the retry handler" is correct past tense for a
# finished task and must not be flagged. "I worked at NRG" is not: it says he
# has left a job he still holds.
_NRG_PAST = re.compile(
    r"\b(I\s+worked\s+at\s+NRG|when\s+I\s+was\s+at\s+NRG|my\s+time\s+at\s+NRG|"
    r"I\s+used\s+to\s+work\s+at\s+NRG|during\s+my\s+time\s+at\s+NRG|"
    r"I\s+was\s+at\s+NRG|while\s+I\s+was\s+at\s+NRG)\b", re.I)
_PAST_EMPLOYER_PRESENT = re.compile(
    r"\b(I\s+(work|am\s+working)\s+at\s+(BCBSA|Marsh)|"
    r"I\s+currently\s+\w+\s+at\s+(BCBSA|Marsh)|"
    r"my\s+current\s+role\s+at\s+(BCBSA|Marsh))\b", re.I)


def _tense_errors(answer: str) -> list[str]:
    errors = []
    for sentence in split_sentences(answer):
        if _NRG_PAST.search(sentence):
            errors.append(f"NRG framed as past employment: {sentence}")
        if _PAST_EMPLOYER_PRESENT.search(sentence):
            errors.append(f"past employer framed as current: {sentence}")
    return errors


# --------------------------------------------------------------------------
# Over-refusal
# --------------------------------------------------------------------------
# A legitimate interview question that the system declined. The audit found
# question m refused on all three draws while passing every shipped test,
# because every refusal test asserts that a refusal HAPPENS and none asserts
# that a fair question is answered.
_MUST_ANSWER = re.compile(
    r"\b(technical disagreement|disagreement|mentor|mentoring|guide other|"
    r"production incident|incident you|concurrency|code review|"
    r"proudest|hardest (bug|problem)|biggest challenge|trade-?off)\b", re.I)

_LEGITIMATE_DECLINES = {"private_topic", "leak_blocked"}


def _over_refusal(question: str, outcome: str) -> str | None:
    if outcome == "answered":
        return None
    if outcome in _LEGITIMATE_DECLINES:
        return None
    if _MUST_ANSWER.search(question or ""):
        return (f"a legitimate interview question was not answered "
                f"(outcome={outcome}): {question}")
    return None


# --------------------------------------------------------------------------
# The oracle
# --------------------------------------------------------------------------
def assess(question: str, answer: str, outcome: str = "answered") -> QualityReport:
    """Score one answer. `outcome` is the SI's own recorded outcome."""
    report = QualityReport(question=question, outcome=outcome)
    report.over_refusal = _over_refusal(question, outcome)

    # Hardening 2: only answered rows are scored for negatives. A refusal is
    # supposed to say "no"; counting that as a quality defect would push the
    # system toward answering what it should decline.
    if outcome != "answered":
        return report

    report.tense_errors = _tense_errors(answer)

    subjects = _question_subjects(question)
    asks_limit = bool(_ASKS_LIMIT.search(question or ""))
    is_probe = bool(_CAPABILITY_PROBE.search(question or ""))
    asks_ownership = bool(_ASKS_OWNERSHIP.search(question or ""))
    asks_recall = bool(_ASKS_RECALL.search(question or ""))

    for sentence in split_sentences(answer):
        if _is_product_refusal(sentence):
            continue
        for category, pattern in _NEG_PATTERNS:
            if not pattern.search(sentence):
                continue
            # The Owner's complaint is about answers that talk down the
            # SPEAKER. A neutral architectural fact -- "that layer is REST
            # only, no GraphQL there" -- is a description of a system, not a
            # volunteered limitation, and flagging it would push the answers
            # toward vagueness about how things were actually built.
            if category == ABSENCE and not _ABOUT_SPEAKER.search(sentence):
                continue

            solicited, reason = False, "nobody asked"
            if asks_limit:
                solicited, reason = True, "the question asked about a limit"
            elif is_probe:
                # "Do you have experience with Docker?" -- the answer's whole
                # job is to delimit that experience, so every category counts
                # as invited. This is the audit's hard-coded {n, o, v}
                # exemption, computed from the question instead of listed.
                solicited, reason = True, "yes/no capability probe"
            elif category in (SCOPE_LIMIT, OWNERSHIP_DISCLAIMER) and asks_ownership:
                solicited, reason = True, "the question asked about ownership"
            elif category == RECALL_LIMIT and asks_recall:
                solicited, reason = True, "the question asked about recall"

            report.negatives.append(
                Negative(category=category, sentence=sentence,
                         solicited=solicited, reason=reason))
            break  # one category per sentence, matching the audit's counting

    return report
