"""
Crash / restart drill for the durable workflow -- Sprint 13, BL-094.

This is the deterministic evidence the Owner asked for, produced by real
process deaths rather than by mocking. Every phase runs in its OWN
Python process against the real Postgres checkpoint store, so "the system
reloads the persisted workflow state" is literally a fresh interpreter with
no memory of the previous one.

    python agent/workflow_drill.py --run-all [--source-repo <path-or-url>]

Phases (each a separate process; the orchestrator only spawns and asserts):
  1. start          -> WAITING_FOR_APPROVAL, checkpoint exists
  2. describe       -> a NEW process still sees WAITING_FOR_APPROVAL
                       ("interruption before approval resumes still waiting")
  3. approve + KILL -> the child approves; inside the apply stage, AFTER the
                       git commit and BEFORE LangGraph checkpoints the node,
                       it prints DRILL_PAUSE and blocks; the orchestrator
                       kills it (TerminateProcess / SIGKILL). Real death,
                       side effect on disk, checkpoint not yet advanced.
  4. continue       -> a NEW process resumes: the apply node re-runs, finds
                       its own commit by binding hash, records
                       skipped_duplicate=True, and compile/test/verify run to
                       COMPLETED. The workspace holds exactly ONE workflow
                       commit.
  5. approve again  -> refused (completed workflow cannot execute again)
  6. reject-after-  -> a second workflow is rejected, then an approve is
     reject             attempted: refused, no workspace ever created
  7. corrupt        -> a checkpoint row is overwritten with garbage; the
                       workflow is reported CORRUPT and refuses to resume
  8. before_compile -> a third workflow is killed AFTER the apply checkpoint
                       and BEFORE compile; on continue the apply node does
                       not run at all (no second APPLIED transition)

Evidence is written to agent/.workflow_drill_evidence/<stamp>.json with
every observed state, commit count, transition list and the exit code of
each phase. Exit code 0 only if every assertion held.

Needs: EVENT_LEDGER_DATABASE_URL (the checkpoint tables live there), git,
a JDK for the real `mvnw compile` inside the workspace clone. It is a
LIVE-INFRASTRUCTURE module and is deliberately NOT in the hermetic CI tier.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time
import uuid

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

try:
    from dotenv import load_dotenv
    load_dotenv(HERE / ".env")
except Exception:
    pass

EVIDENCE_DIR = HERE / ".workflow_drill_evidence"
# The heading operation, not the footer: the catalogue's footer anchor does not
# match the real index.html (a <span> sits inside the footer), which the first
# drill run found -- recorded as an ACTION_QUEUE item, and a real finding of
# the drill rather than a drill defect.
FOOTER_REQ = 'Change the heading text to "Drill {stamp}"'


def _saver():
    from workflow_checkpointer import PostgresWorkflowCheckpointer
    return PostgresWorkflowCheckpointer()


def _commits(workspace: str) -> int:
    if not workspace or not pathlib.Path(workspace).is_dir():
        return 0
    out = subprocess.run(["git", "log", "--format=%s"], cwd=workspace,
                         capture_output=True, text=True).stdout
    return sum(1 for l in out.splitlines() if l.startswith("workflow "))


# --- single phases (each runs in its own process) ---------------------------
def phase_start(wid: str, req: str) -> dict:
    import durable_workflow as dw
    return dw.start_workflow(req, _saver(), workflow_id=wid)


def phase_describe(wid: str) -> dict:
    import durable_workflow as dw
    return dw.describe_workflow(wid, _saver())


def phase_approve(wid: str, decision: str) -> dict:
    import durable_workflow as dw
    saver = _saver()
    d = dw.describe_workflow(wid, saver)
    binding = (d.get("proposal") or {}).get("binding") or ""
    return dw.resume_workflow(wid, decision, binding, "drill-orchestrator", saver)


def phase_continue(wid: str) -> dict:
    import durable_workflow as dw
    return dw.continue_workflow(wid, _saver())


def phase_corrupt(wid: str) -> dict:
    import durable_workflow as dw
    import event_ledger
    conn = event_ledger._connect()   # noqa: SLF001
    try:
        with conn, conn.cursor() as cur:
            cur.execute("UPDATE workflow_checkpoints SET checkpoint=%s WHERE thread_id=%s",
                        (b"\x00garbage", wid))
            n = cur.rowcount
    finally:
        conn.close()
    d = dw.describe_workflow(wid, _saver())
    c = dw.continue_workflow(wid, _saver())
    return {"rows_corrupted": n, "describe": d, "continue": c}


# --- orchestrator -------------------------------------------------------------
def _spawn(args: list[str], env_extra: dict | None = None, kill_on_marker: str | None = None,
           timeout: int = 900) -> dict:
    env = {**os.environ, **(env_extra or {}), "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen([sys.executable, str(HERE / "workflow_drill.py"), *args],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
    lines, killed, t0 = [], False, time.time()
    while True:
        line = proc.stdout.readline()
        if line:
            lines.append(line.rstrip("\n"))
            if kill_on_marker and kill_on_marker in line:
                proc.kill()                        # TerminateProcess on Windows, SIGKILL elsewhere
                killed = True
                proc.wait(timeout=30)
                break
        elif proc.poll() is not None:
            break
        if time.time() - t0 > timeout:
            proc.kill(); break
    result = None
    for l in reversed(lines):
        if l.startswith("RESULT "):
            result = json.loads(l[len("RESULT "):]); break
    return {"args": args, "exit_code": proc.returncode, "killed": killed,
            "result": result, "tail": lines[-8:]}


def run_all(source_repo: str | None, only: str = "ABCD") -> int:
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    EVIDENCE_DIR.mkdir(exist_ok=True)
    env = {"WORKFLOW_SOURCE_REPO": source_repo} if source_repo else {}
    ev: dict = {"stamp": stamp, "phases": [], "assertions": []}
    ok = True

    def check(name: str, cond: bool, detail=""):
        nonlocal ok
        ev["assertions"].append({"name": name, "held": bool(cond), "detail": str(detail)[:300]})
        print(f"  [{'PASS' if cond else 'FAIL'}] {name} {detail if not cond else ''}")
        ok = ok and bool(cond)

    # --- Workflow A: the critical scenario -----------------------------------
    if "A" in only:
      A = f"drill-{stamp}-a"
      print(f"\n== A1 start {A}")
      r = _spawn(["--phase", "start", "--id", A, "--req", FOOTER_REQ.format(stamp=stamp)], env); ev["phases"].append(r)
      check("A1 reached WAITING_FOR_APPROVAL", (r["result"] or {}).get("state") == "WAITING_FOR_APPROVAL", r["tail"])

      print("== A2 describe in a fresh process (interrupted before approval)")
      r = _spawn(["--phase", "describe", "--id", A], env); ev["phases"].append(r)
      check("A2 fresh process still WAITING_FOR_APPROVAL", (r["result"] or {}).get("state") == "WAITING_FOR_APPROVAL")
      r = _spawn(["--phase", "continue", "--id", A], env); ev["phases"].append(r)
      check("A2 continue without a decision stays waiting", (r["result"] or {}).get("status") == "waiting")

      print("== A3 approve, then KILL the process after the commit and before the checkpoint")
      r = _spawn(["--phase", "approve", "--id", A, "--decision", "approve"],
                 {**env, "WORKFLOW_DRILL_PAUSE_AT": "apply_committed"}, kill_on_marker="DRILL_PAUSE apply_committed")
      ev["phases"].append(r)
      check("A3 child was killed at the marker (real process death)", r["killed"], r["tail"])
      r = _spawn(["--phase", "describe", "--id", A], env); ev["phases"].append(r)
      st = (r["result"] or {})
      check("A3 checkpoint shows APPROVED, not APPLIED (node had not checkpointed)", st.get("state") == "APPROVED", st.get("state"))
      ws_guess = str(pathlib.Path.home() / ".agentic-workflows" / f"wf-{A}")
      check("A3 the commit exists on disk although the checkpoint does not know it", _commits(ws_guess) == 1, _commits(ws_guess))

      print("== A4 continue in a fresh process")
      r = _spawn(["--phase", "continue", "--id", A], env, timeout=1500); ev["phases"].append(r)
      st = (r["result"] or {})
      check("A4 resumed to COMPLETED", st.get("state") == "COMPLETED", st.get("state"))
      check("A4 apply recognised its own commit and did not write again",
            (st.get("applied") or {}).get("skipped_duplicate") is True, st.get("applied"))
      check("A4 exactly one workflow commit in the workspace", _commits(st.get("workspace") or ws_guess) == 1)
      check("A4 compile/test/verify all ran after the resume",
            all(x in (st.get("completed_states") or []) for x in ("APPLIED", "COMPILED", "TESTED", "VERIFIED")), st.get("completed_states"))

      print("== A5 approve again on a completed workflow")
      r = _spawn(["--phase", "approve", "--id", A, "--decision", "approve"], env); ev["phases"].append(r)
      check("A5 refused", (r["result"] or {}).get("status") == "refused", r["result"])
      check("A5 still exactly one commit", _commits(st.get("workspace") or ws_guess) == 1)

    # --- Workflow B: reject, then try to approve --------------------------------
    if "B" in only:
      B = f"drill-{stamp}-b"
      print(f"\n== B reject then approve {B}")
      _spawn(["--phase", "start", "--id", B, "--req", FOOTER_REQ.format(stamp=stamp)], env)
      r = _spawn(["--phase", "approve", "--id", B, "--decision", "reject"], env); ev["phases"].append(r)
      check("B rejected", (r["result"] or {}).get("state") == "REJECTED")
      r = _spawn(["--phase", "approve", "--id", B, "--decision", "approve"], env); ev["phases"].append(r)
      check("B approve after reject refused", (r["result"] or {}).get("status") == "refused")
      check("B no workspace was ever created", not (pathlib.Path.home() / ".agentic-workflows" / f"wf-{B}").exists())

    # --- Workflow C: corrupt checkpoint ------------------------------------------
    if "C" in only:
      C = f"drill-{stamp}-c"
      print(f"\n== C corrupt {C}")
      _spawn(["--phase", "start", "--id", C, "--req", FOOTER_REQ.format(stamp=stamp)], env)
      r = _spawn(["--phase", "corrupt", "--id", C], env); ev["phases"].append(r)
      res = r["result"] or {}
      check("C corrupt row reported CORRUPT", (res.get("describe") or {}).get("status") == "corrupt", res)
      check("C corrupt workflow refuses to continue", (res.get("continue") or {}).get("status") == "corrupt")

    # --- Workflow D: crash between nodes (after apply checkpoint) ------------------
    if "D" in only:
      D = f"drill-{stamp}-d"
      print(f"\n== D kill after the apply checkpoint, before compile {D}")
      _spawn(["--phase", "start", "--id", D, "--req", FOOTER_REQ.format(stamp=stamp)], env)
      r = _spawn(["--phase", "approve", "--id", D, "--decision", "approve"],
                 {**env, "WORKFLOW_DRILL_PAUSE_AT": "before_compile"}, kill_on_marker="DRILL_PAUSE before_compile")
      ev["phases"].append(r)
      check("D killed at before_compile", r["killed"])
      r = _spawn(["--phase", "describe", "--id", D], env); ev["phases"].append(r)
      check("D checkpoint shows APPLIED", (r["result"] or {}).get("state") == "APPLIED", (r["result"] or {}).get("state"))
      r = _spawn(["--phase", "continue", "--id", D], env, timeout=1500); ev["phases"].append(r)
      st = r["result"] or {}
      check("D resumed to COMPLETED", st.get("state") == "COMPLETED", st.get("state"))
      applied_transitions = [t for t in (st.get("transitions") or []) if t.get("to") == "APPLIED"]
      check("D the apply node did not run a second time (one APPLIED transition)", len(applied_transitions) == 1, applied_transitions)
      ws_d = st.get("workspace") or str(pathlib.Path.home() / ".agentic-workflows" / f"wf-{D}")
    check("D exactly one commit", _commits(ws_d) == 1, _commits(ws_d))

    ev["all_held"] = ok
    path = EVIDENCE_DIR / f"{stamp}.json"
    path.write_text(json.dumps(ev, indent=2), encoding="utf-8")
    print(f"\nEVIDENCE {path}")
    print("DRILL", "PASSED" if ok else "FAILED", "--", sum(a['held'] for a in ev['assertions']), "of", len(ev["assertions"]), "assertions held")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-all", action="store_true")
    ap.add_argument("--source-repo", default=None)
    ap.add_argument("--only", default="ABCD", help="which scenarios to run, e.g. A or BCD (one per process keeps peak memory low)")
    ap.add_argument("--phase", choices=["start", "describe", "approve", "continue", "corrupt"])
    ap.add_argument("--id")
    ap.add_argument("--req", default=FOOTER_REQ.format(stamp="x"))
    ap.add_argument("--decision", default="approve")
    a = ap.parse_args()
    if a.run_all:
        return run_all(a.source_repo, a.only.upper())
    if a.source_repo:
        os.environ["WORKFLOW_SOURCE_REPO"] = a.source_repo
    fn = {"start": lambda: phase_start(a.id, a.req), "describe": lambda: phase_describe(a.id),
          "approve": lambda: phase_approve(a.id, a.decision), "continue": lambda: phase_continue(a.id),
          "corrupt": lambda: phase_corrupt(a.id)}[a.phase]
    result = fn()
    print("RESULT " + json.dumps(result, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
