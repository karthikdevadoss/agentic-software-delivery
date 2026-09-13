"""
Deterministic, machine-verifiable request contract for the PUBLIC
Workbench demo (RELIABILITY/CORRECTION PHASE, 2026-09-13).

Replaces free-form LLM interpretation for the public demo path. Exactly
5 named operations are supported, each targeting one known, unique,
already-existing field in the real Customer App's static homepage
(app/src/main/resources/static/index.html). A cheap, zero-API-cost
regex-based normalizer maps free text into a NormalizedRequest — the
explicit request contract the Owner asked for: operation type, allowed
target (file + anchor), requested new value, risk class, expected
verification method, expected production assertion.

The LLM may interpret natural language — it is NOT used here at all for
the 5 supported operations (this module never calls any model). It MUST
NOT decide its own permissions: normalize_requirement() is the sole,
deterministic authority over whether a requirement is executable, and
web_server.py must reject anything this module doesn't return a
NormalizedRequest for, before spending any API/agent budget.

All mutation is a pure, deterministic single-field text substitution
inside one already-known HTML anchor. Diff purity is enforced
structurally (compute_diff() raises if more than one line differs), not
just tested after the fact.
"""

import dataclasses
import html
import re

DEMO_TARGET_FILE = "app/src/main/resources/static/index.html"

# Hard bounds applied to every operation's new value. Deliberately
# conservative: no HTML-shaped characters (defense in depth on top of the
# HTML-escaping applied at write time below), no control characters or
# newlines (these are single-line visible text fields), bounded length.
MIN_VALUE_LEN = 1
MAX_VALUE_LEN = 100
_FORBIDDEN_VALUE_CHARS = re.compile(r'[<>\x00-\x1f]')


class UnsupportedRequirement(Exception):
    """The requirement could not be normalized into any of the 5
    supported operations (no operation matched, or more than one did, or
    no new value could be extracted). Caller must show the
    'Authorization required' message with examples — never guess."""


class InvalidValue(Exception):
    """An operation was matched, but the extracted new value fails the
    input-value contract (length/forbidden characters)."""


@dataclasses.dataclass(frozen=True)
class Operation:
    id: str
    human_name: str
    synonyms: tuple
    anchor_pattern: str  # 3 capture groups: (open_tag)(current_value)(close_tag)
    example: str


OPERATIONS = (
    Operation(
        id="heading_text",
        human_name="the main heading text",
        synonyms=("heading", "main title", "page heading", "page title"),
        anchor_pattern=r'(<h1>)([^<]*?)(\s*<span class="badge")',
        example='Change the heading text to "Customer Portal"',
    ),
    Operation(
        id="subtitle_text",
        human_name="the subtitle text",
        synonyms=("subtitle", "sub-title", "sub title", "tagline"),
        anchor_pattern=r'(<p class="subtitle">)([^<]*)(</p>)',
        example='Change the subtitle text to "A live demo application"',
    ),
    Operation(
        id="find_button_label",
        human_name="the Find button label",
        synonyms=("find button",),
        anchor_pattern=r'(<button id="find-btn">)([^<]*)(</button>)',
        example='Change the Find button label to "Search"',
    ),
    Operation(
        id="create_button_label",
        human_name="the Create button label",
        synonyms=("create button",),
        anchor_pattern=r'(<button id="create-btn">)([^<]*)(</button>)',
        example='Change the Create button label to "Add Customer"',
    ),
    Operation(
        id="footer_text",
        human_name="the footer text",
        synonyms=("footer",),
        anchor_pattern=r'(<footer class="app-footer">)([^<]*)(</footer>)',
        example='Change the footer text to "Built with care"',
    ),
)

_BY_ID = {op.id: op for op in OPERATIONS}

# Every OPERATIONS example must itself normalize successfully — checked
# at import time (see _self_test() at the bottom) so a typo in an example
# string can never silently ship as an unusable "supported" example.

SUGGESTED_EXAMPLES = [op.example for op in OPERATIONS]


@dataclasses.dataclass(frozen=True)
class NormalizedRequest:
    """The explicit, machine-verifiable request contract. Every field is
    determined by THIS module alone, never by an LLM."""
    operation_id: str
    human_name: str
    target_file: str
    new_value: str
    risk_class: str
    expected_changed_files: tuple
    expected_verification_method: str
    expected_production_assertion: str


_QUOTED_VALUE = re.compile(r'["‘’“”]([^"‘’“”]{1,%d})["‘’“”]' % MAX_VALUE_LEN)
_TO_CLAUSE_VALUE = re.compile(r'\bto\s+(.+)$', re.IGNORECASE)


def _match_operations(text_lower: str):
    matched = []
    for op in OPERATIONS:
        if any(syn in text_lower for syn in op.synonyms):
            matched.append(op)
    return matched


def _extract_new_value(raw_text: str):
    quoted = _QUOTED_VALUE.findall(raw_text)
    if quoted:
        return quoted[-1].strip()
    m = _TO_CLAUSE_VALUE.search(raw_text)
    if m:
        candidate = m.group(1).strip().strip(".!,;").strip()
        if candidate:
            return candidate
    return None


