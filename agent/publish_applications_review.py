"""Builds agent/web/applications.json for the owner-facing /applications review page.

Source (run on a box that has DEVADOSS checked out):
  python publish_applications_review.py \\
    --architect50 /path/to/storage/applications/architect50-2026-10-06 \\
    --architect10 /path/to/storage/applications/architect-2026-10-06 \\
    --posting-dates /path/to/storage/applications/POSTING_DATES_2026-10-06.json

Bakes PDF packs from architect50 ranks that still have PDFs plus the earlier
10 architect packs, then applies the owner location TOP filter (policy v32 /
rule 62): ONLY remote Germany or remote worldwide/EU/EMEA, Berlin hybrid, or
Berlin office. Within that set, newest-posted first. Non-TOP cities (London,
Munich, Amsterdam, Paris, Stockholm, …) are dropped from the review page.
Cover letters and fit/gaps are inlined so the gated page can render without a
second private store.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent
WEB_DIR = AGENT_DIR / "web"
OUTPUT_PATH = WEB_DIR / "applications.json"
AS_OF = date(2026, 10, 6)

def location_tier(loc: str) -> int | None:
    """1=remote DE/worldwide/EU/EMEA, 2=Berlin hybrid, 3=Berlin office, None=drop.

    Owner 2026-10-06 17:07–17:10 Berlin (policy v32 / rule 62).
    """
    import re as _re
    l = (loc or "").lower()
    has_berlin = "berlin" in l
    has_remote = "remote" in l

    # Munich-only (no Berlin) unless remote-from-Germany
    if "munich" in l and not has_berlin:
        if has_remote and "germany" in l:
            return 1
        return None

    drop_cities = ["stockholm", "paris", "amsterdam", "dublin", "lisbon", "milan", "madrid"]
    if any(c in l for c in drop_cities) and not has_berlin:
        if "amsterdam" in l:
            return None
        if has_remote and any(x in l for x in ["europe", "emea", "germany", "global", "worldwide"]):
            return 1
        if not has_remote:
            return None

    if "london" in l:
        if has_remote and any(x in l for x in ["europe", "emea", "germany", "global", "worldwide"]):
            return 1
        if has_berlin and "hybrid" in l:
            return 2
        return None

    if has_remote and (
        ("united kingdom" in l or _re.search(r"\buk\b", l))
        and "germany" not in l
        and "europe" not in l
        and "emea" not in l
        and "global" not in l
        and "worldwide" not in l
    ):
        return None

    if has_remote:
        return 1
    if has_berlin and "hybrid" in l:
        return 2
    if has_berlin:
        return 3
    return None



# Slug order for architect50 ranks 1–25 (matches INDEX.md / PDF names).
A50_SLUGS = [
    "lovable-forward-deployed-engineer-london",
    "databricks-delivery-solutions-architect-stockholm",
    "openai-forward-deployed-engineer-munich",
    "openai-forward-deployed-engineer-paris",
    "adyen-ai-engineer-knowledge-infrastructure",
    "elevenlabs-forward-deployed-engineer-uk",
    "multiverse-senior-ai-engineer-london",
    "anthropic-applied-ai-architect-partnerships-london",
    "anthropic-applied-ai-engineer-dnb-london",
    "anthropic-applied-ai-engineer-enterprise-london",
    "openai-forward-deployed-engineer-london",
    "openai-applied-ai-engineer-startups-codex-munich",
    "tavily-forward-deployed-engineer-enterprise",
    "openai-applied-ai-engineer-startups-codex-london",
    "openai-applied-ai-engineer-startups-codex-paris",
    "openai-applied-ai-architect-large-enterprise-london",
    "anthropic-applied-ai-engineer-startups-london",
    "writer-ai-engineer-uk",
    "oyster-senior-ai-solutions-engineer-gtm",
    "openai-applied-ai-engineer-quants-london",
    "anthropic-applied-ai-architect-partnerships-munich",
    "pigment-senior-genai-engineer-uk",
    "nebius-fde-physical-ai-infrastructure",
    "decagon-solutions-architect-voice-london",
    "databricks-ai-fde-sweden",
]

# Earlier 10 (Sprint 7) slug order matching SHORTLIST ranks 1–10.
A10_SLUGS = [
    "n8n-forward-deployed-engineer-emea",
    "cursor-solutions-architect-central-europe",
    "cohere-fde-agentic-platform-europe",
    "smartsheet-sr-fde-ai-germany",
    "databricks-forward-deployed-engineer-de",
    "cursor-forward-deployed-engineer-emea",
    "langchain-deployed-architect-amsterdam",
    "anthropic-applied-ai-architect-startups-london",
    "databricks-delivery-solutions-architect-munich",
    "anthropic-forward-deployed-engineer-london",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse_index_row(line: str) -> dict | None:
    """Parse a TOP or legacy INDEX table row. Supports optional Loc tier column."""
    if not line.startswith("|") or "Rank" in line or "Loc tier" in line or line.startswith("|---"):
        return None
    parts = [p.strip() for p in line.strip().strip("|").split("|")]
    if len(parts) < 9:
        return None
    rank_s = parts[0]
    if not re.fullmatch(r"\d+", rank_s):
        return None
    # New INDEX: Rank | Loc tier | Company | Title | Location | Posted | Age | PDF | URL | Fit
    # Legacy:    Rank | Company | Title | Location | Posted | Age | PDF | URL | Fit
    if len(parts) >= 10 and parts[1].startswith(("1 ", "2 ", "3 ")):
        company, title, location, posted, age_s, pdf_cell, url, fit = (
            parts[2], parts[3], parts[4], parts[5], parts[6], parts[7], parts[8], parts[9]
        )
    else:
        company, title, location, posted, age_s, pdf_cell, url, fit = (
            parts[1], parts[2], parts[3], parts[4], parts[5], parts[6], parts[7], parts[8]
        )
    rank = int(rank_s)
    pdf_name = None
    m = re.search(r"(_cv_pdf/[\w.-]+\.pdf)", pdf_cell)
    if m:
        pdf_name = Path(m.group(1)).name
    elif "yes" in pdf_cell and "—" in pdf_cell:
        pdf_name = pdf_cell.split("—", 1)[1].strip().split()[0]
        if pdf_name.startswith("_cv_pdf/"):
            pdf_name = Path(pdf_name).name
    if not pdf_name and "yes" not in pdf_cell.lower():
        return None  # content-only rows are not baked into the review page
    return {
        "source_rank": rank,
        "company": company,
        "title": title,
        "location": location,
        "posted": posted,
        "age_days": int(age_s) if age_s.isdigit() else None,
        "pdf": pdf_name,
        "url": url,
        "fit_oneliner": fit,
    }


def _parse_shortlist(path: Path) -> list[dict]:
    rows = []
    for line in _read(path).splitlines():
        if not line.startswith("|") or "Rank" in line or line.startswith("|---"):
            continue
        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        if len(parts) < 8:
            continue
        if not re.fullmatch(r"\d+", parts[0]):
            continue
        url = parts[7]
        m = re.search(r"\((https?://[^)]+)\)", url)
        url = m.group(1) if m else url
        rows.append({
            "source_rank": int(parts[0]),
            "company": parts[1],
            "title": parts[2],
            "location": parts[4],
            "fit_oneliner": parts[5],
            "gaps": parts[6],
            "url": url,
        })
    return rows


def _age(posted: str) -> int | None:
    try:
        d = date.fromisoformat(posted)
    except ValueError:
        return None
    return (AS_OF - d).days


def _section(md: str, heading: str) -> str:
    """Return markdown body under ## heading until the next ##."""
    pat = re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.I | re.M)
    m = pat.search(md)
    if not m:
        return ""
    rest = md[m.end():]
    nxt = re.search(r"^##\s+", rest, re.M)
    body = rest[: nxt.start()] if nxt else rest
    return body.strip()


