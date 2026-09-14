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
    resolved `capabilities` list (full capability records, in the
    manifest's selected order) and `unresolved_capability_ids` for any
    referenced id that no longer exists in the registry (reported
    honestly, never hidden)."""
    manifest_path = SHOWCASES_DIR / slug / "showcase.yaml"
    if not manifest_path.exists():
        raise ShowcaseNotFoundError(slug)

    manifest = _load_yaml(manifest_path)
    registry = load_capability_registry()

    selected_ids = manifest.get("selected_capabilities", [])
    resolved = []
    unresolved = []
    for cap_id in selected_ids:
        cap = registry.get(cap_id)
        if cap is None:
            unresolved.append(cap_id)
        else:
            resolved.append(cap)

    manifest["capabilities"] = resolved
    manifest["unresolved_capability_ids"] = unresolved
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
