"""
Standing Interview v0 -- grounded, first-person interview answers.

WHAT THIS IS
A typed question in, a typed first-person answer out, generated ONLY from
text retrieved out of the private knowledge corpus. No audio. The person
asking sees the answer and nothing else -- never a source name, never a file
path, never "according to <source>", never internal vocabulary.

WHY IT DOES NOT REUSE ask_codebase.py
ask_codebase.py documents as a security property that "there is no code path
from a query string to any file outside CORPUS_DOCUMENTS, let alone outside
the repository". Standing Interview deliberately answers from a DIFFERENT,
private corpus. Rather than weaken that guarantee, this module keeps its own
isolated corpus, its own loader and its own search. The two surfaces have
opposite postures on purpose, and neither can reach the other's material.

THREE THINGS THAT ARE ENFORCED IN CODE, NOT ONLY IN THE PROMPT
1. NO CORPUS -> NO ANSWER. If the corpus file is missing (e.g. the container
   was deployed without it), this refuses and says the knowledge base is not
   loaded. It must never fall back to the model's own world knowledge, which
   is exactly how a system like this starts inventing employment history.
2. NOTHING RETRIEVED -> NO ANSWER. Below the grounding threshold the question
   is refused and logged, rather than answered thinly.
3. LEAKED SOURCE IDENTIFIERS -> ANSWER REJECTED. A deterministic scan runs on
   the generated text. A prompt instruction alone is not a control; this
   project has repeatedly found that only the deterministic gate holds.

Model-id mismatch between the corpus vectors and the runtime embedder is
treated as no corpus at all -- comparing vectors across models produces
confident nonsense, which is worse than a refusal.

SPRINT 13 (BL-090): THREE MECHANISMS SO ANY ON-BOOK QUESTION IS ANSWERABLE
Sprints 11-12 fixed the questions the Owner had logged. They did not change
why a question the Owner had NOT logged could still refuse or read like a
search report. Three things are added, and none of them is an exam answer:
  (A) A STANDING CAREER MAP -- a first-person brief derived from the private
      books at corpus-build time -- is placed in front of the model on every
      generate, so orientation (who, where, what, when) never depends on
      which six chunks happened to score highest. A corpus without a map is
      treated as no corpus (see load_corpus).
  (B) QUERY REWRITE before retrieval translates interviewer English into the
      words the books actually use ("multithreading" -> CompletableFuture,
      ExecutorService, parallel, fan-out). Every expansion term was taken
      from book wording; none from the public web.
  (C) ONLY WHERE YOU USED IT. The hands-on books each end in a technology
      attribution matrix ("Personal classification: HANDS-ON / NOT USED").
      The corpus builder parses it, and this module uses it to decide which
      employer LEADS a generic answer and which employers get no paragraph at
      all -- deterministically, before the model sees anything. Sprint 11's
      employer balancing remains the fallback when the matrix has no row.
"""

import json
import math
import os
import pathlib
import re

# SI-04 (Sprint 15). The answer-quality oracle. It is imported rather than
# reimplemented so the runtime voice gate and the test suite that scores
# production answers cannot drift apart -- the previous phrase-list version of
# this rule passed every one of the six answers the Owner rejected.
import si_quality

# Loads agent/.env's ANTHROPIC_API_KEY into the process environment. Same
# recurrence as the 2026-09-14 backend_planning.py bug in docs/LESSONS.md:
# reasoning_gateway.py reads ANTHROPIC_API_KEY from os.environ but does NOT
# load .env itself, and this module is reached both through web_server.py
# (which gets the load for free via event_ledger's import side effect) and
# directly from a CLI/replay harness (which does not). Without this, a local
# replay of a real question returns outcome="no_model" -- an honest denial,
# but one that looks identical to "the corpus answered nothing" in a trace and
# hid the real Sprint 11 traces on the first run. Production on Railway is
# unaffected either way; the env var is injected by the platform there.
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:                                  # dotenv absent -> rely on
    pass                                           # the real environment

CORPUS_PATH = pathlib.Path(__file__).resolve().parent / ".si_corpus" / "corpus.json"

# Below this cosine score nothing is considered grounded.
# MEASURED against the real 361-chunk corpus on 2026-09-27, not guessed:
#   "How did you use Spring Security at NRG?"   -> 0.6915  (answerable)
#   "How does your RAG retrieval work?"         -> 0.7067  (answerable)
#   "What is the capital of France?"            -> 0.4491  (must refuse)
# bge-small returns ~0.45 cosine even for unrelated text, so the original 0.34
# admitted everything. 0.50 sits between the observed populations.
#
# The threshold ALONE is not sufficient and was never going to be: a private
# question ("what is Karthik's home address and salary?") scored 0.6816,
# because the words match career text even though the answer is not in it.
# That is what DECLINE_MARKERS below exist for.
GROUNDING_THRESHOLD = 0.50
TOP_K = 6

# This is a SAFETY NET against a mid-sentence cut-off, not the length control
# -- the prompt asks for 6-10 spoken lines, which is about 250 tokens. 400 was
# the old value and it truncated real multi-employer answers. Raised
# deliberately well above the target so that an over-long answer fails the
# gate's word count (informative: "reads as an essay") instead of failing as a
# truncation (ambiguous: was it too long, or did the budget run out?).
MAX_ANSWER_TOKENS = 1000

# The second, stronger gate. When the model has the excerpts in front of it and
# still says it cannot answer, that is the most reliable ungrounded signal
# available -- better than any cosine number, because it is a judgement about
# the actual retrieved text rather than about vector distance. Treat it as a
# refusal: emit the standard line and LOG it, instead of shipping a polite
# non-answer that never reaches the review queue.
DECLINE_MARKERS = (
    "i don't have", "i do not have", "i don't know", "i do not know",
    "not something i", "i can't speak to that", "i cannot speak to that",
    "isn't something i", "is not something i", "not covered in my",
    "i haven't worked", "i have not worked", "no detail on that",
    # Sprint 13, from a real gate run: the model DEFLECTED a private question
    # ("I'm not going to share my home address in this context, but happy to
    # talk through salary...") -- a polite non-answer that is not a refusal
    # and never reached the review queue. These are the shapes it used.
    "i'm not going to share", "i am not going to share", "i won't share",
    "i will not share", "i'd rather not", "i would rather not",
    "i'm not able to share", "i am not able to share", "not something i'd share",
)

# Sprint 13: PRIVATE TOPICS ARE REFUSED BEFORE THE MODEL IS CALLED. The Owner's
# goal statement says private secrets must refuse; the grounding threshold
# cannot do that (career words score well against career text -- the salary
# question scored 0.5725), and the decline gate only sees what the model chose
# to say. A deterministic gate is the control. Kept narrow on purpose:
# compensation, contact details, identity documents, age and family. It does
# NOT cover work authorisation or location, which a recruiter may legitimately
# need and which the Owner has left as an open decision.
_PRIVATE_TOPIC = re.compile(
    r"\b(salary|salaries|compensation|pay\s*(rate|range|expectation)|day\s*rate|"
    r"hourly\s*rate|how much (do|did|would) you (earn|make|charge)|"
    r"home\s*address|street\s*address|postal\s*(code|address)|zip\s*code|"
    r"phone\s*number|mobile\s*number|whatsapp|personal\s*e-?mail|"
    r"passport|national\s*id|social\s*security|tax\s*(id|number)|"
    r"date\s*of\s*birth|birthday|how\s*old\s*are\s*you|your\s*age\b|"
    r"marital|married|spouse|wife|husband|children|kids|religion|caste)\b", re.I)


def is_private_topic(question: str) -> bool:
    return bool(_PRIVATE_TOPIC.search(question or ""))


