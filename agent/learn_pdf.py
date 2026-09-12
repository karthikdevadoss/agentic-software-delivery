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
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate, PageBreak, PageTemplate, Paragraph, Frame, Spacer,
)
from reportlab.platypus.tableofcontents import TableOfContents

import learn_tree

WEB_DIR = Path(__file__).resolve().parent / "web"

_cache = {"key": None, "pdf_bytes": None, "generated_at": None}

# Legacy 15-section labels (existing reference/deep-dive catalog) plus the
# Master Interview Book V1's 17-part schema (P0_PROMPT.txt Section 3) --
# ONE rendering table for the ONE canonical tree, never a second PDF-only
# schema. Order here is deliberately the mandated reading order: WHY first,
# history/evolution, why-now, zoomed-out big picture, design intellect,
# zoomed-in mechanics (how exactly / low-level internals / who), the six
# knowledge lenses, failure/incident, alternatives, interview mode, and
# finally the dated 2026 status section -- kept last so timeless material
# is never crowded out by version trivia.
_SECTION_LABELS = [
    ("what", "WHAT"),
    ("why", "WHY"),
    ("history_evolution", "HISTORY & EVOLUTION"),
    ("why_now", "WHY NOW / WHEN"),
    ("how", "HOW"),
    ("when", "WHEN"),
    ("big_picture", "BIG-PICTURE SYSTEM DESIGN"),
    ("design_intellect", "DESIGN INTELLECT"),
    ("how_exactly", "HOW EXACTLY"),
    ("low_level_internals", "LOW-LEVEL INTERNALS"),
    ("who", "WHO"),
    ("industry", "INDUSTRY KNOWLEDGE"),
    ("business", "BUSINESS KNOWLEDGE"),
    ("product", "PRODUCT KNOWLEDGE"),
    ("cost_economics", "COST / ECONOMICS / PROFIT"),
    ("system_design", "SYSTEM DESIGN"),
    ("real_experience", "REAL EXPERIENCE"),
    ("development_steps", "DEVELOPMENT STEPS"),
    ("decisions", "DECISIONS"),
    ("failure_incident", "FAILURE / INCIDENT"),
    ("failure_modes", "FAILURE MODES / LESSONS"),
    ("alternatives_tradeoffs", "ALTERNATIVES / TRADE-OFFS"),
    ("alternatives", "ALTERNATIVES / TRADEOFFS"),
    ("testing", "TESTING"),
    ("scenario", "SCENARIO"),
    ("interview_mode", "INTERVIEW MODE"),
    ("ai_role", "AI ROLE"),
    ("human_role", "HUMAN ROLE"),
    ("best_practices", "BEST PRACTICES"),
    ("evidence", "EVIDENCE"),
    ("real_incidents", "REAL INCIDENTS"),
    ("current_status_2026", "CURRENT INDUSTRY STATUS — 2026"),
]

_INTERVIEW_MODE_LABELS = [
    ("sec_15", "15-SECOND ANSWER"), ("sec_30", "30-SECOND ANSWER"),
    ("min_2", "2-MINUTE ANSWER"), ("deep_technical", "DEEP TECHNICAL FOLLOW-UP"),
    ("system_design", "SYSTEM DESIGN FRAMING"), ("business_value", "BUSINESS-VALUE FRAMING"),
    ("incident_debugging", "INCIDENT-DEBUGGING FRAMING"),
]

_PRIORITY_LABEL = {
    "INTERVIEW_ESSENTIAL": "INTERVIEW ESSENTIAL",
    "IMPORTANT": "IMPORTANT",
    "MASTERY_DEPTH": "MASTERY DEPTH",
}

_CLASSIFICATION_LABEL = {
    "REAL_PROFESSIONAL_EXPERIENCE": "REAL PROFESSIONAL EXPERIENCE",
    "CURRENT_PROJECT_EXPERIENCE": "CURRENT PROJECT EXPERIENCE",
    "STUDY_SCENARIO": "STUDY SCENARIO",
    "LEARNED_UNDERSTOOD": "LEARNED / UNDERSTOOD",
    "PLANNED_NOT_EXPERIENCED": "PLANNED / NOT EXPERIENCED",
}


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
        "tag": ParagraphStyle("Tag", parent=ss["Normal"], fontSize=8, textColor="#555555", spaceAfter=3),
        "body": ParagraphStyle("BookBody", parent=ss["BodyText"], spaceAfter=4),
        "list_item": ParagraphStyle("ListItem", parent=ss["BodyText"], leftIndent=14, spaceAfter=2),
        "toc_h1": ParagraphStyle("TOCHeading1", fontSize=12, leftIndent=0, spaceBefore=4),
        "toc_h2": ParagraphStyle("TOCHeading2", fontSize=10, leftIndent=14, spaceBefore=2),
        "toc_h3": ParagraphStyle("TOCHeading3", fontSize=9, leftIndent=28, spaceBefore=1, textColor="#555555"),
    }