def validate_value(value: str) -> None:
    """Raises InvalidValue with a specific, honest reason — never
    silently truncates or sanitizes a bad value into a different one."""
    if value is None or len(value) < MIN_VALUE_LEN:
        raise InvalidValue("no usable text value was found in the requirement")
    if len(value) > MAX_VALUE_LEN:
        raise InvalidValue(f"requested value is {len(value)} characters, over the {MAX_VALUE_LEN}-character limit for this field")
    if _FORBIDDEN_VALUE_CHARS.search(value):
        raise InvalidValue("requested value contains characters not allowed in a visible text field (e.g. '<', '>', or control characters)")
    if not value.strip():
        raise InvalidValue("requested value is empty or whitespace-only")


def normalize_requirement(requirement: str) -> NormalizedRequest:
    """The single deterministic authority for the public demo path.
    Raises UnsupportedRequirement or InvalidValue — never returns a
    partial/best-guess result. Zero API calls; pure regex/string logic."""
    text = (requirement or "").strip()
    if not text:
        raise UnsupportedRequirement("empty requirement")

    matched = _match_operations(text.lower())
    if len(matched) == 0:
        raise UnsupportedRequirement("no supported field was named in the requirement")
    if len(matched) > 1:
        raise UnsupportedRequirement(
            f"requirement matched more than one supported field ({', '.join(op.id for op in matched)}) — ambiguous"
        )
    op = matched[0]

    new_value = _extract_new_value(text)
    if new_value is None:
        raise UnsupportedRequirement(f"matched '{op.human_name}' but could not find the requested new text (try quoting it, e.g. {op.example!r})")
    validate_value(new_value)

    return NormalizedRequest(
        operation_id=op.id,
        human_name=op.human_name,
        target_file=DEMO_TARGET_FILE,
        new_value=new_value,
        risk_class="TINY_TEXT_SUBSTITUTION",
        expected_changed_files=(DEMO_TARGET_FILE,),
        expected_verification_method=f"targeted DOM/text extraction of {op.human_name} from the live production HTML",
        expected_production_assertion=f"the live {op.human_name} equals the requested value exactly",
    )


def extract_current_value(file_content: str, operation_id: str):
    """Real, checkable extraction — used both to read the pre-change
    value (diff-purity / no-op detection) and, on the SAME anchor
    pattern, to verify the live production value post-deploy (a targeted
    assertion, never a whole-file substring containment check)."""
    op = _BY_ID[operation_id]
    match = re.search(op.anchor_pattern, file_content)
    if match is None:
        return None
    return html.unescape(match.group(2))


def apply_operation(file_content: str, operation_id: str, new_value: str) -> str:
    """Pure function: returns the new full file content. Raises if the
    anchor doesn't match exactly once — refuses to guess or silently
    apply an ambiguous/absent change."""
    op = _BY_ID[operation_id]
    matches = list(re.finditer(op.anchor_pattern, file_content))
    if len(matches) == 0:
        raise RuntimeError(f"anchor pattern for operation {operation_id!r} did not match the current file — refusing to guess")
    if len(matches) > 1:
        raise RuntimeError(f"anchor pattern for operation {operation_id!r} matched {len(matches)} times — refusing an ambiguous mutation")
    match = matches[0]
    escaped = html.escape(new_value)
    return file_content[:match.start()] + match.group(1) + escaped + match.group(3) + file_content[match.end():]


def compute_single_line_diff(old_content: str, new_content: str):
    """Enforces diff purity structurally: exactly one line may differ
    between old and new content, and line COUNT must be unchanged (a
    single in-place text substitution, never a line inserted/removed).
    Returns (line_index, old_line, new_line). Raises RuntimeError — a
    BLOCKING failure, never silently accepted — otherwise."""
    old_lines = old_content.splitlines()
    new_lines = new_content.splitlines()
    if len(old_lines) != len(new_lines):
        raise RuntimeError(f"line count changed ({len(old_lines)} -> {len(new_lines)}) — refusing, expected a single in-place text substitution only")
    diffs = [(i, o, n) for i, (o, n) in enumerate(zip(old_lines, new_lines)) if o != n]
    if len(diffs) == 0:
        raise RuntimeError("no line differs between old and new content — refusing a no-op mutation")
    if len(diffs) > 1:
        raise RuntimeError(f"{len(diffs)} lines differ, expected exactly 1 — refusing an unexpected/broader diff: {diffs}")
    return diffs[0]


def get_operation(operation_id: str) -> Operation:
    return _BY_ID[operation_id]


def _self_test():
    """Every OPERATIONS example must itself normalize successfully, and
    every operation's anchor must match the REAL baseline file exactly
    once — run at import time so a typo can never silently ship."""
    from pathlib import Path
    baseline_path = Path(__file__).resolve().parent / "demo_baseline" / "index.html"
    baseline_content = baseline_path.read_text(encoding="utf-8") if baseline_path.exists() else None
    for op in OPERATIONS:
        parsed = normalize_requirement(op.example)
        assert parsed.operation_id == op.id, f"{op.id}: own example normalized to {parsed.operation_id}"
        if baseline_content is not None:
            matches = list(re.finditer(op.anchor_pattern, baseline_content))
            assert len(matches) == 1, f"{op.id}: anchor matched {len(matches)} times in the real baseline file, expected exactly 1"


_self_test()
