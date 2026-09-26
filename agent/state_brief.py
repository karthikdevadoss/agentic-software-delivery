"""
Session-startup state brief -- a VIEW over the three durable state documents,
never a fourth copy of them.

WHY THIS EXISTS
CLAUDE.md's session-startup steps 1, 2 and 5 mandate reading three files in
full. Measured 2026-09-25:

    docs/PROJECT_STATE.json   244,401 B
    docs/PROJECT_STATUS.md     59,349 B
    docs/ACTION_QUEUE.json     98,679 B
    ----------------------------------
                              402,429 B, every session, before any work starts

Almost all of that is history, not current state: `verification_state` +
`completed_capabilities` are 95% of PROJECT_STATE.json; 15 dated "Current
Reality" sections + "Completed versions" are 88% of PROJECT_STATUS.md; 23 of
the 33 ACTION_QUEUE items are already resolved/verified/deferred. History is
worth keeping -- this repo's rule is that condensing must never delete data --
but it does not have to be re-read on every single session start to answer
"what version, what ticket, what's verified, what's next, what's still open".

SO: this script prints exactly what steps 1/2/5/10 actually ask for, quotes
the source path next to every block, and reads nothing into a file.

THREE DESIGN CONSTRAINTS, each protecting against a specific failure:

1. IT NEVER WRITES ANYTHING. No output file, no cache, nothing committed.
   A generated summary that gets committed becomes a fourth state document
   that drifts from the three real ones -- the exact "competing source of
   truth" problem this is meant to avoid. stdout only.

2. IT FAILS LOUDLY RATHER THAN SILENTLY DROPPING CONTENT. If a required
   PROJECT_STATUS.md heading is renamed, or ACTION_QUEUE.json grows a status
   value this script does not classify, the brief exits non-zero and names
   what it could not account for. A brief that quietly omits open work is
   worse than no brief -- it would look complete. Same discipline as
   ci_python_tests.py's unaccounted-module guard.

3. IT SURFACES STALENESS INSTEAD OF HIDING IT. PROJECT_STATE.json records
   `last_verified_code_commit`; real git says how far HEAD has moved past it.
   When it is behind, the brief says so in a banner, because under the
   evidence-precedence rule in CLAUDE.md real repository evidence outranks a
   committed state document. Deliberately NOT auto-updated: making the number
   go away by rewriting the doc would destroy the only signal that the doc is
   unverified.

REAL MEASURED EFFECT (2026-09-25, Anthropic count_tokens, model claude-opus-5,
not an estimate): mandatory session-startup context went from 429,450 B /
161,457 tokens (CLAUDE.md + the three documents read in full) to 37,169 B /
13,607 tokens (CLAUDE.md + this brief's output) -- 147,850 tokens saved per
session, 91.6%.

Run:  python agent/state_brief.py
      python agent/state_brief.py --json    # same content, machine-readable
"""

import json
import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PROJECT_STATE = REPO_ROOT / "docs" / "PROJECT_STATE.json"
PROJECT_STATUS = REPO_ROOT / "docs" / "PROJECT_STATUS.md"
ACTION_QUEUE = REPO_ROOT / "docs" / "ACTION_QUEUE.json"

# --- PROJECT_STATE.json -----------------------------------------------------
# Exactly what CLAUDE.md step 10 asks to be reported ("current version, current
# ticket, verified state and exact next action"), plus the staleness inputs.
# Deliberately EXCLUDED and left in the file: `completed_capabilities` (77,515 B)
# and `verification_state` (154,358 B) -- 95% of the document, and both are
# historical records rather than answers to "what do I do next". The verified
# state is reported as a real computed summary below, not dropped.
STATE_KEYS = [
    "project",
    "current_version",
    "current_ticket",
    "current_ticket_implemented",
    "next_phase",
    "next_action",
    "blocked_on",
    "missing_capabilities",
    "open_defects",
    "last_updated",
    "last_verified_code_commit",
]

# --- PROJECT_STATUS.md ------------------------------------------------------
# The four current-facing headings. Everything else in that file is dated
# history ("Current Reality (2026-09-10)" x15, "Completed versions"), which is
# 88% of its bytes and answers no startup question.
# These are matched EXACTLY. A rename must break this script, not silently
# produce a brief that is missing a section.
REQUIRED_STATUS_HEADINGS = [
    "# Exact next development step",
    "# What does NOT exist yet",
    "# Current architecture",
    "# Useful commands",
]

