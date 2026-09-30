# Testing

Sprint 17, 2026-09-30. The machine-readable companion is `docs/testing-matrix.json`.

---

## The one thing to read if you read nothing else

```
python agent/release_health.py            # can this branch truthfully be called green?
python agent/release_health.py --quick    # the seconds-long subset
python agent/release_health.py --changed  # only what the real diff needs
python agent/release_health.py --list     # print the plan, run nothing
```

It never invokes a paid suite, and it prints what it ran, what it excluded this
invocation, and eight gates that are not release health at all with the real
reason for each.

---

## Why this document exists

Before it, "is the branch green?" had six answers: a GitHub workflow with eight
jobs of which two were deliberately non-gating, a Python runner, three Node
harnesses invoked by hand, a Playwright config, a TIA engine, and a
`verify_change.py` dry run. Answering meant remembering all six *and* remembering
which failures were expected.

On 2026-09-30 that broke down completely. The hermetic Python suite reported 784
tests and 2 failures. One was a real wiring defect. The other had been failing for
two sprints because a language model declines one interview question on 2 of 3
captured draws. Both produced the same exit code — so the exit code carried no
information at all, and the only way to tell them apart was to read the log and
already know which failure was expected.

That is how a team learns to ignore red builds.

---

## RELEASE HEALTH

Deterministic checks whose failure means the branch genuinely cannot ship. **Two
properties, both required:**

1. the same input gives the same verdict every run, and
2. the thing measured is a property of **this repository's code**.

| Gate | Command | Local | CI |
|---|---|---|---|
| STATIC (file modes, shebangs, XML/HTML comment `--`) | `python agent/static_gate.py` | yes | gating |
| CONFIG-DRIFT (Spring profile files) | `python agent/check_config_drift.py` | yes | gating |
| Python hermetic suite | `python agent/ci_python_tests.py` | yes | gating |
| Node frontend harnesses | `node agent/test_{trainer,usage,learn}_frontend.js` | yes | gating |
| RAG/MCP retrieval + routing evals | `python agent/eval_runner.py all` | yes | gating |
| Customer App (Java/Spring) | `cd app && ./mvnw test -B` | needs a JDK | gating |
| Customer App Docker image | `docker build` | **no Docker on this machine** | gating |
| Microservices (6 services) | `cd services/<s> && ./mvnw test -B` | needs a JDK | gating, matrix |
| Real-topology multi-instance | `python services/real-topology-tests/run_real_topology_test.py` | heavy | gating since BL-056 |
| Playwright functional | `npx playwright test` | yes | non-blocking (see below) |

---

## QUALITY MONITORS

Separate, and **not** a place to park an inconvenient failure. Every monitor
**runs on every invocation** and its real failure text is **printed in full**.
The only thing it does not do is set the exit code.

| Monitor | What it measures | State |
|---|---|---|
| `agent/test_si_answer_quality_monitor.py` | the content of captured Standing Interview answers | **KNOWN RED** on question m |
| `si-answer-quality-paid` (`agent/si_recapture.py`) | fresh answers from live production | PAID, refused by default |
| Repeated stochastic trials | variance across draws | not built (backlog) |
| Red-team / prompt-injection campaigns | adversarial robustness | not built (backlog) |

### Where the line falls, stated so it cannot be stretched later

A module is a monitor **only** if its assertion is about the *content of model
output*. If the same code run twice on the same input can legitimately give
different verdicts, it is a monitor. If it cannot, it is release health, and no
amount of inconvenience moves it.

"It fails a lot" is not a qualifying reason. "What it measures is not a property
of this repository's code" is.

### The known red one, in full

`DoesNotOverRefuseInProduction.test_a_legitimate_interview_question_is_not_refused`
fails on question m — *"describe a technical disagreement and how you resolved
it"* — with 2 of 3 captured draws not answered.

**Correction on record:** the original docstring blamed a corpus gap. That is
wrong. The draw that *did* answer produced a real grounded story, so the material
is in the corpus and retrieval reaches it inconsistently. Tracked as SI-19/BL-149.

One further detail worth knowing before anyone spends on it: of the two failing
draws, m/2 has `outcome=no_model` — the model was not called at all — and only
m/3 is `ungrounded_model_declined`. They are different causes sharing one
assertion, and a fix aimed at retrieval would only address one of them.

**Loosening the decline gate is not a fix.** It would make the system invent an
anecdote about a disagreement that may never have happened, which is worse than a
refusal.

