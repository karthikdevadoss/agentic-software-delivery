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


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_interview_walkthrough() -> dict:
    """Returns the walkthrough dict with each path's story_ids resolved
    into full story records (in listed order), plus
    unresolved_story_ids/unresolved_capability_ids per path for anything
    referenced that no longer exists -- reported, never hidden."""
    data = _load_yaml(WALKTHROUGH_PATH)
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