# KNOWN STALE, measured 2026-09-25 by a real fresh-session recovery test.
# docs/PROJECT_STATUS.md carries no `last_verified` marker of its own, so unlike
# PROJECT_STATE.json there is nothing to compute staleness FROM -- the only
# honest signal available is this hand-verified list. Three of the four sections
# the brief promotes have current-sounding TITLES but pre-V4-era CONTENT; the
# heading survived while the project moved on underneath it. Each reason below
# was checked against the real file and against real git before being written.
#
# These are LABELLED, not removed: removing them would lose information, and the
# committed prose is still the only place some of this is written down. The
# correction to the document itself is a project-facts change and belongs to the
# Owner, not to this script -- so this list must SHRINK by re-verification, never
# by someone finding the warning inconvenient.
KNOWN_STALE_HEADINGS = {
    # EMPTY IS THE HEALTHY STATE, and it is empty as of 2026-09-26.
    # The three sections listed here on 2026-09-25 -- "Exact next development
    # step", "What does NOT exist yet" and "Current architecture" -- were
    # CORRECTED in docs/PROJECT_STATUS.md rather than left labelled, so the
    # warning is no longer true and has been withdrawn. That is the only
    # legitimate way an entry leaves this dict: the document was fixed and
    # re-verified. Deleting an entry because the banner is inconvenient, while
    # the prose is still stale, is the failure this comment exists to prevent.
}

# --- ACTION_QUEUE.json ------------------------------------------------------
# ACTIVE = work that is not finished. `blocked` is active: blocked work is open
# work that happens to be stuck, and losing it from the brief is precisely the
# silent-loss failure this guard exists to prevent.
ACTIVE_STATUSES = {"open", "in_progress", "ready_for_human_approval", "blocked"}
# TERMINAL = finished or deliberately parked; history, reported only as a count.
TERMINAL_STATUSES = {"resolved", "verified", "deferred"}


def _git(*args) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=30
        ).stdout.strip()
    except Exception:
        return ""


def collect_state(state: dict) -> dict:
    missing = [k for k in STATE_KEYS if k not in state]
    if missing:
        raise SystemExit(
            f"FAIL: docs/PROJECT_STATE.json is missing required key(s): {missing}\n"
            "The brief will not print a partial picture. Either the key was renamed\n"
            "(update STATE_KEYS here) or real state was lost (restore it)."
        )
    out = {k: state[k] for k in STATE_KEYS}

    # Verified state, computed rather than dumped. 86 capability entries ->
    # counts + the names of anything not actually verified, which is the only
    # part a startup report needs to act on.
    vs = state.get("verification_state", {})
    declared = set(vs.get("_status_values", []))
    counts, undeclared, unverified = {}, {}, []
    for name, entry in vs.items():
        if name.startswith("_"):
            continue
        status = entry.get("status") if isinstance(entry, dict) else str(entry)
        counts[status] = counts.get(status, 0) + 1
        if declared and status not in declared:
            undeclared[name] = status
        if status in ("not_verified",) or (declared and status not in declared):
            unverified.append(f"{name} ({status})")
    out["_verification_summary"] = {
        "total": sum(counts.values()),
        "by_status": counts,
        "needs_attention": sorted(unverified),
        # NOT fatal: an undeclared status here is documentation drift, not lost
        # work -- unlike ACTION_QUEUE, where an unrecognised status could hide
        # an open item. Surfaced loudly, never silently normalised away.
        "undeclared_statuses": undeclared,
    }
    return out


