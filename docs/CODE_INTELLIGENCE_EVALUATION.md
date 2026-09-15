# Deterministic Code Intelligence — Evaluation

Base Architecture V3 Section 7. Real experiments against the actual Java
Customer App, not a theoretical comparison — grep (this project's current
mechanism, `agent/tools.py`) evaluated against real questions, with an
honest ADOPT/DEFER decision at the end.

## Experiment 1 — "which methods call a changed method?"

**Question**: which real callers exist for `ContractPlanService.enroll()`
(the method this session's mutation-testing/property-testing work
targeted)?

**Method**: `grep -rn "\.enroll(" app/src/main/java/ app/src/test/java/`

**Real result**: 2 production callers (`ContractPlanController.enroll()`,
`TriageScenarioAService`'s buggy-path replay, which calls it twice by
design) + 6 test call sites. Manually cross-checked against the actual
class hierarchy: no interface/polymorphic dispatch exists for this method
(no `ContractPlanService` subclass or interface), so there is no
indirection grep could miss.

**False positives**: none — no other class defines an unrelated method
also named `enroll` in this codebase (checked directly:
`ContractPlanCacheService.java`'s only "enroll()" occurrences are in
comments, which the `\.enroll\(` pattern — a literal dot immediately
before the name — correctly did not match as call sites).

**False negatives**: none found — no method reference (`::enroll`),
reflection, or string-based dynamic dispatch exists anywhere referencing
this method (checked directly).

## Experiment 2 — "can untrusted input reach a dangerous sink?" (SQL injection surface)

**Question**: does any code path construct a SQL/JPQL query via string
concatenation of external input (the classic dangerous-source→sink
pattern)?

**Method**: `grep -rn "createNativeQuery\|createQuery(\"" app/src/main/java/`
plus `grep -rn "@Query" app/src/main/java/`.

**Real result**: zero dynamic query construction anywhere in the
codebase. Exactly one `@Query` annotation exists (`CustomerRepository`),
using a static JPQL string with Spring Data's own parameter binding — no
string concatenation of any kind. This is a complete, correct answer for
this exact question at this codebase's current size.

## Honest evaluation against real candidates

| Tool | What it would add over the above | Real cost |
|---|---|---|
| JavaParser | A true AST — correct across polymorphism, method overloading, and generics, none of which this codebase's actual `enroll()` question happened to exercise | New Maven dependency, new indexing/build step, real integration work |
| OpenRewrite | Structural search/refactor, most valuable for automated *transformation*, not just querying | Heavier still — a full recipe/transform engine, most of which this project doesn't need yet |
| CodeQL / Semgrep | Real taint-tracking (a genuine improvement over grep for Experiment 2's *class* of question at larger scale, or with more complex call chains) | External tool integration, a real CI cost, and — importantly — Experiment 2 above already got a **complete, correct** answer without it at this codebase's real current size |

## ADOPT / DEFER decision

**DEFER**, with real evidence backing it this time (not just the Phase 1
audit's a priori judgment): both real experiments — one "who calls X"
question and one "dangerous sink" security question, the two clearest
representative cases from the directive's own suggested question list —
were answered **completely and correctly** by grep alone, with zero
observed false positives or false negatives, at this codebase's actual
current scale (one Spring Boot module, no deep polymorphism on the
methods tested). Adopting a heavier tool now would add real build/CI
complexity to answer questions grep already answers correctly here.

**What would change this decision**: a real observed grep failure (a
missed caller due to polymorphism, an interface implementation grep
didn't catch, a taint path spanning enough indirection that manual
verification became unreliable) — none has been observed yet, in this
session's real experiments or in this project's history. Re-evaluate the
next time a real refactor exercises a call site with genuine polymorphic
dispatch, where grep's blind spot would actually be exercised.
