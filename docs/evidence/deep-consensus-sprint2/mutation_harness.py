"""Seed one mutation, run the Sprint 2 suite, report, restore.

Each mutation disables exactly one new Sprint 2 guard. If the suite stays
green, that guard's tests do not actually test it.
"""

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(r"C:\Users\Hemapriya\agentic-software-delivery")

MUTATIONS = {
    # 1. Contradiction guard disabled: a disputed claim can survive into a
    #    CONVERGED answer.
    "contradiction_guard_off": (
        "deep_consensus/candidates.py",
        "def surviving_contradicted_claims(\n    contradicted: list[dict], governed_answer: str\n) -> list[dict]:",
        "def surviving_contradicted_claims(\n    contradicted: list[dict], governed_answer: str\n) -> list[dict]:\n    return []  # MUTATION",
    ),
    # 2. Same-hash rule weakened: any mutual ACCEPT counts as convergence,
    #    even on two different candidates.
    "same_hash_rule_off": (
        "deep_consensus/status_engine.py",
        "        if len(hashes) == 1:",
        "        if True:  # MUTATION: ignore candidate hash",
    ),
    # 3. Parallel dispatch silently becomes sequential.
    "parallelism_off": (
        "deep_consensus/orchestrator.py",
        "        return _dispatch_parallel(jobs, counters, budget, cost_recorder)",
        "        outcome = _DispatchOutcome()  # MUTATION: sequential\n        for slot, provider, request in jobs:\n            counters.reserve_calls(1, budget)\n            try:\n                response = provider.generate(request)\n            except ProviderCallError as exc:\n                outcome.errors[slot] = exc\n                counters.release_calls(1)\n                continue\n            outcome.responses[slot] = response\n            counters.record_tokens(response.input_tokens, response.output_tokens)\n        return outcome",
    ),
    # 4. Reservation becomes post-hoc: budget taken AFTER dispatch.
    "reservation_not_all_or_nothing": (
        "deep_consensus/governor.py",
        "        if self.provider_calls + count > budget.max_provider_calls:",
        "        if False:  # MUTATION: no all-or-nothing check",
    ),
}


def run_suite():
    proc = subprocess.run(
        [sys.executable, "deep_consensus/test_sprint2.py"],
        cwd=ROOT, capture_output=True, text=True,
        env={**__import__("os").environ, "DEEP_CONSENSUS_LEDGER_PATH": "/dev/null"},
    )
    out = proc.stdout + proc.stderr
    failures = [l for l in out.splitlines() if l.startswith(("FAIL:", "ERROR:"))]
    tail = [l for l in out.splitlines() if l.startswith(("Ran ", "OK", "FAILED"))]
    return failures, tail


name = sys.argv[1]
rel, old, new = MUTATIONS[name]
path = ROOT / rel
original = path.read_bytes()
raw = original.decode("utf-8")
nl = "\r\n" if "\r\n" in raw else "\n"
o = old.replace("\n", nl)
if o not in raw:
    print("ANCHOR MISSING for", name)
    sys.exit(2)
path.write_bytes(raw.replace(o, new.replace("\n", nl), 1).encode("utf-8"))
try:
    failures, tail = run_suite()
    print("MUTATION:", name)
    print("  detected by %d test(s)" % len(failures))
    for f in failures[:6]:
        print("   -", f.split("(")[0].strip())
    print("  " + " | ".join(tail))
    print("  VERDICT:", "CAUGHT" if failures else "*** NOT CAUGHT -- guard untested ***")
finally:
    path.write_bytes(original)
