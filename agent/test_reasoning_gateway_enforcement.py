"""
Deterministic enforcement (Base Architecture V3 Phase 3/Section 2): fails
if ANY Python file under agent/ imports the Anthropic SDK directly, other
than the small, explicitly-approved allowlist below. This is the
mechanical guard the directive asks for -- "add deterministic enforcement
that fails if new direct provider access is introduced outside approved
gateway modules" -- so this rule survives future sessions/code review
memory, not just a one-time audit.

Inventory: exactly ONE file -- agent/reasoning_gateway.py -- may import a
provider SDK, construct a client or call .messages.create. Everything else,
including any FUTURE file under agent/ or scripts/, must route through
reasoning_gateway.call() or reasoning_gateway.converse().

Run: python agent/test_reasoning_gateway_enforcement.py
"""

import re
import unittest
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent

# The allowlist is the gateway ONLY. Any other entry must carry a real,
# documented reason a gateway call genuinely cannot express the call site.
# (agent_loop.py and backend_planning.py were removed when they were migrated
# to reasoning_gateway.converse().)
APPROVED_DIRECT_IMPORT_FILES = {
    "reasoning_gateway.py": "IS the gateway -- this is where the one sanctioned SDK import lives",
}

REPO_ROOT = AGENT_DIR.parent
SCAN_DIRS = [AGENT_DIR, REPO_ROOT / "scripts"]

# Any billed-call surface, not just imports. Uses the AST so comments,
# docstrings, pricing tables and slug strings never produce false hits.
_PROVIDER_MODULES = {"anthropic", "openai", "google.generativeai", "cohere", "mistralai", "litellm"}


def _scan_file(path):
    """Returns a list of human-readable bypass findings in one Python file,
    from the AST (so comments, docstrings and string literals never count)."""
    import ast
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return [f"{path.name}: unparseable"]
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in {m.split(".")[0] for m in _PROVIDER_MODULES}:
                    hits.append(f"import {alias.name} (line {node.lineno})")
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in {m.split(".")[0] for m in _PROVIDER_MODULES}:
                hits.append(f"from {node.module} import ... (line {node.lineno})")
        elif isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute) and f.attr == "create" and \
                    isinstance(f.value, ast.Attribute) and f.value.attr == "messages":
                hits.append(f".messages.create(...) (line {node.lineno})")
            name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)
            if name in ("Anthropic", "AsyncAnthropic", "AnthropicBedrock", "AnthropicVertex", "OpenAI", "AsyncOpenAI"):
                hits.append(f"{name}(...) client construction (line {node.lineno})")
    return hits


def _bypass_findings():
    """{path relative to repo: [findings]} for every .py under agent/ and
    scripts/ -- a real static scan, never a hand list. Test files are scanned
    too (they must inject create_fn, never construct a client); tests that
    merely mention a client in strings/mocks are unaffected since this is
    AST based."""
    found = {}
    for d in SCAN_DIRS:
        if not d.exists():
            continue
        for path in d.rglob("*.py"):
            if path.name == "test_reasoning_gateway_enforcement.py":
                continue
            hits = _scan_file(path)
            if hits:
                found[str(path.relative_to(REPO_ROOT))] = hits
    return found


def _files_with_direct_anthropic_import():
    found = {}
    for rel in _bypass_findings():
        found[Path(rel).name] = True
    return found


class ReasoningGatewayCentralizationTestCase(unittest.TestCase):
    def test_allowlist_is_the_gateway_only(self):
        self.assertEqual(set(APPROVED_DIRECT_IMPORT_FILES), {"reasoning_gateway.py"})

    def test_no_unapproved_file_bypasses_the_gateway(self):
        unapproved = {
            rel: hits for rel, hits in _bypass_findings().items()
            if Path(rel).name not in APPROVED_DIRECT_IMPORT_FILES
        }
        self.assertEqual(
            unapproved, {},
            f"Direct provider access outside the gateway: {unapproved}. Route through "
            f"agent/reasoning_gateway.call() or converse(), or add the file to "
            f"APPROVED_DIRECT_IMPORT_FILES with a real documented reason.",
        )

    def test_no_raw_http_to_the_provider_outside_the_gateway(self):
        offenders = []
        for d in SCAN_DIRS:
            for path in d.rglob("*"):
                if path.suffix not in (".py", ".sh") or path.name == "test_reasoning_gateway_enforcement.py":
                    continue
                if path.name in APPROVED_DIRECT_IMPORT_FILES:
                    continue
                if "api.anthropic.com" in path.read_text(encoding="utf-8", errors="ignore"):
                    offenders.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual(offenders, [])

    def test_every_approved_file_still_exists_and_still_needs_the_exemption(self):
        found = _files_with_direct_anthropic_import()
        for filename in APPROVED_DIRECT_IMPORT_FILES:
            self.assertTrue((AGENT_DIR / filename).exists(), f"{filename} no longer exists -- remove it")
            self.assertIn(filename, found, f"{filename} no longer needs its exemption -- remove it")

    def test_migrated_files_are_off_the_allowlist_and_clean(self):
        found = _files_with_direct_anthropic_import()
        for name in ("main.py", "agent_loop.py", "backend_planning.py"):
            self.assertNotIn(name, APPROVED_DIRECT_IMPORT_FILES)
            self.assertNotIn(name, found)

    def test_detector_catches_each_known_bad_shape(self):
        # The scanner must be proven to detect the known-bad case before its
        # clean result is trusted.
        import tempfile
        bad = {
            "import anthropic\n": "import anthropic",
            "from anthropic import Anthropic\n": "from anthropic",
            "import openai\n": "import openai",
            "def f(c):\n    return c.messages.create(model='m')\n": ".messages.create",
            "def f(m):\n    return m.Anthropic(api_key='k')\n": "client construction",
            "def f():\n    return AsyncAnthropic()\n": "client construction",
        }
        with tempfile.TemporaryDirectory() as td:
            for i, (src, expect) in enumerate(bad.items()):
                p = Path(td) / f"bad_{i}.py"
                p.write_text(src, encoding="utf-8")
                hits = _scan_file(p)
                self.assertTrue(any(expect in h for h in hits), f"{src!r} not caught: {hits}")
            ok = Path(td) / "ok.py"
            ok.write_text('# import anthropic\n"""messages.create Anthropic("x")"""\nx = "anthropic-slug"\n')
            self.assertEqual(_scan_file(ok), [])


if __name__ == "__main__":
    unittest.main()
