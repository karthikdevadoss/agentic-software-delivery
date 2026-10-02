"""Nothing private may reach a public surface.

WHY THIS EXISTS SEPARATELY FROM test_public_surface_gate.py
That gate is about CLAIM honesty on two pages -- does the home page overclaim,
does the case study keep its limits. This one is about DISCLOSURE across
everything the server will actually hand to a stranger, which is a different
risk with a different blast radius: an overclaim is embarrassing and
correctable, a disclosure is permanent the moment it is fetched.

It also covers a surface the claim gate does not: every file under agent/web/
and public-site/, not just home.html and the case study.

WHAT COUNTS AS PRIVATE HERE
Four categories, all of which really exist on this machine and none of which is
hypothetical:

  1. The Owner's private moral framework. It governs his judgement and it is
     deliberately NOT public product, component or architecture naming
     (CLAUDE.md, "Public language"). Public surfaces use ordinary professional
     engineering terms.
  2. The private context repository and its contents -- career strategy,
     positioning, target roles, the books, the engineering-memory store.
  3. Personal circumstances that are nobody's business and are not evidence of
     engineering ability: compensation, visa and immigration status, family.
  4. Secrets and credentials.

WHAT IS DELIBERATELY NOT FLAGGED, so the gate is not read as stricter than it is
Employer NAMES already on the Owner's public CV (NRG Energy, Blue Cross Blue
Shield Association, Marsh) are legitimately public, and the existing claim gate
positively REQUIRES them. This module does not flag them. What it flags is
employer-confidential detail -- internal system names, client names, incident
specifics -- and it can only do that for the markers listed below. It cannot
recognise an employer-confidential fact it has never been told about, and that
residual risk belongs to a human reviewer, not to this file.

HONEST LIMIT, STATED RATHER THAN IMPLIED
This is a substring and pattern scan over committed text. It catches the named
things. It does not understand meaning, so it cannot catch a paraphrase that
avoids every listed term -- and it must not be grown into trying, for the reason
recorded in agent/proof_registry.py's docstring. Its value is that a known
category cannot slip in silently; its limit is that it only knows what it is
told.
"""

from __future__ import annotations

import pathlib
import re
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
WEB_DIR = REPO_ROOT / "agent" / "web"
PUBLIC_SITE_DIR = REPO_ROOT / "public-site"

# Extensions a browser can actually be handed from the public mounts.
PUBLIC_SUFFIXES = {".html", ".js", ".css", ".json", ".md", ".txt", ".svg"}

# Files served ONLY when PRIVATE_SURFACES_ENABLED is set. They are not public in
# a production-shaped process (test_public_surface_gate proves the routes 404),
# so they are out of scope here -- and naming them is better than letting them
# silently widen the scan.
NOT_PUBLICLY_SERVED = {
    "learn.html", "learn.js", "learn.css",
    "learn-data.json", "learn-tree.json", "learn-deep-topics.json",
    "jd-match.html", "jd-match.js", "jd-match.css",
    "control-plane.html",
}

# (category, human description, compiled pattern)
PRIVATE_PATTERNS = [
    (
        "private moral framework",
        "the Owner's private framework is not public product or architecture naming",
        re.compile(
            r"\b(shiva|vishnu|shakti|brahmin|grihastha|bhagavan|krishna|"
            r"bhagavad\s*gita|dharmic|akarma|bhakti)\b",
            re.I,
        ),
    ),
    (
        "private context repository",
        "the private career/strategy repository and its files must not be referenced publicly",
        re.compile(
            r"karthik-ai-context|CURRENT_PRIORITIES|PLAN_DECISIONS|CURRENT_MODEL_ROLES|"
            r"CURRENT_NEXT_ACTIONS|CONTEXT_BOOTSTRAP|STALE_FACTS|docsforclaude",
            re.I,
        ),
    ),
    (
        "personal circumstances",
        "compensation, visa/immigration status and family are not engineering evidence",
        re.compile(
            r"\b(salary|salaries|compensation expectation|expected salary|day rate|"
            r"blue\s?card|visa status|work permit|residence permit|immigration|"
            r"aufenthaltstitel|niederlassungserlaubnis)\b",
            re.I,
        ),
    ),
    (
        "credential or secret shape",
        "a key-shaped string must never be committed to a public asset",
        re.compile(
            r"sk-ant-[A-Za-z0-9_\-]{8,}|sk-[A-Za-z0-9]{32,}|AKIA[0-9A-Z]{16}|"
            r"ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|"
            r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----",
        ),
    ),
    (
        "absolute local filesystem path",
        "a developer-machine path tells a visitor nothing and discloses the machine layout",
        # In a raw string a literal backslash is written \\ -- the first version
        # of this line used \\\\, which matches FOUR consecutive backslashes and
        # therefore nothing real. test_the_detector_detects caught it, which is
        # the whole argument for that test existing: a broken pattern does not
        # report "broken", it reports "nothing private found".
        re.compile(r"C:\\Users\\|C:/Users/|/home/[a-z]+/|/Users/[A-Za-z]+/"),
    ),
]


