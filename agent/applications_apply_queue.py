"""Applications Review apply queue (Automation Sprint 13).

Owner taps Approve on the gated /applications page. This module records the
yes + timestamp and keeps a durable queue:

  approved → pending_apply → applied | failed

The web process NEVER submits an application to an employer. Mahadeva (or a
parent agent) reads pending_apply entries and applies via the employer careers
form or email apply link in the pack — never LinkedIn scrape / Easy Apply, and
never without an Approve tap.

Queue path defaults to agent/applications_apply_queue.json (overridable via
APPLICATIONS_APPLY_QUEUE_PATH). Survives process restart on the same
filesystem; Railway ephemeral disks may reset on redeploy — Mahadeva should
also mirror status into DEVADOSS storage/career when updating applied/failed.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()

DEFAULT_QUEUE_PATH = Path(__file__).resolve().parent / "applications_apply_queue.json"

STATUSES = ("approved", "pending_apply", "applied", "failed")

# After Owner Approve, entry is immediately claimable by Mahadeva.
OWNER_APPROVE_STATUS = "pending_apply"


def queue_path() -> Path:
    raw = (os.environ.get("APPLICATIONS_APPLY_QUEUE_PATH") or "").strip()
    if raw:
        return Path(raw)
    return DEFAULT_QUEUE_PATH


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _empty() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": None,
        "items": [],
        "_status_values": list(STATUSES),
        "_note": (
            "Owner Approve on /applications records yes + approved_at. "
            "Web never applies. Mahadeva applies only for pending_apply."
        ),
    }


def _read_unlocked(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return _empty()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty()
    if not isinstance(data, dict):
        return _empty()
    items = data.get("items")
    if not isinstance(items, list):
        data["items"] = []
    return data


def _write_unlocked(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = _now_iso()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_queue() -> dict[str, Any]:
    with _LOCK:
        return _read_unlocked(queue_path())


def find_item(pack_id: str) -> dict[str, Any] | None:
    data = load_queue()
    for item in data.get("items", []):
        if item.get("pack_id") == pack_id:
            return dict(item)
    return None


def record_owner_approve(pack: dict[str, Any]) -> dict[str, Any]:
    """Record Owner Approve for one pack. Idempotent if already approved+.

    Sets status to pending_apply so Mahadeva can pick it up. Does not apply.
    """
    pack_id = (pack.get("id") or "").strip()
    if not pack_id:
        raise ValueError("pack.id is required")

    with _LOCK:
        path = queue_path()
        data = _read_unlocked(path)
        for item in data["items"]:
            if item.get("pack_id") == pack_id:
                # Already recorded — do not downgrade applied/failed.
                return dict(item)

        now = _now_iso()
        entry = {
            "pack_id": pack_id,
            "slug": pack.get("slug") or "",
            "company": pack.get("company") or "",
            "title": pack.get("title") or "",
            "location": pack.get("location") or "",
            "url": pack.get("url") or "",
            "cv_pdf": pack.get("cv_pdf") or "",
            "apply_route": "employer_careers_or_email",
            "owner_approved": True,
            "approved_at": now,
            "status": OWNER_APPROVE_STATUS,
            "claimed_at": None,
            "applied_at": None,
            "failed_at": None,
            "proof": {},
            "error": None,
            "notes": (
                "Owner tapped Approve on Applications Review. "
                "Mahadeva must apply via employer form or email link only; "
                "no LinkedIn Easy Apply; never without this Approve."
            ),
        }
        data["items"].append(entry)
        _write_unlocked(path, data)
        return dict(entry)


def update_item(
    pack_id: str,
    *,
    status: str | None = None,
    proof: dict[str, Any] | None = None,
    error: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Mahadeva updates queue status / proof. Never invents Owner Approve."""
    pack_id = (pack_id or "").strip()
    if not pack_id:
        raise ValueError("pack_id is required")
    if status is not None and status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")

    with _LOCK:
        path = queue_path()
        data = _read_unlocked(path)
        for item in data["items"]:
            if item.get("pack_id") != pack_id:
                continue
            if not item.get("owner_approved"):
                raise ValueError("cannot update: Owner has not Approved this pack")
            if status is not None:
                item["status"] = status
                if status == "pending_apply" and not item.get("claimed_at"):
                    item["claimed_at"] = _now_iso()
                elif status == "applied":
                    item["applied_at"] = _now_iso()
                    item["failed_at"] = None
                    item["error"] = None
                elif status == "failed":
                    item["failed_at"] = _now_iso()
            if proof is not None:
                if not isinstance(proof, dict):
                    raise ValueError("proof must be an object")
                item["proof"] = proof
            if error is not None:
                item["error"] = error
            if notes is not None:
                item["notes"] = notes
            _write_unlocked(path, data)
            return dict(item)
        raise KeyError(f"no queue item for pack_id={pack_id!r}")


def load_pack_by_id(applications_json: Path, pack_id: str) -> dict[str, Any] | None:
    if not applications_json.is_file():
        return None
    try:
        payload = json.loads(applications_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    for pack in payload.get("packs") or []:
        if pack.get("id") == pack_id:
            return pack
    return None