---

## Suite tags

`quick` · `full` · `visual` · `live` · `paid`

`paid` means *would reach a provider*, never *is slow*. Every suite's tags are in
`docs/testing-matrix.json`, and `agent/test_select_tests.py` asserts that a
`paid` cost class always carries the `paid` tag — otherwise a suite could be paid
in behaviour and free-looking in the matrix.

---

## Cost-aware, change-aware selection

```
python agent/select_tests.py --base origin/master
python agent/select_tests.py agent/web/style.css
```

JSON out: `change_class`, `risk`, `included_suites` (with `cost_class` and a
reason each), `excluded_suites` (with reasons), `expected_paid_model_calls`,
`max_paid_budget`.

### Change classes

| Class | Example path | Needs paid evaluation? |
|---|---|---|
| `SECURITY_WRITE_AUTHORITY` | `agent/write_tools.py` | no |
| `PROMPT_MODEL_AGENT` | `agent/standing_interview.py` | **yes** |
| `CI_TESTING_INFRA` | `.github/workflows/ci.yml` | no |
| `JAVA_BACKEND` | `app/src/main/java/...` | no |
| `PYTHON_APP_LOGIC` | `agent/session_history.py` | no |
| `FRONTEND_JS` | `agent/web/workbench.js` | no |
| `STATIC_HTML_COPY` | `agent/web/home.html` | no |
| `CSS_VISUAL` | `agent/web/style.css` | no |
| `UNBOUNDED` | anything unrecognised | no |

A mixed change takes its **riskiest** class, never an average — a commit touching
a stylesheet *and* a prompt is a prompt change that happens to include a
stylesheet. Averaging would let the cheap half hide the expensive half.

### Two rules that are not negotiable

**A CSS / image / purely visual HTML change must never select a paid suite.**
Asserted on the real output of the selector, not promised in a comment.

**Failing closed means more free tests, never more spend.** An unbounded change
gets the full deterministic suite and still reports
`expected_paid_model_calls: 0`. Uncertainty is a reason for breadth, not for cost.

### The default UI/CSS plan

`quick` + affected frontend + affected Playwright functional + visual pack.
Expected paid calls: **0**.

---

## The paid-test guard

A paid suite runs only when **both** are true:

```
ALLOW_PAID_TESTS=1                 AND     PAID_TEST_BUDGET_USD=<a number > 0>
```

Either alone is refused, and the refusal happens **before any provider client is
constructed**. A malformed budget (`PAID_TEST_BUDGET_USD=abc`) is a refusal, not
a fallback — an unparseable ceiling is an unknown ceiling.

Why both: a single switch gets flipped once "just to see" and left on; a budget
alone can be set by a config file nobody reread. Requiring an explicit intent
*and* an explicit ceiling means the default state of a fresh shell, a fresh CI
runner and a fresh container is REFUSE — not because anything was configured, but
because nothing was.

Wired into `agent/si_recapture.py`, whose only previous protection was an
interactive `y/N` prompt that `--yes` bypasses — and `--yes` is exactly what a
script, a CI step or an agent passes.

It is an **authorization gate, not a budget enforcer**: it does not meter spend or
stop a suite mid-run. Metering is backlog, not implied here.

Sprint 17 never set `ALLOW_PAID_TESTS`. Its recorded paid application-model call
count is **0**.

---

## Visual regression — deliberately OFF

```
VISUAL_REGRESSION=1 npx playwright test e2e/visual-regression.spec.js
```

Not part of release-health gating, because the Owner has not accepted the
baseline. Gating on screenshots he has not seen would block every branch on a
diff nobody agreed to — and the branch that produced those screenshots is the one
asking for his opinion.

**Catches** unintended visual *change* — a stylesheet edit that moved a page
nobody was looking at. This is a real and common defect here: the Sprint 15
defects came from `style.css` and `dashboard.css`, which move every page at once.

**Cannot** tell whether a page looks good. A baseline of an ugly page is an ugly
baseline, faithfully defended.

Masking is element-scoped and per page: live timestamps, cost totals, run ids,
dynamic counters. A masked region is a region the suite no longer protects, so a
large mask buys stability by giving up the coverage the suite existed for.

`/usage` and `/dashboard` are captured to a bounded height because their length is
a function of how much real history the environment holds — 6,759px against
production and 69,830px against this laptop, which has 511 session rows to
production's 2. Capping is scoping, not masking.

