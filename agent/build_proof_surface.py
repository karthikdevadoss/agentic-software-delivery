"""Render the public proof surface from the registry, so the pages cannot drift.

WHY GENERATE RATHER THAN HAND-WRITE
Before this, the home page's evidence rows were hand-written HTML: a status
label, a claim and a link, maintained by remembering to. There was no machine
link between what the page said and what docs/PORTFOLIO_CAPABILITIES.yaml
recorded, so the page could claim a capability was live after its evidence had
moved -- and nothing would notice. (It had already half-happened: four of the
recorded evidence paths pointed at files that no longer existed at those paths,
found by agent/proof_registry.py on its first run.)

So the registry is the single source of truth and the pages are rendered from
it. A claim that is not in the registry cannot appear on the page, and a claim
in the registry cannot appear above the verification level recorded for it,
because agent/proof_registry.py refuses the surface first.

TWO MODES, AND WHY --check IS THE IMPORTANT ONE
    --write   regenerate agent/web/proof.html and the generated block inside
              agent/web/home.html
    --check   regenerate IN MEMORY and compare against what is on disk; exit
              non-zero on any difference, printing it

`--check` is what runs in the test suite. It means a hand-edit to the generated
HTML is a build failure rather than a silent fork, which is the whole point:
generation only prevents drift if regenerating is enforced.

WHAT IS NOT GENERATED
Everything else on those pages -- the hero, the positioning, the scope
boundaries, the audience intros, the layout, the CSS. This writes the
claim/status/evidence/limitation block and the evidence index body, and nothing
else. The generated region is fenced by explicit markers.
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

import proof_registry as pr

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = REPO_ROOT / "agent" / "web"
HOME_PATH = WEB_DIR / "home.html"
PROOF_PATH = WEB_DIR / "proof.html"

START = "<!-- GENERATED:proof-rows:start -- do not hand-edit; run agent/build_proof_surface.py -->"
END = "<!-- GENERATED:proof-rows:end -->"

GENERATED_BANNER = (
    "<!-- GENERATED FILE -- do not hand-edit.\n"
    "     Rendered from docs/PUBLIC_PROOF_SURFACE.yaml and\n"
    "     docs/PORTFOLIO_CAPABILITIES.yaml by agent/build_proof_surface.py.\n"
    "     Every claim below is refused by agent/proof_registry.py unless it has a\n"
    "     status within its recorded verification level, a stated limitation and at\n"
    "     least one destination that resolves to a real route or an absolute URL.\n"
    "     Hand-editing this file makes the test suite fail by design. -->"
)


def esc(text: str) -> str:
    return html.escape(" ".join(str(text).split()), quote=True)


def _status_label(surface: dict, status: str) -> str:
    return (surface["status_vocabulary"].get(status) or {}).get("label", status)


def _status_class(status: str) -> str:
    return "st-" + status.lower().replace("_", "-")


# --------------------------------------------------------------------------
# The home page's generated evidence rows.
# Markup deliberately reuses the existing .ev / .erow / .estat / .side classes
# -- this is a data-driven rewrite of a block that already existed and already
# looked the way the Owner accepted, not a redesign of it. The one genuinely
# new element is the per-row limitation, which the mission requires.
# --------------------------------------------------------------------------
def render_home_rows(surface: dict, entries: list[dict]) -> str:
    lines = [START, '  <div class="ev">']
    for entry in entries:
        status = entry["public_status"]
        lines.append("")
        lines.append('    <div class="erow">')
        lines.append("      <div>")
        lines.append(
            f'        <p class="estat {_status_class(status)}">{esc(_status_label(surface, status))}</p>'
        )
        lines.append(f'        <h3>{esc(entry["headline"])}</h3>')
        lines.append(f'        <p>{esc(entry["public_claim"])}</p>')
        lines.append(
            f'        <p class="elimit"><b>Limitation:</b> {esc(entry["public_limitation"])}</p>'
        )
        lines.append("      </div>")
        lines.append('      <div class="side">')
        for destination in entry["destinations"]:
            lines.append(
                f'        <a href="{esc(destination["href"])}">{esc(destination["label"])} &rarr;</a>'
            )
        lines.append("      </div>")
        lines.append("    </div>")
    lines.append("")
    lines.append("  </div>")
    lines.append(END)
    return "\n".join(lines)


# --------------------------------------------------------------------------
# The evidence index at /proof.
# --------------------------------------------------------------------------
PROOF_CSS = """\
  :root {
    --prose: 58ch;
    --ink: #14161a;
    --soft: #545a62;
    --line: #dcdfe3;
    --paper: #fbfaf8;
    --card: #ffffff;
    --accent: #1f4d3d;
    --accent-ink: #123026;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--paper); color: var(--ink);
    font: 17px/1.62 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
  }
  .wrap { max-width: 1200px; margin: 0 auto; padding: 0 32px; }
  p, li, dd { max-width: var(--prose); }
  .routes, .routes > *, .cap, .cap > *, .caphead, .dests { max-width: none; }
  a { color: var(--accent); }
  a:focus-visible { outline: 3px solid var(--accent); outline-offset: 3px; }

  .top-nav {
    display: flex; flex-wrap: wrap; row-gap: .5rem; gap: 1.2rem; align-items: center;
    padding: 18px 32px; max-width: 1200px; margin: 0 auto;
  }
  .top-nav a { color: var(--soft); text-decoration: none; font-size: .88rem; font-weight: 600;
               padding-bottom: .15rem; border-bottom: 2px solid transparent; }
  .top-nav a:hover { color: var(--ink); }
  .top-nav a strong { color: var(--accent); border-bottom: 2px solid var(--accent);
                      padding-bottom: .15rem; font-weight: 700; }
  .navwrap { border-bottom: 1px solid var(--line); }

  header { padding: 52px 0 6px; }
  h1 { font-size: clamp(30px, 5.6vw, 38px); line-height: 1.12; letter-spacing: -.025em;
       margin: 0 0 10px; font-weight: 660; }
  .lede { font-size: 1.03rem; color: var(--soft); margin: 0 0 18px; }
  h2.sec { font-size: 1.02rem; text-transform: uppercase; letter-spacing: .09em;
           color: var(--soft); font-weight: 700; margin: 46px 0 14px;
           padding-bottom: 8px; border-bottom: 1px solid var(--line); }

  /* How to read a status. A legend, because four labels mean nothing unless
     the page says what they mean. */
  .legend { display: grid; gap: 10px; margin: 0 0 8px; padding: 0; list-style: none; }
  .legend li { display: grid; grid-template-columns: 170px 1fr; gap: 14px;
               align-items: start; max-width: none; }
  .legend .nm { font-size: .72rem; font-weight: 700; letter-spacing: .07em;
                text-transform: uppercase; padding: 3px 0; }
  .legend .ds { color: var(--soft); font-size: .95rem; }

  /* Audience routes. One identity, three reading orders. */
  .routes { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin: 0 0 6px; }
  .route { background: var(--card); border: 1px solid var(--line); border-radius: 10px;
           padding: 18px 18px 14px; }
  .route h3 { margin: 0 0 6px; font-size: 1rem; }
  .route p { color: var(--soft); font-size: .93rem; margin: 0 0 10px; max-width: none; }
  .route ol { margin: 0; padding-left: 1.2rem; font-size: .93rem; }
  .route li { margin-bottom: 4px; max-width: none; }

  /* One capability. */
  .cap { background: var(--card); border: 1px solid var(--line); border-radius: 10px;
         padding: 20px 22px; margin-bottom: 14px; }
  .caphead { display: flex; flex-wrap: wrap; gap: 10px; align-items: baseline;
             justify-content: space-between; margin-bottom: 8px; }
  .cap h3 { margin: 0; font-size: 1.08rem; letter-spacing: -.01em; }
  .cap .claim { margin: 0 0 10px; }
  .cap dl { margin: 0; }
  .cap dt { font-size: .72rem; text-transform: uppercase; letter-spacing: .07em;
            color: var(--soft); font-weight: 700; margin-top: 10px; }
  .cap dd { margin: 3px 0 0; font-size: .95rem; }
  .cap .cid { font-size: .78rem; color: var(--soft); }
  /* Sprint 18: measured, not guessed. The first capture of this page reported
     scrollWidth 753 against clientWidth 390 at mobile-390 -- real horizontal
     overflow. The cause is the source paths rendered in <code>: a 70-character
     path contains no spaces, and the default overflow-wrap:normal refuses to
     break inside a word, so one path set the width of the whole document.
     Breaking anywhere is correct for a path; min-width:0 is needed because a
     grid/flex child's automatic minimum size is its content, which otherwise
     silently re-widens the column no matter what the text is allowed to do. */
  .cap code { font-size: .82rem; background: #f1efec; padding: 1px 5px; border-radius: 4px;
              overflow-wrap: anywhere; }
  .cap, .cap dl, .cap dd, .cap dt, .caphead, .legend li, .route { min-width: 0; }
  .cap dd, .cap .claim, .dests a, .legend .ds { overflow-wrap: anywhere; }
  .dests { display: flex; flex-wrap: wrap; gap: 14px; margin-top: 4px; }
  .dests a { font-size: .93rem; font-weight: 600; text-decoration: none; }
  .dests a:hover { text-decoration: underline; }

  /* The status pill. Experimental/paused is deliberately the one that does not
     look like an achievement. */
  .pill { font-size: .68rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase;
          padding: 4px 9px; border-radius: 999px; white-space: nowrap; border: 1px solid; }
  .st-live-verified       { color: #14503c; background: #e8f3ee; border-color: #bcdccd; }
  .st-tested-verified     { color: #1f4160; background: #e9f0f6; border-color: #c3d6e5; }
  .st-documented          { color: #4a4336; background: #f4f0e7; border-color: #ddd4c2; }
  .st-experimental-paused { color: #6b4a12; background: #f8f1e3; border-color: #e3d0ab; }

  .note { background: #f4f2ef; border: 1px solid var(--line); border-left: 3px solid var(--accent);
          border-radius: 8px; padding: 16px 18px; margin: 0 0 8px; }
  .note p { margin: 0 0 8px; }
  .note p:last-child { margin: 0; }

  footer { margin: 56px 0 40px; padding-top: 18px; border-top: 1px solid var(--line);
           color: var(--soft); font-size: .88rem; }
  .btn { display: inline-block; background: var(--accent); color: #fff; text-decoration: none;
         font-weight: 650; padding: 11px 18px; border-radius: 8px; font-size: .95rem; }

  @media (max-width: 860px) {
    .routes { grid-template-columns: 1fr; }
  }
  @media (max-width: 560px) {
    .wrap { padding: 0 20px; }
    header { padding-top: 34px; }
    .legend li { grid-template-columns: 1fr; gap: 2px; }
    .caphead { gap: 6px; }
  }
"""

# The reading order each audience is given. Order matters more than content
# here: it is the one editorial decision on the page, and it is deliberately
# NOT generated from the registry, because "what should this person read
# first" is a judgement, not a data property.
ROUTE_ORDERS = {
    "recruiter": [
        "Start with the three proof points on the home page.",
        "Open one live thing — the Workbench, or the running Java application.",
        "Read the limitation under any claim that matters to you.",
    ],
    "ai_hiring_manager": [
        "The write boundary: an agent with no code path to approve itself.",
        "The durable workflow case study, including where the crash drill stops.",
        "Retrieval with a measured evaluation gate, and the model kill switch.",
        "The paused experiment — what it falsified, and why it was stopped.",
    ],
    "backend_interviewer": [
        "Open the running Java/Spring application.",
        "The schema migrations and the real-PostgreSQL CI run.",
        "The multi-service decomposition and its real-topology test tier.",
        "The durable workflow's Postgres checkpointing.",
    ],
}


def render_proof_page(surface: dict, capabilities: dict) -> str:
    entries = surface["capabilities"]
    primary = [e for e in entries if e["tier"] == "PRIMARY"]
    secondary = [e for e in entries if e["tier"] == "SECONDARY"]

    out: list[str] = []
    a = out.append

    a("<!DOCTYPE html>")
    a('<html lang="en">')
    a("<head>")
    a('<meta charset="utf-8">')
    a('<meta name="viewport" content="width=device-width, initial-scale=1">')
    a("<title>Evidence index &mdash; Karthikeyan Devadoss</title>")
    a('<meta name="description" content="Every public engineering claim on this '
      'platform, with its verification status, the evidence behind it, somewhere '
      'to go and check it, and its stated limitation.">')
    a(GENERATED_BANNER)
    a("<style>")
    a(PROOF_CSS.rstrip())
    a("</style>")
    a("</head>")
    a('<body data-surface="proof">')
    a("")
    a('<div class="navwrap"><nav class="top-nav" id="top-nav" aria-label="Main"></nav></div>')
    a("")
    a('<div class="wrap">')
    a("")
    a("  <header>")
    a("    <h1>Evidence index</h1>")
    a("    <p class=\"lede\">Every engineering claim this site makes in public, with the "
      "status of its verification, somewhere you can go and check it, and the "
      "limitation that goes with it.</p>")
    a("  </header>")
    a("")
    a('  <div class="note">')
    a("    <p>Each claim below is generated from a registry, not written here by hand. A "
      "build check refuses the registry if a claim has no evidence, if a destination "
      "does not resolve, or if a status is higher than the verification actually "
      "recorded for it &mdash; so a claim on this page cannot quietly outgrow its "
      "evidence.</p>")
    a("    <p>What that check does <b>not</b> do is read a claim and decide whether it is "
      "true. A script decides whether a claim has evidence, a destination and a stated "
      "limitation. A person decides whether it is true. Mechanising the second would "
      "read as stronger and would be worse, because a confident false pass is more "
      "dangerous than no check at all.</p>")
    a("    <p>This platform is my own system, which I build and operate myself. It is not "
      "an employer&rsquo;s product, and the traffic on it is mine.</p>")
    a("  </div>")
    a("")

    # --- status legend ---
    a('  <h2 class="sec">How to read a status</h2>')
    a('  <ul class="legend">')
    for status, meta in surface["status_vocabulary"].items():
        a(f'    <li><span class="nm pill {_status_class(status)}">{esc(meta["label"])}</span>'
          f'<span class="ds">{esc(meta["means"])}</span></li>')
    a("  </ul>")
    a("")

    # --- audience routes ---
    a('  <h2 class="sec">Where to start</h2>')
    a('  <div class="routes">')
    for key, meta in surface["audiences"].items():
        a('    <div class="route">')
        a(f'      <h3>{esc(meta["label"])}</h3>')
        a(f'      <p>{esc(meta["question"])}</p>')
        a("      <ol>")
        for step in ROUTE_ORDERS.get(key, []):
            a(f"        <li>{esc(step)}</li>")
        a("      </ol>")
        a("    </div>")
    a("  </div>")
    a("")

    def capability_block(entry: dict) -> None:
        cid = entry["capability_id"]
        registry_entry = capabilities.get(cid, {})
        status = entry["public_status"]
        a('    <div class="cap">')
        a('      <div class="caphead">')
        a(f'        <h3>{esc(entry["headline"])}</h3>')
        a(f'        <span class="pill {_status_class(status)}">'
          f'{esc(_status_label(surface, status))}</span>')
        a("      </div>")
        a(f'      <p class="claim">{esc(entry["public_claim"])}</p>')
        a("      <dl>")
        a("        <dt>Evidence</dt>")
        a(f'        <dd>{esc(entry["evidence_summary"])}</dd>')
        a("        <dt>Limitation</dt>")
        a(f'        <dd>{esc(entry["public_limitation"])}</dd>')
        modules = registry_entry.get("relevant_modules") or []
        if modules:
            a("        <dt>In the source</dt>")
            a("        <dd>" + ", ".join(f"<code>{esc(m)}</code>" for m in modules) + "</dd>")
        a("        <dt>Go and check it</dt>")
        a('        <dd><span class="dests">')
        for destination in entry["destinations"]:
            a(f'          <a href="{esc(destination["href"])}">'
              f'{esc(destination["label"])} &rarr;</a>')
        a("        </span></dd>")
        a("      </dl>")
        a(f'      <p class="cid">Registry id: <code>{esc(cid)}</code></p>')
        a("    </div>")

    a('  <h2 class="sec">The strongest evidence</h2>')
    a("  <div>")
    for entry in primary:
        capability_block(entry)
    a("  </div>")
    a("")

    if secondary:
        a('  <h2 class="sec">Also verifiable</h2>')
        a("  <div>")
        for entry in secondary:
            capability_block(entry)
        a("  </div>")
        a("")

    a('  <p><a class="btn" href="/">&larr; Back to the home page</a></p>')
    a("")
    a("  <footer>")
    a("    This page sets no cookies, loads nothing from a third party, and uses no "
      "analytics or trackers.")
    a("  </footer>")
    a("")
    a("</div>")
    a("")
    a('<script src="/nav.js"></script>')
    a("</body>")
    a("</html>")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
def splice_home(home_html: str, rows: str) -> str:
    """Replace the fenced generated region. Refuses rather than guesses if the
    markers are missing or duplicated -- a renderer that silently appends when
    it cannot find its own fence would corrupt the page it is maintaining."""
    if home_html.count(START) != 1 or home_html.count(END) != 1:
        raise ValueError(
            f"home.html must contain exactly one {START!r} and one {END!r} "
            f"(found {home_html.count(START)} and {home_html.count(END)})"
        )
    head, _, rest = home_html.partition(START)
    _, _, tail = rest.partition(END)
    return head + rows + tail


def build() -> dict[Path, str]:
    """Returns the intended content of every generated artifact. Raises if the
    registry is invalid -- generation must never be able to publish a surface
    the gate would refuse."""
    surface = pr.load_surface()
    capabilities = pr.load_capabilities()
    problems = pr.validate(surface, capabilities)
    if problems:
        raise ValueError(
            "refusing to render an invalid public proof surface:\n  - "
            + "\n  - ".join(problems)
        )
    primary = [e for e in surface["capabilities"] if e["tier"] == "PRIMARY"]
    return {
        PROOF_PATH: render_proof_page(surface, capabilities),
        HOME_PATH: splice_home(
            HOME_PATH.read_text(encoding="utf-8"), render_home_rows(surface, primary)
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true", help="regenerate the files on disk")
    group.add_argument(
        "--check", action="store_true",
        help="compare the rendered output against disk; exit non-zero on any difference",
    )
    args = parser.parse_args()

    try:
        intended = build()
    except Exception as exc:  # noqa: BLE001 -- a refusal is a real result
        print(f"PROOF SURFACE RENDER: FAIL -- {exc}")
        return 1

    if args.write:
        for path, content in intended.items():
            path.write_text(content, encoding="utf-8", newline="\n")
            print(f"wrote {path.relative_to(REPO_ROOT)}")
        return 0

    stale = []
    for path, content in intended.items():
        on_disk = path.read_text(encoding="utf-8") if path.exists() else None
        if on_disk is None:
            stale.append(f"{path.relative_to(REPO_ROOT)} does not exist")
        elif on_disk.replace("\r\n", "\n") != content.replace("\r\n", "\n"):
            stale.append(f"{path.relative_to(REPO_ROOT)} differs from the registry")
    if stale:
        print("PROOF SURFACE RENDER: FAIL -- generated output is stale or hand-edited")
        for item in stale:
            print(f"  {item}")
        print("\nRun: python agent/build_proof_surface.py --write")
        return 1
    print(
        f"PROOF SURFACE RENDER: PASS -- {len(intended)} generated artifact(s) match the registry"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