def _fit_oneliner_from_gaps(fit_gaps: str, fallback: str) -> str:
    fit = _section(fit_gaps, "Fit")
    if not fit:
        return fallback
    # First non-empty line
    for line in fit.splitlines():
        line = line.strip().lstrip("-").strip()
        if line:
            return line
    return fallback


def _load_a50(root: Path) -> list[dict]:
    """Load architect50 PDF packs. INDEX may be location-filtered; match by PDF name / slug."""
    index = root / "INDEX.md"
    by_pdf = {}
    by_url = {}
    for line in _read(index).splitlines():
        row = _parse_index_row(line)
        if not row:
            continue
        if row.get("pdf"):
            by_pdf[row["pdf"]] = row
        if row.get("url"):
            by_url[row["url"]] = row
    packs = []
    for i, slug in enumerate(A50_SLUGS, start=1):
        pdf = f"{i:02d}_{slug}.pdf"
        meta = by_pdf.get(pdf)
        pack_dir = root / slug
        if not meta:
            # Pack dropped from TOP INDEX — still load if we want unfiltered; skip here.
            # Fall back: read nothing; caller filters. Keep loading from posting for filter input.
            if not (pack_dir / "posting.md").exists():
                continue
            # Minimal meta from slug only when not in TOP INDEX (will be filtered out)
            posting = _read(pack_dir / "posting.md")
            cover = _read(pack_dir / "cover_letter.md") if (pack_dir / "cover_letter.md").exists() else ""
            fit_gaps = _read(pack_dir / "fit_gaps.md") if (pack_dir / "fit_gaps.md").exists() else ""
            # Location from first lines of posting if possible
            loc = ""
            for ln in posting.splitlines()[:30]:
                if "location" in ln.lower() or "remote" in ln.lower() or "berlin" in ln.lower():
                    loc = ln.split(":", 1)[-1].strip() if ":" in ln else ln.strip()
                    break
            # Prefer matching INDEX Other EU is not parsed; use slug heuristics for location
            # via hardcoded map from prior bake when missing
            packs.append({
                "id": f"a50-{i:02d}-{slug}",
                "batch": "architect50-2026-10-06",
                "source_rank": i,
                "slug": slug,
                "company": slug.split("-")[0].title(),
                "title": slug,
                "location": loc or slug,
                "posted": "1970-01-01",
                "age_days": None,
                "fit_oneliner": "",
                "url": "",
                "posting": posting,
                "cover_letter": cover,
                "fit_gaps": fit_gaps,
                "cv_pdf": pdf,
                "pdfs": [pdf],
            })
            continue
        posting = _read(pack_dir / "posting.md") if (pack_dir / "posting.md").exists() else ""
        cover = _read(pack_dir / "cover_letter.md") if (pack_dir / "cover_letter.md").exists() else ""
        fit_gaps = _read(pack_dir / "fit_gaps.md") if (pack_dir / "fit_gaps.md").exists() else ""
        packs.append({
            "id": f"a50-{i:02d}-{slug}",
            "batch": "architect50-2026-10-06",
            "source_rank": i,
            "slug": slug,
            "company": meta["company"],
            "title": meta["title"],
            "location": meta["location"],
            "posted": meta["posted"],
            "age_days": meta["age_days"] if meta["age_days"] is not None else _age(meta["posted"]),
            "fit_oneliner": _fit_oneliner_from_gaps(fit_gaps, meta["fit_oneliner"]),
            "url": meta["url"],
            "posting": posting,
            "cover_letter": cover,
            "fit_gaps": fit_gaps,
            "cv_pdf": pdf,
            "pdfs": [pdf] if pdf else [],
        })
    return packs


