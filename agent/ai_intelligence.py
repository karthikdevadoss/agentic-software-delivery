"""
Serves the public-safe "Daily AI Intelligence" files a scheduled cloud
routine writes to docs/ai-intelligence/daily/YYYY-MM-DD.md in this repo.

That routine (see docs/ROADMAP.md) runs against Karthik's separate
PRIVATE repository and pushes only a general-AI-industry, career-content-
free subset here each day — this module just lists and serves what's
already been committed. It never calls a model itself and never writes
anything; if no file exists yet for a given date, or none exist at all,
it says so plainly rather than fabricating content.
"""

import re
from pathlib import Path

DAILY_DIR = Path(__file__).resolve().parent.parent / "docs" / "ai-intelligence" / "daily"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")


def list_dates() -> list[str]:
    """Real dates with a real committed file, newest first. Empty list
    (not an error) if the directory doesn't exist yet — the routine may
    not have run/pushed its first file yet."""
    if not DAILY_DIR.is_dir():
        return []
    names = [p.name for p in DAILY_DIR.iterdir() if _DATE_RE.match(p.name)]
    return sorted((n[:-3] for n in names), reverse=True)


def read_day(date: str) -> str | None:
    """Raw markdown for one real date, or None if that exact file doesn't
    exist — never a partial/guessed reconstruction."""
    if not _DATE_RE.match(f"{date}.md"):
        return None
    path = DAILY_DIR / f"{date}.md"
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def parse_sections(markdown: str) -> list[dict]:
    """Splits on '## ' headers into {heading, body} — the frontend
    renders each heading as a one-line highlight and its body as the
    expand-on-click detail. Deliberately tolerant of whatever heading
    style the routine's own model output actually used that day (no
    hard requirement on an exact section list/order), since the routine
    is a real LLM call, not a template fill."""
    sections = []
    current_heading = None
    current_lines: list[str] = []

    def flush():
        if current_heading is not None:
            body = "\n".join(current_lines).strip()
            if body:
                sections.append({"heading": current_heading, "body": body})

    for line in markdown.splitlines():
        if line.startswith("## "):
            flush()
            current_heading = line[3:].strip()
            current_lines = []
        elif current_heading is not None:
            current_lines.append(line)
    flush()
    return sections
