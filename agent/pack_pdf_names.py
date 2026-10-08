"""The filenames an employer sees. One source of truth for the whole repo.

The Owner's rule, recorded in DEVADOSS `storage/personal/CONTACT.md`
(Automation Sprint 15, 2026-10-06):

    Karthikeyan_Devadoss_CV_<key>.pdf
    Karthikeyan_Devadoss_CoverLetter_<key>.pdf      key at most 10 characters

Before incident INC_2026-10-08 this rule lived only in that one personal file and
in a set of hand-built artifacts. The committed publisher emitted the internal
shortlist filename instead -- `23_nebius-fde-physical-ai-infrastructure.pdf` --
which shows a recruiter their position in a private queue, and which is unstable:
the ranks changed on 2026-10-07 when the posting-date ordering moved
commercetools from 6th to 9th.
"""

from __future__ import annotations

from pathlib import Path

CV_PREFIX = "Karthikeyan_Devadoss_CV_"
COVER_PREFIX = "Karthikeyan_Devadoss_CoverLetter_"
MAX_KEY_LENGTH = 10

#: Pack slug -> the short key used in the filename.
#:
#: Explicit, not derived. The keys are abbreviations a person chose: `dbxfull`
#: for databricks-sr-fde-fullstack-berlin, `taktilops` for
#: taktile-forward-deployed-engineer-ops-berlin. No rule turns one into the
#: other, so deriving them would mean guessing at a filename that goes to an
#: employer. An unmapped slug raises.
PACK_KEYS: dict[str, str] = {
    "tavily-forward-deployed-engineer-enterprise": "tavily",
    "oyster-senior-ai-solutions-engineer-gtm": "oyster",
    "nebius-fde-physical-ai-infrastructure": "nebius",
    "n8n-forward-deployed-engineer-emea": "n8n",
    "moss-applied-ai-engineer-berlin": "moss",
    "runpod-forward-deployed-engineer-emea": "runpod",
    "databricks-forward-deployed-engineer-de": "databricks",
    "databricks-sr-fde-fullstack-berlin": "dbxfull",
    "taktile-solution-architect-berlin": "taktilesa",
    "taktile-forward-deployed-engineer-berlin": "taktilefde",
    "taktile-senior-forward-deployed-engineer-berlin": "taktilesr",
    "taktile-forward-deployed-engineer-ops-berlin": "taktilops",
    "cursor-solutions-architect-central-europe": "cursor",
    "cohere-fde-agentic-platform-europe": "cohere",
    "smartsheet-sr-fde-ai-germany": "smartsheet",
    "langchain-deployed-architect-amsterdam": "langchain",
}


class PackArtifactError(RuntimeError):
    """A pack has no usable candidate-facing PDF pair."""


def key_for(slug: str) -> str:
    key = PACK_KEYS.get(slug)
    if not key:
        raise PackArtifactError(
            "no PDF key for pack slug " + repr(slug)
            + "; add it to PACK_KEYS and bake the pair. A filename an employer "
              "reads is never guessed.")
    if len(key) > MAX_KEY_LENGTH:
        raise PackArtifactError(
            "PDF key " + repr(key) + " is longer than the "
            + str(MAX_KEY_LENGTH) + " characters the Owner's rule allows.")
    return key


def canonical_names(slug: str) -> tuple[str, str]:
    """(cv filename, cover-letter filename) for this pack. Raises if unmapped."""
    key = key_for(slug)
    return CV_PREFIX + key + ".pdf", COVER_PREFIX + key + ".pdf"


def existing_pair(slug: str, pdf_dir: Path) -> tuple[str, str]:
    """Canonical names, checked to exist. Raises if either file is absent.

    A Review entry naming a file nobody can download is worse than no entry: it
    reads as ready to send.
    """
    cv_name, cover_name = canonical_names(slug)
    missing = [n for n in (cv_name, cover_name) if not (Path(pdf_dir) / n).is_file()]
    if missing:
        raise PackArtifactError(
            "pack " + slug + " is missing baked PDFs: " + ", ".join(missing)
            + " (looked in " + str(pdf_dir) + ")")
    return cv_name, cover_name