_NODE_STYLE_BY_DEPTH = {0: "domain", 1: "topic"}  # depth >=2 -> subtopic


def _render_section_value(value, styles, story, key=None):
    if key == "interview_mode" and isinstance(value, dict):
        for k, label in _INTERVIEW_MODE_LABELS:
            v = value.get(k)
            if v:
                story.append(Paragraph(f"<b>{_esc(label)}:</b> {_esc(v)}", styles["body"]))
        for fu in value.get("followups") or []:
            q, a = fu.get("q"), fu.get("a")
            if q:
                story.append(Paragraph(f"<b>Likely follow-up:</b> {_esc(q)}", styles["list_item"]))
            if a:
                story.append(Paragraph(f"<i>Strong answer:</i> {_esc(a)}", styles["list_item"]))
        return
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                _render_section_value(item, styles, story)
            else:
                story.append(Paragraph(f"• {_esc(item)}", styles["list_item"]))
    elif isinstance(value, dict):
        for k, v in value.items():
            if not v:
                continue
            story.append(Paragraph(f"<b>{_esc(k.replace('_', ' ').title())}:</b> {_esc(v)}", styles["body"]))
    else:
        story.append(Paragraph(_esc(value), styles["body"]))


def _render_node(node, depth, styles, story):
    style_key = _NODE_STYLE_BY_DEPTH.get(depth, "subtopic")
    story.append(Paragraph(_esc(node["title"]), styles[style_key]))

    tags = []
    priority = node.get("priority")
    if priority:
        tags.append(_PRIORITY_LABEL.get(priority, priority.replace("_", " ")))
    cls = node.get("experience_classification")
    if cls:
        tags.append(_CLASSIFICATION_LABEL.get(cls, cls.replace("_", " ").title()))
    if tags:
        story.append(Paragraph(f"<i>[{_esc(' | '.join(tags))}]</i>", styles["tag"]))

    overview = node.get("short_overview")
    if overview:
        story.append(Paragraph(_esc(overview), styles["body"]))

    sections = node.get("sections") or {}
    for key, label in _SECTION_LABELS:
        if key in sections and sections[key]:
            story.append(Paragraph(label, styles["section_label"]))
            _render_section_value(sections[key], styles, story, key=key)

    interview = sections.get("interview")
    if interview:
        story.append(Paragraph("INTERVIEW PREPARATION", styles["section_label"]))
        _render_section_value(interview, styles, story)

    related = node.get("related")
    if related:
        story.append(Paragraph(f"<i>Related: {_esc(', '.join(related))}</i>", styles["body"]))

    for child in node.get("children") or []:
        _render_node(child, depth + 1, styles, story)


def _collect_essential_topics(tree):
    """Depth-first walk collecting every INTERVIEW_ESSENTIAL node, paired
    with its owning top-level domain title, in tree order."""
    out = []
    for domain in tree["domains"]:
        def walk(n):
            if n.get("priority") == "INTERVIEW_ESSENTIAL":
                out.append((domain["title"], n["title"]))
            for c in n.get("children") or []:
                walk(c)
        walk(domain)
    return out


