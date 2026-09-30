"""Generate docs/FIRST_SCREEN_REVIEW.md from the two real capture manifests.

    python agent/first_screen_review.py

FACTS ONLY, AND NO AESTHETIC VERDICT. Every cell in the tables below is read out
of visual-audit-sprint17-{before,after}/manifest.json, which were produced by
e2e/capture-pack.js against a real running server. Nothing here is judged, scored
or graded -- not "improved", not "better", not "world class". Where a number got
smaller the number is shown getting smaller, and what that means for how the page
LOOKS is the Owner's call and nobody else's.

It is a generator rather than a hand-written document for one reason: a
hand-written table drifts from the manifests the moment either pack is re-taken,
and then the review document and the screenshots disagree about what was
measured. Re-run this after re-taking either pack.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BEFORE = REPO / "visual-audit-sprint17-before"
AFTER = REPO / "visual-audit-sprint17-after"
OUT = REPO / "docs" / "FIRST_SCREEN_REVIEW.md"


def load(pack: Path) -> dict:
    manifest = pack / "manifest.json"
    if not manifest.exists():
        raise SystemExit(
            f"missing {manifest}. Produce it with:\n"
            f"  node e2e/capture-pack.js --out {pack.name} --base <url>"
        )
    return json.loads(manifest.read_text(encoding="utf-8"))


def key(rec: dict) -> tuple:
    return (rec["page"], rec["viewport"])


def yes_no(value) -> str:
    if value is None:
        return "n/a"
    return "YES" if value else "no"


def main() -> int:
    before = load(BEFORE)
    after = load(AFTER)
    b = {key(r): r for r in before["records"]}
    a = {key(r): r for r in after["records"]}

    pages = [p["name"] for p in after["pages"]]
    viewports = [v["label"] for v in after["viewports"]]

    lines = []
    w = lines.append

    w("# First-screen review — Sprint 17")
    w("")
    w("**GENERATED FILE.** Produced by `python agent/first_screen_review.py` from the")
    w("two real capture manifests. Do not hand-edit: re-run it after re-taking either")
    w("pack, or the tables and the screenshots will disagree about what was measured.")
    w("")
    w("## What the Owner is being asked to do")
    w("")
    w("Look at the screenshots and say whether the pages look good. That is the one")
    w("question this document deliberately does not answer, and the one question that")
    w("matters. Sprint 15 shipped 67 green UI guards on pages you opened and disliked;")
    w("Sprint 16 shipped 86. Every guard was right about what it measured, and not one")
    w("of them measured whether a page is pleasant to look at. Nothing in Sprint 17")
    w("changes that, and this session does not certify it.")
    w("")
    w("## How the two packs were produced")
    w("")
    w("| | BEFORE | AFTER |")
    w("|---|---|---|")
    w(f"| Base URL | `{before['base_url']}` | `{after['base_url']}` |")
    w(f"| Captured (UTC) | {before['captured_utc']} | {after['captured_utc']} |")
    w(f"| Folder | `{BEFORE.name}/` | `{AFTER.name}/` |")
    w(f"| Records | {len(before['records'])} | {len(after['records'])} |")
    w(f"| Screenshots | {sum(1 for r in before['records'] if r.get('file'))} "
      f"| {sum(1 for r in after['records'] if r.get('file'))} |")
    w(f"| Model calls | {before['model_calls']} | {after['model_calls']} |")
    w("")
    w(f"Interaction, both packs: {after['interaction']}")
    w("")
    w("### One thing that is NOT comparable between the packs, stated up front")
    w("")
    w("BEFORE is **production**; AFTER is **this laptop**. For every page whose length")
    w("is fixed by its content that makes no difference. For `/usage` and `/dashboard`")
    w("it makes a large one, because both render real accumulated history and the two")
    w("environments hold very different amounts of it:")
    w("")
    w("| Page | BEFORE (production) | AFTER (this laptop) | Why |")
    w("|---|---|---|---|")
    for page in ("usage", "dashboard"):
        rb, ra = b.get((page, "desktop-1920")), a.get((page, "desktop-1920"))
        hb = rb["overflow"]["scrollHeight"] if rb and rb.get("overflow") else "n/a"
        ha = ra["overflow"]["scrollHeight"] if ra and ra.get("overflow") else "n/a"
        w(f"| `/{page}` desktop height | {hb}px | {ha}px | real session/history rows, "
          f"not a layout change |")
    w("")
    w("Measured directly: `/usage` renders **2** session rows against production and")
    w("**511** against this machine. The page is not ten times longer because anything")
    w("changed; it is ten times longer because this laptop has a year of its own")
    w("development history in it. Read those two heights as environment, not as")
    w("regression.")
    w("")

    # ---------------- per-surface factual table ----------------
    w("## Per-surface measurements")
    w("")
    w("`overflow` is `document.documentElement.scrollWidth > clientWidth + 1`.")
    w("`primary Y` is the document-space Y of the first visible, interactive,")
    w("non-navigation control -- the thing a recruiter would click. `3p fonts` counts")
    w("real requests to a third-party font host on load.")
    w("")
    for page in pages:
        route = next(p["route"] for p in after["pages"] if p["name"] == page)
        w(f"### `{route}`")
        w("")
        w("| Viewport | BEFORE file | AFTER file | HTTP | overflow B→A | primary Y B→A "
          "| console errors B→A | 3p fonts B→A | trackers B→A |")
        w("|---|---|---|---|---|---|---|---|---|")
        for vp in viewports:
            rb, ra = b.get((page, vp)), a.get((page, vp))
            if ra is None:
                continue
            fb = f"`{rb['file']}`" if rb and rb.get("file") else "—"
            fa = f"`{ra['file']}`" if ra.get("file") else "—"
            status = f"{rb['status'] if rb else 'n/a'} → {ra['status']}"

            def ov(r):
                if not r or not r.get("overflow"):
                    return "n/a"
                o = r["overflow"]
                return f"{'YES' if o['overflows'] else 'no'} ({o['scrollWidth']}/{o['clientWidth']})"

            def py(r):
                if not r or not r.get("primaryControl"):
                    return "not detected"
                return str(r["primaryControl"]["y"])

            def n(r, field):
                return "n/a" if not r else str(len(r.get(field) or []))

            w(f"| {vp} | {fb} | {fa} | {status} "
              f"| {ov(rb)} → {ov(ra)} "
              f"| {py(rb)} → {py(ra)} "
              f"| {n(rb, 'consoleErrors')} → {n(ra, 'consoleErrors')} "
              f"| {n(rb, 'thirdPartyFontRequests')} → {n(ra, 'thirdPartyFontRequests')} "
              f"| {n(rb, 'trackerRequests')} → {n(ra, 'trackerRequests')} |")
        w("")

    # ---------------- totals ----------------
    def total(pack, field):
        return sum(len(r.get(field) or []) for r in pack["records"])

    def overflow_count(pack):
        return sum(1 for r in pack["records"]
                   if r.get("overflow") and r["overflow"]["overflows"])

    w("## Totals across all records")
    w("")
    w("| Measurement | BEFORE | AFTER |")
    w("|---|---|---|")
    w(f"| Records with horizontal overflow | {overflow_count(before)} | {overflow_count(after)} |")
    w(f"| Third-party font requests | {total(before, 'thirdPartyFontRequests')} "
      f"| {total(after, 'thirdPartyFontRequests')} |")
    w(f"| Tracker/analytics requests | {total(before, 'trackerRequests')} "
      f"| {total(after, 'trackerRequests')} |")
    w(f"| Other third-party requests | {total(before, 'otherThirdPartyRequests')} "
      f"| {total(after, 'otherThirdPartyRequests')} |")
    w(f"| Console errors | {total(before, 'consoleErrors')} | {total(after, 'consoleErrors')} |")
    w(f"| Uncaught page errors | {total(before, 'pageErrors')} | {total(after, 'pageErrors')} |")
    w(f"| Non-200 responses | "
      f"{sum(1 for r in before['records'] if r['status'] != 200)} | "
      f"{sum(1 for r in after['records'] if r['status'] != 200)} |")
    w("")

    # ---------------- primary control against the stated band ----------------
    w("## Primary control against the brief's 700–800px band")
    w("")
    w("The brief asked that, for an interactive recruiter destination, the primary next")
    w("action sit within roughly the first 700–800 desktop pixels. This table reports")
    w("the measurement and nothing else; where a page is over, it is shown as over.")
    w("")
    w("| Page | BEFORE | AFTER | Within 800px? |")
    w("|---|---|---|---|")
    for page in pages:
        rb, ra = b.get((page, "desktop-1920")), a.get((page, "desktop-1920"))
        yb = rb["primaryControl"]["y"] if rb and rb.get("primaryControl") else None
        ya = ra["primaryControl"]["y"] if ra and ra.get("primaryControl") else None
        verdict = "n/a" if ya is None else ("yes" if ya <= 800 else "NO")
        w(f"| `{page}` | {yb if yb is not None else 'not detected'} "
          f"| {ya if ya is not None else 'not detected'} | {verdict} |")
    w("")
    w("Two entries need their own explanation rather than being left to look like gaps:")
    w("")
    w("- **`usage`** is a report, not an interactive destination. Its first *control* is")
    w("  a LOAD MORE button far down the page, so this measurement answers the wrong")
    w("  question for it. The right one is where the numbers are: measured separately,")
    w("  its four cost metrics sit at y=586 and its not-NRG scope sentence at y=219,")
    w("  both inside the first screen.")
    w("- **`case-study`** has no primary action by design -- it is a document to read.")
    w("  It also has no `<main>` landmark, which is a real screen-reader defect")
    w("  independent of this sprint and is recorded as backlog rather than fixed here.")
    w("")

    w("## Files")
    w("")
    w(f"- BEFORE pack: `{BEFORE.name}/` (production, read-only)")
    w(f"- AFTER pack: `{AFTER.name}/` (local sprint branch)")
    w("- Approval-story audit: `docs/SPRINT17_APPROVAL_STORY.md`")
    w("- Design lock, including the Sprint 16 reversal: `docs/DESIGN.md`")
    w("- Testing architecture: `docs/TESTING.md`")
    w("- Decisions waiting on the Owner: `docs/OWNER_DECISIONS_PENDING.md`")
    w("")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)} from {len(before['records'])} BEFORE "
          f"and {len(after['records'])} AFTER records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