def _model_declined(text: str) -> bool:
    """True when the answer IS a refusal, not when it merely contains an honest
    caveat.

    Checked against the FIRST SENTENCE only. An earlier version scanned the
    first 160 characters and over-fired on a genuinely good answer that ended
    "...and wired it into the aggregator services. I don't have the exact
    key-rotation detail though." -- which is precisely the tone the system
    prompt asks for. Turning that into a refusal would punish the honesty the
    whole surface is built on. Caught by this module's own test before it
    shipped."""
    head = text.strip().lower()
    first = re.split(r'(?<=[.!?])\s', head, maxsplit=1)[0][:200]
    return any(m in first for m in DECLINE_MARKERS)

# The single standard refusal. One short line, no lecture, no hint about what
# the corpus does or does not contain -- a refusal that explains itself in
# detail is an information leak and it also reads badly in an interview.
# Sprint 15: "a grounded answer" is retrieval vocabulary, not something a
# person says in an interview -- and this line is what a recruiter sees, so it
# is the one sentence on the surface most likely to read as a machine. It also
# used to open on "I don't have", which is the shape the answers were being
# corrected away from everywhere else.
REFUSAL = ("That's not something I've got a specific example of to hand. Ask me "
           "about the backend systems I've worked on, or about the AI delivery "
           "platform I built.")
NO_CORPUS = ("The knowledge base isn't loaded on this instance, so I can't answer "
             "from it. I won't guess.")

SYSTEM_PROMPT = """You are answering interview questions AS Karthik, in first person.

ABSOLUTE RULES
- Use ONLY the supplied excerpts and the WHO YOU ARE summary below. If they do
  not support an answer, say you don't have that detail. Never use general knowledge about any company,
  technology or person. Never infer or embellish.
- Never mention where the information came from. No source names, no document
  or book titles, no chapter or section numbers, no file paths, no phrases
  like "according to", "the document says", "my notes", "the corpus", "the
  excerpt". Just answer as someone who did the work and remembers it.
- Never overstate your own involvement. If the excerpts say something was a
  system-level fact rather than your personal work, describe what you did
  rather than claiming the whole: "I implemented the filter against the
  platform's token flow" is the shape. That is a ban on OVERCLAIMING, not an
  instruction to DISCLAIM -- do not volunteer "I didn't design that" unless
  the sentence would otherwise read as a claim that you did.
- Never state a date, employer, title or metric that is not in the excerpts.
- When the excerpts or your standing summary describe something as the team's
  work or in the passive ("the call was parallelized"), say it that way -- "we
  parallelized it" -- and do not convert it into "I rewrote it". Say "I" only
  where the material says you personally did it.
- Answer the technology that was asked about. Do not bring in a neighbouring
  technology from the same job (a data format, a database, a framework) unless
  the answer cannot be explained without it. Asked about Kafka:
    Not: "keeping the FHIR-normalized data layer current"
    Not: "the services were DB2-backed"
    Say: "keeping the downstream data current as changes landed"
  The interviewer asked about one thing; name the others only if they ask.
- Never name a file, module, path or extension. Describe what the code does,
  not what it is called.

ONE EMPLOYER AT A TIME
Each excerpt is labelled with the employer it belongs to. Attribute every
claim to the employer whose excerpt it came from, and never blend two
employers' systems into one description -- if two employers solved the same
problem differently, that is two separate statements, not an average.

LEAD WITH WHERE YOU ACTUALLY USED IT
When the question names no employer ("explain your experience with X"), start
with the employer where you actually did hands-on work with X, whichever one
that is -- NOT the most recent one, and never with a place that did not use
it. Give that employer the answer. Do NOT close by touring the employers
where it did not come up -- that was not asked, and it turns a confident
answer into a coverage report. Name another employer only when the question
asks across your career AND the answer is incomplete without it.

When the question DOES name one employer, answer only about that employer.

ONLY WHERE YOU USED IT
Some questions arrive with a line that begins "Your own record says". It names
the employer(s) where the work actually happened and the employer(s) where it
was not used. Lead with the first employer it names and give that employer the
answer. Do not give a paragraph to an employer it marks as not used, and do not
mention an employer it does not name at all. An employer marked "not used" is
a CONSTRAINT on what you may claim, not a fact to recite: say nothing about it
unless the question names that employer. Never tour every employer.

LEAVE OUT AN EMPLOYER YOU HAVE NOTHING TO SAY ABOUT
If the excerpts for one employer contain nothing substantive about the
question, do not give that employer a paragraph at all. A paragraph whose
content is "at X I don't have the detail on how that worked" is worse than
silence: it spends the interviewer's attention on nothing and it makes the
whole answer read as a coverage report. Two employers answered well beats
three employers listed.

ANSWER THE QUESTION THAT WAS ASKED, AND STOP
State the hands-on work plainly. Then stop.

Do NOT volunteer a limitation. Not what you did not set up, not what you do
not remember, not what someone else ran, not what a different employer did not
use. None of that was asked for, and an answer that reaches for it sounds like
someone arguing against themselves.

There are exactly three times a limit belongs in an answer:
  1. The question asks for one ("have you used X", "what are your gaps").
  2. Leaving it out would imply something false -- you would be taken to have
     built or owned something you did not.
  3. The interviewer has asked a follow-up that needs it.
Outside those three, the correct number of volunteered limitations is ZERO.

This is not a budget to spend. A previous version of this instruction asked
for "the boundary in one sentence" and allowed "at most one sentence about
something you cannot recall"; measured against 57 real production answers,
that produced 37 volunteered negatives across 21 of them, because a permitted
sentence reads as a required one. If the question does not ask, write none.

When rule 2 does apply, it is one clause inside a sentence about the work --
"I wrote the producer and consumer code against those topics" -- not a
sentence, not a paragraph, and never the closing line. Never open with one.

NEVER SAY, BECAUSE A PERSON DOES NOT TALK LIKE THIS
Nothing about how you looked the answer up. No "census", no "zero hits", no
"keyword hits", no "confirmed absence", no "no genuine evidence", no "the
evidence shows", no explaining that something was a false positive. You are
remembering your own work out loud. "We didn't use Kafka there" is how a
person says it.

Some excerpts are written in audit language and record an absence as "no
genuine evidence of X", "confirmed absence", "zero hits". That is the wording
of a record, not the wording of a person. Translate it: "we didn't use X
there", or "X wasn't part of that stack". Never repeat the audit phrasing back
-- it is the single clearest tell that the answer is being read rather than
remembered.

NEVER STATE A DETAIL THE EXCERPTS DO NOT CONTAIN, and be most careful with the
plausible ones: a partition key, a delivery guarantee, a schema registry, a
retry policy, an exact count of scheduled jobs. If it is not in front of you,
it did not happen.

TWO THINGS THIS MATERIAL WILL TEMPT YOU INTO. Say neither.
  Not: "SQS plus a dead-letter queue and one scheduled cron job."
  Say: "SQS with a dead-letter queue, and some scheduled jobs."
The exact number of cron jobs is not something you would recall in a room, and
it is not in the hands-on record.
  Not: "JMS turned up but it was a false positive, just a substring match
       inside base64 tokens."
  Say: "We didn't use JMS either."
How a fact was established is never part of remembering your own project. If
you find yourself explaining why something LOOKED true but wasn't, stop and
just say what was actually used.

AND WHEN THE WHOLE ANSWER IS AN ABSENCE. Sometimes the honest answer is that
you did not use the thing at all. That answer is short, and it is finished as
soon as you have said what you DID use instead.
  Not: "Kafka is a confirmed absence at NRG - zero keyword hits across the
       full codebase census."
  Say: "We didn't use Kafka at NRG. The async work there ran on SQS with a
       dead-letter queue and some scheduled jobs, and that was enough for what
       we were doing."
Do not reach for the record's vocabulary just because there is no story to
tell. "We didn't use it" is a complete, confident answer.

SOME EXCERPTS ARE PREPARATION MATERIAL, NOT MEMORY. An excerpt may be written
as a practice question with a model answer, or as a list of general concerns a
technology raises, or as a note about what is and is not known. None of that
is your experience and none of it is a thing you did. Use such an excerpt only
for the plain facts it states about your work, and never repeat its theory,
its checklists or its question-and-answer framing. Concretely: do NOT recite
general messaging concepts -- delivery guarantees, duplicate handling,
ordering keys, schema registries, idempotency -- as if they were part of what
you built. An interviewer asks about the things you touched; volunteering
textbook material reads as covering for not having done the work, and it is
also the fastest way to state something that is not true.

NEVER CLAIM TO HAVE OWNED THE ARCHITECTURE. "I designed the overall
architecture" is not something you would say. Describe what you built instead:
"I implemented the filter against the platform's token flow" is the shape.

That is a ban on overclaiming, NOT an instruction to disclaim. Do not
volunteer that a lead or an architect owned the design -- saying what you
built already says what you built, and adding "though the architecture came
from the architect" hands away credit nobody asked you to give up. Name the
architect's ownership only if the question asks who designed it, or if the
sentence would otherwise read as a claim that you did.

LENGTH
Six to ten spoken lines. Always finish the final sentence.

STYLE
Short. Spoken, not written. First person. Two to five sentences for most
questions -- for a multi-employer answer, two to three sentences per employer.
No bullet lists, no headings, no markdown. Plain sentences, the way you would
actually say it in a room."""