def collect_status_sections() -> dict:
    text = PROJECT_STATUS.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    starts = [(i, l.rstrip("\n")) for i, l in enumerate(lines) if l.startswith("# ")]
    sections = {}
    for idx, (i, head) in enumerate(starts):
        end = starts[idx + 1][0] if idx + 1 < len(starts) else len(lines)
        sections[head] = "".join(lines[i:end]).rstrip() + "\n"

    absent = [h for h in REQUIRED_STATUS_HEADINGS if h not in sections]
    if absent:
        raise SystemExit(
            "FAIL: docs/PROJECT_STATUS.md no longer contains required heading(s):\n"
            + "".join(f"  {h}\n" for h in absent)
            + "This brief replaces the full read of that file at session startup, so a\n"
            "renamed or deleted heading would silently remove current-state information\n"
            "from every future session. Restore the heading, or update\n"
            "REQUIRED_STATUS_HEADINGS in agent/state_brief.py deliberately."
        )
    return {h: sections[h] for h in REQUIRED_STATUS_HEADINGS}


def collect_queue() -> dict:
    queue = json.loads(ACTION_QUEUE.read_text(encoding="utf-8"))
    items = queue["items"]

    seen = {i.get("status") for i in items}
    unknown = sorted(s for s in seen if s not in ACTIVE_STATUSES | TERMINAL_STATUSES)
    if unknown:
        raise SystemExit(
            f"FAIL: docs/ACTION_QUEUE.json contains unclassified status value(s): {unknown}\n"
            "This brief is what session startup reads instead of the full queue. An\n"
            "unclassified status would be neither shown as active nor counted as done --\n"
            "it would simply vanish. Add each value to ACTIVE_STATUSES or\n"
            "TERMINAL_STATUSES in agent/state_brief.py before proceeding."
        )

    active = [
        {"id": i["id"], "status": i["status"], "priority": i.get("priority"), "title": i["title"]}
        for i in items
        if i.get("status") in ACTIVE_STATUSES
    ]
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    active.sort(key=lambda i: (order.get(i["priority"], 9), i["id"]))
    return {"active": active, "total": len(items)}


def collect_staleness(state: dict) -> dict:
    recorded = state.get("last_verified_code_commit", "")
    head = _git("rev-parse", "--short", "HEAD")
    behind_raw = _git("rev-list", "--count", f"{recorded}..HEAD") if recorded else ""
    try:
        behind = int(behind_raw)
    except ValueError:
        behind = None  # unknown commit, shallow clone, or git unavailable
    return {
        "last_updated": state.get("last_updated"),
        "last_verified_code_commit": recorded,
        "head": head,
        "commits_behind": behind,
        "dirty": bool(_git("status", "--short")),
    }


def build() -> dict:
    state = json.loads(PROJECT_STATE.read_text(encoding="utf-8"))
    return {
        "state": collect_state(state),
        "status_sections": collect_status_sections(),
        "queue": collect_queue(),
        "staleness": collect_staleness(state),
        "sources": {
            "state": "docs/PROJECT_STATE.json",
            "status": "docs/PROJECT_STATUS.md",
            "queue": "docs/ACTION_QUEUE.json",
        },
    }


