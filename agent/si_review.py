"""
Standing Interview review queue -- what the next sprint has to look at.

WHY THIS EXISTS
BL-079 requires that saved refusals and dissatisfied answers are visible to the
sprint process. They are written to the durable event ledger (see
event_ledger.py's KNOWN_EVENT_TYPES) rather than to a file, because a file on
the deployed container does not survive a redeploy and a file committed to this
public repository would contain whatever text an interviewer typed.

So "visible to the sprint process" means: a person or agent running this
command before planning the next sprint, the same way they already run
backlog.py and verify_tracking_updated.py.

Two outcomes are deliberately kept apart:
  REFUSAL      -- the system declined to answer. Usually a corpus coverage gap,
                  sometimes a correctly-refused out-of-scope question.
  DISSATISFIED -- a human read the answer and said it was wrong or weak. This
                  is the more expensive signal: it means retrieval found
                  something and the answer still missed.

Run:  python agent/si_review.py            # pending review queue
      python agent/si_review.py --limit 50
      python agent/si_review.py --json
"""

import argparse
import json
import sys

REVIEW_EVENT_TYPES = ("standing_interview_refusal", "standing_interview_dissatisfied")


def fetch(limit: int = 25) -> dict:
    """Read the queue from the ledger, falling back to the local spool. Returns
    a dict with an explicit `source` so the reader always knows whether they are
    looking at durable rows or at un-synced local ones -- silently mixing the
    two would make an empty remote look like an empty queue."""
    import event_ledger as el

    rows, source, error = [], None, None
    try:
        conn = el._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT event_id, timestamp_utc, event_type, payload "
                    "FROM delivery_events WHERE event_type = ANY(%s) "
                    "ORDER BY timestamp_utc DESC LIMIT %s",
                    (list(REVIEW_EVENT_TYPES), limit),
                )
                for event_id, ts, etype, payload in cur.fetchall():
                    rows.append({"event_id": event_id, "at": str(ts), "type": etype,
                                 "payload": payload or {}})
            source = "ledger"
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001 - a review tool must still work offline
        error = f"{type(exc).__name__}: {exc}"
        spool = el.SPOOL_PATH if hasattr(el, "SPOOL_PATH") else None
        if spool and spool.exists():
            for line in spool.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    env = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if env.get("event_type") in REVIEW_EVENT_TYPES:
                    rows.append({"event_id": env.get("event_id"),
                                 "at": env.get("timestamp_utc"),
                                 "type": env.get("event_type"),
                                 "payload": env.get("payload") or {}})
            rows = rows[-limit:]
            source = "local spool (ledger unreachable)"
        else:
            source = "unavailable"

    counts = {t: sum(1 for r in rows if r["type"] == t) for t in REVIEW_EVENT_TYPES}
    return {"source": source, "error": error, "counts": counts, "rows": rows}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    q = fetch(args.limit)
    if args.json:
        print(json.dumps(q, indent=2, default=str))
        return 0

    print("=" * 72)
    print("STANDING INTERVIEW -- REVIEW QUEUE")
    print(f"source: {q['source']}")
    if q["error"]:
        print(f"note  : ledger unreachable -- {q['error']}")
    print("=" * 72)
    print(f"refusals     : {q['counts']['standing_interview_refusal']}")
    print(f"dissatisfied : {q['counts']['standing_interview_dissatisfied']}")
    if not q["rows"]:
        print("\nnothing pending review.")
        if q["source"] == "unavailable":
            print("WARNING: neither the ledger nor a local spool was readable, so an")
            print("empty queue here does NOT mean there is nothing to review.")
            return 1
        return 0

    for r in q["rows"]:
        p = r["payload"]
        kind = "REFUSED " if r["type"].endswith("refusal") else "UNHAPPY "
        print(f"\n{kind} {r['at']}  [{r.get('event_id', '')[:8]}]")
        print(f"  question : {str(p.get('question', ''))[:160]}")
        if p.get("outcome"):
            print(f"  outcome  : {p['outcome']}"
                  + (f"   best_score={p['best_score']}" if p.get("best_score") is not None else "")
                  + (f"   scope={p['scope']}" if p.get("scope") else ""))
        if p.get("answer"):
            print(f"  answer   : {str(p['answer'])[:200]}")
        if p.get("leaks"):
            print(f"  !! LEAK BLOCKED: {p['leaks']}")
    print("\nTriage these into docs/ACTION_QUEUE.json or docs/BACKLOG.json before "
          "planning the next sprint.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