# Deterministic post-generation leak scan. Prompt instructions are advisory;
# this is the control.
_LEAK_PATTERNS = [
    re.compile(r'\bbook[\s\-]*(0?\d|one|two|three|four|five|six|seven|eight)\b', re.I),
    re.compile(r'\bBOOK-\d', re.I),
    re.compile(r'according to (the|my|a)\b', re.I),
    # Sprint 13: narrowed to PROVENANCE SENSES. The whole-noun form refused a
    # correct answer about this surface's own retrieval ("runs locally
    # against my own notes", "the knowledge base isn't loaded" is the
    # product's own line). What must still be caught is the answer citing
    # where it read something: "my notes say", "the document describes",
    # "in the corpus". Same shape as the Sprint 11 `source` narrowing below.
    re.compile(r'\b(the|my|our) (document|corpus|excerpt|notes|knowledge base|material)s?\s+'
               r'(say|says|said|state|states|mention|mentions|indicate|indicates|'
               r'note|notes|describe|describes|show|shows|suggest|suggests|record|records|'
               r'list|lists|contain|contains|include|includes|confirm|confirms|cover|covers|'
               r'hold|holds|discuss|discusses|address|addresses|document|documents|reflect|reflects|'
               r'have|has|had|got|keep|keeps|kept|give|gives|gave|put|puts|call|calls|'
               r'tell|tells|explain|explains)\b', re.I),
    re.compile(r'\b(in|per) (the|my) (document|corpus|excerpt|notes)s?\b', re.I),
    # 'excerpt' has no interview sense at all -- it exists only because of the
    # prompt -- so any determiner + excerpt stays an unconditional leak.
    re.compile(r'\b(the|my|our|this|that|these|those) excerpts?\b', re.I),
    # `source` WAS in the alternation above until Sprint 11. It produced a real
    # false positive on a genuinely good answer: "...without the source service
    # having to synchronously coordinate with every consumer" -- ordinary
    # backend English for the upstream service, zero provenance leakage. That
    # single word silently converted the best generic-Kafka answer the system
    # produces into a refusal, which is exactly what the Owner reported. `source`
    # is kept below only in senses that actually reveal the answer is being read
    # off supplied text; "source service/system/of truth/code/table" no longer
    # trips it. Verified against the real observed sentence in the tests.
    re.compile(r'\b(the|my) sources?\s+'
               r'(say|says|said|state|states|mention|mentions|indicate|indicates|'
               r'note|notes|describe|describes|show|shows|suggest|suggests)\b', re.I),
    re.compile(r'\b(the|my) source (material|document|text|excerpt|passage)s?\b', re.I),
    re.compile(r'\.(docx|md|yaml|json|py)\b', re.I),
    re.compile(r'\b(krishna|vishnu|shiva|rudra|yamaraj|brahma|ganesha|shakti)\b', re.I),
    re.compile(r'\bkarthik-ai-context\b', re.I),
    re.compile(r'(?:[A-Za-z]:)?[\\/](?:books|artifacts|derived|coaching)[\\/]', re.I),
]


# The corpus builder keys the matrix by the registry's employer string; this
# module's EMPLOYER_BOOKS uses the spoken name. One canonical form, resolved
# once at load time, so no comparison anywhere below has to know both.
_CANON_EMPLOYER = {"nrg": "NRG Energy", "nrg energy": "NRG Energy",
                   "bcbsa": "BCBSA", "marsh": "Marsh"}


def canon_employer(name: str | None) -> str | None:
    if not name:
        return None
    return _CANON_EMPLOYER.get(name.strip().lower(), name.strip())


class Corpus:
    def __init__(self, data: dict):
        self.model_id = data.get("model_id")
        self.chunks = data.get("chunks", [])
        self.source_book_hashes = data.get("source_book_hashes", {})
        self.format_version = data.get("format_version", 1)
        self.career_map = (data.get("career_map") or "").strip()
        self.attribution = {canon_employer(k): v
                            for k, v in (data.get("attribution") or {}).items()}

    def __len__(self):
        return len(self.chunks)


def load_corpus(path: pathlib.Path | None = None) -> Corpus | None:
    """Returns None when there is no usable corpus. None is a first-class
    state here, not an error to be swallowed -- the caller must refuse."""
    path = path or CORPUS_PATH
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not data.get("chunks"):
        return None
    # Sprint 13: a corpus without the standing career map is not a corpus.
    # A v1 file left on a container after a partial deploy would otherwise
    # answer without the map and look healthy on the status endpoint.
    if data.get("format_version", 1) < 2 or not (data.get("career_map") or "").strip():
        return None
    return Corpus(data)


# --- routing ----------------------------------------------------------------
# Backend/career questions go to the employer books; AI-platform questions to
# the personal-platform books; anything ambiguous searches both rather than
# guessing wrong and refusing a question that was answerable.
_AI_HINTS = re.compile(
    r'\b(ai|llm|agent|agentic|rag|retriev|embedding|vector|prompt|token|claude|'
    r'anthropic|model|mcp|eval|orchestrat|hallucinat|guardrail|inject)\w*\b', re.I)
_BACKEND_HINTS = re.compile(
    r'\b(spring|java|jpa|hibernate|kafka|oracle|sql|db2|rest|soap|graphql|'
    r'microservice|eureka|jwt|oauth|security|batch|api|endpoint|deploy|'
    r'marsh|bcbsa|nrg|energy|insurance|billing|claim)\w*\b', re.I)


def route(question: str) -> str:
    ai, backend = bool(_AI_HINTS.search(question)), bool(_BACKEND_HINTS.search(question))
    if ai and not backend:
        return "ai"
    if backend and not ai:
        return "career"
    return "both"


# Book -> employer. Verified against the real corpus on 2026-09-27 by counting
# employer mentions per book rather than assumed: BOOK-01/02 are 97/19 Marsh,
# BOOK-03/04 are 109/32 BCBSA, BOOK-05/06 are 77/19 NRG. Ordered NRG first
# (2021-present), then BCBSA, then Marsh -- reverse chronological, which is
# also the order the Owner asked a generic answer to be given in.
EMPLOYER_BOOKS: tuple[tuple[str, frozenset[str]], ...] = (
    ("NRG Energy", frozenset({"BOOK-05", "BOOK-06"})),
    ("BCBSA", frozenset({"BOOK-03", "BOOK-04"})),
    ("Marsh", frozenset({"BOOK-01", "BOOK-02"})),
)

# When the question itself names an employer, retrieval stays pure top-k --
# those questions already produce the answers the Owner asked to keep, and
# balancing them would import material about employers nobody asked about.
_EMPLOYER_NAMED = re.compile(
    r"\b(nrg|bcbsa|blue\s*cross|blue\s*shield|marsh|bluestream|m2\s*broker)\b", re.I)


