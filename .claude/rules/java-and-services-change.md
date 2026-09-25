---
paths:
  - "app/**"
  - "services/**"
  - "**/*.java"
  - "**/pom.xml"
---

# Java / Spring / multi-service change rules

Moved verbatim out of CLAUDE.md's "AI-characteristic defect discipline"
section on 2026-09-25 (Phase 3, context efficiency). Nothing was reworded or
dropped -- only the three bullets that are genuinely specific to Java/Spring
and to multi-process service work were relocated here, so they load when a
Java or `services/` file is actually read instead of on every session. The
language-independent rules in that section (remembered APIs, SKIPPED is not
PASSED, a new test observed failing, computed numbers, worktree isolation,
independent evaluation, diagnostic tools proven) deliberately stayed in
CLAUDE.md, because they apply to Python and infrastructure work too and moving
them here would have quietly narrowed their scope.

Same origin and rationale as the rest of that section: these rules are
designed around how *this* agent actually got things wrong (see the
2026-09-20 audit, docs/AI_NATIVE_TESTING_RESEARCH.md), not around how humans
get things wrong.

- **A new `@Bean` of a framework-owned, auto-configured type is
  HIGH/CROSS_MODULE** (`RestClient.Builder`, `RestTemplate`,
  `WebClient.Builder`, `ObjectMapper`, `TaskExecutor`, `SecurityFilterChain`,
  any `*Customizer`), regardless of which directory it lives in, and
  requires a real full-context boot of every service sharing that context
  -- not a slice test. `@ConditionalOnMissingBean` matches by TYPE, so an
  unqualified consumer elsewhere silently takes your bean.
- **First-of-its-kind multi-process work must be verified multi-process.**
  The backlog rubric already defaults a first integration of a given kind
  to LARGE; verification must match. A mocked integration test never
  satisfies an integration acceptance criterion. Real registry + 2+ real
  instances + one real end-to-end request with a real token, asserted at
  the far end.
- **Cross-service calls require propagation and negative assertions.** For
  every new outbound service-to-service call: (a) assert the *outbound
  request* actually carries required headers (Authorization, correlation
  id) -- assert on the recorded request, never the response; (b) assert
  the downstream rejects the call when the credential is absent. A 200
  happy-path assertion cannot fail on a propagation bug.

Related, still in CLAUDE.md and always loaded: **never write against a
remembered API** -- for Java, resolve the symbol against the resolved
dependency's real class or version-exact docs matching `pom.xml`, never
generic docs.