def _front_matter(tree, styles, story):
    essentials = _collect_essential_topics(tree)

    story.append(Paragraph("How to Use This Book", styles["domain"]))
    story.append(Paragraph(
        "This book is one printable view of a single canonical knowledge base — the same content that "
        "powers the interactive Learn section of this platform. It is organized by domain (Java, JVM, "
        "Spring, Databases, Distributed Systems, Security, Testing, Observability, Cloud/DevOps, System "
        "Design, Architecture & Delivery Leadership, and AI-Assisted Software Engineering), and within "
        "each domain, from broad reference coverage down to a smaller number of full deep-dive topics.",
        styles["body"],
    ))
    story.append(Paragraph(
        "Every deep-dive topic follows the same structure so it can be read the same way every time: "
        "WHY it exists, its HISTORY & EVOLUTION, WHY NOW it matters (and when it would be overkill), the "
        "BIG-PICTURE system design, the DESIGN INTELLECT behind it, HOW EXACTLY a request or requirement "
        "flows through every real actor involved, the LOW-LEVEL INTERNALS, WHO (which process/thread/"
        "service/human/AI) is responsible, the INDUSTRY / BUSINESS / PRODUCT / COST knowledge lenses, a "
        "realistic FAILURE / INCIDENT trace, ALTERNATIVES & TRADE-OFFS, an honest SCENARIO classification, "
        "an INTERVIEW MODE section with ready answers at several depths, and a dated CURRENT STATUS — 2026 "
        "section for anything that changes with the industry.",
        styles["body"],
    ))
    story.append(Paragraph("Print it, read it while walking, and come back to specific topics before an interview.", styles["body"]))
    story.append(PageBreak())

    story.append(Paragraph("Labels Used in This Book", styles["domain"]))
    story.append(Paragraph("<b>Priority labels</b> (how much interview weight a topic carries):", styles["body"]))
    for k, v in _PRIORITY_LABEL.items():
        story.append(Paragraph(f"• <b>{_esc(v)}</b>", styles["list_item"]))
    story.append(Paragraph("<b>Experience classification labels</b> (how a claim is evidenced — never fabricated):", styles["body"]))
    for k in ("REAL_PROFESSIONAL_EXPERIENCE", "CURRENT_PROJECT_EXPERIENCE", "STUDY_SCENARIO", "LEARNED_UNDERSTOOD", "PLANNED_NOT_EXPERIENCED"):
        v = _CLASSIFICATION_LABEL[k]
        story.append(Paragraph(f"• <b>{_esc(v)}</b>", styles["list_item"]))
    story.append(Paragraph(
        "REAL PROFESSIONAL EXPERIENCE is used only where real job/resume evidence supports it. CURRENT "
        "PROJECT EXPERIENCE is used only where this platform's own code/incidents genuinely demonstrate the "
        "concept. STUDY SCENARIO is a realistic, clearly-labeled interview-rehearsal hypothetical, never "
        "presented as something that actually happened. Nothing in this book claims professional experience "
        "beyond what is genuinely evidenced.",
        styles["disclaimer"],
    ))
    story.append(PageBreak())

    story.append(Paragraph("2-Day Priority Reading Path", styles["domain"]))
    story.append(Paragraph(
        "If you have about two days before interviews begin, read every INTERVIEW ESSENTIAL deep-dive topic "
        "below in order, then read the front matter of every domain for broad-map familiarity. This list is "
        f"generated from the same live priority labels in the book ({len(essentials)} topics).",
        styles["body"],
    ))
    last_domain = None
    for domain_title, topic_title in essentials:
        if domain_title != last_domain:
            story.append(Paragraph(_esc(domain_title), styles["toc_h2"]))
            last_domain = domain_title
        story.append(Paragraph(f"• {_esc(topic_title)}", styles["list_item"]))
    story.append(PageBreak())

    story.append(Paragraph("Fast Interview Revision Path (Day-Of)", styles["domain"]))
    story.append(Paragraph(
        "The morning of an interview, re-read only the INTERVIEW MODE section (15-second, 30-second, and "
        "2-minute answers) of each INTERVIEW ESSENTIAL topic above — skip straight to that section within "
        "each topic rather than re-reading the full deep-dive.",
        styles["body"],
    ))
    story.append(PageBreak())

    story.append(Paragraph("Domain Index", styles["domain"]))
    for domain in tree["domains"]:
        story.append(Paragraph(_esc(domain["title"]), styles["toc_h1"]))
    story.append(PageBreak())


def _build_story(tree: dict, styles) -> list:
    story = []

    # Title page
    story.append(Spacer(1, 1.2 * inch))
    story.append(Paragraph("Master Interview Book", styles["title"]))
    story.append(Paragraph("Senior/Staff Java Backend, System Design & AI-Assisted Software Delivery", styles["title"]))
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
        "Designed to work offline once downloaded, and to print cleanly on A4 paper.",
        styles["disclaimer"],
    ))
    story.append(PageBreak())

    _front_matter(tree, styles, story)

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


def _draw_footer(canvas, doc):
    """Page number in the bottom margin -- A4, grayscale-safe, printable."""
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor("#666666")
    canvas.drawCentredString(doc.pagesize[0] / 2.0, 0.4 * inch, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


def generate_pdf_bytes() -> bytes:
    tree = learn_tree.load_tree()
    buf = io.BytesIO()
    doc = _BookDocTemplate(
        buf, pagesize=A4,
        title="Master Interview Book — Senior Java Backend, System Design & AI-Assisted Delivery",
        author="Agentic Software Delivery",
        topMargin=0.85 * inch, bottomMargin=0.85 * inch,
        leftMargin=0.85 * inch, rightMargin=0.85 * inch,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=_draw_footer)])
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