def _public_files():
    files = []
    for directory in (WEB_DIR, PUBLIC_SITE_DIR):
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in PUBLIC_SUFFIXES:
                continue
            if path.name in NOT_PUBLICLY_SERVED:
                continue
            files.append(path)
    return files


class PublicAssetsCarryNothingPrivateTestCase(unittest.TestCase):
    def setUp(self):
        self.files = _public_files()

    def test_the_scan_actually_found_the_public_surface(self):
        """A scan over zero files passes vacuously and reports clean, which is
        worse than no scan. This is the control."""
        self.assertGreater(len(self.files), 15,
                           f"expected the real public surface, scanned only {len(self.files)} files")
        names = {p.name for p in self.files}
        for expected in ("home.html", "proof.html", "case-study-durable-agent.html", "nav.js"):
            self.assertIn(expected, names, f"{expected} was not scanned")

    def test_no_public_asset_contains_anything_private(self):
        findings = []
        for path in self.files:
            text = path.read_text(encoding="utf-8", errors="replace")
            for category, why, pattern in PRIVATE_PATTERNS:
                for match in pattern.finditer(text):
                    line = text.count("\n", 0, match.start()) + 1
                    findings.append(
                        f"{path.relative_to(REPO_ROOT)}:{line} [{category}] "
                        f"{match.group(0)!r} -- {why}"
                    )
        self.assertEqual(
            findings, [],
            "PRIVATE MATERIAL ON A PUBLIC SURFACE:\n" + "\n".join(findings),
        )

    def test_the_detector_detects(self):
        """Seeded mutation. Each pattern is shown matching a string of the class
        it is meant to catch, so a clean run above means the patterns work and
        not merely that they never matched anything.

        Without this, a typo that broke a regex would read as 'nothing private
        found' -- the exact false-clean this project keeps paying for.
        """
        known_bad = {
            "private moral framework": "the Shakti budget layer decides spend",
            "private context repository": "see karthik-ai-context/current/CURRENT_PRIORITIES.md",
            "personal circumstances": "expected salary is negotiable",
            "credential or secret shape": "key=sk-ant-abc123DEF456ghi789",
            "absolute local filesystem path": r"C:\Users\Hemapriya\agentic-software-delivery",
        }
        self.assertEqual(
            set(known_bad), {category for category, _, _ in PRIVATE_PATTERNS},
            "every pattern category needs a known-bad sample, or it is untested",
        )
        for category, _, pattern in PRIVATE_PATTERNS:
            with self.subTest(category=category):
                sample = known_bad[category]
                self.assertRegex(
                    sample, pattern,
                    f"the {category!r} pattern does not match its own known-bad sample, "
                    "so a clean scan proves nothing",
                )

    def test_public_cv_employer_names_are_not_treated_as_private(self):
        """The counterpart to the test above: the gate must not become so broad
        that it flags what the claim gate positively requires. These three are on
        the Owner's public CV and the home page is required to name them."""
        for allowed in ("NRG Energy", "Blue Cross Blue Shield Association", "Marsh"):
            with self.subTest(employer=allowed):
                for category, _, pattern in PRIVATE_PATTERNS:
                    self.assertIsNone(
                        pattern.search(allowed),
                        f"{allowed!r} is legitimately public but the {category!r} "
                        "pattern flags it",
                    )


class ProofSurfaceCarriesNoPrivateDestinationTestCase(unittest.TestCase):
    """The proof surface is the one public artifact whose whole content is
    links, so it is the most likely route for an accidental disclosure."""

    def test_no_rendered_href_points_at_a_private_location(self):
        import proof_registry as pr

        surface = pr.load_surface()
        forbidden = surface["forbidden_destination_patterns"]
        findings = []
        for path in (WEB_DIR / "proof.html", WEB_DIR / "home.html"):
            text = path.read_text(encoding="utf-8")
            for href in re.findall(r'href="([^"]+)"', text):
                for pattern in forbidden:
                    if pattern in href:
                        findings.append(f"{path.name}: {href} matched {pattern!r}")
        self.assertEqual(findings, [], "private destination(s) rendered:\n" + "\n".join(findings))

    def test_the_forbidden_list_is_not_empty(self):
        import proof_registry as pr

        self.assertGreater(len(pr.load_surface()["forbidden_destination_patterns"]), 5)


if __name__ == "__main__":
    unittest.main()
