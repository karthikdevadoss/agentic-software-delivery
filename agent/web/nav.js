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
const CANONICAL_NAV_DESTINATIONS = [
  { href: "/workbench", label: "Workbench" },
  { href: "/triage", label: "Triage" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/usage", label: "Usage" },
  { href: "/learn", label: "Learn", hiddenOn: ["/workbench", "/dashboard", "/usage"] },
  { href: "/showcase/senior-java-ai-transformation", label: "Role Showcase" },
];

function _isCurrentPage(href, pathname) {
  if (href === pathname) return true;
  // "/" and "/workbench" both serve the Workbench page (see
  // agent/web_server.py's route table); Triage's own sub-scenarios
  // (/triage/scenario-b, /triage/scenario-c) should still bold "Triage"
  // as the current top-level section.
  if (href === "/workbench" && pathname === "/") return true;
  if (href === "/triage" && pathname.startsWith("/triage/")) return true;
  if (href === "/learn" && pathname.startsWith("/learn/")) return true;
  return false;
}

// "/" serves the same page as "/workbench" (see _isCurrentPage above) --
// hiddenOn must treat them as the same page too, or Learn would
// incorrectly reappear on "/" while staying hidden on "/workbench".
function _isHiddenOnPage(hiddenOn, pathname) {
  if (!hiddenOn) return false;
  const normalized = pathname === "/" ? "/workbench" : pathname;
  return hiddenOn.includes(normalized);
}

function renderCanonicalNav(containerId = "top-nav") {
  const container = document.getElementById(containerId);
  if (!container) return;
  const pathname = window.location.pathname;
  container.innerHTML = "";
  for (const { href, label, hiddenOn } of CANONICAL_NAV_DESTINATIONS) {
    if (_isHiddenOnPage(hiddenOn, pathname)) continue;
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
