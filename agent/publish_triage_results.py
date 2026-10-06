"""
Publish the Incident Triage Lab's EVIDENCE AND STATUS as a static JSON file
the public /triage/evidence page renders (agent/web/triage-evidence.json).

What this is NOT: an accuracy score. The triage feature has no labelled set
of expected diagnoses, so there is nothing to score; the page says so.

What it records, all from real sources:
  * the scenario catalogue (triage/scenarios.yaml), plus any scenario that
    exists in the Customer App's Java triage code/tests but is not in the
    catalogue (Scenario D at the time of writing) -- flagged, not hidden;
  * which public walkthrough page serves each scenario (from web_server.py);
  * real offline Python test results (agent/test_triage_execution.py,
    agent/test_triage_promotion.py), run here by subprocess;
  * real Java integration test results, parsed from Maven surefire XML
    reports if a run exists (app/target/surefire-reports), else "not run";
  * an explicit not_run list with reasons (live Railway reproduce/reset is
    never called; AI diagnosis needs an API key; Testcontainers needs Docker);
  * content hashes of the inputs, checked by test_publish_triage_results.py.

Run (from agent/):
    # optional, for real Java counts (needs JDK 21):
    (cd ../app && ./mvnw -B test -Dtest='TriageScenario*IntegrationTest' \
        -Dsurefire.failIfNoSpecifiedTests=false -Djacoco.skip=true)
    python publish_triage_results.py
"""

import json
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import yaml

from publish_eval_results import _sha256_text

AGENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = AGENT_DIR.parent
OUTPUT_PATH = AGENT_DIR / "web" / "triage-evidence.json"
CATALOGUE = REPO_ROOT / "triage" / "scenarios.yaml"
JAVA_TEST_DIR = REPO_ROOT / "app/src/test/java/com/example/customer/triage"
JAVA_MAIN_DIR = REPO_ROOT / "app/src/main/java/com/example/customer/triage"
SUREFIRE_DIR = REPO_ROOT / "app/target/surefire-reports"
WEB_SERVER = AGENT_DIR / "web_server.py"
REPO_URL = "https://github.com/karthikdevadoss/agentic-software-delivery"

PYTHON_TEST_MODULES = ["test_triage_execution", "test_triage_promotion"]

# Staleness inputs: the catalogue, the triage code and every triage test.
HASHED_GLOBS = [
    "triage/scenarios.yaml",
    "agent/triage_execution.py",
    "agent/triage_promotion.py",
    "agent/test_triage_execution.py",
    "agent/test_triage_promotion.py",
    "app/src/main/java/com/example/customer/triage/*.java",
    "app/src/test/java/com/example/customer/triage/*.java",
]
INPUTS_NOT_COVERED = [
    "Customer App code outside the triage package that the scenarios exercise",
    "the deployed Railway environment (never called by this publisher)",
]

_SCENARIO_ID_RE = re.compile(r"^TRIAGE-([A-Z])-")
_JAVA_TEST_RE = re.compile(r"^TriageScenario([A-Z])(\w*)IntegrationTest\.java$")


def scenario_letter(scenario_id: str) -> str:
    m = _SCENARIO_ID_RE.match(scenario_id)
    return m.group(1) if m else None


def count_java_tests(source: str) -> int:
    """@Test annotations outside comments (a Javadoc can mention @Test)."""
    code = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    code = re.sub(r"//[^\n]*", "", code)
    return len(re.findall(r"@Test\b", code))


def discover_java_tests(test_dir: Path = JAVA_TEST_DIR) -> dict:
    """letter -> [{"class", "file", "declared_tests", "needs_docker"}]"""
    out = {}
    for f in sorted(test_dir.glob("TriageScenario*IntegrationTest.java")):
        m = _JAVA_TEST_RE.match(f.name)
        if not m:
            continue
        src = f.read_text(encoding="utf-8")
        out.setdefault(m.group(1), []).append({
            "class": f.stem,
            "file": f.relative_to(REPO_ROOT).as_posix() if f.is_relative_to(REPO_ROOT) else f.name,
            "declared_tests": count_java_tests(src),
            "needs_docker": "disabledWithoutDocker = true" in src,
        })
    return out


def walkthrough_page(letter: str, web_server_source: str) -> str:
    """The public page for a scenario, only if web_server.py routes it."""
    path = "/triage" if letter == "A" else f"/triage/scenario-{letter.lower()}"
    return path if f'Route("{path}",' in web_server_source else None


