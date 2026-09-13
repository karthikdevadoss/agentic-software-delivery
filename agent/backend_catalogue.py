"""
Deterministic, machine-verifiable request contract for the INTERNAL/GATED
backend (Java/Spring) change scenario -- ACT-008 foundation
(docs/ACTION_QUEUE.json).

Structurally the same idea as demo_catalogue.py (an explicit
Operation/anchor-pattern catalogue, zero API calls, a NormalizedRequest
contract the caller must reject anything outside of) applied to ONE Java
source file's string constant instead of static HTML. Kept as a
SEPARATE module rather than generalizing demo_catalogue.py's engine: at
N=1 backend operation, a shared abstraction is not yet justified (see
docs/CONSTITUTION.md's "don't design for hypothetical future
requirements" principle) -- if a second backend operation is added
later (see PROJECT_STATE.json's Interview Scenario #2), extracting a
shared anchor-substitution engine used by both this module and
demo_catalogue.py becomes a well-justified, previously-flagged
refactor, not before.

NOT wired into any public Workbench route. See agent/backend_execution.py
for the pipeline that uses this (compile -> targeted JUnit/integration
test -> commit -> push -> deploy -> production API assertion -> restore),
and docs/ACTION_QUEUE.json's ACT-008 entry for the current gating status.
"""

import dataclasses
import json
import re

BACKEND_TARGET_FILE = "app/src/main/java/com/example/customer/service/CustomerService.java"

# A Java string-literal value: no unescaped quote, no backslash (both
# would require real Java string-escaping this deterministic substitution
# deliberately does not implement -- narrower is safer), no newlines
# (this is a one-line constant declaration).
MIN_VALUE_LEN = 1
MAX_VALUE_LEN = 80
_FORBIDDEN_VALUE_CHARS = re.compile(r'["\\\x00-\x1f]')


class UnsupportedBackendRequirement(Exception):
    """The requirement could not be normalized into the one supported
    backend operation (no operation matched, or no new value could be
    extracted). Caller must reject with the exact real example — never
    guess at Java source."""


class InvalidBackendValue(Exception):
    """An operation was matched, but the extracted new value fails the
    input-value contract (length/forbidden characters for a safe Java
    string literal)."""


@dataclasses.dataclass(frozen=True)
class BackendOperation:
    id: str
    human_name: str
    synonyms: tuple
    anchor_pattern: str  # 3 capture groups: (prefix)(current_value)(suffix)
    example: str


BACKEND_OPERATIONS = (
    BackendOperation(
        id="customer_not_found_message",
        human_name="the customer-not-found error message",
        synonyms=("customer not found", "customer-not-found", "not found message", "not-found message"),
        # Anchored on CustomerService.CUSTOMER_NOT_FOUND_MESSAGE's own
        # declaration line (see that class's own comment on why this
        # constant was isolated) -- never a whole-file substring match.
        anchor_pattern=r'(CUSTOMER_NOT_FOUND_MESSAGE = ")([^"]*)(";)',
        example='Change the customer-not-found message to "Customer record not found"',
    ),
)

_BY_ID = {op.id: op for op in BACKEND_OPERATIONS}

SUGGESTED_BACKEND_EXAMPLES = [op.example for op in BACKEND_OPERATIONS]


@dataclasses.dataclass(frozen=True)
class NormalizedBackendRequest:
    """The explicit, machine-verifiable backend request contract. Every
    field is determined by THIS module alone, never by an LLM."""
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
    for op in BACKEND_OPERATIONS:
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


def validate_backend_value(value: str) -> None:
    """Raises InvalidBackendValue with a specific, honest reason — never
    silently truncates or sanitizes a bad value into a different one."""
    if value is None or len(value) < MIN_VALUE_LEN:
        raise InvalidBackendValue("no usable text value was found in the requirement")
    if len(value) > MAX_VALUE_LEN:
        raise InvalidBackendValue(f"requested value is {len(value)} characters, over the {MAX_VALUE_LEN}-character limit for this field")
    if _FORBIDDEN_VALUE_CHARS.search(value):
        raise InvalidBackendValue("requested value contains characters not allowed in a Java string literal (a quote, backslash, or control character)")
    if not value.strip():
        raise InvalidBackendValue("requested value is empty or whitespace-only")