def employer_for_book(book_id: str) -> str | None:
    for name, books in EMPLOYER_BOOKS:
        if book_id in books:
            return name
    return None


def names_employer(question: str) -> bool:
    return bool(_EMPLOYER_NAMED.search(question))


_EMPLOYER_ALIASES = (("NRG Energy", re.compile(r"\bnrg\b", re.I)),
                     ("BCBSA", re.compile(r"\b(bcbsa|blue\s*cross|blue\s*shield)\b", re.I)),
                     ("Marsh", re.compile(r"\b(marsh|bluestream|m2\s*broker)\b", re.I)))


def named_employers(question: str) -> set[str]:
    """Canonical names of every employer the question mentions."""
    return {name for name, rx in _EMPLOYER_ALIASES if rx.search(question or "")}


def _allowed_books(scope: str) -> set[str] | None:
    if scope == "career":
        return {f"BOOK-0{i}" for i in range(1, 7)}
    if scope == "ai":
        return {"BOOK-07", "BOOK-08"}
    return None                                   # both -> no filter


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def retrieve(question: str, corpus: Corpus, embed_query=None, top_k: int = TOP_K) -> list[dict]:
    """Cosine retrieval over the isolated corpus. Returns [] when the runtime
    embedder disagrees with the corpus's model -- incomparable vectors would
    otherwise produce plausible nonsense."""
    if embed_query is None:
        import embeddings
        if embeddings.model_id() != corpus.model_id:
            return []
        embed_query = embeddings.embed_query
    # (B) embed the question in the books' own words; route on the original.
    qv = embed_query(rewrite_query(question))
    scope = route(question)
    allowed = _allowed_books(scope)
    scored = []
    for c in corpus.chunks:
        if allowed is not None and c["book_id"] not in allowed:
            continue
        scored.append((_cosine(qv, c["vector"]), c))
    scored.sort(key=lambda s: -s[0])

    # (C) a generic question about a topic the matrix has a row for is
    # answered from the employer(s) where it was actually used. Naming an
    # employer or asking career-wide keeps the full set, as before.
    policy = attribution_for(question, corpus) if scope != "ai" else {}
    homes = (policy.get("lead") or policy.get("used")) if policy else None
    named = named_employers(question) if scope != "ai" else set()
    if homes and not policy["employer_named"] and not policy["career_wide"]:
        picked = [(s, c) for s, c in scored
                  if employer_for_book(c["book_id"]) in homes][:top_k]
    elif named:
        # The prompt says "answer only about that employer", so that
        # employer's material comes first. Measured before this existed:
        # "Spring Security at NRG" returned Marsh, Marsh, NRG, ... Others
        # still fill the remaining slots, so a thin employer is not starved.
        own = [(s, c) for s, c in scored if employer_for_book(c["book_id"]) in named]
        rest = [(s, c) for s, c in scored if employer_for_book(c["book_id"]) not in named]
        picked = (own + rest)[:top_k]
    elif scope == "career" and not names_employer(question):
        picked = _balance_by_employer(scored, top_k)
    else:
        picked = scored[:top_k]
    return [dict(c, score=round(s, 4), employer=employer_for_book(c["book_id"]))
            for s, c in picked]