def java_only_title(letter: str, main_dir: Path = JAVA_MAIN_DIR) -> str:
    """First Javadoc line of TriageScenario<X>Service naming the scenario."""
    svc = main_dir / f"TriageScenario{letter}Service.java"
    if not svc.exists():
        return None
    lines = [l.strip(" */").strip() for l in svc.read_text(encoding="utf-8").splitlines()]
    start = next((i for i, l in enumerate(lines) if f"Scenario {letter}" in l), None)
    if start is None:
        return None
    text = " ".join(lines[start:start + 6])
    m = re.search(rf"Scenario {letter} \(([^)]*)\)", text)
    if not m:
        return lines[start]
    return f"Scenario {letter}: " + m.group(1).split(", see")[0].strip()


def parse_surefire(report_dir: Path = SUREFIRE_DIR) -> dict:
    """class simple name -> counts from TEST-*.xml, plus file mtime (UTC)."""
    out = {}
    if not report_dir.is_dir():
        return out
    for f in sorted(report_dir.glob("TEST-com.example.customer.triage.*.xml")):
        root = ET.parse(f).getroot()
        name = root.get("name", "").rsplit(".", 1)[-1]
        out[name] = {
            "tests": int(root.get("tests", 0)),
            "failures": int(root.get("failures", 0)),
            "errors": int(root.get("errors", 0)),
            "skipped": int(root.get("skipped", 0)),
            "report_time_utc": datetime.fromtimestamp(f.stat().st_mtime, timezone.utc)
                                       .replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        }
    return out


_RAN_RE = re.compile(r"^Ran (\d+) tests? in", re.M)
_TAIL_RE = re.compile(r"^(OK|FAILED)(?: \((.*)\))?\s*$", re.M)


def parse_unittest_output(output: str) -> dict:
    ran = _RAN_RE.search(output)
    tail = _TAIL_RE.findall(output)
    if not ran or not tail:
        return None
    verdict, detail = tail[-1]
    counts = dict(failures=0, errors=0, skipped=0)
    for part in filter(None, (p.strip() for p in (detail or "").split(","))):
        k, _, v = part.partition("=")
        if k in counts:
            counts[k] = int(v)
    tests = int(ran.group(1))
    failing = re.findall(r"^(?:FAIL|ERROR): (\w+) \(([\w.]+)\)", output, re.M)
    return dict(tests=tests, passed=tests - counts["failures"] - counts["errors"] - counts["skipped"],
                ok=verdict == "OK", failing=[dotted for _name, dotted in failing], **counts)


def run_python_tests(module: str) -> dict:
    proc = subprocess.run([sys.executable, "-m", "unittest", module], cwd=AGENT_DIR,
                          capture_output=True, text=True, timeout=600)
    return parse_unittest_output(proc.stdout + proc.stderr)


def build_scenarios(catalogue: dict, java_tests: dict, surefire: dict, web_server_source: str,
                    java_titles: dict = None) -> list:
    java_titles = java_titles or {}
    scenarios, seen = [], set()

    def java_block(letter):
        rows = []
        for t in java_tests.get(letter, []):
            rows.append(dict(t, result=surefire.get(t["class"])))
        return rows

    for s in catalogue.get("scenarios", []):
        letter = scenario_letter(s["id"])
        seen.add(letter)
        scenarios.append({
            "letter": letter,
            "id": s["id"],
            "title": s.get("title"),
            "engineering_area": s.get("engineering_area"),
            "risk": s.get("risk"),
            "blast_radius": s.get("blast_radius"),
            "in_catalogue": True,
            "catalogue_status": s.get("status"),
            "evidence_links": s.get("evidence_links", []),
            "walkthrough_page": walkthrough_page(letter, web_server_source),
            "java_integration_tests": java_block(letter),
        })
    for letter in sorted(set(java_tests) - seen):
        scenarios.append({
            "letter": letter,
            "id": f"TRIAGE-{letter} (not in catalogue)",
            "title": java_titles.get(letter),
            "engineering_area": None,
            "risk": None,
            "blast_radius": None,
            "in_catalogue": False,
            "catalogue_status": (f"Exists only in the Customer App (TriageScenario{letter}Service + "
                                 f"integration test); not listed in triage/scenarios.yaml and not "
                                 f"wired to an agent walkthrough page."),
            "evidence_links": [],
            "walkthrough_page": walkthrough_page(letter, web_server_source),
            "java_integration_tests": java_block(letter),
        })
    return scenarios