def _posting_dates_map(path: Path | None) -> dict[str, str]:
    """Map company+title → posted_at from Sprint 9 JSON when available."""
    if not path or not path.exists():
        return {}
    data = json.loads(_read(path))
    out = {}
    # Accept either list or dict-with-jobs shapes
    rows = data if isinstance(data, list) else data.get("jobs") or data.get("rows") or []
    if isinstance(data, dict) and not rows:
        # Try nested sections
        for v in data.values():
            if isinstance(v, list):
                rows = v
                break
    for row in rows:
        if not isinstance(row, dict):
            continue
        company = row.get("company") or ""
        title = row.get("title") or ""
        posted = row.get("posted_at") or row.get("posted") or row.get("date")
        if company and title and posted:
            out[f"{company}::{title}"] = str(posted)[:10]
            # Also key by URL when present
            url = row.get("url") or row.get("posting_url") or ""
            if url:
                out[f"url::{url}"] = str(posted)[:10]
    return out


def _load_a10(root: Path, dates: dict[str, str]) -> list[dict]:
    shortlist = _parse_shortlist(root / "SHORTLIST.md")
    by_rank = {r["source_rank"]: r for r in shortlist}
    # Hardcoded ATS dates from POSTING_DATES (fallback if JSON shape differs)
    fallback_dates = {
        "n8n-forward-deployed-engineer-emea": "2026-09-15",
        "cursor-solutions-architect-central-europe": "2026-07-02",
        "cohere-fde-agentic-platform-europe": "2026-05-12",
        "smartsheet-sr-fde-ai-germany": "2026-05-01",
        "databricks-forward-deployed-engineer-de": "2026-08-24",
        "cursor-forward-deployed-engineer-emea": "2026-06-03",
        "langchain-deployed-architect-amsterdam": "2026-08-28",
        "anthropic-applied-ai-architect-startups-london": "2026-09-23",
        "databricks-delivery-solutions-architect-munich": "2026-09-21",
        "anthropic-forward-deployed-engineer-london": "2026-09-14",
    }
    packs = []
    for i, slug in enumerate(A10_SLUGS, start=1):
        meta = by_rank.get(i)
        if not meta:
            raise SystemExit(f"architect SHORTLIST missing rank {i}")
        pack_dir = root / slug
        posting = _read(pack_dir / "posting.md") if (pack_dir / "posting.md").exists() else ""
        cover = _read(pack_dir / "cover_letter.md") if (pack_dir / "cover_letter.md").exists() else ""
        fit_gaps = ""
        if (pack_dir / "fit_gaps.md").exists():
            fit_gaps = _read(pack_dir / "fit_gaps.md")
        else:
            fit_gaps = f"## Fit\n\n{meta['fit_oneliner']}\n\n## Gaps\n\n{meta.get('gaps', '')}\n"
        posted = (
            dates.get(f"url::{meta['url']}")
            or dates.get(f"{meta['company']}::{meta['title']}")
            or fallback_dates.get(slug)
        )
        if not posted:
            # Try posting.md
            m = re.search(r"posted_at:\s*(\d{4}-\d{2}-\d{2})", posting)
            posted = m.group(1) if m else "1970-01-01"
        pdf = f"{i:02d}_{slug}.pdf"
        packs.append({
            "id": f"a10-{i:02d}-{slug}",
            "batch": "architect-2026-10-06",
            "source_rank": i,
            "slug": slug,
            "company": meta["company"],
            "title": meta["title"],
            "location": meta["location"],
            "posted": posted,
            "age_days": _age(posted),
            "fit_oneliner": _fit_oneliner_from_gaps(fit_gaps, meta["fit_oneliner"]),
            "url": meta["url"],
            "posting": posting,
            "cover_letter": cover,
            "fit_gaps": fit_gaps,
            "cv_pdf": pdf,
            "pdfs": [pdf],
        })
    return packs


