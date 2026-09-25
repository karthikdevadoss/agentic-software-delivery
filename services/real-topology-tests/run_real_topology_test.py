"""
REAL-TOPOLOGY multi-instance test tier (BL-021).

Closes a real, previously-empty gap in this project's testing pyramid
(see docs/TESTING_ARCHITECTURE_V1.md's new section on this tier, and
docs/AI_NATIVE_TESTING_RESEARCH.md for the audit that motivated it):
nothing existed between "one service in isolation" (unit /
Testcontainers-backed single-service integration / WireMock contract
tests) and "a human manually starting all N services and poking at
them" -- which is exactly what a human had to do to catch 4 of 7 real
defects found building services/'s microservices decomposition. Those 4
defects ONLY manifested with multiple REAL service instances running
together against a REAL Eureka registry:

1. A `@LoadBalanced RestClient.Builder` bean silently hijacking Eureka's
   own internal registration client.
2. `.before(uri("http://service-name"))` alone does not load-balance
   through Eureka -- needs an explicit `.filter(lb(serviceId))`.
3. `eureka.instance.prefer-ip-address=true` breaking same-machine
   self-connections via real local network/firewall behavior.
4. A missing JWT-propagation gap between two services, only visible on
   a real authenticated end-to-end request through the real system.

This script makes that a real, repeatable, scripted, automated tier
instead of a manual one-off:

  1. Starts a real eureka-server instance.
  2. Starts 3 real, independent service instances that depend on each
     other via real REST calls through real Eureka-based service
     discovery: customer-service, billing-service, api-gateway (the
     minimum real topology that exercises ALL FOUR bug classes above --
     #1/#3/#4 need customer-service+billing-service talking to each
     other for real; #2 is specifically an api-gateway load-balancing
     bug, so api-gateway has to be a real participant too, not skipped).
  3. Waits for real registration to complete by POLLING Eureka's real
     registry (GET /eureka/apps) -- never a fixed sleep. Eureka's own
     response cache refreshes on a real ~30s interval by default, so a
     fixed short sleep would be exactly the kind of flaky shortcut this
     project's own testing discipline argues against; this polls with a
     generous timeout instead and returns as soon as it's real.
  4a. Also retries a real 500 caused by a downstream service's Eureka
     client-side load-balancer cache still warming up on its OWN first
     use (a real race distinct from the gateway's own readiness, caught
     live during this harness's development -- see
     `_call_with_lb_warmup_retry`'s docstring) with a bounded backoff,
     never an unbounded retry and never retrying a genuine 4xx.
  4. Makes ONE real, authenticated, end-to-end HTTP request CHAIN through
     the real api-gateway, reusing the EXACT sequence already proven in
     this codebase's own BL-007 smoke test and
     docs/MICROSERVICES_ARCHITECTURE.md's real end-to-end smoke test --
     not a new invented flow:
       POST /auth/demo-token
       -> POST /customers
       -> POST /customers/{id}/plan   (real billing-service ->
                                        customer-service REST call,
                                        real JWT propagation)
       -> GET  /customers/{id}/plan
  5. Asserts on real, specific observable outcomes (exact HTTP status
     codes + exact response body field values), never "no exception was
     thrown."
  6. Cleans up every started process reliably, success or failure -- by
     walking each started process's REAL descendant PID tree (see
     `_descendant_pids`) and killing every verified descendant
     individually, because `taskkill /T /F` alone does not reliably
     cascade to the separate JVM Spring Boot's Maven plugin forks for the
     actual running application in this dev environment (a real,
     confirmed gap, not a hypothetical). Deliberately does NOT fall back
     to "kill whatever is listening on this port" -- an earlier version
     of this script did exactly that and, on a machine running multiple
     git worktrees of this repo concurrently, killed a DIFFERENT
     worktree's real, unrelated running service processes. That fallback
     was removed, not hardened.

Usage:
    python services/real-topology-tests/run_real_topology_test.py
    python services/real-topology-tests/run_real_topology_test.py --startup-timeout 120 --registry-timeout 120

Exit code 0 = PASS (every step verified for real). Exit code 1 = FAIL,
with the real failing step and evidence printed. Does NOT touch
Railway/production -- entirely local processes on this dev machine, and
does NOT modify any existing service's source (uses them as black
boxes), per this task's hard constraints.
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import uuid
from datetime import date
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICES_DIR = REPO_ROOT / "services"
LOG_DIR = Path(__file__).resolve().parent / "logs"

IS_WINDOWS = os.name == "nt"


def _mvnw(service_dir: Path) -> Path:
    return service_dir / ("mvnw.cmd" if IS_WINDOWS else "mvnw")


# Default local ports, matching services/README.md's existing convention.
# A --port-offset lets an entire run be shifted onto alternate ports (see
# build_services() below) -- added after a real run on this exact machine
# was interrupted mid-flow by a DIFFERENT git worktree concurrently
# exercising these same services on their fixed default ports (confirmed
# via `git worktree list` + live process inspection, not assumed). Every
# service already reads its own port and its EUREKA_URL from the
# environment (see each service's application.properties -- e.g.
# `server.port=${PORT:8081}`, `eureka.client.service-url.defaultZone=
# ${EUREKA_URL:...}`), so this is a real, zero-risk, non-invasive
# parameterization: no service source or config file is touched, and
# inter-service calls still resolve purely through Eureka service ids
# (never a hardcoded port), so an offset topology behaves identically to
# the default one.
DEFAULT_EUREKA_PORT = 8761
DEFAULT_PORTS = {"customer-service": 8081, "billing-service": 8082, "api-gateway": 8080,
                 # BL-038: the legacy billing system stand-in (fixed URL, not Eureka-registered)
                 "legacy-billing-stub": 9099}

# Startup order matters only in the sense that eureka-server should be
# reachable before the others bother registering (they'll retry anyway
# if not, but starting it first avoids pointless early registration
# failures in the logs). The other 3 are started concurrently after that.


def build_services(port_offset: int):
    eureka_port = DEFAULT_EUREKA_PORT + port_offset
    eureka = {"name": "eureka-server", "dir": SERVICES_DIR / "eureka-server", "port": eureka_port, "eureka_app_id": None}
    dependents = [
        # BL-038 / ACT-015: billing-service's facade confirms every plan rate
        # with this stand-in; without it every POST /customers/{id}/plan is a
        # real 503 (the exact regression ACT-015 recorded). eureka_app_id is
        # None on purpose: a legacy system is reached at a fixed URL, never
        # through discovery, so it is not part of the registry convergence wait.
        {"name": "legacy-billing-stub", "dir": SERVICES_DIR / "legacy-billing-stub",
         "port": DEFAULT_PORTS["legacy-billing-stub"] + port_offset, "eureka_app_id": None},
        {"name": "customer-service", "dir": SERVICES_DIR / "customer-service",
         "port": DEFAULT_PORTS["customer-service"] + port_offset, "eureka_app_id": "CUSTOMER-SERVICE"},
        {"name": "billing-service", "dir": SERVICES_DIR / "billing-service",
         "port": DEFAULT_PORTS["billing-service"] + port_offset, "eureka_app_id": "BILLING-SERVICE"},
        {"name": "api-gateway", "dir": SERVICES_DIR / "api-gateway",
         "port": DEFAULT_PORTS["api-gateway"] + port_offset, "eureka_app_id": "API-GATEWAY"},
    ]
    return eureka, dependents, [eureka] + dependents, eureka_port


# Populated by main() before anything else runs (default offset 0 keeps
# every module-level function usable standalone/under test without
# requiring main() to run first).
EUREKA, DEPENDENT_SERVICES, ALL_SERVICES, EUREKA_PORT = build_services(0)
GATEWAY_PORT = DEFAULT_PORTS["api-gateway"]


class HarnessError(Exception):
    """Raised for any real, evidenced failure of this harness -- the
    message is always the real observed evidence, never a guess."""


# ---------------------------------------------------------------------
# Process lifecycle
# ---------------------------------------------------------------------

def _port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        return sock.connect_ex((host, port)) == 0


def preflight_check_ports():
    """Refuse to start if any target port is already occupied -- this
    project has real prior pain with leftover processes/ports from
    manual smoke-testing; failing fast with a clear message beats
    silently colliding with a stale process."""
    occupied = [s["port"] for s in ALL_SERVICES if _port_in_use(s["port"])]
    if occupied:
        raise HarnessError(
            f"Port preflight failed -- already occupied: {occupied}. "
            "A leftover process from a prior run is likely still bound to "
            "one of these ports. Find it (Windows: `netstat -ano | findstr "
            f"\"{' '.join(':' + str(p) for p in occupied)}\"`) and stop it "
            "before re-running this harness."
        )


def start_service(service: dict) -> subprocess.Popen:
    mvnw = _mvnw(service["dir"])
    if not mvnw.exists():
        raise HarnessError(f"Maven wrapper not found for {service['name']!r} at {mvnw}")

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{service['name']}.log"
    log_file = open(log_path, "w", encoding="utf-8", errors="replace")

    # PORT/EUREKA_URL overrides -- see build_services()'s docstring-comment
    # for why this is safe: every service already supports these via its
    # own application.properties, and inter-service calls resolve purely
    # through Eureka service ids, never a hardcoded port.
    env = dict(os.environ)
    env["PORT"] = str(service["port"])
    if service["name"] != "eureka-server":
        env["EUREKA_URL"] = f"http://localhost:{EUREKA_PORT}/eureka"
        # ROOT CAUSE OF A REAL FLAKE, fixed 2026-09-25 (CI run 36173704049,
        # reproduced locally first run). The Eureka CLIENT caches the registry
        # locally and refreshes it on its own timer -- default 30s. This
        # harness proves the Eureka SERVER's registry converged
        # (wait_for_eureka_registration) and that the GATEWAY can route
        # (wait_for_gateway_routing_ready), but neither of those says anything
        # about billing-service's OWN client-side cache, which is what
        # BillingCustomerClient resolves CUSTOMER-SERVICE through.
        #
        # Measured failure, from services/real-topology-tests/logs:
        #   18:53:22.593  billing-service fetches registry (no customer-service yet)
        #   18:53:35.8 -> 18:53:48.0  all 5 harness retries fail:
        #       IllegalStateException: No instances available for CUSTOMER-SERVICE
        #   18:53:53.179  NEXT registry fetch -- 30.6s after the previous one
        # The call-layer retry budget (~12s) is shorter than the refresh
        # interval (30s), so whenever the POST lands just after a refresh every
        # retry falls inside the same stale-cache window. Pure coin-flip: green
        # when it lands near a refresh, red when it doesn't.
        #
        # The fix is to shrink the staleness window below the retry budget, NOT
        # to add retries (the existing ones are sound and were never the
        # problem) and NOT to weaken the assertion. 5s is a test-topology
        # value: production keeps the 30s default, and the services' own
        # application.properties are untouched -- this is a harness-scoped env
        # override exactly like PORT/EUREKA_URL above. The application's real
        # behaviour under a stale cache is CORRECT and stays under test: it
        # still returns a clear 503 "please retry", which is what a real client
        # should see.
        env["EUREKA_CLIENT_REGISTRYFETCHINTERVALSECONDS"] = "5"
    if service["name"] == "billing-service":
        # BL-038: point the facade at the stand-in started by this harness
        # (respects --port-offset), overriding application.properties' default.
        legacy = next(svc for svc in ALL_SERVICES if svc["name"] == "legacy-billing-stub")
        env["LEGACY_BILLING_SYSTEM_BASE_URL"] = f"http://localhost:{legacy['port']}"

    # shell=False, explicit argv -- same pattern already proven correct
    # in this codebase (agent/build_tools.py's run_maven): no shell
    # metacharacter risk, and subprocess CAN launch a .cmd wrapper this
    # way on this machine (already verified live for `mvnw.cmd compile`).
    proc = subprocess.Popen(
        [str(mvnw), "-q", "spring-boot:run"],
        cwd=str(service["dir"]),
        stdout=log_file,
        stderr=subprocess.STDOUT,
        shell=False,
        env=env,
    )
    service["_log_file_handle"] = log_file
    service["_log_path"] = log_path
    return proc


def _descendant_pids(root_pid: int) -> list[int]:
    """Real, full descendant PID set of `root_pid` (children, grandchildren,
    ...), computed fresh via a live PowerShell CIM process-tree walk.

    WHY THIS EXISTS (real incident, 2026-09-20, during this harness's own
    development): `taskkill /PID <root> /T /F` does NOT reliably cascade
    to the JVM Spring Boot's Maven plugin forks for the actual application
    (`mvnw.cmd` -> Maven's own java.exe -> a SEPARATE forked java.exe
    running the real Spring Boot app) in this dev environment -- confirmed
    live: after a normal `/T` taskkill of the tracked `mvnw.cmd` PID, the
    forked application JVM was still alive and still bound to its port.
    An EARLIER version of this cleanup then tried a port-based fallback
    sweep (find whatever PID is LISTENING on our target port, kill it) --
    that is unsafe on a machine running multiple git worktrees of this
    same repo concurrently: it force-killed a DIFFERENT, unrelated
    worktree's real running service processes, just because they happened
    to occupy the same port at the same moment. This function replaces
    that with a provably-safe alternative: walk the REAL OS process tree
    down from a PID this harness itself holds a `Popen` handle for, so
    every PID returned is a genuine, verified descendant of a process we
    ourselves started -- never a guess based on which port something is
    bound to."""
    if not IS_WINDOWS:
        return []
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
             "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=20, shell=False,
        )
        rows = json.loads(proc.stdout)
    except Exception:
        return []
    if isinstance(rows, dict):
        rows = [rows]
    children_of: dict[int, list[int]] = {}
    for row in rows:
        try:
            pid, ppid = int(row["ProcessId"]), int(row["ParentProcessId"])
        except (KeyError, TypeError, ValueError):
            continue
        children_of.setdefault(ppid, []).append(pid)

    descendants: list[int] = []
    frontier = [root_pid]
    while frontier:
        current = frontier.pop()
        for child in children_of.get(current, []):
            if child not in descendants:
                descendants.append(child)
                frontier.append(child)
    return descendants


def _kill_pid(pid: int):
    if IS_WINDOWS:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, shell=False)
    else:
        try:
            os.kill(pid, 9)
        except ProcessLookupError:
            pass


def cleanup(procs: dict):
    """Best-effort, always-run cleanup -- STRICTLY SCOPED to processes this
    specific run started (`procs`, keyed by service name). Captures each
    started process's real descendant PID tree BEFORE killing anything
    (see `_descendant_pids`'s docstring for why `/T` alone isn't
    sufficient here), then kills the tracked top PID plus every real
    descendant individually. Never touches a port-based "whatever is
    listening here" fallback -- that class of fallback caused a real
    incident (killed a different worktree's unrelated live processes) and
    was deliberately removed, not just hardened."""
    print("\n--- cleanup: stopping all started service processes ---")
    service_by_name = {s["name"]: s for s in ALL_SERVICES}

    # Capture descendants FIRST, while the tree is still intact.
    descendants_by_name = {}
    for name, entry in procs.items():
        proc = entry.get("proc")
        if proc is not None and proc.poll() is None:
            descendants_by_name[name] = _descendant_pids(proc.pid)

    for name, entry in procs.items():
        proc = entry.get("proc")
        if proc is None:
            continue
        if proc.poll() is not None:
            print(f"  {name}: already exited (code {proc.returncode})")
        else:
            if IS_WINDOWS:
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    capture_output=True, shell=False,
                )
            else:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
            descendants = descendants_by_name.get(name, [])
            for pid in descendants:
                _kill_pid(pid)
            print(f"  {name}: killed pid {proc.pid}" +
                  (f" + verified descendant PID(s) {descendants}" if descendants else " (no descendants found)"))
        handle = entry.get("_log_file_handle")
        if handle:
            try:
                handle.close()
            except Exception:
                pass

    if not procs:
        # Nothing was ever started by this run (e.g. preflight refused
        # before starting anything) -- nothing of ours to clean up, and no
        # port may be touched. Exists so cleanup() is always safe to call
        # unconditionally from a top-level `finally`, even on a run that
        # never started anything.
        return

    # Real verification, reporting-only: confirm each port THIS run
    # started is actually free again. Never kills based on this check --
    # anything still bound here is surfaced as a loud warning for manual
    # investigation instead, on purpose (see docstring above).
    time.sleep(2.0)
    for name in procs:
        port = service_by_name[name]["port"]
        if _port_in_use(port):
            print(f"  WARNING: port {port} ({name}) still appears bound after killing this run's "
                  "own tracked process + its verified descendants -- do NOT assume this is ours; "
                  "investigate manually (e.g. `netstat -ano | findstr :" + str(port) + "`) before touching it")
        else:
            print(f"  port {port} ({name}): confirmed free")


# ---------------------------------------------------------------------
# Real readiness polling (never a fixed sleep)
# ---------------------------------------------------------------------

def wait_for_health(name: str, port: int, timeout: float, interval: float = 2.0) -> float:
    """Polls the real Spring Boot Actuator health endpoint until it
    reports UP. Returns real elapsed seconds. Raises HarnessError with
    the real last-seen evidence on timeout."""
    url = f"http://localhost:{port}/actuator/health"
    start = time.monotonic()
    last_evidence = "no successful response yet"
    while time.monotonic() - start < timeout:
        try:
            resp = requests.get(url, timeout=3)
            last_evidence = f"HTTP {resp.status_code}: {resp.text[:200]}"
            if resp.status_code == 200 and resp.json().get("status") == "UP":
                return round(time.monotonic() - start, 1)
        except requests.exceptions.RequestException as exc:
            last_evidence = f"{type(exc).__name__}: {exc}"
        time.sleep(interval)
    raise HarnessError(
        f"{name}: did not report UP at {url} within {timeout}s. Last evidence: {last_evidence}. "
        f"See {LOG_DIR / (name + '.log')} for the real service log."
    )


def _parse_eureka_registered_up_apps(payload: dict) -> set[str]:
    """Eureka's own JSON envelope collapses a single application/instance
    to a bare dict instead of a 1-element list -- a real, documented
    Eureka quirk, not a hypothetical. Handles both shapes."""
    apps_node = payload.get("applications", {}).get("application", [])
    if isinstance(apps_node, dict):
        apps_node = [apps_node]
    up_apps = set()
    for app in apps_node:
        name = app.get("name")
        instances = app.get("instance", [])
        if isinstance(instances, dict):
            instances = [instances]
        if any(inst.get("status") == "UP" for inst in instances):
            up_apps.add(name)
    return up_apps


def wait_for_eureka_registration(expected_app_ids: list[str], timeout: float, interval: float = 3.0) -> float:
    """Polls Eureka's REAL registry (GET /eureka/apps) until every
    expected app id has at least one real UP instance -- never a fixed
    sleep. Eureka Server's own full-registry response cache refreshes on
    a real ~30s default interval, so this intentionally uses a generous
    timeout rather than a short one; it still returns the instant the
    real registry converges, which is the whole point of polling instead
    of sleeping a guessed fixed amount."""
    url = f"http://localhost:{EUREKA_PORT}/eureka/apps"
    start = time.monotonic()
    last_seen: set[str] = set()
    while time.monotonic() - start < timeout:
        try:
            resp = requests.get(url, headers={"Accept": "application/json"}, timeout=5)
            if resp.status_code == 200:
                last_seen = _parse_eureka_registered_up_apps(resp.json())
                if set(expected_app_ids).issubset(last_seen):
                    return round(time.monotonic() - start, 1)
        except requests.exceptions.RequestException:
            pass
        time.sleep(interval)
    raise HarnessError(
        f"Eureka registry did not converge within {timeout}s. Expected UP: "
        f"{expected_app_ids}. Last real registry snapshot showed UP: {sorted(last_seen)}."
    )


def wait_for_gateway_routing_ready(gateway_port: int, timeout: float, interval: float = 3.0) -> float:
    """REAL FINDING from this harness's own first real run (2026-09-20):
    the Eureka SERVER's registry (what wait_for_eureka_registration polls)
    can report an instance UP before every individual CLIENT's own local
    DiscoveryClient cache has actually ingested that instance -- each
    Eureka client fetches the registry into its own local cache on its
    own periodic cycle, separate from server-side registration. The
    api-gateway's very first real routed call failed with a real 503
    ("Unable to find instance for customer-service") surfaced as a 500,
    even though the eureka-server's own registry already showed
    CUSTOMER-SERVICE UP -- a genuine race, not a flake to paper over.

    The only real proof that routing is actually ready is a real
    successful route through it, so this polls the gateway with a
    harmless, side-effect-free real call (issuing a demo token mutates
    nothing) until it actually succeeds -- still polling, never a fixed
    sleep, just polling the right real signal instead of a proxy for it."""
    url = f"http://localhost:{gateway_port}/auth/demo-token"
    start = time.monotonic()
    last_evidence = "no attempt yet"
    while time.monotonic() - start < timeout:
        try:
            resp = requests.post(url, timeout=5)
            last_evidence = f"HTTP {resp.status_code}: {resp.text[:200]}"
            if resp.status_code == 200:
                return round(time.monotonic() - start, 1)
        except requests.exceptions.RequestException as exc:
            last_evidence = f"{type(exc).__name__}: {exc}"
        time.sleep(interval)
    raise HarnessError(
        f"api-gateway never successfully routed a real request within {timeout}s "
        f"of Eureka registry convergence. Last evidence: {last_evidence}"
    )


# ---------------------------------------------------------------------
# The real, authenticated, end-to-end request chain
# ---------------------------------------------------------------------

def _call_with_lb_warmup_retry(method: str, url: str, max_attempts: int = 5, backoff: float = 3.0, **kwargs) -> requests.Response:
    """REAL FINDING from this harness's own first real runs (2026-09-20):
    Spring Cloud LoadBalancer's default `ServiceInstanceListSupplier`
    warms up its instance cache PER downstream service id, independently,
    on that service id's own first real use -- proving the gateway can
    already route to `customer-service` (see
    `wait_for_gateway_routing_ready`) does NOT prove it can yet route to
    `billing-service`, and does NOT prove billing-service's OWN internal
    `BillingCustomerClient` (billing-service -> customer-service) is warm
    either -- three independent client-side caches, each warming up on
    its own first real use. The harness caught all three live:
      - gateway -> customer-service: real 503 "Unable to find instance",
        surfaced as a bare 500 (see `wait_for_gateway_routing_ready`).
      - gateway -> billing-service: same, on the first real
        POST /customers/{id}/plan call.
      - billing-service -> customer-service (BillingCustomerClient): a
        real, DELIBERATELY DISTINCT 503 from billing-service's own
        GlobalExceptionHandler ("customer-service unreachable ... please
        retry" -- see CustomerLookupOutcome.SERVICE_UNAVAILABLE's Javadoc:
        this is a genuine, never-fabricated "could not find out" outcome,
        by design always kept separate from a real 404 "does not exist").
    Pre-warming every possible downstream route ahead of time is fragile
    and does not generalize; instead, this retries on 500 AND 503 (the
    two classes this warm-up race manifests as -- a genuine 4xx from a
    real auth/validation/not-found problem is never retried, so a real
    bug still fails fast) with a real bounded backoff, exactly the same
    "poll for real readiness, do not guess a fixed sleep" principle
    applied at the HTTP-call layer instead of a separate pre-flight
    probe."""
    last_resp = None
    for attempt in range(1, max_attempts + 1):
        last_resp = requests.request(method, url, **kwargs)
        if last_resp.status_code not in (500, 503) or attempt == max_attempts:
            return last_resp
        time.sleep(backoff)
    return last_resp


def run_real_flow(gateway_port: int) -> dict:
    """Reuses BL-007's own real, already-proven sequence (see
    docs/MICROSERVICES_ARCHITECTURE.md's real end-to-end smoke test)
    rather than inventing a new flow. Every assertion checks a real,
    specific observable value -- never just absence of an exception."""
    base = f"http://localhost:{gateway_port}"
    evidence = {}

    # 1. POST /auth/demo-token
    resp = _call_with_lb_warmup_retry("POST", f"{base}/auth/demo-token", timeout=15)
    if resp.status_code != 200:
        raise HarnessError(f"POST /auth/demo-token: expected 200, got {resp.status_code}: {resp.text[:300]}")
    token_body = resp.json()
    token = token_body.get("access_token")
    if not token or token_body.get("token_type") != "Bearer":
        raise HarnessError(f"POST /auth/demo-token: malformed token response: {token_body}")
    evidence["auth_demo_token"] = {"status": resp.status_code, "token_type": token_body.get("token_type")}
    auth_header = {"Authorization": f"Bearer {token}"}

    # 2. POST /customers
    unique_suffix = uuid.uuid4().hex[:8]
    customer_payload = {
        "name": f"Real Topology Test {unique_suffix}",
        "email": f"real-topology-{unique_suffix}@example.com",
    }
    # customer-service's real SecurityConfig requires SCOPE_customer:write
    # for POST /customers (the CustomerController method signature alone
    # doesn't show this -- it has no @AuthenticationPrincipal parameter --
    # but the security filter chain enforces it regardless; the demo
    # token carries customer:write, same as every other scope used below).
    resp = _call_with_lb_warmup_retry("POST", f"{base}/customers", json=customer_payload, headers=auth_header, timeout=15)
    if resp.status_code != 201:
        raise HarnessError(f"POST /customers: expected 201, got {resp.status_code}: {resp.text[:300]}")
    customer_body = resp.json()
    customer_id = customer_body.get("id")
    if not customer_id or customer_body.get("email") != customer_payload["email"]:
        raise HarnessError(f"POST /customers: unexpected body: {customer_body}")
    evidence["create_customer"] = {"status": resp.status_code, "id": customer_id, "email": customer_body.get("email")}

    # 3. POST /customers/{id}/plan -- the real billing-service ->
    #    customer-service cross-service REST call + real JWT propagation.
    plan_payload = {
        "planName": f"Real-Topology-Residential-{unique_suffix}",
        "ratePerKwh": 0.1825,
        "effectiveStartDate": date.today().isoformat(),
    }
    resp = _call_with_lb_warmup_retry("POST", f"{base}/customers/{customer_id}/plan", json=plan_payload, headers=auth_header, timeout=15)
    if resp.status_code != 201:
        raise HarnessError(f"POST /customers/{customer_id}/plan: expected 201, got {resp.status_code}: {resp.text[:300]}")
    plan_body = resp.json()
    if (plan_body.get("customerId") != customer_id
            or plan_body.get("planName") != plan_payload["planName"]
            or abs(float(plan_body.get("ratePerKwh", -1)) - plan_payload["ratePerKwh"]) > 1e-9):
        raise HarnessError(f"POST /customers/{customer_id}/plan: unexpected body: {plan_body}")
    evidence["enroll_plan"] = {
        "status": resp.status_code, "customerId": plan_body.get("customerId"),
        "planName": plan_body.get("planName"), "ratePerKwh": plan_body.get("ratePerKwh"),
        "status_field": plan_body.get("status"),
    }

    # 4. GET /customers/{id}/plan -- confirms the write is really durable
    #    and visible on a fresh read through the same real topology.
    resp = _call_with_lb_warmup_retry("GET", f"{base}/customers/{customer_id}/plan", headers=auth_header, timeout=15)
    if resp.status_code != 200:
        raise HarnessError(f"GET /customers/{customer_id}/plan: expected 200, got {resp.status_code}: {resp.text[:300]}")
    get_body = resp.json()
    if (get_body.get("customerId") != customer_id
            or get_body.get("planName") != plan_payload["planName"]
            or abs(float(get_body.get("ratePerKwh", -1)) - plan_payload["ratePerKwh"]) > 1e-9):
        raise HarnessError(f"GET /customers/{customer_id}/plan: unexpected body: {get_body}")
    evidence["get_plan"] = {
        "status": resp.status_code, "customerId": get_body.get("customerId"),
        "planName": get_body.get("planName"), "ratePerKwh": get_body.get("ratePerKwh"),
        "status_field": get_body.get("status"),
    }

    # BL-039: the aggregator/BFF fan-out, verified MULTI-PROCESS (CLAUDE.md:
    # first-of-its-kind multi-process work must be verified multi-process).
    # customer-service and billing-service are real processes here, so those
    # two sections must carry real data; metering-service is deliberately NOT
    # part of this topology, so its section must come back UNAVAILABLE and
    # the response must say partial=true -- a real dependency missing is the
    # exact degradation the BFF exists to survive, never a fabricated section.
    resp = _call_with_lb_warmup_retry("GET", f"{base}/bff/customers/{customer_id}/dashboard", headers=auth_header, timeout=20)
    if resp.status_code != 200:
        raise HarnessError(f"GET /bff/customers/{customer_id}/dashboard: expected 200, got {resp.status_code}: {resp.text[:300]}")
    dash = resp.json()
    sections = dash.get("sections", {})
    if (sections.get("customer", {}).get("status") != "OK"
            or sections.get("plan", {}).get("status") != "OK"
            or sections.get("plan", {}).get("data", {}).get("planName") != plan_payload["planName"]
            or sections.get("usage", {}).get("status") != "UNAVAILABLE"
            or dash.get("partial") is not True):
        raise HarnessError(f"GET /bff/customers/{customer_id}/dashboard: unexpected sections/partial: {dash}")
    evidence["bff_dashboard"] = {
        "status": resp.status_code, "partial": dash.get("partial"), "elapsedMs": dash.get("elapsedMs"),
        "customer": sections["customer"]["status"], "plan": sections["plan"]["status"],
        "usage": sections["usage"]["status"], "usage_reason": sections["usage"].get("reason"),
    }

    return evidence


# ---------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--startup-timeout", type=float, default=90.0,
                         help="Max seconds to wait for each service's own /actuator/health to report UP")
    parser.add_argument("--registry-timeout", type=float, default=90.0,
                         help="Max seconds to wait for real Eureka registry convergence (its own response cache refreshes on a real ~30s cycle)")
    parser.add_argument("--port-offset", type=int, default=0,
                         help="Shift every service's port by this amount (e.g. 10000 -> eureka-server on 18761, customer-service on 18081, ...). "
                              "Lets this harness run without colliding with another worktree/session using the default ports on this machine.")
    args = parser.parse_args()

    global EUREKA, DEPENDENT_SERVICES, ALL_SERVICES, EUREKA_PORT, GATEWAY_PORT
    EUREKA, DEPENDENT_SERVICES, ALL_SERVICES, EUREKA_PORT = build_services(args.port_offset)
    GATEWAY_PORT = DEFAULT_PORTS["api-gateway"] + args.port_offset

    overall_start = time.monotonic()
    procs: dict = {}
    result = {"result": "FAIL", "phases": {}, "evidence": {}, "error": None}

    try:
        preflight_check_ports()

        # Phase 1: eureka-server
        procs["eureka-server"] = {"proc": start_service(EUREKA)}
        eureka_up_s = wait_for_health("eureka-server", EUREKA["port"], args.startup_timeout)
        result["phases"]["eureka_health_s"] = eureka_up_s
        print(f"[OK] eureka-server UP after {eureka_up_s}s")

        # Phase 2: the 3 dependent real service instances, started concurrently
        for svc in DEPENDENT_SERVICES:
            procs[svc["name"]] = {"proc": start_service(svc)}
        for svc in DEPENDENT_SERVICES:
            up_s = wait_for_health(svc["name"], svc["port"], args.startup_timeout)
            result["phases"][f"{svc['name']}_health_s"] = up_s
            print(f"[OK] {svc['name']} UP after {up_s}s")

        # Phase 3: real Eureka registry convergence -- polled, never slept.
        expected = [svc["eureka_app_id"] for svc in DEPENDENT_SERVICES if svc["eureka_app_id"]]
        convergence_s = wait_for_eureka_registration(expected, args.registry_timeout)
        result["phases"]["eureka_registry_convergence_s"] = convergence_s
        print(f"[OK] Eureka registry shows {expected} all UP after {convergence_s}s")

        # Phase 3b: the real gateway-side readiness gate -- see
        # wait_for_gateway_routing_ready's docstring for the real race
        # this closes (server-side registry vs. each client's own local
        # DiscoveryClient cache).
        routing_ready_s = wait_for_gateway_routing_ready(GATEWAY_PORT, args.registry_timeout)
        result["phases"]["gateway_routing_ready_s"] = routing_ready_s
        print(f"[OK] api-gateway routing confirmed ready after {routing_ready_s}s")

        # Phase 4: the real authenticated end-to-end request chain.
        flow_start = time.monotonic()
        evidence = run_real_flow(GATEWAY_PORT)
        result["phases"]["flow_s"] = round(time.monotonic() - flow_start, 1)
        result["evidence"] = evidence
        print(f"[OK] real end-to-end flow through api-gateway succeeded: {json.dumps(evidence, indent=2)}")

        result["result"] = "PASS"

    except HarnessError as exc:
        result["error"] = str(exc)
        print(f"[FAIL] {exc}", file=sys.stderr)
    except Exception as exc:  # genuinely unexpected -- still report, still clean up
        result["error"] = f"unexpected {type(exc).__name__}: {exc}"
        print(f"[FAIL] unexpected error: {exc}", file=sys.stderr)
    finally:
        cleanup(procs)

    result["phases"]["total_wall_clock_s"] = round(time.monotonic() - overall_start, 1)
    print("\n--- REAL-TOPOLOGY TEST RESULT ---")
    print(json.dumps(result, indent=2))

    sys.exit(0 if result["result"] == "PASS" else 1)


if __name__ == "__main__":
    main()
