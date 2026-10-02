"""Seed one Sprint 3 mutation, run the suite, report, restore."""

import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(r"C:\Users\Hemapriya\agentic-software-delivery")

MUTATIONS = {
    # 1. API-key stripping removed: the child inherits the whole parent env.
    "api_key_stripping_off": (
        "deep_consensus/cli_transport.py",
        "    parent = os.environ if parent_env is None else parent_env\n    child: dict[str, str] = {}",
        "    parent = os.environ if parent_env is None else parent_env\n    child: dict[str, str] = dict(parent)  # MUTATION: inherit everything",
    ),
    # 2. The defence-in-depth leak assertion neutered.
    "leak_assertion_off": (
        "deep_consensus/cli_transport.py",
        "    leaked = [name for name in env if name in BILLING_DENYLIST]",
        "    return  # MUTATION: guard disabled\n    leaked = [name for name in env if name in BILLING_DENYLIST]",
    ),
    # 3. No-paid-fallback eligibility ignores whether auth was proven.
    "eligibility_ignores_auth": (
        "deep_consensus/accounts.py",
        "        return (\n            self.billing in P0_ALLOWED_BILLING\n            and self.auth_verified == AUTH_VERIFIED_SUBSCRIPTION\n        )",
        "        return self.billing in P0_ALLOWED_BILLING  # MUTATION",
    ),
    # 4. Conflict detection disabled: everything looks like agreement.
    "conflict_detection_off": (
        "deep_consensus/claim_engine.py",
        "def values_agree(claim_type: str, a_value: str, b_value: str) -> bool:",
        "def values_agree(claim_type: str, a_value: str, b_value: str) -> bool:\n    return True  # MUTATION",
    ),
    # 5. The 4-call hard cap removed.
    "call_cap_off": (
        "deep_consensus/claim_review.py",
        "    if budget_state[\"calls\"] + len(jobs) > budget_state[\"max_calls\"]:",
        "    if False:  # MUTATION: cap removed",
    ),
    # 6. Unresolved claims no longer block convergence.
    "unresolved_does_not_block_convergence": (
        "deep_consensus/claim_engine.py",
        "def claim_level_converged(pairings: list[Pairing]) -> bool:",
        "def claim_level_converged(pairings: list[Pairing]) -> bool:\n    return True  # MUTATION",
    ),
}


def run_suite():
    proc = subprocess.run(
        [sys.executable, "deep_consensus/test_sprint3.py"],
        cwd=ROOT, capture_output=True, text=True, env=dict(os.environ),
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
