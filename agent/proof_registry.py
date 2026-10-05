"""The public proof surface: load it, and refuse it when it drifts.

WHAT THIS GUARDS
Every capability shown to a stranger must resolve to six things:

    capability id -> public claim -> verification status -> evidence
                  -> inspectable destination(s) -> limitation

This module loads docs/PUBLIC_PROOF_SURFACE.yaml together with
docs/PORTFOLIO_CAPABILITIES.yaml and refuses the pair unless that holds, with
every destination resolving to something real and no public status exceeding
the verification level actually recorded for that capability.

WHAT IT DELIBERATELY DOES NOT GUARD, AND WHY THAT MATTERS
It checks STRUCTURE and REFERENCES. It does not read the claim prose and decide
whether the claim is true, and it must never be grown in that direction.

That is not caution for its own sake -- it is this project's most expensive
lesson, paid for twice. In Deep Consensus Sprint 5 a scorer's substring match
read the answer "they are NOT suited to CPU-bound work" as publishing "suited to
cpu-bound", and manufactured a headline that the engine had introduced a
falsehood. In Sprint 6 the same pattern manufactured the opposite headline. The
honest conclusion was recorded as unapproved lesson A17: treat any assertion
over prose in a guard, scorer, identity mechanism, routing rule or test as
suspect by default. So the division of labour here is explicit:

    a script decides whether a claim has evidence, a destination and a stated
    limitation, and whether its status is within what the registry records;
    a human decides whether the claim is true.

Mechanising the second would feel stronger and would be worse, because it would
produce confident verdicts about prose -- and a false PASS from a truth-checker
is far more dangerous than no truth-checker at all.

CHECKS, each of which has failed at least once against a seeded mutation in
agent/test_proof_registry.py:

  1. every capability_id exists in docs/PORTFOLIO_CAPABILITIES.yaml
  2. no duplicate capability_id in the proof surface
  3. public_status is one of the four published vocabulary values
  4. public_status does not exceed the recorded verification_level
     (this is what stops DOCUMENTED being presented as LIVE)
  5. required public fields are present and non-empty -- including BOTH
     limitation forms, which are required rather than optional, with the short
     one bounded in length and required to differ from the long one
  6. at least one destination, each with a label and an href
  7. every internal href matches a REAL registered GET route, decided by
     Starlette's own matcher rather than by string comparison
  8. every external href is an absolute http(s) URL
  9. no href points at a forbidden/private path
 10. every repo-relative evidence path recorded for a public capability
     actually exists on disk
 11. an EXPERIMENTAL_PAUSED capability carries an explicit limitation naming
     its paused/unproven state -- a presence check on the required words, not
     a judgement about the prose around them
 12. at least one audience per capability, each from the published list
 13. the front door (tier PRIMARY) stays within a sane range

Run:  python agent/proof_registry.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SURFACE_PATH = REPO_ROOT / "docs" / "PUBLIC_PROOF_SURFACE.yaml"
CAPABILITIES_PATH = REPO_ROOT / "docs" / "PORTFOLIO_CAPABILITIES.yaml"

REQUIRED_FIELDS = (
    "capability_id",
    "tier",
    "public_status",
    "headline",
    "public_claim",
    "public_limitation",
    "limitation_short",
    "evidence_summary",
    "audiences",
    "destinations",
)

VALID_TIERS = ("PRIMARY", "SECONDARY")

# A front door with two items proves nothing and one with twenty proves nothing
# either, for opposite reasons. The brief's range, enforced.
MIN_PRIMARY = 5
MAX_PRIMARY = 7

# A collapsed card shows only limitation_short, so it has to carry a real
# boundary on its own. Too long and the compression achieved nothing; identical
# to the full text and it is not a compression at all; too short and it is
# decoration. Checked, because the collapsed view is what most visitors read.
MAX_SHORT_LIMITATION = 130
MIN_SHORT_LIMITATION = 25

# Words an EXPERIMENTAL_PAUSED limitation must actually contain. A presence
# check, not a reading: it stops a paused research result being published with
# a limitation that never mentions it is paused or unproven.
PAUSED_REQUIRED_WORDS = ("paused", "unproven")


def load_surface(path: Path = SURFACE_PATH) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_capabilities(path: Path = CAPABILITIES_PATH) -> dict:
    """capability id -> its registry entry."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {c["id"]: c for c in data["capabilities"]}


def _registered_get_paths():
    """Real registered GET routes, imported lazily so that a import-time
    failure in the web app surfaces as its own error rather than as a
    misleading 'no routes registered' verdict."""
    import web_server as ws
    from starlette.routing import Route

    return [r for r in ws.routes if isinstance(r, Route) and "GET" in (r.methods or set())]


