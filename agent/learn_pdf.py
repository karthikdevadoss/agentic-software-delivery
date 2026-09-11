"""
Generates the downloadable "Learn" PDF book (P0-C) from the SAME
canonical recursive Learn knowledge model (agent/web/learn-tree.json,
loaded via agent/learn_tree.py) used by the interactive Learn UI. There
is exactly ONE knowledge source — this module never hand-authors PDF-only
content.

Library choice: reportlab. Justification (see docs/DECISIONS.md-style
reasoning inline rather than duplicated): reportlab is a mature (20+
years), pure-Python-installable library (precompiled wheels, no native
build step) that directly supports headings, a real auto-numbered Table
of Contents with resolved page numbers (via SimpleDocTemplate.multiBuild
+ the documented afterFlowable/bookmark pattern), and page breaks —
without needing an external binary or a heavy browser-rendering
dependency (e.g. WeasyPrint requires GTK/Cairo system libraries that are
fragile to install on Windows, which this project's dev machine is).

Caching: the generated PDF is cached in-process, keyed by the source
tree file's mtime plus its git_commit field, so a request never
regenerates an unchanged book, but a real content change (rerun
build_learn_tree.py) is picked up on the very next request — never
served stale silently (Section 43: version/freshness).
"""

import io
from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate, PageBreak, PageTemplate, Paragraph, Frame, Spacer,
)
from reportlab.platypus.tableofcontents import TableOfContents

import learn_tree

WEB_DIR = Path(__file__).resolve().parent / "web"

_cache = {"key": None, "pdf_bytes": None, "generated_at": None}

_SECTION_LABELS = [
    ("what", "WHAT"), ("why", "WHY"), ("how", "HOW"), ("when", "WHEN"),
    ("system_design", "SYSTEM DESIGN"), ("real_experience", "REAL EXPERIENCE"),
    ("development_steps", "DEVELOPMENT STEPS"), ("decisions", "DECISIONS"),
    ("alternatives", "ALTERNATIVES / TRADEOFFS"), ("testing", "TESTING"),
    ("failure_modes", "FAILURE MODES / LESSONS"), ("ai_role", "AI ROLE"),
    ("human_role", "HUMAN ROLE"), ("best_practices", "BEST PRACTICES"),
    ("evidence", "EVIDENCE"), ("real_incidents", "REAL INCIDENTS"),
]


def _esc(s) -> str:
    if s is None:
        return ""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


class _BookDocTemplate(BaseDocTemplate):
    """Standard reportlab pattern for a resolved-page-number TOC: detect
    heading flowables by style name in afterFlowable(), bookmark that
    exact page, and notify the TableOfContents flowable — resolved over
    a second build pass via multiBuild()."""

    def afterFlowable(self, flowable):
        if not isinstance(flowable, Paragraph):
            return
        style_name = flowable.style.name
        text = flowable.getPlainText()
        level = {"Domain": 0, "Topic": 1, "SubTopic": 2}.get(style_name)
        if level is not None:
            bookmark = f"bm-{id(flowable)}"
            self.canv.bookmarkPage(bookmark)
            self.notify("TOCEntry", (level, text, self.page, bookmark))


def _styles():
    ss = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("BookTitle", parent=ss["Title"], fontSize=26, alignment=TA_CENTER, spaceAfter=18),
        "meta": ParagraphStyle("BookMeta", parent=ss["Normal"], alignment=TA_CENTER, textColor="#555555"),
        "disclaimer": ParagraphStyle("Disclaimer", parent=ss["Normal"], fontSize=9, textColor="#666666", spaceBefore=24),
        "domain": ParagraphStyle("Domain", parent=ss["Heading1"], spaceBefore=18, spaceAfter=6),
        "topic": ParagraphStyle("Topic", parent=ss["Heading2"], spaceBefore=12, spaceAfter=4),
        "subtopic": ParagraphStyle("SubTopic", parent=ss["Heading3"], spaceBefore=8, spaceAfter=3),
        "section_label": ParagraphStyle("SectionLabel", parent=ss["Heading4"], fontSize=10, textColor="#333333", spaceBefore=6, spaceAfter=2),
        "body": ParagraphStyle("BookBody", parent=ss["BodyText"], spaceAfter=4),
        "list_item": ParagraphStyle("ListItem", parent=ss["BodyText"], leftIndent=14, spaceAfter=2),
        "toc_h1": ParagraphStyle("TOCHeading1", fontSize=12, leftIndent=0, spaceBefore=4),
        "toc_h2": ParagraphStyle("TOCHeading2", fontSize=10, leftIndent=14, spaceBefore=2),
        "toc_h3": ParagraphStyle("TOCHeading3", fontSize=9, leftIndent=28, spaceBefore=1, textColor="#555555"),
    }


_NODE_STYLE_BY_DEPTH = {0: "domain", 1: "topic"}  # depth >=2 -> subtopic


