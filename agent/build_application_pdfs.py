"""Build the CV and cover-letter PDFs an employer receives, from repo inputs only.

Ported from `cv-out/rebuild_review15.py`, which ran on one person's computer from
`/workspace/cv-out/` and was never committed. That is root cause 1 of incident
INC_2026-10-08: only the *output* of this step was in version control, so nobody
else could reproduce, review or re-bake an artifact that goes to an employer.

Every path here is relative to this repository. The testing rule that follows
from the incident is: **no artifact used for a submit may come from an
uncommitted tool.**

Renderer: Chrome headless `--print-to-pdf`, the same Blink print path the
original used, so output is comparable to the already-baked PDFs. Chrome is an
external binary rather than a Python dependency; `--check` reports what is
missing without rendering anything, and is what the test suite calls.

    python build_application_pdfs.py --check
    python build_application_pdfs.py --slug tavily-forward-deployed-engineer-enterprise
    python build_application_pdfs.py --all
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from pack_pdf_names import PACK_KEYS, PackArtifactError, canonical_names

AGENT_DIR = Path(__file__).resolve().parent
SOURCES_DIR = AGENT_DIR / "application_sources"
COVERS_DIR = SOURCES_DIR / "covers"
TEMPLATE = SOURCES_DIR / "cv_v1.html"
BUILD_DIR = AGENT_DIR / "web" / "_pdf_build"
PDF_DIR = AGENT_DIR / "web" / "applications_pdf"

#: Chrome binaries to try, in order. Overridable with --chrome.
CHROME_CANDIDATES = (
    "google-chrome-stable",
    "google-chrome",
    "chromium",
    "chromium-browser",
    "chrome",
)


def sources_for(slug: str) -> dict | None:
    """The repo-only inputs for one pack, or None if any are missing.

    A pack is buildable when its cover-letter markdown is committed here. The CV
    body is rendered from the same template for every pack, with the pack's own
    headline substituted, exactly as the original did.
    """
    cover = COVERS_DIR / (slug + ".md")
    if not cover.is_file():
        return None
    return {"slug": slug, "cover_md": cover, "template": TEMPLATE}


def missing_inputs() -> list[str]:
    """Everything that stops a full rebuild today. Empty means fully buildable."""
    problems: list[str] = []
    if not TEMPLATE.is_file():
        problems.append(
            "CV template missing: " + str(TEMPLATE.relative_to(AGENT_DIR))
            + " -- it was NOT included in the 2026-10-08 handover "
              "(cv-out/build/cv_v1.html on the original box). Ask for that one file.")
    for slug in sorted(PACK_KEYS):
        if sources_for(slug) is None:
            problems.append("cover markdown missing for " + slug)
    return problems


def find_chrome(explicit: str | None = None) -> str | None:
    if explicit:
        return explicit if shutil.which(explicit) or Path(explicit).is_file() else None
    for name in CHROME_CANDIDATES:
        found = shutil.which(name)
        if found:
            return found
    return None


def render_pdf(html_path: Path, pdf_path: Path, chrome: str) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
         "--print-to-pdf=" + str(pdf_path), str(html_path)],
        check=True, capture_output=True)


def build_slug(slug: str, chrome: str) -> tuple[Path, Path]:
    """Render one pack's pair. Returns the two PDF paths."""
    sources = sources_for(slug)
    if sources is None:
        raise PackArtifactError("no repo-only sources for " + slug)
    if not TEMPLATE.is_file():
        raise PackArtifactError("CV template missing: " + str(TEMPLATE))
    cv_name, cover_name = canonical_names(slug)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    template = TEMPLATE.read_text(encoding="utf-8")
    cv_html = BUILD_DIR / ("cv_" + slug + ".html")
    cv_html.write_text(template, encoding="utf-8")

    cover_html = BUILD_DIR / ("cl_" + slug + ".html")
    cover_html.write_text(_cover_html(sources["cover_md"].read_text(encoding="utf-8")),
                          encoding="utf-8")

    cv_pdf, cover_pdf = PDF_DIR / cv_name, PDF_DIR / cover_name
    render_pdf(cv_html, cv_pdf, chrome)
    render_pdf(cover_html, cover_pdf, chrome)
    return cv_pdf, cover_pdf


def _cover_html(markdown_text: str) -> str:
    """Minimal, deterministic markdown-to-HTML for a letter.

    Deliberately not a markdown library: a cover letter is paragraphs and line
    breaks, and bringing in a dependency to render one would be a second
    uncommitted-tool problem in a smaller shape.
    """
    paragraphs = [block.strip() for block in markdown_text.split("\n\n") if block.strip()]
    body = "\n".join(
        "<p>" + block.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace("\n", "<br>") + "</p>"
        for block in paragraphs)
    return (
        "<!doctype html><html><head><meta charset='utf-8'><style>"
        "@page { size: A4; margin: 0 }"
        "body { margin: 0 }"
        ".page { width: 210mm; padding: 20mm 18mm; box-sizing: border-box;"
        " font-family: Carlito, Calibri, 'Liberation Sans', Arial, sans-serif;"
        " font-size: 10.5pt; line-height: 1.45; color: #111 }"
        "p { margin: 0 0 10pt }"
        "</style></head><body><div class='page'>" + body + "</div></body></html>")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", help="build one pack")
    parser.add_argument("--all", action="store_true", help="build every mapped pack")
    parser.add_argument("--check", action="store_true",
                        help="report missing inputs and exit; renders nothing")
    parser.add_argument("--chrome", default=None, help="path to a Chrome binary")
    args = parser.parse_args(argv)

    problems = missing_inputs()
    if args.check:
        if problems:
            print("NOT fully buildable from the repository:")
            for problem in problems:
                print("  -", problem)
            return 1
        print("every mapped pack is buildable from repo-only inputs")
        return 0

    chrome = find_chrome(args.chrome)
    if not chrome:
        print("REFUSED: no Chrome binary found; pass --chrome", file=sys.stderr)
        return 1
    if problems:
        print("REFUSED: inputs missing; run --check", file=sys.stderr)
        return 1

    slugs = sorted(PACK_KEYS) if args.all else ([args.slug] if args.slug else [])
    if not slugs:
        parser.error("pass --slug, --all or --check")
    for slug in slugs:
        cv_pdf, cover_pdf = build_slug(slug, chrome)
        print("built", cv_pdf.name, "and", cover_pdf.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