def internal_path_is_routable(path: str, routes=None) -> bool:
    """True if `path` matches a real registered GET route, using Starlette's
    own Route.matches() -- the same mechanism that decides a real incoming
    request. A hand-rolled string comparison would quietly disagree with the
    router on exactly the parameterised routes (/showcase/{slug}) where being
    wrong matters.

    agent/test_showcase_data.py once carried an identical copy (ACT-027); it
    now calls this one, passing its own route list.
    """
    from starlette.routing import Match

    if routes is None:
        routes = _registered_get_paths()
    scope = {"type": "http", "method": "GET", "path": path}
    for route in routes:
        match, _ = route.matches(scope)
        if match == Match.FULL:
            return True
    return False


def classify_href(href: str, routes=None) -> str:
    """'ABSOLUTE_EXTERNAL' | 'VALID_INTERNAL_ROUTE' | 'BROKEN_INTERNAL_ROUTE'
    | 'BARE_RELATIVE_PATH'. The last is always invalid as a rendered href."""
    parsed = urlparse(href)
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return "ABSOLUTE_EXTERNAL"
    if href.startswith("/"):
        return (
            "VALID_INTERNAL_ROUTE"
            if internal_path_is_routable(parsed.path, routes)
            else "BROKEN_INTERNAL_ROUTE"
        )
    return "BARE_RELATIVE_PATH"


def validate(surface: dict, capabilities: dict, repo_root: Path = REPO_ROOT,
             routes=None, check_routes: bool = True) -> list[str]:
    """Return a list of human-readable problems. Empty list means the public
    proof surface is structurally sound. Never raises on bad input -- a
    malformed file is reported as a problem, because a validator that crashes
    on the thing it validates tells you nothing about the thing."""
    problems: list[str] = []

    if not isinstance(surface, dict):
        return ["PUBLIC_PROOF_SURFACE.yaml did not parse as a mapping"]

    vocabulary = surface.get("status_vocabulary") or {}
    status_requires = surface.get("status_requires") or {}
    known_audiences = set((surface.get("audiences") or {}).keys())
    forbidden = surface.get("forbidden_destination_patterns") or []
    entries = surface.get("capabilities")

    if not vocabulary:
        problems.append("status_vocabulary is missing or empty")
    if not status_requires:
        problems.append("status_requires is missing or empty -- nothing stops a status being overstated")
    if not known_audiences:
        problems.append("audiences is missing or empty")
    if not entries:
        return problems + ["capabilities is missing or empty -- there is no proof surface"]

    if routes is None and check_routes:
        routes = _registered_get_paths()

    seen_ids: set[str] = set()
    primary_count = 0

    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            problems.append(f"capabilities[{index}] is not a mapping")
            continue

        cid = entry.get("capability_id") or f"<missing id at index {index}>"
        where = f"{cid}"

        # 5. required fields present and non-empty
        for field in REQUIRED_FIELDS:
            value = entry.get(field)
            if value is None or (isinstance(value, (str, list)) and len(value) == 0) or (
                isinstance(value, str) and not value.strip()
            ):
                problems.append(f"{where}: required field '{field}' is missing or empty")

        # 2. no duplicates
        if cid in seen_ids:
            problems.append(f"{where}: duplicate capability_id in the proof surface")
        seen_ids.add(cid)

        # 1. the id is real
        registry_entry = capabilities.get(cid)
        if registry_entry is None:
            problems.append(
                f"{where}: capability_id does not exist in docs/PORTFOLIO_CAPABILITIES.yaml "
                "-- a public claim with no registered capability behind it"
            )

        tier = entry.get("tier")
        if tier not in VALID_TIERS:
            problems.append(f"{where}: tier {tier!r} is not one of {VALID_TIERS}")
        if tier == "PRIMARY":
            primary_count += 1

        status = entry.get("public_status")
        # 3. status is in the published vocabulary
        if status not in vocabulary:
            problems.append(
                f"{where}: public_status {status!r} is not in the published status_vocabulary "
                f"{sorted(vocabulary)}"
            )
        # 4. status does not exceed what the registry records
        elif registry_entry is not None:
            allowed = status_requires.get(status) or []
            level = registry_entry.get("verification_level")
            if level not in allowed:
                problems.append(
                    f"{where}: public_status {status} requires verification_level in {allowed}, "
                    f"but PORTFOLIO_CAPABILITIES.yaml records {level!r} "
                    "-- this is a claim presented above its evidence"
                )

        # 5b. the one-line limitation must be short, real, and not a copy
        short = (entry.get("limitation_short") or "").strip()
        full = " ".join((entry.get("public_limitation") or "").split())
        if short:
            if len(short) > MAX_SHORT_LIMITATION:
                problems.append(
                    f"{where}: limitation_short is {len(short)} chars, over the "
                    f"{MAX_SHORT_LIMITATION} limit -- it has to fit a collapsed card"
                )
            if len(short) < MIN_SHORT_LIMITATION:
                problems.append(
                    f"{where}: limitation_short is {len(short)} chars, under "
                    f"{MIN_SHORT_LIMITATION} -- a boundary that short is decoration"
                )
            if short == full:
                problems.append(
                    f"{where}: limitation_short is identical to public_limitation, "
                    "so nothing was actually compressed"
                )

        # 11. a paused/experimental thing must say so in its limitation
        if status == "EXPERIMENTAL_PAUSED":
            for field in ("public_limitation", "limitation_short"):
                limitation = (entry.get(field) or "").lower()
                missing = [w for w in PAUSED_REQUIRED_WORDS if w not in limitation]
                if missing:
                    problems.append(
                        f"{where}: EXPERIMENTAL_PAUSED but its {field} never says "
                        f"{missing} -- paused research must not read as working "
                        "product, and the collapsed card shows only the short form"
                    )

        # 12. audiences
        audiences = entry.get("audiences") or []
        if not isinstance(audiences, list) or not audiences:
            problems.append(f"{where}: needs at least one audience")
        else:
            for audience in audiences:
                if audience not in known_audiences:
                    problems.append(
                        f"{where}: audience {audience!r} is not one of {sorted(known_audiences)}"
                    )

        # 6/7/8/9. destinations
        destinations = entry.get("destinations") or []
        if not isinstance(destinations, list) or not destinations:
            problems.append(f"{where}: needs at least one inspectable destination")
            destinations = []
        for destination in destinations:
            if not isinstance(destination, dict):
                problems.append(f"{where}: a destination is not a mapping")
                continue
            label = (destination.get("label") or "").strip()
            href = (destination.get("href") or "").strip()
            if not label:
                problems.append(f"{where}: a destination has no label")
            if not href:
                problems.append(f"{where}: destination {label!r} has no href")
                continue

            for pattern in forbidden:
                if pattern in href:
                    problems.append(
                        f"{where}: destination {label!r} -> {href} points at a FORBIDDEN/PRIVATE "
                        f"path (matched {pattern!r})"
                    )

            if check_routes:
                classification = classify_href(href, routes)
                if classification == "BROKEN_INTERNAL_ROUTE":
                    problems.append(
                        f"{where}: destination {label!r} -> {href} is not a registered route "
                        "-- a visitor clicking it gets a 404"
                    )
                elif classification == "BARE_RELATIVE_PATH":
                    problems.append(
                        f"{where}: destination {label!r} -> {href} is a bare relative path, "
                        "which never resolves correctly as a rendered href"
                    )

        # 10. recorded evidence paths still exist on disk
        if registry_entry is not None:
            for module in registry_entry.get("relevant_modules") or []:
                if not (repo_root / module).exists():
                    problems.append(
                        f"{where}: recorded evidence path {module!r} does not exist on disk "
                        "-- the evidence for a public claim has moved or been deleted"
                    )

    # 13. front-door size
    if primary_count < MIN_PRIMARY:
        problems.append(
            f"only {primary_count} PRIMARY capabilities -- a front door needs at least {MIN_PRIMARY}"
        )
    if primary_count > MAX_PRIMARY:
        problems.append(
            f"{primary_count} PRIMARY capabilities -- more than {MAX_PRIMARY} floods the first "
            "screen and nothing stands out; move the weakest to SECONDARY"
        )

    return problems


