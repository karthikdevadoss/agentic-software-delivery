"""
Job-specific showcase factory — reads showcases/<slug>/showcase.yaml plus
docs/PORTFOLIO_CAPABILITIES.yaml and resolves them into one JSON payload
for the reusable showcase.html/js renderer. No showcase content is
invented here: every capability shown must already exist in the registry,
and a manifest referencing an unknown capability id is reported as a real
data error, not silently dropped.
"""

import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SHOWCASES_DIR = REPO_ROOT / "showcases"
CAPABILITIES_PATH = REPO_ROOT / "docs" / "PORTFOLIO_CAPABILITIES.yaml"


class ShowcaseNotFoundError(Exception):
    pass


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_capability_registry() -> dict:
    """Returns {capability_id: capability_dict}."""
    data = _load_yaml(CAPABILITIES_PATH)
    return {c["id"]: c for c in data.get("capabilities", [])}


def list_showcase_slugs() -> list:
    if not SHOWCASES_DIR.exists():
        return []
    return sorted(
        p.parent.name for p in SHOWCASES_DIR.glob("*/showcase.yaml")
    )


def load_showcase(slug: str) -> dict:
    """Resolves one showcase manifest against the live capability registry.

    Returns a single JSON-ready dict: the manifest's own fields plus a
    resolved `capabilities` list (full capability records, each carrying
    its own `addresses_requirement` -- the EXACT requirement text this
    specific capability is evidence for, or None for real additional
    evidence that isn't itself a named requirement -- in the manifest's
    selected order), `unresolved_capability_ids` for any referenced id no
    longer in the registry, and `unresolved_requirement_texts` for any
    `addresses_requirement` value that doesn't exactly match an entry in
    `job_requirements_addressed` (a typo/drift here would otherwise be a
    silent, undetectable data error). AEQ-026: `selected_capabilities`
    used to be a flat id list paired with `job_requirements_addressed` by
    ARRAY POSITION in showcase.js -- this explicit per-capability mapping
    replaces that positional coupling entirely; every requirement pairing
    a capability claims is asserted once, here, not implied by list order."""
    manifest_path = SHOWCASES_DIR / slug / "showcase.yaml"
    if not manifest_path.exists():
        raise ShowcaseNotFoundError(slug)

    manifest = _load_yaml(manifest_path)
    registry = load_capability_registry()
    known_requirements = set(manifest.get("job_requirements_addressed", []))

    selected = manifest.get("selected_capabilities", [])
    resolved = []
    unresolved_caps = []
    unresolved_reqs = []
    for entry in selected:
        cap_id = entry["id"]
        addresses = entry.get("addresses_requirement")
        cap = registry.get(cap_id)
        if cap is None:
            unresolved_caps.append(cap_id)
            continue
        if addresses is not None and addresses not in known_requirements:
            unresolved_reqs.append(f"{cap_id} -> {addresses!r}")
        resolved.append({**cap, "addresses_requirement": addresses})

    manifest["capabilities"] = resolved
    manifest["unresolved_capability_ids"] = unresolved_caps
    manifest["unresolved_requirement_texts"] = unresolved_reqs
    return manifest


if __name__ == "__main__":
    for slug in list_showcase_slugs():
        showcase = load_showcase(slug)
        print(json.dumps({
            "slug": slug,
            "title": showcase.get("title"),
            "capabilities_resolved": len(showcase["capabilities"]),
            "unresolved": showcase["unresolved_capability_ids"],
        }, indent=2))
