"""What was actually uploaded, recorded at submit time.

Incident INC_2026-10-08. Eight applications were submitted on 6 and 7 October
2026 and the repository cannot say which files went to which employer. The queue
record had no cover-letter field at all, and its `cv_pdf` is a static pack
attribute -- present even on Moss, which was never submitted -- so it was never
evidence of an upload. Every employer confirmation that arrived is a generic
template that echoes no filename, so the question is now unanswerable.

This module makes the same gap impossible next time. An entry records the exact
bytes that were attached, by sha256, and `assert_attachment_allowed` refuses
anything that is not the recorded file.

It also records the unknowns **by name** rather than omitting them. That is the
subtler half of the incident: a missing field and an unanswered question looked
identical afterwards.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

#: Facts the Owner's standing instructions require per submit
#: (DEVADOSS storage/personal/DIGITAL_WORK_LOG.md: screenshot + full Q&A before
#: every submit). Each is written as "not recorded" until supplied, so an absent
#: answer can never be mistaken for an absent requirement.
UNKNOWN_FIELDS = (
    "form_fields",
    "work_authorisation_answer",
    "notice_answer",
    "salary_stated",
    "email_used",
    "linkedin_used",
    "screenshot",
    "question_and_answer_list",
    "time_taken",
    "tokens_used",
)

NOT_RECORDED = "not recorded"


class AttachmentRefused(RuntimeError):
    """An attachment is not the file the manifest recorded for this submit."""


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_record(path: Path) -> dict:
    path = Path(path)
    if not path.is_file():
        raise AttachmentRefused("no such file: " + str(path))
    if path.suffix.lower() != ".pdf":
        raise AttachmentRefused(
            "only PDF may be attached to an application; got " + path.name
            + ". A markdown file is not a document an applicant tracking system "
              "renders, and one reached an Owner email on 2026-10-08.")
    return {"name": path.name, "sha256": sha256_of(path), "bytes": path.stat().st_size}


def build_entry(*, slug: str, cv_path: Path, cover_path: Path, submitted_by: str,
                submitted_at_berlin: str, url: str, **known) -> dict:
    """One manifest entry. Everything not supplied is written as "not recorded"."""
    unknowns = {field: known.pop(field, NOT_RECORDED) for field in UNKNOWN_FIELDS}
    entry = {
        "slug": slug,
        "url": url,
        "submitted_by": submitted_by,
        "submitted_at_berlin": submitted_at_berlin,
        "recorded_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cv": _file_record(cv_path),
        "cover": _file_record(cover_path),
        "unknowns": unknowns,
    }
    if known:
        entry["extra"] = dict(known)
    return entry


def attachment_allowed(entry: dict, path: Path) -> bool:
    """True only if `path` is byte-for-byte one of the two recorded files."""
    path = Path(path)
    if not path.is_file() or path.suffix.lower() != ".pdf":
        return False
    digest = sha256_of(path)
    return digest in {entry["cv"]["sha256"], entry["cover"]["sha256"]}


def assert_attachment_allowed(entry: dict, path: Path) -> None:
    """Raise unless `path` is a file this manifest entry recorded.

    Name equality is deliberately not enough. Two packs can carry the same
    filename shape, and the failure that started the incident was the right-looking
    name over the wrong content.
    """
    path = Path(path)
    if path.suffix.lower() != ".pdf":
        raise AttachmentRefused(
            "refusing to attach " + path.name + ": only PDF may be sent.")
    if not attachment_allowed(entry, path):
        raise AttachmentRefused(
            "refusing to attach " + path.name + " for " + entry.get("slug", "?")
            + ": its sha256 is not the CV or cover letter this submit recorded.")


def append(manifest_path: Path, entry: dict) -> Path:
    """Append one entry. The manifest is a list, newest last, never rewritten."""
    manifest_path = Path(manifest_path)
    existing: list = []
    if manifest_path.is_file():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        except ValueError:
            existing = []
    existing.append(entry)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest_path
