"""
STATIC verification tier (BL-018, 2026-09-20) -- Testing & Verification
Architecture V1's first real inhabitant of the previously-empty STATIC
tier (docs/TESTING_ARCHITECTURE_V1.md SS G). Zero-LLM, deterministic,
no model involved: real file-mode/shebang checks via `git ls-files -s`.

Real defect class this closes: a file's Unix executable bit silently
lost when copying files on Windows (mode 100644 instead of 100755) is
invisible on this Windows dev machine and only surfaces as a real CI
"Permission denied" failure (exit 126) -- see docs/LESSONS.md and
docs/AI_NATIVE_TESTING_RESEARCH.md finding 3c. This gate catches it
locally, deterministically, before it ever reaches CI.

Rule (CLAUDE.md's "AI-characteristic defect discipline"): every file with
a real `#!` shebang, or any file under scripts/, must be git mode 100755.

Second real check, added 2026-09-20 after the SAME AI hit the SAME
documented bug a third time in one session: a literal `--` inside an
XML/HTML comment (`<!-- ... -- ... -->`) breaks Maven's POM parser and
any other real XML parser, with a misleading error pointing at the
*closing* `-->`. Writing this down twice in docs/LESSONS.md did not
prevent a third real occurrence -- this is the mechanical gate instead.

Third real check, added 2026-09-23 (Sprint 6 retro action item) after
the SAME framework-owned-`@Bean` collision recurred a third time in this
project (BL-007 item 7, then BL-039's api-gateway `RestClient.Builder`
collision, neither previously logged in docs/LESSONS.md until now) --
see CLAUDE.md's own rule: "a new @Bean of a framework-owned,
auto-configured type is HIGH/CROSS_MODULE... @ConditionalOnMissingBean
matches by TYPE, so an unqualified consumer elsewhere silently takes
your bean." This is a deterministic, regex-based HEURISTIC, not full
Java semantic analysis: it flags a `@Bean` method whose declared return
type is one of a known list of framework-owned auto-configured types
and which has no `@Primary`/`@Qualifier` annotation in its own
annotation block. A flag here means "review this bean for a possible
autoconfiguration collision," not "this is definitely broken" -- real
false positives are possible (e.g. the only bean of that type in the
whole application context), so this stays advisory-only in CI, the same
posture V1 already uses for the risk-classifier annotation.

Usage:
    python agent/static_gate.py        # check the whole real repo
"""

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_XML_LIKE_SUFFIXES = (".xml", ".pom", ".html", ".htm", ".xsd", ".svg")
_XML_COMMENT_RE = re.compile(r"<!--(.*?)-->", re.DOTALL)

# Framework-owned, auto-configured bean types named explicitly in CLAUDE.md's
# defect discipline -- a new @Bean of one of these is the real, recurring risk.
_FRAMEWORK_OWNED_BEAN_TYPES = (
    "RestClient.Builder", "RestTemplate", "WebClient.Builder", "ObjectMapper",
    "TaskExecutor", "SecurityFilterChain",
)
# Matches a `@Bean` annotation, optionally other annotations/comments in between,
# then a method declaration whose return type is captured in group 1.
_BEAN_METHOD_RE = re.compile(
    r"@Bean\b(?P<between>(?:(?!\n\s*(?:public|protected|private|static)\b).)*?)"
    r"\n\s*(?:public|protected|private|static)[\w\s<>,]*?\s(\w[\w.<>]*)\s+\w+\s*\(",
    re.DOTALL,
)

# Cheap, real candidate filters -- avoids reading every tracked file's
# content (slow across a whole repo); covers the real, known cases in
# this repo (mvnw scripts, anything under scripts/, any .sh file)
# without needing a full byte-by-byte shebang scan of everything.
_CANDIDATE_NAME_PATTERNS = ("mvnw",)
_CANDIDATE_SUFFIXES = (".sh",)
_CANDIDATE_DIR_PREFIXES = ("scripts/",)


def _list_tracked_with_mode() -> list[tuple[str, str]]:
    """Real (mode, path) pairs for every git-tracked file, via
    `git ls-files -s` -- never estimated, never assumed."""
    proc = subprocess.run(
        ["git", "ls-files", "-s"], cwd=str(REPO_ROOT),
        capture_output=True, text=True, check=True,
    )
    pairs = []
    for line in proc.stdout.splitlines():
        # Format: "<mode> <sha> <stage>\t<path>"
        meta, path = line.split("\t", 1)
        mode = meta.split()[0]
        pairs.append((mode, path))
    return pairs