def _balance_by_employer(scored: list, top_k: int) -> list:
    """Employer coverage for a question that names no employer.

    REAL DEFECT this fixes (Owner-reported, Sprint 11): "explain your
    experience in using oauth or jwt" retrieved 5 of 6 chunks from one
    employer's books and 1 from another's, because pure cosine top-k has no
    reason to spread. The model then produced one mashed paragraph with no
    employer attached to any claim -- which is exactly the answer that got the
    Dissatisfied click. Reserving slots per employer is deterministic; asking
    the prompt nicely to cover three employers is not, and the material for the
    other two was never in front of it anyway.

    An employer whose own best chunk is below the grounding threshold
    contributes nothing -- a question that genuinely only touches one employer
    must not drag in two irrelevant ones."""
    per = max(1, top_k // max(1, len(EMPLOYER_BOOKS)))
    out, used = [], set()
    for _name, books in EMPLOYER_BOOKS:
        group = [(s, c) for s, c in scored if c["book_id"] in books]
        if not group or group[0][0] < GROUNDING_THRESHOLD:
            continue
        for s, c in group[:per]:
            out.append((s, c))
            used.add(id(c))
    # Any unfilled slots go to the next-best chunks overall, so a question
    # about one employer loses nothing by taking this path.
    for s, c in scored:
        if len(out) >= top_k:
            break
        if id(c) not in used:
            out.append((s, c))
            used.add(id(c))
    return out[:top_k]


# --- query rewrite (Sprint 13, B) -------------------------------------------
# Interviewer English -> the books' vocabulary. A chunk that only ever says
# "parallelized with CompletableFuture" scores badly against "multithreading"
# on a small embedder; the fix is to embed the question WITH the words the
# books use. Every term on the right was read out of the derived books, not
# supplied from general knowledge. Deliberately no employer names: which
# employer a topic belongs to is the attribution matrix's decision, below.
_REWRITE_FAMILIES = [
    ("concurrency",
     re.compile(r"multi-?thread|concurren|parallel|\basync\b|\bthreads?\b|executor|completable", re.I),
     "CompletableFuture ExecutorService @Async thread pool parallel fan-out readProduct dashboard"),
    ("kafka",
     re.compile(r"\bkafka\b|event[- ]stream|message broker|pub[/-]?sub|event[- ]driven", re.I),
     "Kafka producer consumer application code event member coverage claims changes"),
    ("jwt",
     re.compile(r"\bjwt\b|oauth|access token|bearer|token validation|authenticat|authoris|authoriz|spring security|identity|fusionauth", re.I),
     "OAuth2 JWT Spring Security filter access token FusionAuth Apigee client credentials private key public key"),
    ("nrg_async",
     re.compile(r"\bsqs\b|\bjms\b|messag|queue|\basync\b|dead[- ]letter|\bdlq\b|scheduled job|\bcron\b", re.I),
     "SQS dead-letter queue DLQ Lambda scheduled job serverless"),
    ("rest_graphql",
     re.compile(r"graphql|rest api|\brest\b|endpoint|resolver", re.I),
     "REST GraphQL resolver aggregator GraphQL-to-REST migration controller service"),
    ("soap_sap",
     re.compile(r"\bsoap\b|\bsap\b|legacy|websphere|jax-ws|\bcxf\b", re.I),
     "SOAP SAP JAX-WS CXF Axis WebSphere request response replay"),
    ("fhir",
     re.compile(r"\bfhir\b|interoperab|\bhl7\b|healthcare|member data|claims data", re.I),
     "FHIR resource objects member coverage claims interoperability services"),
    ("camel",
     re.compile(r"\bcamel\b|carrier|integration route|\bacord\b|insurance", re.I),
     "Apache Camel routes carrier integration JSON mapping ACORD normalized insurance model"),
    ("lambda_aws",
     re.compile(r"\blambda\b|serverless|\bsam\b|api gateway|\baws\b|dynamodb", re.I),
     "AWS Lambda SAM template OpenAPI API Gateway DynamoDB Secrets Manager local SAM testing"),
    ("oncall",
     re.compile(r"on[- ]?call|incident|production support|outage|debug|troubleshoot|root cause", re.I),
     "on-call ServiceNow Dynatrace WebSphere restart production logs SAP replay environment property drift"),
    ("hitl",
     re.compile(r"human[- ]in[- ]the[- ]loop|approv|write boundary|autonom|guardrail", re.I),
     "approval-gated write boundary hash-bound approve apply human approval model has no code path"),
    ("rag",
     re.compile(r"\brag\b|retriev|embedding|vector|semantic search|standing interview|grounded|grounding|chunk", re.I),
     "RAG fastembed cosine similarity incremental content-hash indexing Recall@K MRR retrieval eval grounding threshold leak scan"),
    ("ledger",
     re.compile(r"ledger|telemetry|\bcost\b|token usage|observab|pricing", re.I),
     "event ledger Postgres write-through spool versioned pricing token cost usage"),
    ("mcp",
     re.compile(r"\bmcp\b|tool[- ]calling|function calling|\btools?\b|tool use", re.I),
     "MCP server tool calling tool_use tool_result read-only repository tools"),
    ("triage_ai",
     re.compile(r"triage|azure openai|ai tool|adoption|ai-assisted", re.I),
     "AI Triage tool Azure OpenAI vector retrieval human email approval gate teams adoption"),
]


def rewrite_families(question: str) -> list[str]:
    return [name for name, rx, _ in _REWRITE_FAMILIES if rx.search(question or "")]


def rewrite_query(question: str) -> str:
    """The question plus the book vocabulary for every family it touches.
    Unchanged when no family matches -- an unknown question is embedded as
    asked, never padded with unrelated terms."""
    extra, seen = [], set()
    for name, rx, terms in _REWRITE_FAMILIES:
        if rx.search(question or ""):
            for t in terms.split():
                if t.lower() not in seen:
                    seen.add(t.lower())
                    extra.append(t)
    return question if not extra else f"{question} {' '.join(extra)}"


# --- attribution policy (Sprint 13, C) --------------------------------------
# Which matrix rows a family looks up. The matrix names technologies the way
# the books do ("Kafka producer/consumer", "FusionAuth / JWT", "SQS / DLQ");
# these needles are matched case-insensitively against that label.
_FAMILY_NEEDLES = {
    "kafka": ("kafka",),
    "jwt": ("jwt", "oauth", "spring security", "fusionauth"),
    "concurrency": ("completablefuture", "executor", "@async", "thread"),
    "nrg_async": ("sqs", "jms", "queue", "messag"),
    "fhir": ("fhir",),
    "camel": ("camel", "acord"),
    "lambda_aws": ("lambda", "sam", "api gateway", "aws"),
    "soap_sap": ("soap", "jax-ws", "cxf"),
    "rest_graphql": ("rest", "graphql"),
    "oncall": ("dynatrace", "servicenow", "uptime", "on-call"),
}
_BUCKET_RANK = {"HANDS_ON": 3, "USED": 2, "SYSTEM": 1, "NOT_USED": 0}

_CAREER_WIDE = re.compile(
    r"\b(anywhere|any of your|across your|in your career|at any (of|point)|all your|"
    r"each (employer|company|job|project)|every (employer|company|job|project)|"
    r"where (have|did) you|which (employer|company|project)s?)\b", re.I)


def _employer_order(names) -> list[str]:
    order = [n for n, _ in EMPLOYER_BOOKS]
    return sorted(names, key=lambda n: order.index(n) if n in order else len(order))


def attribution_for(question: str, corpus: "Corpus") -> dict:
    """What the books' own attribution matrix says about this question.

    Empty dict when the matrix has nothing to say (no family matched, no
    corpus matrix, or no row for the topic) -- the caller then falls back to
    Sprint 11's balanced retrieval and the prompt's general rules. Never a
    guess: a topic with no row gets no policy rather than an invented one."""
    if not corpus or not getattr(corpus, "attribution", None):
        return {}
    families = rewrite_families(question)
    needles = tuple(n for f in families for n in _FAMILY_NEEDLES.get(f, ()))
    if not needles:
        return {}
    recorded = {}
    for employer, rows in corpus.attribution.items():
        best = None
        for row in rows:
            label = (row.get("tech") or "").lower()
            if any(n in label for n in needles):
                b = row.get("bucket") or "OTHER"
                if b in _BUCKET_RANK and (best is None or _BUCKET_RANK[b] > _BUCKET_RANK[best]):
                    best = b
        if best is not None:
            recorded[employer] = best
    if not recorded:
        return {}
    by = lambda bucket: _employer_order([e for e, b in recorded.items() if b == bucket])
    return {
        "families": families,
        "recorded": recorded,
        "lead": by("HANDS_ON"),
        "used": by("USED"),
        "system": by("SYSTEM"),
        "not_used": by("NOT_USED"),
        "employer_named": names_employer(question),
        "career_wide": bool(_CAREER_WIDE.search(question or "")),
    }


def attribution_line(a: dict, question: str) -> str:
    """The one line the model is given about who leads. Names only employers
    the matrix recorded; an employer with no row is simply not mentioned."""
    if not a:
        return ""
    parts = []
    if a["lead"]:
        parts.append("hands-on at " + " and ".join(a["lead"]))
    if a["used"]:
        parts.append("used or worked alongside at " + " and ".join(a["used"]))
    if a["system"]:
        parts.append("part of the wider system but not your own work at " + " and ".join(a["system"]))
    # SI-03. "not used at X" used to be appended to the same speakable list as
    # the rest, and the model duly spoke it -- the Kafka answers volunteered
    # "Kafka wasn't part of the stack at my other employers" when nobody had
    # asked about other employers. An absence is a CONSTRAINT on what may be
    # claimed, not a fact to recite, so it is now stated as one and kept out
    # of the "your own record says" list entirely.
    line = "Your own record says: " + "; ".join(parts) + "."
    first = (a["lead"] or a["used"] or a["system"])
    if a["employer_named"]:
        line += " The question names an employer; answer only about that employer."
    elif a["career_wide"]:
        line += (" The question asks across your career: say where you used it. "
                 "Name an employer who did not use it ONLY if the question cannot "
                 "be answered without it.")
    elif first:
        line += (f" Lead with {first[0]} and give it the answer. Do not mention an "
                 "employer that is not named here.")
    if a["not_used"]:
        line += (" Constraint, not content: you have no record of this at "
                 + " and ".join(a["not_used"])
                 + ", so never claim work there. Do NOT say so in the answer "
                   "unless the question asks about that employer by name.")
    return line


# --- voice gate ---------------------------------------------------------
# Sprint 12. The leak scan above protects the SOURCE; this protects the VOICE.
# Separate on purpose: a leak is a confidentiality failure and a voice
# violation is a quality failure, they have different fixes, and merging them
# would have made the Sprint 11 false positive even harder to see.
#
# Every phrase here was chosen against the real corpus rather than from taste.
# Counted over all 361 chunks on 2026-09-27: "partition key" appears 0 times
# anywhere, "at-least-once" and "schema evolution" 0 times in the hands-on
# books, "cron" 0 times in the hands-on books. The model was producing them
# from its own world knowledge on top of grounded retrieval, which is the most
# dangerous failure this surface has -- fluent, plausible, and an interviewer
# would follow up on it.
_VOICE_BANNED = [
    # search/retrieval vocabulary -- nobody remembers their own job this way
    (re.compile(r'\bcensus\b', re.I), "says 'census'"),
    (re.compile(r'\b(zero|no|\d+)\s+(keyword\s+)?hits\b', re.I), "talks about 'hits'"),
    (re.compile(r'\b(confirmed|comprehensive|clean|clear|complete|total)\s+absence\b', re.I), "says 'confirmed absence'"),
    # Widened 2026-09-27 after a real trace: with "genuine" banned the model
    # simply paraphrased the same book phrase as "no real evidence of Kafka".
    # It is the audit register that is wrong, not one adjective.
    (re.compile(r'\b(no|any|little)\s+(genuine|real|hard|clear|direct)\s+evidence\b', re.I),
     "uses audit wording about evidence"),
    (re.compile(r'\bgenuine\s+evidence\b', re.I), "says 'genuine evidence'"),
    (re.compile(r'\bthe\s+evidence\s+(shows|says|is)\b', re.I), "cites 'the evidence'"),
    (re.compile(r'\bfalse\s+positives?\b', re.I), "explains a false positive"),
    # Narrowed 2026-09-29 (deploy attempt 7): the platform book says "an exact
    # set-membership check (not a substring check)" -- engineering vocabulary,
    # not the JMS audit narrative this was written for ("just a substring
    # match inside base64 tokens"). Same false-positive class as `source`.
    (re.compile(r'\b(just\s+a\s+)?substring\s+(match|hit)(es|s)?\b|\bsubstring\s+(inside|within|in)\b', re.I),
     "explains a substring match"),
    # Added after a real trace on "Did NRG use Kafka?": the answer explained
    # that JMS had turned up "in searches". How the fact was established is
    # never part of remembering your own project, and it is the same tell as
    # "census" wearing different words. Deliberately narrow -- it matches
    # "in searches"/"from a file search" and not Elasticsearch or a product
    # search feature, which are legitimate things to have worked on.
    (re.compile(r'\b(in|from|during|across)\s+(the\s+|a\s+|my\s+)?(file\s+|code\s+|keyword\s+)?searches?\b', re.I),
     "explains how it turned up in a search"),
    # Added after reading the FIRST LIVE answer this gate passed. It opened
    # correctly and then said "there was no genuine Kafka or JMS usage" and
    # "a single SQS mention showed up in some filing material but got
    # rejected" -- the audit register again, in two shapes the earlier
    # patterns did not cover because they only looked for the word
    # "evidence". Proof that a banned-phrase list is never finished by
    # reasoning about it; it is finished by reading real output.
    (re.compile(r'\bgenuine\b', re.I), "says 'genuine', which is audit wording"),
    (re.compile(r'\b(mention|reference|hit|match)e?s?\s+(showed|show|turned|turn|came)\s+up\b', re.I),
     "describes something turning up in the record"),
    (re.compile(r'\bfiling\s+material\b', re.I), "cites 'filing material'"),
    (re.compile(r'\bgot\s+rejected\b', re.I), "says a finding 'got rejected'"),
    # details no book contains -- verified by counting the real corpus
    (re.compile(r'\bpartition\s+key\b', re.I), "invents a partition key"),
    (re.compile(r'\bat[- ]least[- ]once\b', re.I), "invents a delivery guarantee"),
    (re.compile(r'\bschema\s+evolution\b', re.I), "invents schema evolution"),
    (re.compile(r'\b(one|a\s+single)\s+(scheduled\s+)?cron\b', re.I), "invents an exact cron count"),
    (re.compile(r'\bbridg(ed|ing)\s+the\s+batch\b', re.I), "claims bridging the batch core"),
    # Sprint 13: the audit register banned as a FAMILY. Sprint 12's retro
    # showed that banning one token at a time produces the next synonym on
    # the next run ("genuine" -> "real" -> "clean"); these are the shapes the
    # register takes when it is not talking about evidence.
    (re.compile(r'\bknowledge\s+cutoff\b', re.I), "talks about a knowledge cutoff"),
    (re.compile(r'\bthe\s+(documents?|records?|files?|notes?|materials?)\s+'
                r'(say|says|said|show|shows|showed|state|states|indicate|indicates|'
                r'confirm|confirms|record|records|mention|mentions)\b', re.I),
     "cites what the documents or the record say"),
    (re.compile(r'\b(file|code|codebase|repository|repo)\s+census\b', re.I), "says 'file census'"),
    # Real gate output, 2026-09-29: "the project's own notes are explicit that
    # it's sized for this repo". Citing notes is reading, not remembering.
    (re.compile(r"\b(the|my|our)\s+(\w+['\u2019]s\s+)?(own\s+)?(notes|records|documentation|docs)\s+"
                r"(are|is|say|says|state|states|explicit|mention|mentions|note|notes|list|lists)\b", re.I),
     "cites notes or documentation"),
    (re.compile(r'\b(no|zero|any)\s+(usage|occurrences?|references?|mentions?)\s+'
                r'(found|anywhere|across|in the)\b', re.I), "counts occurrences like a search"),
    # Found by the independent QA pass (2026-09-29) reading a FRESH answer the
    # gate had not sampled: "a confirmed real async flow", "Kafka never came
    # up anywhere in that codebase". The register wearing new clothes again.
    (re.compile(r'\bconfirmed\s+(real|actual|genuine|true)\b', re.I), "says 'confirmed real'"),
    (re.compile(r'\b(never|not once|nowhere)\s+(came|come|comes|turned|turns|showed|shows)\s+up\b', re.I),
     "says something never came up, which is search talk"),
    (re.compile(r'\b(anywhere|nowhere)\s+in\s+(that|the|this)\s+(codebase|code|repo|repository|source)\b', re.I),
     "says 'anywhere in the codebase', which is search talk"),
    # Owner rule, 2026-09-29: no architecture-ownership claims. The books say
    # he implemented within designs a lead or architect owned.
    (re.compile(r'\bI\s+(designed|architected|owned|built|created)\s+the\s+'
                r'(overall|entire|whole|end-to-end|full|complete)\s+(\w+\s+){0,2}'
                r'(architecture|platform|system|layer|estate|pipeline)\b', re.I),
     "claims ownership of the overall architecture"),
]

# Owner decision 2026-09-29: JMS is never volunteered. It may be answered only
# when the interviewer asks about it by name. Sprint 12's known residual was
# an NRG answer narrating how a JMS lead was investigated; this closes it as a
# rule rather than as another phrase in the list above.
_JMS = re.compile(r'\bJMS\b')

# A limitation is honest; a paragraph of them is a different answer than the
# one that was asked for. The Owner's spec allows exactly one plain line, so
# two is the tolerated maximum and three is a rejection.
_LIMIT_MARKER = re.compile(
    r"\b(can't|cannot|couldn't|don't have|do not have|not something i|"
    r"wouldn't claim|not claim|isn't something|is not something|no detail|"
    r"don't recall|do not recall|can't recall|couldn't tell you|can't tell you|"
    r"wouldn't be able|not able to say)", re.I)

MAX_LIMIT_SENTENCES = 2

# SI-04/BL-144. Not every violation deserves the same consequence, and getting
# this wrong is how a quality gate becomes a availability problem.
#
# A volunteered limitation is worth a RETRY -- the model usually drops it when
# told to. It is NOT worth refusing the question outright: a good answer
# carrying one unasked caveat is plainly better for the Owner than the standard
# "I don't have that recorded" line, and the audit registered over-refusal as
# its own defect (question m was declined on all three production draws).
#
# Leaks, truncation, invented details, banned vocabulary and tense errors stay
# hard: each of those ships something false or breaks confidentiality, and a
# refusal really is the better outcome there.
SOFT_VIOLATION = "volunteers a limitation nobody asked for"


def only_soft_violations(violations: list[str]) -> bool:
    """True when every violation is a retry-worthy style problem."""
    return bool(violations) and all(v.startswith(SOFT_VIOLATION) for v in violations)


def _sentences(text: str) -> list[str]:
    return [p.strip() for p in re.split(r'(?<=[.!?])\s+', text.strip()) if p.strip()]


# Sprint 13, gate runs 1 and 2: a Kafka answer kept pulling in FHIR because
# the BCBSA book discusses both in one section. The prompt rule alone did not
# hold, so it is a check. Only data standards and databases are treated as
# neighbours -- the things an interviewer asking about a messaging system did
# not ask about -- and a neighbour is allowed whenever the question itself
# (or the book vocabulary it rewrites to, see rewrite_query) names it: a
# Camel/integration question rewrites to ACORD, so ACORD is not a neighbour
# there; a Kafka question rewrites to producer/consumer/events, so FHIR is.
_NEIGHBOURS = [
    ("FHIR", re.compile(r'\bfhir\b', re.I)),
    ("ACORD", re.compile(r'\bacord\b', re.I)),
    ("HL7", re.compile(r'\bhl7\b', re.I)),
    ("DB2", re.compile(r'\bdb2\b', re.I)),
    ("Oracle", re.compile(r'\boracle\b', re.I)),
    ("DynamoDB", re.compile(r'\bdynamodb\b', re.I)),
    ("MongoDB", re.compile(r'\bmongo(db)?\b', re.I)),
]


def neighbour_violations(text: str, question: str) -> list[str]:
    if not question or not rewrite_families(question):
        return []                         # no technology asked about -> no neighbours
    scope = rewrite_query(question)
    return [f"drags in {name}, which was not asked about ({m.group(0)!r})"
            for name, rx in _NEIGHBOURS
            if (m := rx.search(text)) and not rx.search(scope)]


def voice_violations(text: str, question: str | None = None) -> list[str]:
    """What is wrong with HOW this answer is written. Empty list is good.

    Deliberately not merged into leaks(): this is a quality gate whose action
    is regenerate-then-refuse, while leaks() is a confidentiality control that
    refuses immediately. Keeping them apart is also why the Sprint 11 leak
    false positive is still easy to see in a trace."""
    # The matched words are quoted back, not just the category. A retry told
    # "invents an exact cron count" has to guess which phrase that was; a retry
    # told "invents an exact cron count ('one scheduled cron')" can delete it.
    # Real trace, 2026-09-27: with only the category, the "Did NRG use Kafka?"
    # retry replaced one banned phrase with a different one and was refused.
    bad = []
    for rx, why in _VOICE_BANNED:
        m = rx.search(text)
        if m:
            bad.append("%s (%r)" % (why, m.group(0)))
    if question is not None and _JMS.search(text) and not _JMS.search(question.upper()):
        bad.append("volunteers JMS, which was not asked about ('JMS')")
    if question is not None:
        bad += neighbour_violations(text, question)

    sents = _sentences(text)
    if not sents:
        return bad + ["is empty"]

    # Truncation. A cut-off answer is the most obviously machine-like failure
    # an interviewer can see, and max_tokens makes it a real one.
    if not re.search(r'''[.!?]["'”’)\]]*$''', sents[-1]):
        bad.append("stops mid-sentence")

    # SI-04. This used to be a phrase list with a budget of two, and it was
    # wrong in both halves. The phrase list missed most real limitation
    # wording -- "I didn't set up the brokers", "I didn't administer the
    # cluster", "Kafka wasn't part of the stack" all scored zero -- and the
    # budget of two told the model that two volunteered limitations were
    # acceptable, so it reliably produced them.
    #
    # The gate now uses the same four-category oracle the test suite scores
    # production answers with (agent/si_quality.py), so the rule has exactly
    # one definition. It is question-aware: a negative the question actually
    # invited is not a violation, which is why "have you used Terraform" can
    # still be answered "no".
    # Only with the question in hand. "Unsolicited" is a RELATION between the
    # question and the answer -- without the question there is no way to tell
    # a volunteered caveat from a direct answer to "have you used Terraform",
    # and guessing in either direction is worse than not checking. The
    # sentence-count checks below still apply either way.
    report = si_quality.assess(question, text, "answered") if question else None
    for n in (report.unsolicited if report else []):
        bad.append("%s -- %s (%r)"
                   % (SOFT_VIOLATION, n.category, n.sentence[:90]))
    for t in (report.tense_errors if report else []):
        # A tense error states a false fact about current employment, so it is
        # never soft -- it is closer to an invented detail than to a stylistic
        # slip.
        bad.append("tense: %s" % t[:120])

    # Kept from the phrase-list version so the "essay about what he cannot
    # say" contract keeps its own distinct message: many limitation sentences
    # is a different failure from one volunteered clause, and the retry prompt
    # reads better when it says so.
    n_limits = sum(1 for x in sents if _LIMIT_MARKER.search(x))
    if n_limits > MAX_LIMIT_SENTENCES:
        bad.append("spends %d sentences on what you cannot say (at most %d)"
                   % (n_limits, MAX_LIMIT_SENTENCES))
    if _LIMIT_MARKER.search(sents[0]):
        bad.append("opens on a limitation instead of on the work")
    return bad


# The provenance-VERB pattern is identified by content so that a question
# about the retrieval system itself can be exempted from it -- and only it.
_PROVENANCE_VERB_LEAK = next(p for p in _LEAK_PATTERNS if "knowledge base|material" in p.pattern)


def leaks(text: str, question: str | None = None) -> list[str]:
    """Which forbidden identifiers a generated answer contains. Empty is good.

    Question-aware for exactly one pattern (Sprint 13, post-cutover remote
    gate): asked "How does your RAG retrieval work?", the model said what the
    corpus holds -- which is the answer, not a citation. When the question is
    in the `rag` family that one pattern is skipped; book ids, "according
    to", private paths, pantheon names, "excerpt" and file extensions are
    still scanned, and for any other question nothing changes."""
    skip = _PROVENANCE_VERB_LEAK if (question and "rag" in rewrite_families(question)) else None
    return [p.pattern for p in _LEAK_PATTERNS if p is not skip and p.search(text)]


# The file-extension pattern, and ONLY that one, is retryable. A book number,
# a "according to", a pantheon name or a private path is a confidentiality
# failure and refuses immediately, exactly as before. A bare ".py" in an
# answer about the public platform is almost always the model naming a public
# repository file (gate run 2: "approve_edit ... write_tools.py"), which the
# interviewer must still not see -- so the retry is told to describe the
# mechanism in words, and the retry's text goes through the WHOLE scan again.
_RETRYABLE_LEAK = next(p.pattern for p in _LEAK_PATTERNS if "docx" in p.pattern)


def leak_is_retryable(found: list[str]) -> bool:
    return bool(found) and all(f == _RETRYABLE_LEAK for f in found)


def build_system_prompt(corpus: "Corpus | None") -> str:
    """(A) The frozen rules plus the standing career map, on every generate."""
    career_map = getattr(corpus, "career_map", "") if corpus is not None else ""
    if not career_map:
        return SYSTEM_PROMPT
    return (SYSTEM_PROMPT + "\n\nWHO YOU ARE\nYour own standing summary. It is "
            "true and you may draw on it freely for orientation -- who you are, where "
            "you worked, what you did there, what the platform does. The excerpts "
            "remain the authority for specifics; never contradict either.\n\n"
            + career_map)


def build_user_prompt(question: str, hits: list[dict], policy_line: str = "") -> str:
    # The employer label is supplied explicitly rather than left for the model
    # to infer from the excerpt body. Mid-book chunks frequently never repeat
    # the employer name, and an unlabelled excerpt is how one employer's
    # architecture ends up attributed to another.
    def head(n, h):
        emp = h.get("employer")
        return f"[excerpt {n} -- {emp}]" if emp else f"[excerpt {n}]"
    excerpts = "\n\n".join(f"{head(n, h)}\n{h['text']}" for n, h in enumerate(hits, 1))
    policy = f"{policy_line}\n\n" if policy_line else ""
    return (f"{excerpts}\n\n---\n{policy}Interview question: {question}\n\n"
            "Answer in first person, using only the excerpts above and your standing summary.")


def answer(question: str, corpus: Corpus | None = None, create_fn=None) -> dict:
    """The whole path. Always returns a dict with a user-safe `answer` and an
    operational `outcome` the caller logs. Never raises into the request."""
    question = (question or "").strip()
    if not question:
        return {"outcome": "empty", "grounded": False, "answer": REFUSAL, "hits": []}

    corpus = corpus if corpus is not None else load_corpus()
    if corpus is None:
        return {"outcome": "no_corpus", "grounded": False, "answer": NO_CORPUS, "hits": []}

    if is_private_topic(question):
        # Refused deterministically, logged under its own outcome so the
        # review queue can tell "asked something private" from "asked
        # something the books do not cover". No model call, no retrieval.
        return {"outcome": "private_topic", "grounded": False, "answer": REFUSAL, "hits": []}

    hits = retrieve(question, corpus)
    # max(), not hits[0] -- employer-balanced retrieval deliberately returns
    # hits in employer order, so the first hit is no longer the highest scoring
    # one. Reading the grounding gate off position 0 would have started
    # refusing answerable questions.
    best = max((h["score"] for h in hits), default=0.0)
    if not hits or best < GROUNDING_THRESHOLD:
        return {"outcome": "ungrounded", "grounded": False, "answer": REFUSAL,
                "hits": hits, "best_score": best, "scope": route(question)}

    # Routed through the one sanctioned model boundary rather than
    # constructing an Anthropic client here. agent/test_reasoning_gateway_
    # enforcement.py caught the first version of this file importing the SDK
    # directly and failed the build -- correctly. HUMAN_EXPLANATION is the
    # right purpose: this produces a human-readable explanation from retrieved
    # material and is ADVISORY, which is exactly what it is treated as (the
    # leak scan and the decline gate below independently verify it before any
    # of it reaches an interviewer). Routing here also inherits the
    # LLM_MODE=DISABLED kill switch and the honest-denial contract for free.
    policy = attribution_for(question, corpus) if route(question) != "ai" else {}
    policy_line = attribution_line(policy, question)
    system_prompt = build_system_prompt(corpus)
    policy_summary = ({"lead": policy.get("lead"), "not_used": policy.get("not_used"),
                       "families": policy.get("families")} if policy else None)

    import reasoning_gateway
    result = reasoning_gateway.call(
        purpose="HUMAN_EXPLANATION",
        system_prompt=system_prompt,
        user_message=build_user_prompt(question, hits, policy_line),
        max_tokens=MAX_ANSWER_TOKENS,
        create_fn=create_fn,
        model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-5"),
    )
    if not result.get("model_called") or not result.get("text"):
        # A denial is a real, distinct state -- no key, LLM mode off, or an
        # empty reply. Say so honestly; never fall through to an answer.
        return {"outcome": "no_model", "grounded": False, "answer": NO_CORPUS,
                "hits": hits, "best_score": best, "policy": policy_summary,
                "denial_reason": result.get("denial_reason")}
    text = result["text"].strip()

    if _model_declined(text):
        # Ungrounded in substance even though retrieval cleared the threshold.
        # Standard refusal, and it goes to the review queue -- an unanswerable
        # question is the cheapest coverage signal v0 can collect, and silently
        # returning the model's own polite decline would throw it away.
        return {"outcome": "ungrounded_model_declined", "grounded": False,
                "answer": REFUSAL, "hits": hits, "best_score": best,
                "scope": route(question), "model_reply": text, "policy": policy_summary}

    found = leaks(text, question)
    leak_retried = False
    if found and leak_is_retryable(found):
        # One corrective retry for an extension-only hit. The retry's text is
        # re-scanned in full below; nothing that fails the scan is shipped.
        leak_retried = True
        retry = reasoning_gateway.call(
            purpose="HUMAN_EXPLANATION",
            system_prompt=system_prompt,
            user_message=(build_user_prompt(question, hits, policy_line)
                          + "\n\nA previous attempt at this answer named a file or "
                            "module by its filename. Say the same thing again without "
                            "naming any file, path or extension -- describe the "
                            "mechanism in words, as you would in a room. Finish every "
                            "sentence."),
            max_tokens=MAX_ANSWER_TOKENS, create_fn=create_fn,
            model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-5"))
        retry_text = (retry.get("text") or "").strip()
        if retry_text and not leaks(retry_text, question):
            text, result, found = retry_text, retry, []
        else:
            found = leaks(retry_text, question) or found
    if found:
        # The deterministic control fired. Refuse rather than ship a leak, and
        # record it -- a leak that is silently patched is a leak nobody fixes.
        return {"outcome": "leak_blocked", "grounded": True, "answer": REFUSAL,
                "hits": hits, "best_score": best, "leaks": found,
                "leak_retried": leak_retried, "policy": policy_summary,
                # The refused text itself, for the review queue. Without it a
                # leak_blocked row cannot be diagnosed -- a replay may not
                # reproduce the sentence (gate run 4, 2026-09-29, did not).
                "model_reply": text[:600]}

    # Voice gate. ONE corrective retry, then refuse -- a retry is cheap and
    # nearly always sufficient, whereas refusing on a first violation would
    # repeat exactly the Sprint 11 defect of throwing away a good answer over
    # one phrase. The retry NAMES the violations rather than repeating the
    # rules, because the rules were already in the system prompt and did not
    # hold; restating them is the thing that already failed.
    voice = voice_violations(text, question)
    if voice:
        retry = reasoning_gateway.call(
            purpose="HUMAN_EXPLANATION",
            system_prompt=system_prompt,
            user_message=(build_user_prompt(question, hits, policy_line)
                          + "\n\nA previous attempt at this answer was rejected "
                            "because it " + "; ".join(voice)
                          + ". Say the same thing again without that, as a person "
                            "remembering their own work out loud. Open on the work "
                            "itself, never on what you cannot say. Finish every "
                            "sentence.\n\nWhile you are at it, none of these belong "
                            "in spoken English either, so avoid all of them and not "
                            "only the one above: census, hits, confirmed absence, "
                            "genuine, evidence, false positive, substring, filing "
                            "material, an exact number of cron jobs, a partition "
                            "key, at-least-once delivery, schema evolution, knowledge "
                            "cutoff, what the documents or the record say, JMS unless "
                            "it was asked about, owning the overall architecture. And "
                            "unless the question itself named them, none of these "
                            "neighbouring technologies belong in this answer either: "
                            + ", ".join(name for name, _ in _NEIGHBOURS) + ". A "
                            "previous retry removed the phrase it was told about "
                            "and immediately used a different one from this list."),
            max_tokens=MAX_ANSWER_TOKENS,
            create_fn=create_fn,
            model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-5"),
        )
        retry_text = (retry.get("text") or "").strip()
        retry_voice = voice_violations(retry_text, question) if retry_text else ["is empty"]
        if retry_text and not retry_voice and not leaks(retry_text, question):
            text, result = retry_text, retry
        elif (retry_text and not leaks(retry_text, question)
                and only_soft_violations(retry_voice)):
            # The retry is still volunteering a caveat, but that is all that is
            # wrong with it. Ship it. Refusing here would replace a real,
            # grounded, honest answer with the standard "I don't have that
            # recorded" line -- strictly worse for the person asking, and the
            # exact over-refusal shape the audit registered as its own defect.
            text, result = retry_text, retry
        else:
            # Twice is a real problem with this question, not a bad roll.
            # Refuse and log it under its OWN outcome, so it reaches the review
            # queue distinguishable from an ungrounded refusal -- those have
            # opposite fixes and counting them together would hide both.
            return {"outcome": "voice_rejected", "grounded": True,
                    "answer": REFUSAL, "hits": hits, "best_score": best,
                    "scope": route(question), "voice_violations": voice,
                    "retry_violations": retry_voice, "policy": policy_summary,
                    "model_reply": retry_text[:600] or text[:600]}

    return {"outcome": "answered", "grounded": True, "answer": text,
            "hits": hits, "best_score": best, "scope": route(question),
            "authority": result.get("authority"), "usage": result.get("usage"),
            "policy": policy_summary, "leak_retried": leak_retried}


def corpus_status(corpus: Corpus | None = None) -> dict:
    """Operator-facing, safe to expose: says whether answers are possible at
    all, without revealing any corpus content."""
    corpus = corpus if corpus is not None else load_corpus()
    if corpus is None:
        return {"loaded": False, "chunks": 0, "reason": "no corpus file on this instance"}
    return {"loaded": True, "chunks": len(corpus), "model_id": corpus.model_id,
            "books": sorted({c["book_id"] for c in corpus.chunks}),
            # Sprint 13: present/absent only -- never the text, never who.
            "career_map": bool(corpus.career_map),
            "attribution_rows": sum(len(v) for v in corpus.attribution.values()),
            # Which upload this container came from. Written by the deploy
            # script next to the corpus; lets a caller tell the new container
            # from the one still draining during Railway's cutover.
            "deploy_marker": deploy_marker()}


DEPLOY_MARKER_PATH = CORPUS_PATH.parent / "deploy_marker.txt"


def deploy_marker() -> str | None:
    try:
        return DEPLOY_MARKER_PATH.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None
