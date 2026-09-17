"""
Loads docs/INTERVIEW_WALKTHROUGH.yaml -- a deterministic, project-derived
index over real interview-readiness evidence (paths, featured stories, and
a compact index of the remaining real docs/interview-scenarios/<n>.md
write-ups). No content is generated or invented here: this module only
reads and validates the one YAML file; the actual narrative lives in that
file and in the linked docs/interview-scenarios/*.md write-ups.

Mirrors agent/showcase_data.py's pattern deliberately: same simplicity,
same "resolve references against a registry, report unresolved ones
honestly" discipline, so an unrecognized path_id or capability_id is a
visible data error, never silently dropped.
"""

from pathlib import Path

import yaml

import showcase_data

REPO_ROOT = Path(__file__).resolve().parent.parent
WALKTHROUGH_PATH = REPO_ROOT / "docs" / "INTERVIEW_WALKTHROUGH.yaml"
GITHUB_REPO_URL = "https://github.com/karthikdevadoss/agentic-software-delivery"


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _resolve_evidence_item(item: dict) -> list:
    """An evidence item already carrying a `url` passes through unchanged
    (as a single-item list, for a uniform return shape). `commit: "<sha>"`
    resolves to one real GitHub commit permalink. `source_paths: [...]`
    resolves to one evidence item PER path (never one inert comma-joined
    string) -- a trailing "/" is a real directory (tree link), otherwise a
    real file (blob link). Purely deterministic string construction here,
    no subprocess/I/O -- whether each commit/path is REAL is verified
    separately by agent/test_interview_walkthrough_data.py (same
    test-time-not-runtime discipline as the existing doc_path check),
    since this loader runs on every page request and must stay cheap."""
    if "url" in item:
        return [item]
    if "commit" in item:
        sha = item["commit"]
        return [{"label": item["label"], "url": f"{GITHUB_REPO_URL}/commit/{sha}"}]
    if "source_paths" in item:
        resolved = []
        for path in item["source_paths"]:
            kind = "tree" if path.endswith("/") else "blob"
            resolved.append({
                "label": f"{item['label']}: {path}",
                "url": f"{GITHUB_REPO_URL}/{kind}/master/{path}",
            })
        return resolved
    return [item]


def load_interview_walkthrough() -> dict:
    """Returns the walkthrough dict with each path's story_ids resolved
    into full story records (in listed order), plus
    unresolved_story_ids/unresolved_capability_ids per path for anything
    referenced that no longer exists -- reported, never hidden. Every
    story's real_evidence is also resolved so every item carries a real
    `url` by the time it reaches showcase.js -- evidenceLine() there never
    needs to know about `commit`/`source_paths`."""
    data = _load_yaml(WALKTHROUGH_PATH)

    for story in data.get("stories", []):
        resolved_evidence = []
        for item in story.get("real_evidence", []):
            resolved_evidence.extend(_resolve_evidence_item(item))
        story["real_evidence"] = resolved_evidence

    stories_by_id = {s["id"]: s for s in data.get("stories", [])}
    capability_registry = showcase_data.load_capability_registry()

    for path in data.get("paths", []):
        resolved_stories = []
        unresolved_stories = []
        for story_id in path.get("story_ids", []):
            story = stories_by_id.get(story_id)
            if story is None:
                unresolved_stories.append(story_id)
            else:
                resolved_stories.append(story)
        path["stories"] = resolved_stories
        path["unresolved_story_ids"] = unresolved_stories

        unresolved_caps = [
            cap_id for cap_id in path.get("capability_ids", [])
            if cap_id not in capability_registry
        ]
        path["unresolved_capability_ids"] = unresolved_caps

    return data


if __name__ == "__main__":
    import json
    print(json.dumps(load_interview_walkthrough(), indent=2))