def _is_candidate(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    if name in _CANDIDATE_NAME_PATTERNS:
        return True
    if any(path.endswith(suf) for suf in _CANDIDATE_SUFFIXES):
        return True
    if any(path.startswith(pfx) for pfx in _CANDIDATE_DIR_PREFIXES):
        return True
    return False


def _has_real_shebang(path: str) -> bool:
    full = REPO_ROOT / path
    if not full.is_file():
        return False
    try:
        with open(full, "rb") as f:
            head = f.read(2)
        return head == b"#!"
    except OSError:
        return False


def check() -> list[dict]:
    """Returns a list of real violations: candidate files that are
    scripts (shebang or under scripts/) but are NOT git mode 100755.
    Empty list means the gate passes. Never raises for a clean repo."""
    violations = []
    for mode, path in _list_tracked_with_mode():
        if not _is_candidate(path):
            continue
        name = path.rsplit("/", 1)[-1]
        is_script = (
            name in _CANDIDATE_NAME_PATTERNS
            or any(path.endswith(suf) for suf in _CANDIDATE_SUFFIXES)
            or _has_real_shebang(path)
        )
        if is_script and mode != "100755":
            violations.append({"path": path, "mode": mode, "expected_mode": "100755"})
    return violations


def check_xml_comments() -> list[dict]:
    """Returns real violations: any tracked .xml/.pom/.html/.xsd/.svg file
    with a literal '--' inside an XML/HTML comment body. Reads real
    tracked-file content via `git show HEAD:<path>` (so it checks what's
    actually committed, not stray working-tree noise), scans the whole
    comment body (not a single-line grep, which misses a '--' sitting at
    the very end of a line -- the exact way this bug bit multiple times
    already, see docs/LESSONS.md)."""
    violations = []
    proc = subprocess.run(
        ["git", "ls-files"], cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
    )
    for path in proc.stdout.splitlines():
        if not path.endswith(_XML_LIKE_SUFFIXES):
            continue
        show = subprocess.run(
            ["git", "show", f"HEAD:{path}"], cwd=str(REPO_ROOT),
            capture_output=True, text=True,
        )
        if show.returncode != 0:
            continue
        for match in _XML_COMMENT_RE.finditer(show.stdout):
            if "--" in match.group(1):
                line_no = show.stdout.count("\n", 0, match.start()) + 1
                violations.append({"path": path, "line": line_no})
    return violations


def check_unqualified_framework_beans() -> list[dict]:
    """Returns real, heuristic HEURISTIC findings (not proofs): any tracked
    .java file declaring a @Bean method whose return type is a known
    framework-owned auto-configured type, with no @Primary or @Qualifier
    annotation in the same annotation block. Reads real tracked-file content
    via `git show HEAD:<path>`. Advisory-only -- a real false positive is
    possible when a bean type has only one real instance in the whole
    application context, so this is reported, never gated, same posture as
    V1's risk-classifier CI annotation."""
    findings = []
    proc = subprocess.run(
        ["git", "ls-files", "*.java"], cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
    )
    for path in proc.stdout.splitlines():
        show = subprocess.run(
            ["git", "show", f"HEAD:{path}"], cwd=str(REPO_ROOT),
            capture_output=True, text=True,
        )
        if show.returncode != 0:
            continue
        content = show.stdout
        for match in _BEAN_METHOD_RE.finditer(content):
            between, return_type = match.group("between"), match.group(2)
            is_flagged_type = (
                return_type in _FRAMEWORK_OWNED_BEAN_TYPES
                or return_type.endswith("Customizer")
            )
            if not is_flagged_type:
                continue
            if "@Primary" in between or "@Qualifier" in between:
                continue
            line_no = content.count("\n", 0, match.start()) + 1
            findings.append({"path": path, "line": line_no, "type": return_type})
    return findings


def main():
    mode_violations = check()
    comment_violations = check_xml_comments()
    all_clean = not mode_violations and not comment_violations

    if mode_violations:
        print(f"STATIC gate (file-mode/shebang): FAIL -- {len(mode_violations)} violation(s):")
        for v in mode_violations:
            print(f"  {v['path']}: mode={v['mode']} (expected {v['expected_mode']})")
        print("Fix with: git update-index --chmod=+x <path>")
    else:
        print("STATIC gate (file-mode/shebang): PASS -- no violations found.")

    if comment_violations:
        print(f"STATIC gate (XML/HTML comment '--'): FAIL -- {len(comment_violations)} violation(s):")
        for v in comment_violations:
            print(f"  {v['path']} (comment starting near line {v['line']}): contains a literal '--'")
        print("Fix: replace '--' with ':' or a real em dash inside the comment.")
    else:
        print("STATIC gate (XML/HTML comment '--'): PASS -- no violations found.")

    bean_findings = check_unqualified_framework_beans()
    if bean_findings:
        print(f"STATIC gate (unqualified framework @Bean, ADVISORY-ONLY): {len(bean_findings)} finding(s):")
        for v in bean_findings:
            print(f"  {v['path']}:{v['line']} -- @Bean returning {v['type']}, no @Primary/@Qualifier found")
        print("Review each for a possible autoconfiguration collision (see docs/LESSONS.md, 2026-09-23).")
    else:
        print("STATIC gate (unqualified framework @Bean): PASS -- no findings.")

    sys.exit(0 if all_clean else 1)


if __name__ == "__main__":
    main()