**Promotion criterion:** the Owner accepts the baseline. Until then it stays off,
and that is a decision, not an oversight.

---

## Playwright functional — non-blocking, with a stated way out

Currently `continue-on-error: true` in CI, because it has no CI track record.

**Promotion criterion, already written into the workflow:** five consecutive green
runs on master, then remove `continue-on-error`. Red or flaky instead is a real
finding to fix, not a reason to delete the job.

Five specs fail on this laptop for environment reasons proven pre-existing in
Sprint 16 by stashing all changes and re-running against a clean tree: no ledger
data, no verified run, Customer App not running. They pass in production. Do not
chase them.

---

## SKIPPED is not PASSED

A gate that could not execute is reported SKIPPED with the real reason, never
folded into a pass. `agent/release_health.py` checks the real prerequisite —
`node` on PATH, a JDK, `node_modules/@playwright` present — rather than assuming
this machine has it. That is the exact trap that once made four Python modules
look hermetic because this laptop happened to hold a JDK and a ledger URL.

---

## Gap inventory

### Already strong

- **Deterministic Python breadth.** 812 blocking tests across 47 modules, with a
  runner that fails if zero ran, if the count falls below a floor, or if a
  `test_*.py` exists in `agent/` that is in no declared bucket.
- **Whole-file accounting.** A new test module cannot be silently unrun.
- **TIA drift ratchet.** A new Playwright spec that no source path maps to fails a
  test. This caught `design-standards.spec.js` after Sprint 16 left it
  unreachable, and it caught `visual-regression.spec.js` within an hour of that
  file being written.
- **Real infrastructure where it counts.** Real Postgres via Testcontainers, a
  real 4-process service topology (gating), real Redis-backed tests.
- **Security/authority boundaries.** Path traversal, symlinks, secret-name
  rejection, a write-path whitelist, hash-bound approvals, and a deterministic
  request contract — each with its own tests.
- **Cost.** Zero paid calls in the default path, enforced by a module rather than
  by a rule in a prompt.
- **Recruiter-facing invariants.** Nine pages × four widths for overflow and
  console errors; third-party font and tracker requests; accessible names; the
  public copy claims.

### Genuinely missing, and not pretended otherwise

- **An eval dataset of real failures.** The SI capture is 63 archived answers from
  one day. 20–50+ labelled real failures is backlog, not built.
- **Repeated stochastic trials.** Every answer-quality figure comes from 3 draws.
  Three draws cannot separate a fixed defect from a lucky one — which is exactly
  the ambiguity in the one known red monitor.
- **Adversarial evals.** No indirect prompt-injection suite, no poisoned-retrieval
  suite, no malicious-tool-output suite, no excessive-agency suite.
- **Output-honesty checks against the real trace.** Nothing verifies that what a
  run *says* it did matches what the tool events show it did.
- **LLM-as-judge.** Deliberately absent. Deterministic oracles only.
- **Accessibility beyond names and contrast.** No axe run. No keyboard-navigation
  suite.
- **Performance.** No Core Web Vitals, no bundle or latency budgets.
- **Browsers.** Chromium only. No Firefox, no WebKit, no real device.
- **Mutation testing.** Coverage is not measured and mutation score is not
  measured on the Python side.
- **Spend metering.** The paid guard authorizes; it does not meter against the
  declared ceiling.

### Intentionally deferred, with the reason

- **Visual baseline gating** — needs the Owner's acceptance of the baseline.
- **Playwright as a blocking CI gate** — needs five consecutive green runs.
- **OWASP dependency-check as a gate** — needs an NVD API key (a real NVD policy
  change) and then evidence it is not noisy.
- **Model-diversity review.** `qa-evaluator` is a second instance of the same
  model: an independent *evidence path*, not an independent mind. It catches
  unverified claims, skipped gates and absent observable effects. It will not
  catch a subtle logic error the implementer made, because same-family models
  share blind spots. That is a known residual risk, not a solved problem.

---

## The honest limit of everything above

Sprint 15 shipped 67 green UI guards on pages the Owner opened and disliked.
Sprint 16 shipped 86. Every guard was right about what it measured — alignment,
sizes, widths, characters per line, overflow, legibility floors — and not one of
them measured whether a page looks good.

Nothing in this document changes that. No guard here, present or planned, is
evidence that a page is pleasant to look at.