def _render_section_value(value, styles, story):
    if isinstance(value, list):
        for item in value:
            story.append(Paragraph(f"&bull; {_esc(item)}", styles["list_item"]))
    elif isinstance(value, dict):
        # interview sub-dict
        for k, v in value.items():
            if not v:
                continue
            story.append(Paragraph(f"<b>{_esc(k.replace('_', ' ').title())}:</b> {_esc(v)}", styles["body"]))
    else:
        story.append(Paragraph(_esc(value), styles["body"]))


def _render_node(node, depth, styles, story):
    style_key = _NODE_STYLE_BY_DEPTH.get(depth, "subtopic")
    story.append(Paragraph(_esc(node["title"]), styles[style_key]))

    overview = node.get("short_overview")
    if overview:
        story.append(Paragraph(_esc(overview), styles["body"]))

    cls = node.get("experience_classification")
    if cls:
        story.append(Paragraph(f"<i>Experience classification: {_esc(cls.replace('_', ' ').title())}</i>", styles["body"]))

    sections = node.get("sections") or {}
    for key, label in _SECTION_LABELS:
        if key in sections and sections[key]:
            story.append(Paragraph(label, styles["section_label"]))
            _render_section_value(sections[key], styles, story)

    interview = sections.get("interview")
    if interview:
        story.append(Paragraph("INTERVIEW PREPARATION", styles["section_label"]))
        _render_section_value(interview, styles, story)

    related = node.get("related")
    if related:
        story.append(Paragraph(f"<i>Related: {_esc(', '.join(related))}</i>", styles["body"]))

    for child in node.get("children") or []:
        _render_node(child, depth + 1, styles, story)


def _build_story(tree: dict, styles) -> list:
    story = []

    # Title page
    story.append(Spacer(1, 1.5 * inch))
    story.append(Paragraph("Agentic Software Delivery", styles["title"]))
    story.append(Paragraph("The Technical Wikipedia + Engineering Book", styles["title"]))
    story.append(Spacer(1, 0.3 * inch))
    generated_at = tree.get("generated_at_utc", "UNKNOWN")
    m = tree.get("metrics", {})
    story.append(Paragraph(f"Generated: {_esc(generated_at)}", styles["meta"]))
    story.append(Paragraph(f"Knowledge version (git commit): {_esc(tree.get('git_commit', 'UNKNOWN'))}", styles["meta"]))
    story.append(Paragraph(
        f"{m.get('total_domains', '?')} domains · {m.get('total_reference_topics', '?')} reference topics · "
        f"{m.get('total_deep_topics', '?')} deep evidence-backed topics",
        styles["meta"],
    ))
    story.append(Paragraph(
        "Experience-classification legend: CURRENT PROJECT EXPERIENCE (this project's own code/incidents), "
        "LEARNED / UNDERSTOOD (general, correct engineering knowledge, not claimed as personal professional "
        "experience), PLANNED / NOT EXPERIENCED (roadmap only).",
        styles["disclaimer"],
    ))
    story.append(Paragraph(
        "Disclaimer: professional-experience claims are evidence-backed. LEARNED/UNDERSTOOD topics are "
        "educational knowledge and are not represented as professional experience.",
        styles["disclaimer"],
    ))
    story.append(PageBreak())

    # Table of contents
    story.append(Paragraph("Table of Contents", styles["domain"]))
    toc = TableOfContents()
    toc.levelStyles = [styles["toc_h1"], styles["toc_h2"], styles["toc_h3"]]
    story.append(toc)
    story.append(PageBreak())

    for domain in tree["domains"]:
        _render_node(domain, 0, styles, story)
        story.append(PageBreak())

    return story


def generate_pdf_bytes() -> bytes:
    tree = learn_tree.load_tree()
    buf = io.BytesIO()
    doc = _BookDocTemplate(
        buf, pagesize=LETTER,
        title="Agentic Software Delivery — Learn Book",
        author="Agentic Software Delivery",
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame])])
    styles = _styles()
    story = _build_story(tree, styles)
    doc.multiBuild(story)
    return buf.getvalue()


def _cache_key():
    mtime = learn_tree.TREE_PATH.stat().st_mtime
    tree = learn_tree.load_tree()
    return (mtime, tree.get("git_commit"))


def get_or_generate_pdf():
    """Returns (pdf_bytes, generated_at_iso, is_freshly_generated).
    Regenerates only when the canonical tree's mtime or git_commit
    changes — never serves a stale book silently, never regenerates a
    large document on every page view when nothing changed."""
    key = _cache_key()
    if _cache["key"] == key and _cache["pdf_bytes"] is not None:
        return _cache["pdf_bytes"], _cache["generated_at"], False
    pdf_bytes = generate_pdf_bytes()
    generated_at = datetime.now(timezone.utc).isoformat()
    _cache.update(key=key, pdf_bytes=pdf_bytes, generated_at=generated_at)
    return pdf_bytes, generated_at, True
