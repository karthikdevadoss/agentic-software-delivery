# Static Quality / Security / Supply-Chain — Evaluation

Base Architecture V3 Section 14. Real inspection of what already exists
before evaluating new tools, per the directive's own rule ("what did we
have before?").

## What already exists — verified directly, not assumed

- **Dependency vulnerability scanning**: `.github/dependabot.yml` was
  already configured (found during this session's inspection, not added
  by it) for all 4 real package ecosystems this repo actually uses:
  Maven (`app/`), pip (`agent/`), npm (root), and GitHub Actions itself —
  weekly. GitHub automatically surfaces Dependabot alerts for a public
  repository once this file exists, no further setup needed.
- **Secret scanning**: GitHub automatically enables secret scanning on
  every public repository at no cost, no configuration file required.
  Independently sanity-checked this session with a direct grep for
  known credential shape patterns (Anthropic API keys, AWS access keys)
  across all tracked `.py`/`.java`/`.js`/`.json`/`.yaml` files — zero
  real matches (only a test fixture explicitly named as such).
- **Static code analysis (SAST)**: **did not exist** before this session
  — confirmed via direct inspection: no `spotbugs`/`checkstyle`/`sonar`
  plugin in `app/pom.xml`, no code-scanning workflow in
  `.github/workflows/`.

## Decision: add CodeQL, nothing else

Answered against the directive's own Technology Decision Rule:

1. **What problem exists?** No first-party static/security analysis at
   all — a real vulnerability class (SQL injection, XSS, hardcoded
   credentials, unsafe deserialization) in this project's own Java/
   Python/JS source would currently only be caught by manual review.
2. **Is it important?** Yes — this is a real, live, public production
   system.
3. **Can existing code solve it?** No — Section 7's grep-based
   experiments answer narrow, pre-known questions well; general
   vulnerability *discovery* (finding classes of bug nobody thought to
   grep for) is a different problem.
4. **Does it provide stronger deterministic intelligence?** Yes — CodeQL
   is a mature, widely-used SAST engine, not a novel/unproven choice.
5. **Does it reduce LLM dependence?** Yes, for this specific class of
   review — currently the only way to catch these bug classes is human
   (or LLM-assisted human) code review.
6. **Does it improve evidence?** Yes — structured findings in GitHub's
   Security tab, not prose.
7. **Reusable value?** Yes — a generic CI addition, no Customer-App-
   specific coupling.
8. **Complexity/cost?** Low: free for a public repository, GitHub-hosted
   (zero new infrastructure), and `.github/workflows/codeql.yml` is
   purely additive — a separate job from `ci.yml`, never blocks the real
   `mvn test -B` / deploy gates.

**Added**: `.github/workflows/codeql.yml`, covering all three real
languages in this repo (`java-kotlin` via autobuild against `app/`'s
Maven project, `python`, `javascript-typescript`), on push/PR to master
plus a weekly schedule matching `dependabot.yml`'s existing cadence.

**Not adopted, with reasons**:

- **Semgrep / Chennai**: would meaningfully overlap with CodeQL's SAST
  coverage for this repo's real languages — the directive explicitly
  warns against "several overlapping technologies for appearance." No
  evidence CodeQL's coverage is insufficient here yet; revisit only if a
  real gap in CodeQL's findings is observed.
- **SpotBugs/Checkstyle (Java-specific linters)**: narrower than CodeQL
  (style/bug-pattern checks, not security-focused) and would be a second,
  Java-only tool alongside a broader one already being added — genuine
  future value (code style consistency) but not urgent, and not this
  section's actual ask (security/supply-chain).
- **SBOM generation**: no current consumer of an SBOM exists (no
  downstream compliance/audit process asks for one) — real, deferred
  future work if that need ever arises, not built speculatively.
