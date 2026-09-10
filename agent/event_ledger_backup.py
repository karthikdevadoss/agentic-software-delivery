"""
On-demand, portable logical backup of the durable event ledger.

This is NOT a substitute for Railway's own Point-in-Time Recovery (PITR)
— see docs/RESOURCE_REGISTRY.md for the current PITR status (disabled as
of last verification) and why enabling it was left as an explicit next
action rather than auto-enabled (it provisions billed cloud storage, a
cost/production decision, not a default-safe one to make unattended).

This script exists because `pg_dump`/the Postgres client tools are not
installed on this laptop (only the psycopg2 driver is), so a portable
dump is done at the row level via the same connection this whole ledger
already uses — good enough to prove a real, restorable-in-principle
export exists today, not good enough to call this "backups enabled."

A REAL RESTORE HAS NOT BEEN TESTED. Per CLAUDE.md: a backup is not
considered proven recovery until a restore has actually been performed.
That restore drill is a recorded, explicit gap — not silently assumed.

Run: python agent/event_ledger_backup.py
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import event_ledger

BACKUP_DIR = Path(__file__).resolve().parent / "event_ledger_backups"


def dump_to_file(path: Path = None) -> dict:
    """Dumps every row of delivery_events, in full, to one JSONL file —
    one real row per line, nothing summarized or sampled. Returns the
    path written and the row count actually dumped (never estimated)."""
    conn = event_ledger._connect()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT {', '.join(event_ledger.ENVELOPE_FIELDS)}, ingested_at FROM delivery_events ORDER BY timestamp_utc ASC")
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
    finally:
        conn.close()

    if path is None:
        BACKUP_DIR.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = BACKUP_DIR / f"delivery_events_{stamp}.jsonl"

    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            record = dict(zip(cols, row))
            f.write(json.dumps(record, default=str) + "\n")

    return {"path": str(path), "rows_dumped": len(rows)}


if __name__ == "__main__":
    result = dump_to_file()
    print(f"BACKUP WRITTEN: {result['path']} ({result['rows_dumped']} rows)")