def public_entries(tier: str | None = None, audience: str | None = None):
    """The validated public surface, for a renderer to consume. Raises rather
    than returning a partial surface -- rendering an invalid proof surface is
    the failure this whole module exists to prevent."""
    surface = load_surface()
    capabilities = load_capabilities()
    problems = validate(surface, capabilities)
    if problems:
        raise ValueError(
            "refusing to serve an invalid public proof surface:\n  - "
            + "\n  - ".join(problems)
        )
    entries = surface["capabilities"]
    if tier is not None:
        entries = [e for e in entries if e.get("tier") == tier]
    if audience is not None:
        entries = [e for e in entries if audience in (e.get("audiences") or [])]
    return entries


def main() -> int:
    try:
        surface = load_surface()
        capabilities = load_capabilities()
    except Exception as exc:  # noqa: BLE001 -- a parse failure is a real result
        print(f"PROOF SURFACE GATE: FAIL -- could not load the registry: {exc}")
        return 1

    problems = validate(surface, capabilities)
    entries = surface.get("capabilities") or []
    primary = [e for e in entries if e.get("tier") == "PRIMARY"]

    if not problems:
        print(
            f"PROOF SURFACE GATE: PASS -- {len(entries)} public capabilities "
            f"({len(primary)} on the front door), every claim with a status, a stated "
            "limitation and at least one destination that resolves"
        )
        for entry in entries:
            print(
                f"  {entry['public_status']:<20} {entry['tier']:<10} {entry['capability_id']}"
            )
        return 0

    print(f"PROOF SURFACE GATE: FAIL -- {len(problems)} problem(s)")
    for problem in problems:
        print(f"  {problem}")
    print(
        "\nThe public surface would misrepresent the evidence. Fix the registry, or "
        "REMOVE the claim -- weakening a check to let a claim through is the one "
        "repair that is never allowed here."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