def compute_input_hashes(repo_root: Path = REPO_ROOT) -> dict:
    files = {}
    for pattern in HASHED_GLOBS:
        for f in sorted(repo_root.glob(pattern)):
            raw = f.read_text(encoding="utf-8")
            files[f.relative_to(repo_root).as_posix()] = _sha256_text(raw.replace("\r\n", "\n"))
    return {"files": files}


def build_not_run(scenarios: list, environment: dict) -> list:
    items = [
        {"what": "Live reproduce / reset / approve against the deployed Customer App",
         "why": "Deliberately not called: these mutate the production app's synthetic triage data. "
                "Evidence here comes from tests only."},
        {"what": "Diagnosis accuracy score",
         "why": "There is no labelled set of expected diagnoses for the triage scenarios, so no "
                "accuracy can be measured. None is shown."},
    ]
    if not environment["anthropic_key_configured"]:
        items.append({"what": "AI diagnosis and AI candidate-patch generation (real model calls)",
                      "why": "No ANTHROPIC_API_KEY in this environment; the unit tests exercise "
                             "this code with an injected fake model instead."})
    for s in scenarios:
        for t in s["java_integration_tests"]:
            r = t["result"]
            if r is None:
                items.append({"what": f"Java {t['class']}",
                              "why": "No surefire report found: the Java tests were not run where "
                                     "this file was published (needs JDK 21)."})
            elif r["skipped"] and r["skipped"] == r["tests"] and t["needs_docker"] and not environment["docker_available"]:
                items.append({"what": f"Java {t['class']} ({r['skipped']} tests skipped)",
                              "why": "Testcontainers real-Postgres test; skipped automatically "
                                     "because no Docker is available where this was published. "
                                     "It runs in CI on GitHub's Docker-enabled runners."})
    return items


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()


def _java_version() -> str:
    java = shutil.which("java") or (Path(os.environ["JAVA_HOME"]) / "bin" / "java"
                                    if os.environ.get("JAVA_HOME") else None)
    if not java:
        return None
    out = subprocess.run([str(java), "-version"], capture_output=True, text=True).stderr
    return out.splitlines()[0] if out else None


def build_triage_evidence(*, scenarios, python_tests, environment, commit_sha, generated_at,
                          working_tree_dirty, inputs) -> dict:
    return {
        "schema_version": 1,
        "generated_at": generated_at,
        "commit_sha": commit_sha,
        "working_tree_dirty": working_tree_dirty,
        "scoring": None,  # explicit: there is no labelled set, so no accuracy
        "environment": environment,
        "scenarios": scenarios,
        "python_tests": python_tests,
        "not_run": build_not_run(scenarios, environment),
        "inputs": dict(inputs, not_covered=INPUTS_NOT_COVERED),
        "sources": {
            "catalogue": f"{REPO_URL}/blob/master/triage/scenarios.yaml",
            "engine": f"{REPO_URL}/blob/master/agent/triage_execution.py",
            "java_tests": f"{REPO_URL}/tree/master/app/src/test/java/com/example/customer/triage",
            "design": f"{REPO_URL}/blob/master/docs/TRIAGE_LAB_DESIGN.md",
            "publisher": f"{REPO_URL}/blob/master/agent/publish_triage_results.py",
        },
    }


def main(argv: list) -> int:
    out_rel = OUTPUT_PATH.relative_to(REPO_ROOT).as_posix()
    dirty = any(l.strip() and not l.endswith(out_rel) for l in _git("status", "--porcelain").splitlines())
    web_src = WEB_SERVER.read_text(encoding="utf-8")
    java_tests = discover_java_tests()
    scenarios = build_scenarios(
        yaml.safe_load(CATALOGUE.read_text(encoding="utf-8")), java_tests, parse_surefire(), web_src,
        java_titles={l: java_only_title(l) for l in java_tests})
    environment = {
        "java": _java_version(),
        "docker_available": shutil.which("docker") is not None,
        "anthropic_key_configured": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "network_used_by_tests": "none to Railway: offline unit tests mock HTTP; Java tests run in-process",
    }
    python_tests = {m: run_python_tests(m) for m in PYTHON_TEST_MODULES}
    result = build_triage_evidence(
        scenarios=scenarios, python_tests=python_tests, environment=environment,
        commit_sha=_git("rev-parse", "HEAD"),
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        working_tree_dirty=dirty, inputs=compute_input_hashes())
    text = json.dumps(result, indent=2) + "\n"
    if "--stdout" in argv:
        print(text, end="")
    else:
        OUTPUT_PATH.write_text(text, encoding="utf-8")
        print(f"wrote {out_rel} (commit={result['commit_sha'][:7]}, scenarios={len(scenarios)})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
