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
"""

import json
import math
import os
import pathlib
import re

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
)


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
REFUSAL = ("I don't have a grounded answer for that one. Ask me about the backend "
           "systems I've worked on, or about the AI platform I've built.")
NO_CORPUS = ("The knowledge base isn't loaded on this instance, so I can't answer "
             "from it. I won't guess.")

SYSTEM_PROMPT = """You are answering interview questions AS Karthik, in first person.

ABSOLUTE RULES
- Use ONLY the supplied excerpts. If they do not support an answer, say you
  don't have that detail. Never use general knowledge about any company,
  technology or person. Never infer or embellish.
- Never mention where the information came from. No source names, no document
  or book titles, no chapter or section numbers, no file paths, no phrases
  like "according to", "the document says", "my notes", "the corpus", "the
  excerpt". Just answer as someone who did the work and remembers it.
- Be honest about the limits of your own involvement. If the excerpts say
  something was a system-level fact rather than your personal work, say so
  plainly -- "I didn't design that; I implemented the filter against it" is a
  better answer than a vague claim of ownership.
- Never state a date, employer, title or metric that is not in the excerpts.

ONE EMPLOYER AT A TIME
Each excerpt is labelled with the employer it belongs to. Attribute every
claim to the employer whose excerpt it came from, and never blend two
employers' systems into one description -- if two employers solved the same
problem differently, that is two separate statements, not an average.

When the question names no employer ("explain your experience with X"), take
the employers in the order the excerpts appear, which is most recent first.
Give each one its own short paragraph, starting with the employer name. Cover
only employers whose excerpts actually speak to the question. If an excerpt
says a technology was NOT used somewhere, say that plainly as its own point --
a confirmed absence is a real, useful interview answer, not a gap to hide.

When the question DOES name one employer, answer only about that employer.

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
    re.compile(r'\b(the|my) (document|corpus|excerpt|notes|knowledge base)s?\b', re.I),
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


class Corpus:
    def __init__(self, data: dict):
        self.model_id = data.get("model_id")
        self.chunks = data.get("chunks", [])
        self.source_book_hashes = data.get("source_book_hashes", {})

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
    qv = embed_query(question)
    scope = route(question)
    allowed = _allowed_books(scope)
    scored = []
    for c in corpus.chunks:
        if allowed is not None and c["book_id"] not in allowed:
            continue
        scored.append((_cosine(qv, c["vector"]), c))
    scored.sort(key=lambda s: -s[0])

    if scope == "career" and not names_employer(question):
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


def leaks(text: str) -> list[str]:
    """Which forbidden identifiers a generated answer contains. Empty is good."""
    return [p.pattern for p in _LEAK_PATTERNS if p.search(text)]


def build_user_prompt(question: str, hits: list[dict]) -> str:
    # The employer label is supplied explicitly rather than left for the model
    # to infer from the excerpt body. Mid-book chunks frequently never repeat
    # the employer name, and an unlabelled excerpt is how one employer's
    # architecture ends up attributed to another.
    def head(n, h):
        emp = h.get("employer")
        return f"[excerpt {n} -- {emp}]" if emp else f"[excerpt {n}]"
    excerpts = "\n\n".join(f"{head(n, h)}\n{h['text']}" for n, h in enumerate(hits, 1))
    return (f"{excerpts}\n\n---\nInterview question: {question}\n\n"
            "Answer in first person, using only the excerpts above.")


def answer(question: str, corpus: Corpus | None = None, create_fn=None) -> dict:
    """The whole path. Always returns a dict with a user-safe `answer` and an
    operational `outcome` the caller logs. Never raises into the request."""
    question = (question or "").strip()
    if not question:
        return {"outcome": "empty", "grounded": False, "answer": REFUSAL, "hits": []}

    corpus = corpus if corpus is not None else load_corpus()
    if corpus is None:
        return {"outcome": "no_corpus", "grounded": False, "answer": NO_CORPUS, "hits": []}

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
    import reasoning_gateway
    result = reasoning_gateway.call(
        purpose="HUMAN_EXPLANATION",
        system_prompt=SYSTEM_PROMPT,
        user_message=build_user_prompt(question, hits),
        max_tokens=400,
        create_fn=create_fn,
        model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-5"),
    )
    if not result.get("model_called") or not result.get("text"):
        # A denial is a real, distinct state -- no key, LLM mode off, or an
        # empty reply. Say so honestly; never fall through to an answer.
        return {"outcome": "no_model", "grounded": False, "answer": NO_CORPUS,
                "hits": hits, "best_score": best,
                "denial_reason": result.get("denial_reason")}
    text = result["text"].strip()

    if _model_declined(text):
        # Ungrounded in substance even though retrieval cleared the threshold.
        # Standard refusal, and it goes to the review queue -- an unanswerable
        # question is the cheapest coverage signal v0 can collect, and silently
        # returning the model's own polite decline would throw it away.
        return {"outcome": "ungrounded_model_declined", "grounded": False,
                "answer": REFUSAL, "hits": hits, "best_score": best,
                "scope": route(question), "model_reply": text}

    found = leaks(text)
    if found:
        # The deterministic control fired. Refuse rather than ship a leak, and
        # record it -- a leak that is silently patched is a leak nobody fixes.
        return {"outcome": "leak_blocked", "grounded": True, "answer": REFUSAL,
                "hits": hits, "best_score": best, "leaks": found}

    return {"outcome": "answered", "grounded": True, "answer": text,
            "hits": hits, "best_score": best, "scope": route(question),
            "authority": result.get("authority"), "usage": result.get("usage")}


def corpus_status(corpus: Corpus | None = None) -> dict:
    """Operator-facing, safe to expose: says whether answers are possible at
    all, without revealing any corpus content."""
    corpus = corpus if corpus is not None else load_corpus()
    if corpus is None:
        return {"loaded": False, "chunks": 0, "reason": "no corpus file on this instance"}
    return {"loaded": True, "chunks": len(corpus), "model_id": corpus.model_id,
            "books": sorted({c["book_id"] for c in corpus.chunks})}