def render(brief: dict) -> str:
    out = []
    w = out.append
    st, stale, q = brief["state"], brief["staleness"], brief["queue"]

    w("=" * 74)
    w("SESSION STATE BRIEF -- a view over three documents, not a fourth one.")
    w("Every block below quotes the file it came from. Nothing here is generated")
    w("knowledge; when this disagrees with the real repository, the repository wins")
    w("(evidence precedence, CLAUDE.md).")
    w("=" * 74)

    # --- staleness first: it changes how everything below should be read ---
    if stale["commits_behind"] is None:
        w("")
        w(f"!! STALENESS UNKNOWN -- could not resolve last_verified_code_commit "
          f"{stale['last_verified_code_commit']!r} against this checkout.")
    elif stale["commits_behind"] > 0:
        w("")
        w("!! " + "-" * 68)
        w(f"!! STALE STATE: docs/PROJECT_STATE.json is {stale['commits_behind']} commits behind HEAD.")
        w(f"!!   last_updated              : {stale['last_updated']}")
        w(f"!!   last_verified_code_commit : {stale['last_verified_code_commit']}")
        w(f"!!   real HEAD                 : {stale['head']}")
        w("!! Treat next_action/current_ticket below as a HISTORICAL CLAIM, not a")
        w("!! verified instruction. Check git log for what actually happened since,")
        w("!! before acting on it. Do NOT 'fix' this by editing the date.")
        w("!! " + "-" * 68)
    else:
        w("")
        w(f"State is current with HEAD ({stale['head']}).")
    if stale["dirty"]:
        w("   (working tree has uncommitted changes -- run git status --short)")

    w("")
    w("--- docs/PROJECT_STATE.json ------------------------------------------")
    w(f"project        : {st['project']}")
    w(f"current_version: {st['current_version']}")
    w(f"current_ticket : {st['current_ticket']}")
    w(f"  implemented  : {st['current_ticket_implemented']}")
    w(f"next_phase     : {st['next_phase']}")
    w(f"blocked_on     : {st['blocked_on'] or '(nothing)'}")
    w("next_action    :")
    for line in str(st["next_action"]).splitlines() or [""]:
        w(f"  {line}")

    vsum = st["_verification_summary"]
    w("")
    w(f"verified state : {vsum['total']} capability entries -- "
      + ", ".join(f"{k}={v}" for k, v in sorted(vsum["by_status"].items())))
    if vsum["needs_attention"]:
        w("  NOT fully verified:")
        for name in vsum["needs_attention"]:
            w(f"    - {name}")
    if vsum["undeclared_statuses"]:
        w("  !! status value(s) not in _status_values (doc drift, not lost work):")
        for name, status in sorted(vsum["undeclared_statuses"].items()):
            w(f"    - {name}: {status}")
    w("  (full per-capability evidence stays in docs/PROJECT_STATE.json)")

    if st["open_defects"]:
        opens = [d for d in st["open_defects"] if isinstance(d, dict) and d.get("status") != "closed"]
        w(f"open_defects   : {len(opens)} open of {len(st['open_defects'])} recorded")
        for d in opens:
            w(f"    - {d.get('id')}: {str(d.get('evidence',''))[:110]}")
    if st["missing_capabilities"]:
        w(f"missing_capabilities: {len(st['missing_capabilities'])} "
          "(full list in docs/PROJECT_STATE.json)")

    w("")
    w("--- docs/ACTION_QUEUE.json -------------------------------------------")
    w(f"{len(q['active'])} ACTIVE of {q['total']} total items "
      f"(active = {', '.join(sorted(ACTIVE_STATUSES))})")
    for item in q["active"]:
        w(f"  [{item['priority']:<8}] {item['id']:<9} {item['status']:<24} {item['title']}")
    if not q["active"]:
        w("  (none open)")
    w("  (resolved/verified/deferred history stays in docs/ACTION_QUEUE.json)")

    w("")
    w("--- docs/PROJECT_STATUS.md (4 sections, verbatim) --------------------")
    w("!! COMMITTED PROSE -- NOT INDEPENDENTLY VERIFIED CURRENT STATE.")
    w("!! This file carries no last_verified marker, so nothing here has been")
    w("!! checked against the real repository. Under the evidence-precedence rule")
    w("!! it ranks BELOW anything you observe directly from git or a live run:")
    w("!! if a command's real output disagrees with a line below, the output wins.")
    if KNOWN_STALE_HEADINGS:
        w(f"!! {len(KNOWN_STALE_HEADINGS)} of these sections are KNOWN STALE as of "
          "2026-09-25 and are marked")
        w("!! individually below. Verify before acting on any of them.")
    for heading, body in brief["status_sections"].items():
        w("")
        why = KNOWN_STALE_HEADINGS.get(heading)
        if why:
            w(f"!! KNOWN STALE ({heading.lstrip('# ')}) -- {why}.")
            w("!! Reproduced verbatim below because the text is still the only record;")
            w("!! do NOT act on it without verifying against git/runtime first.")
        w(body.rstrip())
    w("")
    w("(dated 'Current Reality' history and 'Completed versions' remain in")
    w(" docs/PROJECT_STATUS.md -- read the file directly when history matters.)")
    w("=" * 74)
    return "\n".join(out)


def main() -> int:
    # The source documents contain non-ASCII (arrows, em dashes). Windows'
    # default cp1252 stdout raises UnicodeEncodeError on them, which would make
    # the brief crash on the very platform this project runs on.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    brief = build()
    if "--json" in sys.argv:
        print(json.dumps(brief, indent=2))
    else:
        print(render(brief))
    return 0


if __name__ == "__main__":
    sys.exit(main())
