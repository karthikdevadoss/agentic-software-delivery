"""Build a LOCAL side-by-side BEFORE|AFTER contact sheet for Owner review.

    python agent/build_review_contact_sheet.py
    # then open visual-audit-sprint17-review.html

BL-R4. This exists only to make the Owner's review faster. It is not a gate, it
scores nothing, and it states no aesthetic opinion -- comparing 36 screenshots by
opening 36 files in a viewer is the friction it removes, and that is its whole job.

WHY A LOCAL FILE AND NOT A PUBLISHED PAGE. It references the PNGs by relative path
rather than embedding them, so the whole thing stays a few kilobytes and stays on
the laptop. The two packs are untracked working-tree artefacts; nothing here
uploads, publishes or transmits anything.

WHAT IT DELIBERATELY DOES NOT DO
  * It does not resize or crop. A screenshot scaled to fit a column and then
    judged is a judgement about the scaled image, so each pane is scrollable at
    its natural width and a click opens the file itself at full size.
  * It does not mark anything improved, regressed, better or worse. The numbers
    next to each pair are the measurements from the manifests; the reading of them
    is the Owner's.
  * It does not hide a page because its numbers look bad.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BEFORE = REPO / "visual-audit-sprint17-before"
AFTER = REPO / "visual-audit-sprint17-after"
OUT = REPO / "visual-audit-sprint17-review.html"


def load(pack: Path) -> dict:
    m = pack / "manifest.json"
    if not m.exists():
        raise SystemExit(f"missing {m} -- take the pack first with e2e/capture-pack.js")
    return json.loads(m.read_text(encoding="utf-8"))


def esc(v) -> str:
    return html.escape(str(v), quote=True)


def facts(rec) -> str:
    """The measurements for one record, as plain labelled values."""
    if rec is None:
        return '<span class="na">no record</span>'
    bits = []
    bits.append(f"HTTP {esc(rec.get('status'))}")
    ov = rec.get("overflow")
    if ov:
        bits.append(
            f"<span class='{'bad' if ov['overflows'] else 'ok'}'>"
            f"{'overflow' if ov['overflows'] else 'no overflow'} "
            f"{ov['scrollWidth']}/{ov['clientWidth']}</span>"
        )
        bits.append(f"height {ov['scrollHeight']}px")
    pc = rec.get("primaryControl")
    bits.append(f"primary y={pc['y']}" if pc else "<span class='na'>primary not detected</span>")
    nf = len(rec.get("thirdPartyFontRequests") or [])
    bits.append(f"<span class='{'bad' if nf else 'ok'}'>{nf} third-party font req</span>")
    nt = len(rec.get("trackerRequests") or [])
    if nt:
        bits.append(f"<span class='bad'>{nt} tracker req</span>")
    ce = len(rec.get("consoleErrors") or [])
    bits.append(f"<span class='{'bad' if ce else 'ok'}'>{ce} console err</span>")
    return " · ".join(bits)


def main() -> int:
    before, after = load(BEFORE), load(AFTER)
    b = {(r["page"], r["viewport"]): r for r in before["records"]}
    a = {(r["page"], r["viewport"]): r for r in after["records"]}

    pages = [p["name"] for p in after["pages"]]
    routes = {p["name"]: p["route"] for p in after["pages"]}
    # Only viewports that actually produced an image; the 1920x940 pass is
    # geometry-only by design.
    shot_viewports = [v["label"] for v in after["viewports"] if v.get("screenshot")]

    parts = []
    w = parts.append

    w("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
    w("<title>Sprint 17 — BEFORE | AFTER review sheet</title>")
    w("""<style>
  :root {
    --ink:#14161a; --soft:#545a62; --line:#dcdfe3; --paper:#fbfaf8; --card:#fff;
    --accent:#1f4d3d; --bad:#a4262c; --okc:#1f6f4a;
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--paper); color:var(--ink);
         font:16px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; }
  .wrap { max-width:1760px; margin:0 auto; padding:0 24px 80px; }
  header { padding:40px 0 8px; }
  h1 { font-size:30px; letter-spacing:-.02em; margin:0 0 10px; }
  .lede { color:var(--soft); max-width:74ch; margin:0 0 6px; }
  .warn { border-left:3px solid var(--accent); padding:10px 0 10px 14px;
          margin:18px 0 0; max-width:82ch; color:var(--soft); }
  nav.toc { margin:26px 0 10px; display:flex; flex-wrap:wrap; gap:14px; }
  nav.toc a { color:var(--accent); font-weight:600; font-size:15px; text-decoration:none; }
  nav.toc a:hover { text-decoration:underline; }
  h2 { font-size:21px; margin:52px 0 4px; letter-spacing:-.01em; }
  h2 code { font-size:17px; color:var(--soft); font-weight:400; }
  h3 { font-size:14px; text-transform:uppercase; letter-spacing:.08em;
       color:var(--soft); margin:26px 0 10px; }
  .pair { display:grid; grid-template-columns:1fr 1fr; gap:18px; align-items:start; }
  .pane { background:var(--card); border:1px solid var(--line); min-width:0; }
  .pane > figcaption { padding:10px 14px; border-bottom:1px solid var(--line);
                       font-size:13.5px; color:var(--soft); }
  .pane > figcaption b { color:var(--ink); font-size:14.5px; }
  .shot { max-height:620px; overflow:auto; background:#0b0d12; }
  .shot img { display:block; width:100%; height:auto; }
  .meta { padding:9px 14px; font-size:13px; color:var(--soft);
          border-top:1px solid var(--line); }
  .ok { color:var(--okc); } .bad { color:var(--bad); font-weight:600; }
  .na { color:var(--soft); font-style:italic; }
  a.full { display:inline-block; margin:8px 14px 12px; font-size:13px;
           color:var(--accent); font-weight:600; }
  @media (max-width:1100px) { .pair { grid-template-columns:1fr; } }
</style></head><body><div class='wrap'>""")

    w("<header><h1>Sprint 17 — BEFORE | AFTER review sheet</h1>")
    w("<p class='lede'>Every public surface, left as it is in production right now, "
      "right as it is on the local <code>sprint17-recruiter-ux-testing</code> branch. "
      "Each pane scrolls at the screenshot's natural width; the link under it opens "
      "the full file.</p>")
    w("<div class='warn'><b>This sheet makes no aesthetic claim.</b> The values under "
      "each pane are measurements read out of the two capture manifests. Whether the "
      "pages look good is the one question it does not answer and the one that "
      "matters — Sprint 15 shipped 67 green UI guards on pages you opened and "
      "disliked, Sprint 16 shipped 86, and none of them measured that.</div>")
    w(f"<div class='warn'><b>One thing that is not comparable.</b> BEFORE is production; "
      f"AFTER is this laptop. <code>/usage</code> and <code>/dashboard</code> render "
      f"real accumulated history, and this machine holds 511 session rows to "
      f"production's 2 — so their heights differ by roughly ten times for reasons "
      f"that have nothing to do with layout. Read those two as environment.</div>")
    w(f"<p class='lede' style='margin-top:18px'>BEFORE <code>{esc(before['base_url'])}</code> "
      f"captured {esc(before['captured_utc'])} · AFTER <code>{esc(after['base_url'])}</code> "
      f"captured {esc(after['captured_utc'])} · model calls "
      f"{before['model_calls']}/{after['model_calls']} · {esc(after['interaction'])}</p>")

    w("<nav class='toc'>")
    for page in pages:
        w(f"<a href='#{esc(page)}'>{esc(page)}</a>")
    w("</nav></header>")

    for page in pages:
        w(f"<h2 id='{esc(page)}'>{esc(page)} <code>{esc(routes[page])}</code></h2>")
        for vp in shot_viewports:
            rb, ra = b.get((page, vp)), a.get((page, vp))
            w(f"<h3>{esc(vp)}</h3><div class='pair'>")
            for label, rec, pack in (("BEFORE — production", rb, BEFORE),
                                     ("AFTER — local branch", ra, AFTER)):
                w("<figure class='pane' style='margin:0'>")
                w(f"<figcaption><b>{esc(label)}</b></figcaption>")
                if rec and rec.get("file"):
                    src = f"{pack.name}/{rec['file']}"
                    w(f"<div class='shot'><img loading='lazy' src='{esc(src)}' "
                      f"alt='{esc(page)} at {esc(vp)}, {esc(label)}'></div>")
                    w(f"<a class='full' href='{esc(src)}' target='_blank' "
                      f"rel='noopener'>open full size ↗</a>")
                else:
                    w("<div class='shot' style='padding:28px;color:#8b93a7'>"
                      "no screenshot in this pack</div>")
                w(f"<div class='meta'>{facts(rec)}</div>")
                w("</figure>")
            w("</div>")

    w("<h2>Where the rest of the evidence is</h2><ul>")
    w("<li><code>docs/FIRST_SCREEN_REVIEW.md</code> — the same measurements as tables, "
      "including the 1920×940 geometry pass that takes no screenshot</li>")
    w("<li><code>docs/SPRINT17_APPROVAL_STORY.md</code> — the approval audit, with file "
      "and line references</li>")
    w("<li><code>docs/DESIGN.md</code> — the design lock, and the Sprint 16 reversal it "
      "contains</li>")
    w("<li><code>docs/OWNER_DECISIONS_PENDING.md</code> — six things waiting on you</li>")
    w("</ul>")

    w("</div></body></html>")

    OUT.write_text("\n".join(parts), encoding="utf-8")
    pairs = len(pages) * len(shot_viewports)
    print(f"wrote {OUT.name} — {pairs} before/after pairs across "
          f"{len(pages)} surfaces and {len(shot_viewports)} viewports")
    print(f"open it with: start {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
