"""Re-run the audit's questions against live production and archive the answers.

Sprint 15. The Sprint 15 specification fix changes what the Standing Interview
is INSTRUCTED to do. That is not evidence that it changed what the model
actually does -- the audit's central finding was that a confident prompt rule
and a measured outcome are different things. This script produces the
measurement.

    python agent/si_recapture.py                 # the 6 questions that failed worst
    python agent/si_recapture.py --all           # all 23 audit questions
    python agent/si_recapture.py --draws 3       # more draws per question

Output: agent/testdata/si_production_answers_after.json, in the same shape as
the archived baseline, which agent/test_si_quality.py then scores.

COST. Every request is a real model call against real production. The audit's
63 requests cost $1.4353 -- about $0.023 each -- so the default 18 requests is
roughly $0.41 and --all with 3 draws is roughly $1.59. The default is
deliberately the small one: the six worst questions are where the defect was
measured, so they are where the fix has to show. Nothing here changes a spend
limit, and the total is printed before anything is sent.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

import paid_test_guard

PROD = "https://agentic-platform-backend-production.up.railway.app"
OUT = pathlib.Path(__file__).parent / "testdata" / "si_production_answers_after.json"
BASELINE = pathlib.Path(__file__).parent / "testdata" / "si_production_answers.json"

# The questions carrying the defect, in the audit's own lettering. This is
# where the fix has to show up: a and b are the Owner's two examples, and
# e/f/g/w were the next worst by volunteered-negative count.
#
# "m" is here for a different reason. It is the OVER-REFUSAL case -- "describe
# a technical disagreement and how you resolved it", declined on all three
# baseline draws -- and leaving it out would let
# test_a_legitimate_interview_question_is_not_refused pass VACUOUSLY, by
# measuring a capture that contains nothing it could fail on. A test that
# passes because it was handed no refusable question is worse than one that
# stays red over a known, documented, Owner-blocked corpus gap.
WORST = ["a", "b", "e", "f", "g", "w", "m"]

APPROX_USD_PER_REQUEST = 0.023   # $1.4353 / 63, from the audit's real total


def _questions(all_questions: bool) -> list[tuple[str, str]]:
    """The audit's questions, read back out of the archived baseline so the
    before/after comparison is question-for-question."""
    if not BASELINE.exists():
        sys.exit(f"missing baseline at {BASELINE}")
    recs = json.loads(BASELINE.read_text(encoding="utf-8"))
    seen: dict[str, str] = {}
    for r in recs:
        seen.setdefault(r["question_id"], r["question"])
    wanted = sorted(seen) if all_questions else [q for q in WORST if q in seen]
    return [(qid, seen[qid]) for qid in wanted]


def _ask(question: str, timeout: int = 90) -> dict:
    payload = json.dumps({"question": question}).encode("utf-8")
    req = urllib.request.Request(
        PROD + "/api/standing-interview/ask",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            # The spend cap refused us. That is the cap working, but it means
            # this capture is INCOMPLETE -- say so loudly rather than storing
            # the refusal text as though it were an answer.
            raise RuntimeError(
                "rate limited by the deployed spend cap (HTTP 429). The capture "
                "would be incomplete; raise the sleep or wait for the daily "
                "window to reset.") from None
        raise


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true",
                    help="all 23 audit questions instead of the 6 worst")
    ap.add_argument("--draws", type=int, default=3,
                    help="draws per question (default 3, matching the audit)")
    ap.add_argument("--yes", action="store_true",
                    help="skip the cost confirmation")
    args = ap.parse_args()

    # SPRINT 17: the mechanical half of "spend zero unless someone said
    # otherwise". Before this, the only thing between a stray invocation and
    # ~$0.41-$1.59 of real spend was an interactive y/N prompt that --yes
    # bypasses -- and --yes is exactly what any script, CI step or agent would
    # pass. The guard runs FIRST, before the question list is even built and
    # long before a request is constructed, so a refusal is provably pre-call.
    #
    # It requires BOTH ALLOW_PAID_TESTS=1 AND a positive PAID_TEST_BUDGET_USD.
    # The interactive confirmation below is kept, not replaced: a human at a
    # terminal should still see the real figure and agree to it. This guard is
    # for the case where no human is there.
    try:
        authorized_budget = paid_test_guard.require_paid_tests_allowed(
            "si-answer-quality-paid (agent/si_recapture.py)")
    except paid_test_guard.PaidTestsNotAuthorized as exc:
        print(exc, file=sys.stderr)
        return 3

    questions = _questions(args.all)
    total = len(questions) * args.draws
    cost = total * APPROX_USD_PER_REQUEST

    print(f"paid tests  : AUTHORIZED, declared budget ${authorized_budget:.2f}")
    print(f"target      : {PROD}")
    print(f"questions   : {len(questions)}  ({', '.join(q for q, _ in questions)})")
    print(f"draws each  : {args.draws}")
    print(f"requests    : {total}")
    print(f"est. cost   : ~${cost:.2f}  (ESTIMATE from the audit's real "
          f"${APPROX_USD_PER_REQUEST}/request -- not an actual figure)")
    if not args.yes:
        if input("proceed? [y/N] ").strip().lower() not in ("y", "yes"):
            print("aborted; nothing sent")
            return 1

    records, failures = [], 0
    for qid, qtext in questions:
        for draw in range(1, args.draws + 1):
            try:
                data = _ask(qtext)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                failures += 1
                print(f"  {qid}/draw {draw}: REQUEST FAILED -- {exc}")
                continue
            records.append({
                "question_id": qid,
                "draw": draw,
                "question": qtext,
                "outcome": data.get("outcome", "unknown"),
                "answer": (data.get("answer") or "").strip(),
                "grounded": data.get("grounded"),
                "captured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
            print(f"  {qid}/draw {draw}: {data.get('outcome')} "
                  f"({len((data.get('answer') or '').split())} words)")
            # Must exceed si_budget.SI_PER_VISITOR_MIN_SECONDS (5s), or this
            # script trips the very cooldown it deployed and 429s itself.
            time.sleep(6.0)

    if not records:
        print("NOTHING CAPTURED -- not writing a file. "
              "An empty capture must never be mistaken for a clean result.")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {len(records)} records to {OUT}")
    if failures:
        print(f"WARNING: {failures} request(s) failed and are absent from the "
              f"capture -- the measurement is incomplete, not clean.")

    # Score it immediately, so the result is visible without a second command.
    try:
        import si_quality
    except ImportError:
        return 0
    answered = [r for r in records if r["outcome"] == "answered"]
    bad = tot = 0
    for r in answered:
        rep = si_quality.assess(r["question"], r["answer"], r["outcome"])
        if rep.unsolicited:
            bad += 1
            tot += len(rep.unsolicited)
    # Compare against the SAME questions in the baseline, not against the
    # 57-answer headline -- a 21-request sample and a 63-request capture are
    # not the same measurement, and presenting one as the other would be
    # exactly the sort of number this project exists to not produce.
    asked = {r["question_id"] for r in records}
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    base_same = [r for r in base
                 if r["question_id"] in asked and r["outcome"] == "answered"]
    b_bad = b_tot = 0
    for r in base_same:
        rep = si_quality.assess(r["question"], r["answer"], r["outcome"])
        if rep.unsolicited:
            b_bad += 1
            b_tot += len(rep.unsolicited)

    print()
    print(f"  LIKE FOR LIKE, questions {''.join(sorted(asked))}")
    print(f"  BEFORE : {b_tot} unsolicited negatives across {b_bad} of "
          f"{len(base_same)} answered")
    print(f"  AFTER  : {tot} unsolicited negatives across {bad} of "
          f"{len(answered)} answered")
    refused_before = sorted({r["question_id"] for r in base
                             if r["question_id"] in asked
                             and r["outcome"] != "answered"})
    refused_after = sorted({r["question_id"] for r in records
                            if r["outcome"] != "answered"})
    print(f"  declined before: {refused_before or 'none'}")
    print(f"  declined after : {refused_after or 'none'}")
    print()
    print("  Full-baseline context (NOT like-for-like, quoted for reference):")
    print("  37 unsolicited negatives across 21 of 57 answered, "
          "deploy-20260929T004905Z-8533d67")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
