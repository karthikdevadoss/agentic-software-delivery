"""Generate docs/NETWORK_INVENTORY.md: what every public page actually fetches.

    python agent/network_inventory.py

BL-R2. A FACTUAL inventory, read out of the capture manifests that
e2e/capture-pack.js already produces. It changes nothing and recommends nothing.

WHY IT IS WORTH HAVING SEPARATELY FROM THE GUARD.
e2e/third-party-network.spec.js asserts that the counts are zero. That is the
right shape for a gate and the wrong shape for a question like "what does this
site talk to?" -- a passing assertion tells you a number is zero and tells you
nothing about the seventy requests that are fine. This lists them by class so a
new one has to be looked at rather than arriving unnoticed.

Reads the manifests rather than driving a browser itself: the packs already hold a
full per-page request classification, and taking a third capture just to count the
same requests again would be waste.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parent.parent
PACKS = [
    ("BEFORE (production, before Sprint 17)", REPO / "visual-audit-sprint17-before"),
    ("AFTER (local sprint17 branch)", REPO / "visual-audit-sprint17-after"),
]
OUT = REPO / "docs" / "NETWORK_INVENTORY.md"


def load(pack: Path):
    m = pack / "manifest.json"
    if not m.exists():
        return None
    return json.loads(m.read_text(encoding="utf-8"))


def host_of(url: str) -> str:
    try:
        return urlparse(url).netloc or "(unparseable)"
    except ValueError:
        return "(unparseable)"


def main() -> int:
    lines = []
    w = lines.append

    w("# First-load network inventory")
    w("")
    w("**GENERATED FILE** — `python agent/network_inventory.py`, read out of the two")
    w("capture manifests. Facts only: it classifies what each public page actually")
    w("fetched on load and recommends nothing.")
    w("")
    w("## Classes")
    w("")
    w("| Class | Meaning | Acceptable? |")
    w("|---|---|---|")
    w("| same-origin | the application's own pages, assets and APIs | yes, this is the app working |")
    w("| third-party font | a typeface fetched from another host | **no** — asserted zero by `e2e/third-party-network.spec.js` |")
    w("| tracker / analytics | a known analytics, session-replay or ad host | **no** — asserted zero |")
    w("| other third-party | anything else off-origin | must be looked at; none exist today |")
    w("")
    w("An outbound LINK to GitHub or LinkedIn is not a request and does not appear")
    w("here. Only what the page actually fetches counts, which is why this is read from")
    w("real request events rather than from grepping the HTML for hostnames.")
    w("")

    for label, pack in PACKS:
        manifest = load(pack)
        w(f"## {label}")
        w("")
        if manifest is None:
            w(f"No manifest at `{pack.name}/manifest.json`. Take the pack with")
            w("`node e2e/capture-pack.js --out <dir> --base <url>` and re-run this.")
            w("")
            continue

        w(f"Base URL `{manifest['base_url']}`, captured {manifest['captured_utc']}, "
          f"{len(manifest['records'])} page/viewport records.")
        w("")
        w("| Page | same-origin | third-party font | tracker | other third-party |")
        w("|---|---|---|---|---|")

        seen_pages = []
        totals = Counter()
        hosts = Counter()
        for rec in manifest["records"]:
            # One row per PAGE, not per viewport: the request set does not depend
            # on the viewport, and three identical rows per page would bury the
            # one thing this table is for.
            if rec["page"] in seen_pages:
                continue
            seen_pages.append(rec["page"])
            nf = len(rec.get("thirdPartyFontRequests") or [])
            nt = len(rec.get("trackerRequests") or [])
            no = len(rec.get("otherThirdPartyRequests") or [])
            so = rec.get("sameOriginRequests") or 0
            totals.update({"same_origin": so, "font": nf, "tracker": nt, "other": no})
            for url in (rec.get("thirdPartyFontRequests") or []) + \
                       (rec.get("trackerRequests") or []) + \
                       (rec.get("otherThirdPartyRequests") or []):
                hosts[host_of(url)] += 1
            fmt = lambda n: f"**{n}**" if n else "0"  # noqa: E731
            w(f"| `{rec['route']}` | {so} | {fmt(nf)} | {fmt(nt)} | {fmt(no)} |")

        w(f"| **total (one row per page, not per viewport)** | **{totals['same_origin']}** "
          f"| **{totals['font']}** | **{totals['tracker']}** | **{totals['other']}** |")
        w("")
        if hosts:
            w("Third-party hosts contacted, with request counts:")
            w("")
            for host, count in hosts.most_common():
                w(f"- `{host}` — {count} request(s)")
            w("")
        else:
            w("**No third-party host was contacted by any page.** Every request on every")
            w("public surface was same-origin.")
            w("")

    w("## What changed, as a number")
    w("")
    before, after = load(PACKS[0][1]), load(PACKS[1][1])
    if before and after:
        def tot(manifest, field):
            return sum(len(r.get(field) or []) for r in manifest["records"])
        w("| | BEFORE | AFTER |")
        w("|---|---|---|")
        w(f"| third-party font requests | {tot(before, 'thirdPartyFontRequests')} "
          f"| {tot(after, 'thirdPartyFontRequests')} |")
        w(f"| tracker / analytics requests | {tot(before, 'trackerRequests')} "
          f"| {tot(after, 'trackerRequests')} |")
        w(f"| other third-party requests | {tot(before, 'otherThirdPartyRequests')} "
          f"| {tot(after, 'otherThirdPartyRequests')} |")
        w("")
        w("The figure above counts every RECORD, so a page captured at three viewports")
        w("contributes three times. Per unique page the BEFORE counts were 1 on Home and")
        w("Case Study and 3 on the other seven.")
        w("")
        w("What those requests actually were, read out of the manifest rather than assumed")
        w("(an earlier version of this paragraph guessed `preconnect` and was wrong):")
        w("")
        w("- **1 request** = the `fonts.googleapis.com/css2?...` stylesheet. Home and Case")
        w("  Study stopped there because neither page's CSS ever *used* any of the nine")
        w("  families it declares, so the browser had no face to download. They were")
        w("  paying a round trip for nothing.")
        w("- **3 requests** = that stylesheet plus two real `.woff2` font files from")
        w("  `fonts.gstatic.com` — on Workbench, `inter/v20/...woff2` and")
        w("  `sora/v17/...woff2`. Those are genuine typeface downloads blocking first")
        w("  paint.")
        w("")
        w("`preconnect` appears in the HTML and is not in these counts: it opens a")
        w("connection rather than fetching a resource, so it raises no request event.")
        w("Removing the `<link>` tags removed the preconnects too.")
        w("")
    w("## Known limitation")
    w("")
    w("This is **first load only**, with no interaction. A request a page makes after a")
    w("click, a form submission or a model-backed action is outside what these packs")
    w("captured, by design — the capture never interacts with anything. A page that")
    w("fetched a tracker only after a button press would not appear here, and nothing")
    w("currently checks for that.")
    w("")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