def normalize_backend_requirement(requirement: str) -> NormalizedBackendRequest:
    """The single deterministic authority for the internal backend
    scenario. Raises UnsupportedBackendRequirement or
    InvalidBackendValue — never returns a partial/best-guess result.
    Zero API calls; pure regex/string logic."""
    text = (requirement or "").strip()
    if not text:
        raise UnsupportedBackendRequirement("empty requirement")

    matched = _match_operations(text.lower())
    if len(matched) == 0:
        raise UnsupportedBackendRequirement("no supported backend field was named in the requirement")
    if len(matched) > 1:
        raise UnsupportedBackendRequirement(
            f"requirement matched more than one supported backend field ({', '.join(op.id for op in matched)}) — ambiguous"
        )
    op = matched[0]

    new_value = _extract_new_value(text)
    if new_value is None:
        raise UnsupportedBackendRequirement(f"matched '{op.human_name}' but could not find the requested new text (try quoting it, e.g. {op.example!r})")
    validate_backend_value(new_value)

    return NormalizedBackendRequest(
        operation_id=op.id,
        human_name=op.human_name,
        target_file=BACKEND_TARGET_FILE,
        new_value=new_value,
        risk_class="TINY_JAVA_CONSTANT_SUBSTITUTION",
        expected_changed_files=(BACKEND_TARGET_FILE,),
        expected_verification_method=f"mvn compile + targeted JUnit/integration test, then a live production API call asserting {op.human_name} matches exactly",
        expected_production_assertion=f"{op.human_name} is live in production with exactly the requested value, observed via a real GET /customers/<missing-id> API call",
    )


def extract_current_value(file_content: str, operation_id: str):
    """Real, checkable extraction — used both to read the pre-change
    value (diff-purity / no-op detection) and, applied to a real API
    response body instead of file content, to verify the live production
    value post-deploy (a targeted JSON-field assertion, never a
    whole-response substring containment check)."""
    op = _BY_ID[operation_id]
    match = re.search(op.anchor_pattern, file_content)
    if match is None:
        return None
    return match.group(2)


def apply_operation(file_content: str, operation_id: str, new_value: str) -> str:
    """Pure function: returns the new full file content. Raises if the
    anchor doesn't match exactly once — refuses to guess or silently
    apply an ambiguous/absent change. new_value was already validated by
    validate_backend_value() to exclude quotes/backslashes/control
    characters, so it is safe to splice directly into the Java string
    literal with no further escaping needed."""
    op = _BY_ID[operation_id]
    matches = list(re.finditer(op.anchor_pattern, file_content))
    if len(matches) == 0:
        raise RuntimeError(f"anchor pattern for backend operation {operation_id!r} did not match the current file — refusing to guess")
    if len(matches) > 1:
        raise RuntimeError(f"anchor pattern for backend operation {operation_id!r} matched {len(matches)} times — refusing an ambiguous mutation")
    match = matches[0]
    return file_content[:match.start()] + match.group(1) + new_value + match.group(3) + file_content[match.end():]


def compute_single_line_diff(old_content: str, new_content: str):
    """Enforces diff purity structurally: exactly one line may differ
    between old and new content, and line COUNT must be unchanged.
    Returns (line_index, old_line, new_line). Raises RuntimeError — a
    BLOCKING failure, never silently accepted — otherwise. Identical
    contract to demo_catalogue.compute_single_line_diff (duplicated
    rather than shared for the same N=1 reason as the rest of this
    module — see the module docstring)."""
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


def get_operation(operation_id: str) -> BackendOperation:
    return _BY_ID[operation_id]


def extract_value_from_not_found_api_response(response_body_text: str, operation_id: str):
    """The production-side counterpart to extract_current_value(): reads
    the one controlled field's current value from a REAL live API
    response body, never from a whole-response substring containment
    check. GlobalExceptionHandler's real JSON shape is
    {"error": "<message>: <id>"} — this returns just the message prefix
    (the part this scenario's one operation actually controls), or None
    if the body isn't valid JSON or lacks the expected shape (an honest
    "could not verify", never a guessed match)."""
    if operation_id != "customer_not_found_message":
        raise ValueError(f"no API-response extractor defined for operation {operation_id!r}")
    try:
        data = json.loads(response_body_text)
    except (json.JSONDecodeError, TypeError):
        return None
    error = data.get("error") if isinstance(data, dict) else None
    if not isinstance(error, str) or ": " not in error:
        return None
    return error.rsplit(": ", 1)[0]


def _self_test():
    """Every BACKEND_OPERATIONS example must itself normalize
    successfully, and every operation's anchor must match the REAL
    current CustomerService.java exactly once — run at import time so a
    typo, or a future unrelated refactor of CustomerService.java that
    accidentally breaks this anchor, can never silently ship unnoticed."""
    from pathlib import Path
    target_path = Path(__file__).resolve().parent.parent / BACKEND_TARGET_FILE
    target_content = target_path.read_text(encoding="utf-8") if target_path.exists() else None
    for op in BACKEND_OPERATIONS:
        parsed = normalize_backend_requirement(op.example)
        assert parsed.operation_id == op.id, f"{op.id}: own example normalized to {parsed.operation_id}"
        if target_content is not None:
            matches = list(re.finditer(op.anchor_pattern, target_content))
            assert len(matches) == 1, f"{op.id}: anchor matched {len(matches)} times in the real current CustomerService.java, expected exactly 1"


_self_test()
