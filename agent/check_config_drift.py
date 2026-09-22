#!/usr/bin/env python3
"""BL-041 -- config-drift static gate (STATIC tier, zero LLM).

Detects a property key that exists in one Spring profile file
(application-<profile>.properties|yml) but is missing from another profile
file of the same application. That is the exact class of the Owner's real
NRG incident (Sep 2025): a downstream URL change that worked in stage
because prod's environment file silently carried different keys, found
only after ten days of debug logging. A key legitimately specific to one
profile goes in agent/config_drift_allowlist.json.

Rules kept deliberately simple and deterministic:
  * only profile files are compared with each other (the base
    application.* file is a shared layer, so a key present in base need
    not be repeated in a profile);
  * a key is "drift" when at least one profile file has it and at least
    one other profile file does not, and the base file does not have it;
  * one profile file alone cannot drift.

Exit 0 = no drift; exit 1 = drift found (report printed); exit 2 = usage.
"""
import json
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ROOTS = ["app/src/main/resources"] + [
    os.path.join("services", d, "src", "main", "resources")
    for d in sorted(os.listdir(os.path.join(REPO_ROOT, "services")))
    if os.path.isdir(os.path.join(REPO_ROOT, "services", d, "src", "main", "resources"))
] if os.path.isdir(os.path.join(REPO_ROOT, "services")) else ["app/src/main/resources"]
ALLOWLIST_PATH = os.path.join(REPO_ROOT, "agent", "config_drift_allowlist.json")
PROFILE_RE = re.compile(r"^application-([A-Za-z0-9_]+)\.(properties|ya?ml)$")
BASE_RE = re.compile(r"^application\.(properties|ya?ml)$")


def flatten_properties(text: str) -> set[str]:
    keys = set()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "!")):
            continue
        m = re.match(r"^([A-Za-z0-9_.\-\[\]]+)\s*[=:]", stripped)
        if m:
            keys.add(m.group(1))
    return keys


def flatten_yaml(text: str) -> set[str]:
    """Indentation-based flattener sufficient for Spring application yml
    (no PyYAML dependency; '---' document separators reset the path)."""
    keys, stack = set(), []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.strip() == "---":
            stack = []
            continue
        indent = len(line) - len(line.lstrip(" "))
        m = re.match(r"\s*-?\s*([A-Za-z0-9_.\-\[\]]+)\s*:(\s*(.*))?$", line)
        if not m:
            continue
        key, value = m.group(1), (m.group(3) or "").strip()
        while stack and stack[-1][0] >= indent:
            stack.pop()
        stack.append((indent, key))
        if value:  # leaf with a value
            keys.add(".".join(k for _, k in stack))
    return keys


def load_keys(path: str) -> set[str]:
    with open(path, encoding="utf-8", errors="ignore") as f:
        text = f.read()
    return flatten_properties(text) if path.endswith(".properties") else flatten_yaml(text)


def detect_drift(resources_dir: str, allowlist: list[str]) -> list[dict]:
    if not os.path.isdir(resources_dir):
        return []
    base_keys, profiles = set(), {}
    for name in sorted(os.listdir(resources_dir)):
        path = os.path.join(resources_dir, name)
        if BASE_RE.match(name):
            base_keys |= load_keys(path)
        elif PROFILE_RE.match(name):
            profiles[name] = load_keys(path)
    if len(profiles) < 2:
        return []
    allowed = [re.compile("^" + re.escape(a).replace(r"\*", ".*") + "$") for a in allowlist]
    union = set().union(*profiles.values())
    drift = []
    for key in sorted(union):
        if key in base_keys or any(a.match(key) for a in allowed):
            continue
        present = sorted(n for n, k in profiles.items() if key in k)
        missing = sorted(n for n, k in profiles.items() if key not in k)
        if present and missing:
            drift.append({"key": key, "present_in": present, "missing_from": missing})
    return drift


def load_allowlist() -> dict:
    if not os.path.exists(ALLOWLIST_PATH):
        return {}
    with open(ALLOWLIST_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def main(argv: list[str]) -> int:
    roots = [a for a in argv if not a.startswith("--")] or DEFAULT_ROOTS
    as_json = "--json" in argv
    allowlist = load_allowlist()
    report, total = {}, 0
    for root in roots:
        abs_root = root if os.path.isabs(root) else os.path.join(REPO_ROOT, root)
        drift = detect_drift(abs_root, allowlist.get(root, []) + allowlist.get("*", []))
        report[root] = drift
        total += len(drift)
    if as_json:
        print(json.dumps(report, indent=2))
    else:
        for root, drift in report.items():
            if not drift:
                print(f"CONFIG-DRIFT gate: PASS -- {root}")
                continue
            print(f"CONFIG-DRIFT gate: FAIL -- {root}: {len(drift)} key(s) present in some profiles but missing from others")
            for d in drift:
                print(f"  {d['key']}: present in {', '.join(d['present_in'])}; MISSING from {', '.join(d['missing_from'])}")
        print("Fix: add the key to every profile (or to the base file), or allowlist a genuinely "
              "profile-specific key in agent/config_drift_allowlist.json.")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
