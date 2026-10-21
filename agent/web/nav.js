// Canonical public engineering navigation (single source of truth).
//
// Root cause this file fixes: every public page previously hand-copied
// its own hardcoded <nav> block (8 independently-maintained copies:
// workbench/dashboard/usage/learn/triage/triage-b/triage-c/showcase.html)
// with no single canonical list -- they silently drifted, and "Role
// Showcase" was missing from all 6 core engineering pages entirely
// (never added to any of them, not merely dropped from one). This is
// the generalized architectural fix, not a one-off "add a missing <a>
// tag": every page now renders the SAME canonical destination set from
// this ONE array, so a future addition/removal/rename happens exactly
// once, here, and cannot drift again.
//
// Each page keeps its own <nav class="top-nav" id="top-nav"></nav>
// placeholder (empty) and includes <script src="/nav.js"></script>
// before </body> -- this script populates it on load, marking the
// current page (by real location.pathname, not a per-page hardcoded
// flag) with <strong>.

// AEQ-027 (2026-09-17): AEQ-024's nav unification silently reintroduced
// Learn into Workbench/Dashboard/Usage's nav, reversing a real, explicit
// Owner instruction (2026-09-13, see e2e/profile.spec.js's "Learn retired
// from top nav" describe block) that predates AEQ-024 and was never
// reconciled with it -- AEQ-024's own regression tests only asserted
// Learn's PRESENCE on the pages it was missing from, never checked
// whether it should still be ABSENT from these three. `hiddenOn` is the
// generalized fix: a destination can name the specific pages it must NOT
// appear on, keeping ONE canonical source (no per-page duplicate lists)
// while still honoring a real, narrower Owner decision.
// Sprint 14 (2026-09-29): the canonical recruiter-facing set. "/" is now a
// real home page rather than an alias for Workbench, so Home leads. Three
// destinations were deliberately removed from PUBLIC navigation:
//   * Learn and JD Match -- Owner decision, they become private/authenticated
//     tools; their public routes now 404 in production (see web_server.py's
//     PRIVATE_SURFACES_ENABLED gate). Implementation, datasets and tests are
//     all preserved.
//   * Dashboard -- de-emphasized, not deleted. It is the densest surface on
//     the site (3,470 words) and a poor second click for a recruiter; it stays
//     reachable as a deep link from Usage.
// `hiddenOn` is retained as a mechanism (no destination currently uses it)
// because removing it would delete the only per-page exclusion capability.
const CANONICAL_NAV_DESTINATIONS = [
  { href: "/", label: "Home" },
  { href: "/workbench", label: "Workbench" },
  { href: "/triage", label: "Triage" },
  { href: "/ask-codebase", label: "Ask Codebase" },
  // Automation Sprint 4 (Owner decision, 2026-10-06): Showcase and Usage
  // left the public nav (both routes stay reachable by direct link), and
  // "For Recruiters" joined it -- the one page built from what real job
  // postings ask for, with links to where each thing can be checked.
  { href: "/recruiters", label: "For Recruiters" },
  // Automation Sprint 14 (Owner decision, 2026-10-06; rewrite same day):
  // Interviewer Brief showcase for the technical interviewer before the
  // interview. /recruiters stays HR-facing; Standing Interview is a quiet
  // later link on that page, not a featured section.
  { href: "/interviewer", label: "Interviewer Brief" },
  // BL-079: gated, not unconditional. The Owner's condition was that Standing
  // Interview may appear in the live nav ONLY if the production page can
  // actually answer, and the corpus is delivered at deploy time rather than
  // committed -- so an instance can legitimately exist without one. Rather
  // than rely on remembering to add the link after a successful deploy, the
  // entry asks the server whether a corpus is loaded and removes itself if
  // not. A nav link to a page that cannot answer is worse than no link.
  { href: "/standing-interview", label: "Standing Interview",
    requiresEndpoint: "/api/standing-interview/status", requiresKey: "loaded" },
];

function _isCurrentPage(href, pathname) {
  if (href === pathname) return true;
  // Sprint 14: "/" is its own page now, so the old "/workbench" === "/"
  // aliasing rule is gone -- keeping it would bold Workbench while the
  // visitor is on Home. Triage's sub-scenarios still bold "Triage" as the
  // current top-level section, and the showcase slug bolds "Showcase".
  if (href === "/triage" && pathname.startsWith("/triage/")) return true;
  if (href.startsWith("/showcase/") && pathname.startsWith("/showcase/")) return true;
  return false;
}

function _isHiddenOnPage(hiddenOn, pathname) {
  if (!hiddenOn) return false;
  return hiddenOn.includes(pathname);
}

function renderCanonicalNav(containerId = "top-nav") {
  const container = document.getElementById(containerId);
  if (!container) return;
  const pathname = window.location.pathname;
  container.innerHTML = "";
  for (const { href, label, hiddenOn, requiresEndpoint, requiresKey } of CANONICAL_NAV_DESTINATIONS) {
    if (_isHiddenOnPage(hiddenOn, pathname)) continue;
    // A gated destination renders hidden and is only revealed once the server
    // confirms it can actually serve. Fail-closed: any error leaves it hidden.
    if (requiresEndpoint) {
      const gated = document.createElement("a");
      gated.href = href;
      gated.textContent = label;
      gated.hidden = true;
      gated.dataset.navGated = "true";
      container.appendChild(gated);
      fetch(requiresEndpoint)
        .then((r) => r.json())
        .then((s) => { if (s && s[requiresKey]) gated.hidden = false; })
        .catch(() => { /* stays hidden */ });
      continue;
    }
    const a = document.createElement("a");
    a.href = href;
    if (_isCurrentPage(href, pathname)) {
      const strong = document.createElement("strong");
      strong.textContent = label;
      a.appendChild(strong);
    } else {
      a.textContent = label;
    }
    container.appendChild(a);
  }
}

if (typeof document !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => renderCanonicalNav());
  } else {
    renderCanonicalNav();
  }
}

// Node/test environment (no `window`/`document`) exports for direct
// unit testing of the canonical list and current-page logic.
if (typeof module !== "undefined" && module.exports) {
  module.exports = { CANONICAL_NAV_DESTINATIONS, _isCurrentPage, _isHiddenOnPage, renderCanonicalNav };
}