def build(architect50: Path, architect10: Path, posting_dates: Path | None) -> dict:
    dates = _posting_dates_map(posting_dates)
    packs = _load_a50(architect50) + _load_a10(architect10, dates)
    filtered = []
    for p in packs:
        tier = location_tier(p.get("location") or "")
        if tier is None:
            continue
        p["loc_tier"] = tier
        filtered.append(p)
    filtered.sort(key=lambda p: (p["posted"] or "0000-00-00", -p.get("loc_tier", 9), -p["source_rank"]), reverse=True)
    for i, p in enumerate(filtered, start=1):
        p["rank"] = i
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "as_of": AS_OF.isoformat(),
        "title": "Applications Review",
        "description": (
            "Owner-facing application packs (CV + cover letter + posting). "
            "TOP filter (policy v32): remote DE/worldwide/EU/EMEA, Berlin hybrid, Berlin office; "
            "newest posted first. Never apply or send from this page."
        ),
        "filter": {
            "policy": "v32",
            "rule": 62,
            "allow": [
                "remote Germany or remote worldwide/EU/EMEA",
                "Berlin hybrid full-time",
                "Berlin all-days office",
            ],
        },
        "count": len(filtered),
        "packs": filtered,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--architect50", type=Path, required=True)
    ap.add_argument("--architect10", type=Path, required=True)
    ap.add_argument("--posting-dates", type=Path, default=None)
    ap.add_argument("--stdout", action="store_true")
    args = ap.parse_args(argv)
    data = build(args.architect50, args.architect10, args.posting_dates)
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if args.stdout:
        sys.stdout.write(text)
    else:
        OUTPUT_PATH.write_text(text, encoding="utf-8")
        print(f"Wrote {OUTPUT_PATH} ({data['count']} packs)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
