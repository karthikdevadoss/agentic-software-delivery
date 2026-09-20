# AI-Native Testing & Verification: Research and Proposed Changes

**Purpose:** Real, deep research (Opus-model agent, 2026-09-20) into how an
AI coding agent can verify its own work rigorously enough to ship
high-quality, low-bug code quickly, **without a human catching the
mistakes** — a discipline distinct from traditional human-team QA, which
is designed around how *humans* get things wrong. Grounded in a real,
honest audit of 7 actual defects/mistakes from one session building this
project (2026-09-20, BL-007 through BL-015). Owner-requested; intended to
directly change this project's process (CLAUDE.md), not just be a
reference document. **No CLAUDE.md/qa-evaluator edits have been applied
yet — this file is the research and proposal; changes need explicit
Owner approval before being applied.**

---

## Part 1 — What the research actually says

### (a) Failure modes characteristic of LLM-generated code

The taxonomy work converges on a split that matters here: **hallucination-class** defects (the model invents or misremembers an interface) and **silent-semantic** defects (code compiles, runs, passes a happy-path test, and is wrong).

- *Beyond Functional Correctness* ([arXiv 2404.00971](https://arxiv.org/pdf/2404.00971)) finds API hallucination the most frequent detected category, and — critically — that the hardest class to detect is **syntactically correct, executable code with plausible output that doesn't match the specification**. These evade functional-correctness testing by construction.
- The evolving-API work ([arXiv 2604.09515](https://arxiv.org/html/2604.09515)) gives the distribution that maps most directly onto tonight's bugs: at adoption level, **omission 42.1%, old-API usage 16.4%**; at execution level, **incorrect parameters 26.6%, hallucinated behavior 16%**. Over half of execution failures are *incorrect usage of a real API*, not invented APIs.
- 2026 work names **"scaffolding hallucination"** — the model hallucinates the surrounding code needed to call a real target API (imports, attribute names, constants), the invented tokens being **"phantom symbols."** Package-level hallucination in a 576k-sample study: Python 5.2%, JavaScript 21.7%.
- Practitioner pattern-reporting ([Hannecke](https://medium.com/@michael.hannecke/three-patterns-where-agent-generated-code-quietly-fails-1b9735493468)) names three recurring quiet-failure patterns: **silent bypass of language guarantees, confident hallucination on thinly-represented APIs, and swallowed errors**. "Thinly represented" is the key variable — the model is most confident and most wrong on APIs with low training-corpus density.
- The infrastructure-layer point is consistent across sources ([Testkube](https://testkube.io/blog/system-level-testing-ai-generated-code)): AI-generated code **fails at the infrastructure layer, not the logic layer** — it is written without sight of real network policy, firewall behavior, RBAC, container runtime, or OS permission semantics, and **mocks hide exactly those constraints**.
- Population-level evidence that this is not anecdote: DORA/Faros 2026 telemetry across ~22,000 developers — **bugs per developer +54%, incidents per PR +242.7%**, PR size +51.3%, median review time +441%, 31% more PRs merged with no review at all. AI is an amplifier, not an improver, of whatever verification discipline already exists.
- And the reason self-report can't close the gap: METR's RCT found experienced developers were **19% slower with AI while believing they were 20% faster**. The perception/reality gap is measured, large, and in the wrong direction.

### (b) Self-verification by the agent itself

- [*Large Language Models Cannot Self-Correct Reasoning Yet*](https://arxiv.org/abs/2310.01798) (ICLR 2024) is the anchor: **intrinsic self-correction without external feedback frequently degrades performance.** The bottleneck is not fixing errors — models fix errors fine when told where they are — it is **autonomously detecting and localizing** them.
- Reflexion's numbers show the shape of the fix: 80% → 91% on a coding benchmark, but **only with execution feedback plus verbal reflection**; blind retry on clear error signals gave *zero* improvement. Execution/grounding is the differentiating ingredient, not more thinking.
- For the specific API-hallucination class, **grounding is quantitatively the fix and prompting is not**: documentation-augmented generation gives +8.20 absolute points on CloudAPIBench for GPT-4o and lifts low-frequency-API performance to 47.94% ([arXiv 2407.09726](https://arxiv.org/pdf/2407.09726)); MARIN reports **−67.5% / −73.6%** on hallucination rates versus a RAG baseline ([arXiv 2505.05057](https://arxiv.org/pdf/2505.05057)). Reported breakdown: ~65% of code-reference errors are phantom import paths or signatures, and the fix is grounding against the real artifact (language server, repo/installed package), not better prompts.

### (c) Multi-agent / adversarial verification — and its named failure mode

- [*Adversarial Review: Structured Disagreement for Grounded Agentic Code Review*](https://arxiv.org/abs/2608.18167) (2026): coder + reviewer + **critic that audits the review**. Highest pass rate on LiveCodeBench, beating a five-agent baseline with three agents. Its most useful contribution is the named failure mode: **false consensus** — agents agreeing without evidence — which is mitigated *only* by explicitly prompting for disagreement. Agreement is the default failure, not the success signal.
- [*Refute-or-Promote*](https://arxiv.org/pdf/2604.19049) (2026) exists because LLM defect discovery has unacceptable false-positive rates in production codebases — HackerOne paused the Internet Bug Bounty in March 2026 over AI-amplified submission volume.
- [*Property-Generated Solver*](https://arxiv.org/html/2506.18315v1) decouples a Generator and a Tester via property-based tests explicitly to break **"the cycle of self-deception," where the tests share the flaws of the code they validate.**
- Real-world measured effectiveness of a second AI reviewer, honestly: Greptile's own 2025 benchmark 82%/58%/44% catch rates; Martian's independent 2026 study put the best of ten tools at **51.2% F1**; the March 2026 c-CRAB benchmark puts top agents at **30–45% defect detection with 40–70% false positives**. A second agent is a real but partial filter with a real noise tax.

### (f) The risk of AI checking AI — the part that must not be oversold

- [*Great Models Think Alike and this Undermines AI Oversight*](https://www.alphaxiv.org/abs/2502.04313) is the decisive source. Using a chance-adjusted agreement metric (CAPA) over 130+ models: **as models get more capable, their errors get more correlated** — an "algorithmic monoculture." For LLM-as-judge it reports **κp = 0.84 between judge preference and student similarity, independent of actual accuracy** — judges measure similarity-to-self, not correctness. And weak-to-strong oversight gains correlate **r = −0.85** with model similarity: the more alike the checker, the less oversight value.
- Corroborating quantification: an inter-model error correlation of r = 0.77 means ~59% shared error variance, so a **three-model ensemble behaves like an effective ensemble of ~1.3**.
- Self-preference bias (NeurIPS 2024; [arXiv 2604.22891](https://arxiv.org/html/2604.22891v4)): LLM judges over-rate low-perplexity, own-style outputs, ranging −38% to +90% on ArenaHard; and [authorship labels alone](https://arxiv.org/html/2608.18091) shift judgments bidirectionally — self-labels inflate, other-labels deflate.

**The honest conclusion:** a second Claude instance reviewing a first Claude instance is *not* an independent mind. It is an **independent evidence path**. Its value comes from being structurally forbidden to accept the implementer's claims and required to re-execute real evidence — not from having different priors. Design the rule around that mechanism, and it will work; design it around "a second opinion," and correlated blind spots will make it theater.

### (e) Did the tests actually test anything

- LLM-generated suites achieve high line coverage with **mutation scores sometimes under 15%**; peak reported mutation score 0.546 versus 0.690 for human-written tests. MutGen: 53% → **89.5%** with mutation feedback in the loop; **unchanged after four iterations without it** — iteration alone buys nothing.
- The replicability study ([arXiv 2607.22880](https://arxiv.org/html/2607.22880v1)) is the sharpest finding: for **buggy** code inputs, coverage correlations become **uniformly weak** — coverage loses predictive power precisely when the code is wrong. Raw mutation score holds up far better (r = 0.863 inter-model). Its recommendation: directly evaluate whether tests detect bugs; don't trust proxy metrics.
- The failure mechanism to internalize: *"If the feature code contains a subtle logic bug, the LLM will generate test assertions that validate that exact bug as expected behaviour"* — **automated confirmation bias**. Dominant test smells: weak assertions (`assertNotNull` instead of a value), magic numbers, assertion roulette.

### (d) What real organizations concluded

Verification, not generation, is now the bottleneck (Cognition's Kevin Lee, via [TechNode](https://technode.global/2026/09/15/enterprise-ai-code-verification-cognition-kevin-lee/); [Futurum](https://futurumgroup.com/insights/why-ai-coding-agents-need-an-independent-review-layer-trust-not-output-is-the-bottleneck/) on the need for an independent review *layer*). 55.4% of enterprise decision-makers name AI agent reliability/hallucination management in production as a top challenge. Agent PRs that fail to merge are the ones that are larger, touch more files, and fail CI more — hence the push toward small, stacked, inspectable changes. And for the orchestration hazard specifically, the first-party answer is documented: Claude Code [worktree isolation](https://code.claude.com/docs/en/worktrees) and `isolation: "worktree"` on write-capable subagents.

---

## Part 2 — Seven real bugs from tonight, mapped to real categories

| # | Real defect | Named category | What would have caught it, specifically |
|---|---|---|---|
| **1b** | `mcp` SDK: 3-tuple vs 2-tuple, `serverInfo` vs `server_info` | **Phantom symbols / scaffolding hallucination** + **knowledge conflict from evolving APIs** (the model's prior is the TypeScript SDK's camelCase; installed Python SDK is snake_case) — the "incorrect parameters 26.6%" bucket | **Pre-generation grounding against the installed artifact**, not a test. `inspect.signature`, `dir()`, or reading the real file in `site-packages` *before* writing the client. Research: 65% of code-ref errors are phantom imports/signatures; grounding cuts hallucination 67–74%, prompting does not. Cost: one shell command. |
| **1a** | Gateway `.before(uri(...))` assumed to load-balance via Eureka | **Confident hallucination on a thinly-represented API** — functional WebMVC gateway routing is sparse in training data versus annotation/YAML config. Note: *signature grounding would NOT have caught this* — the method exists and compiles. It is a **semantic** API misuse | **Real multi-instance runtime exercise.** The only check that distinguishes "routes" from "load-balances across registered instances" is two real instances behind one real registry and a real request. This is a test-tier gap, not a grounding gap. |
| **2** | `@LoadBalanced RestClient.Builder` silently hijacked Eureka's client | **Implicit ambient-context coupling / silent bypass of framework guarantees.** Not hallucination — the API was used correctly. The model reasons locally and cannot see emergent whole-context effects. `@ConditionalOnMissingBean` matches by TYPE | **Blast-radius reclassification + full multi-service context boot.** A context-load smoke test passes here (the wrong bean injects *successfully*). The catching check is either an explicit bean-resolution assertion, or — cheaper and more general — treating *any new `@Bean` of a framework-owned auto-configured type* as CROSS_MODULE, forcing a real multi-service boot instead of a slice test. |
| **3a** | `prefer-ip-address` + local firewall broke self-connection | **Infrastructure-layer / environment-coupling failure** — mocks structurally hide network policy | **A named, scripted "real topology" tier**: registry + ≥2 real instances on the real machine, one real cross-call. Same catch as 1a — one tier closes both. |
| **3b** | JWT never propagated between services | **Cross-service contract gap with a happy-path-only oracle.** This is the automated-confirmation-bias pattern exactly: a mocked integration test returns 200 regardless of the `Authorization` header, and an LLM writing that test asserts 200 | **Assert on the outbound request, not the response** (`RecordedRequest.getHeader("Authorization")` / MockWebServer), **plus a negative test** that the downstream returns 401 with no credential. A positive-path assertion cannot fail on this bug; a negative one cannot pass. |
| **3c** | Unix exec bit lost copying on Windows | **Cross-platform toolchain divergence on a non-source artifact property** — nothing in the source is wrong; the *file metadata* is | **A zero-LLM STATIC gate**: `git ls-files --stage` asserting mode `100755` for anything with a `#!` shebang or under `scripts/`. Deterministic, ~10 lines, no model involved. V1 §G lists STATIC as "none formalized yet" — this is the first real inhabitant. |
| **3d** | Security config needing `HttpSecurity`; the one covering test always skipped locally | **The most serious of the seven: a green report that encodes "not run."** This is the verification-bottleneck / proxy-metric failure in its purest form — the metric said PASSED, the fact was NOT EXECUTED | **Skip accounting as a first-class verification output, failing closed on execution (not just selection).** `verify_change.py` already fails closed on *selection* ambiguity; it has no equivalent for a mandatory suite that was selected and then skipped. A HIGH/SECURITY change whose mandatory suite skipped must report `UNVERIFIED`, never `PASSED`. |
| **4** | Test asserted a POSIX error message on Windows | **Platform-assumption hallucination** (same family as 1b, lower stakes) — *and the system working correctly*: immediate execution feedback caught it. This is evidence **for** the existing discipline | Already caught. The missing half to make explicit: a new test must also be **observed failing** against the unfixed code, or you have an assertion that cannot fail (coverage doesn't predict fault detection on buggy code; only demonstrated kill-capability does). |
| **5** | Retro classified items "on target" by soft judgment instead of computing the ratio it had itself defined | **Substituting an LLM judgment for a deterministic computation the agent itself specified** — the self-correction verification bottleneck (models apply a rule when forced, but don't notice they skipped it), compounded by self-preference bias (soft-rubric self-assessment over-rates own work), and structurally identical to SpecBench's **reward-hacking gap**: scoring against the cheap visible proxy ("did anything obviously go wrong") instead of the stated specification | **Execute the number; never judge it.** `agent/backlog.py` already computes size-vs-actual. The rule is that the classification must be the script's real output pasted in, and the LLM may only interpret the computed table. |
| **6** | Write-capable background subagent in the shared working directory; its defensive `git stash` swept up concurrent work | **Agent-orchestration concurrency hazard**, not a code defect. Documented first-party answer exists | A hard rule, not a test: `isolation: "worktree"` on every Agent call whose agent can Write/Edit. Note the pleasing alignment — `qa-evaluator` is already `disallowedTools: Write, Edit`, so **independent verification is precisely the class of subagent that is safe to run in the shared tree**. |
| **7** | `qa-evaluator` exists, was invoked **zero** times across ~8–9 items | **The verification/trust gap**: writing is no longer the bottleneck, verifying is; and self-certification is measurably unreliable (METR: felt +20%, actually −19%; self-correction degrades without external feedback; self-preference bias) | Not a technique — a **structural rule about who gets the last word**. See §3.3's mandatory-invocation rule below, with an honest account of what a same-family evaluator can and cannot do. |

**One pattern worth naming across the whole audit:** of the seven, exactly **one** (1b) is classic "AI made up an API." Five are **composition and environment** failures — correct-in-isolation code that is wrong in the real system — and two are **process/meta** failures. That is the opposite of the popular framing of AI code defects, and it should drive where verification effort goes: not more unit tests, but *fewer mocks, more real topology, and no self-certification*.

---

## Part 3 — Concrete changes proposed (NOT YET APPLIED)

### 3.1 What the existing Testing Architecture is specifically missing

Ranked by (defects in Part 2 closed) ÷ (cost), building on V1/V2, duplicating nothing:

1. **Skip accounting + fail-closed-on-execution** in `verify_change.py`'s evidence JSON. Closes 3d. Highest value/cost ratio — V1 already has the fail-closed *concept* for selection; this extends it one step. Small.
2. **STATIC tier, first inhabitant** (file-mode/shebang/line-ending gate). Closes 3c. V1 §G explicitly has this tier empty. Small, zero-LLM, zero token cost forever.
3. **A "real topology" test tier** between Testcontainers-single-service and production: a scripted multi-instance boot (registry + ≥2 instances + one real authenticated cross-service call asserted at the far end). Closes 1a, 2, 3a, 3b. Medium — the single biggest structural gap, since four of tonight's seven live in the space this tier covers.
4. **Outbound-request assertion pattern** as a mandatory convention for any new service-to-service call. Closes 3b even without (3). Small.
5. **Seeded-mutation as the acceptance rule for a *new test*** — not a mutation-testing programme. V2 already proved the technique manually against `ContractPlanService` (two mutants, both killed). Making "observed to fail for the intended reason" the definition of a trusted test gets the mutation benefit at near-zero cost. Justified by the replicability study: coverage loses predictive power on buggy code; demonstrated kill-capability doesn't.
6. **Property-based testing, narrowly.** V2 already identified the correct first candidate: `ContractPlanService`'s idempotency invariant ("N identical enrollment requests → exactly 1 active plan, for any N"). Adopt jqwik **for registered invariants only**, listed in a new `docs/INVARIANT_REGISTRY.md`. PBT is the decoupling that breaks the self-deception cycle between code and its own tests. Do not generalize it further.
7. **Python TIA** (V1's known gap) matters more now: every deterministic gate above is Python, so the gates themselves would be outside impact analysis if this isn't closed.

### 3.2 Should independent AI review be mandatory? A calibrated yes, with a stated limit

**Yes for specific classes, no as a blanket rule** — the reasoning is about *mechanism*:

- What a second Claude **cannot** reliably do: catch subtle logic bugs the first Claude made. Error correlation rises with capability (CAPA), judges reward similarity-to-self at κp = 0.84 independent of accuracy, weak-to-strong oversight gains fall off at r = −0.85 with similarity, and an r = 0.77 correlation collapses a 3-model ensemble to an effective ~1.3. Real tools measure 30–50% detection at 40–70% false positives.
- What it **can** reliably do, and what `qa-evaluator` is already built for: refuse the implementer's claims and **re-execute the evidence**. Was the gate actually run? Did it actually skip? Is the requested observable effect actually present, or only an HTTP 200? Those are questions of *fact*, not judgment, and shared model priors don't degrade them.

So mandate it where the risk is **"the claim is unverified,"** not where the risk is "the logic might be subtly wrong."

**Cost:** one extra Opus-scale read-and-verify pass per gated item — real minutes, real tokens. Under the proposed gate it fires on roughly the top third of items, not all of them. Against that: tonight produced 7 defect classes across ~8–9 items with zero independent checks, and at least two (3d, 7) are precisely the "unverified claim" class the evaluator catches at near-100% rather than 40%. Instrument it rather than take it on faith (see §3.4).

### 3.3 Proposed new CLAUDE.md section (for Owner review, not yet applied)

Suggested placement: after "Stability / Execution Discipline."

```markdown
## AI-characteristic defect discipline
Traditional QA is designed around how humans get things wrong. These rules
are designed around how *this* agent actually got things wrong (see the
2026-09-20 audit, docs/AI_NATIVE_TESTING_RESEARCH.md). Research basis: LLM
self-correction degrades without external feedback; same-family models
share correlated blind spots; coverage does not predict fault detection on
buggy code.

- **Never write against a remembered API.** Before calling any external
  library/framework API this repository does not already use somewhere,
  resolve the real symbol against the *actually installed artifact* and
  record the real output: Python -- `inspect.signature` / `dir()` / the
  real file under site-packages; Java -- the resolved dependency's real
  class or version-exact docs matching `pom.xml`, never generic docs.
  Grounding, not prompting, is what fixes phantom symbols/signatures. When
  what's uncertain is an API's *semantics* (routing, load balancing,
  transaction/filter ordering), a correct signature proves nothing -- it
  requires a real runtime exercise before it counts as verified.
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
- **SKIPPED is not PASSED.** Every verification report states pass/fail/
  skip counts. A HIGH or CRITICAL change whose mandatory suite was skipped
  (Docker absent, profile absent, tag excluded) is `UNVERIFIED` -- never
  `PASSED` -- and must name which gate did not execute and where it will.
- **A new test is not trusted until it has been observed failing.** Every
  new regression/acceptance test is run once against the unfixed code or a
  deliberately seeded mutation, observed to FAIL for the intended reason,
  and that real failure output recorded next to the pass. A passing new
  test proves nothing on its own.
- **Non-source artifact properties get a deterministic gate, never a
  judgment.** File mode bits, shebangs, line endings, encoding: a zero-LLM
  script in the STATIC tier. Minimum: every file with a `#!` shebang or
  under `scripts/` is mode 100755 in `git ls-files --stage`.
- **Any rule this project states as a number must be computed, not
  judged.** Tolerance ratios, size-vs-actual, coverage/mutation
  thresholds, cost-per-verified-outcome: the verdict is the real output of
  the real script (e.g. `agent/backlog.py`), quoted. The agent may
  interpret a computed table; it may not produce the classification. A
  narrative classification of a numeric rule is invalid by construction.
- **Write-capable subagents run in an isolated git worktree.** Pass
  `isolation: "worktree"` on every Agent call whose agent can Write/Edit.
  Read-only agents (Explore, qa-evaluator) may share the working directory
  because they cannot mutate it. Never run a write-capable background
  agent in the directory the main session is editing.
- **Independent evaluation is mandatory before "done" when any of these
  hold** -- invoke the `qa-evaluator` subagent:
  1. change classification is HIGH/CRITICAL, or blast radius is
     CROSS_MODULE/SYSTEM;
  2. acceptance criteria include the SECURITY or PRODUCTION category;
  3. the work was performed by a background/autonomous subagent -- i.e.
     the only account of what happened is another agent's self-report;
  4. any mandatory gate was skipped, degraded, or could not run locally;
  5. the backlog item is sized LARGE or XLARGE.
  May be skipped for SMALL/MEDIUM LOW-risk items where the implementer ran
  the real deterministic gate and the evidence JSON exists -- there the
  evidence is already independent of the claim, because an exit code is
  not an opinion.
  **Honest limit, stated so it is not oversold:** a second instance of the
  same model is not an independent mind, it is an independent *evidence
  path*. Expect it to catch unverified claims, skipped gates, and absent
  observable effects; do not expect it to catch subtle logic errors the
  implementer made, because same-family models share blind spots. Genuine
  model-diversity review would require a different model family or the
  Owner; neither is currently in the loop, and that is a known residual
  risk, not a solved problem.
- **The implementer never gets the last word on its own production
  success.** This already exists as a rule inside qa-evaluator; it belongs
  here too, because tonight it existed and was never invoked.
```

### 3.4 Two supporting changes outside CLAUDE.md (also not yet applied)

**Amend `.claude/agents/qa-evaluator.md`** with a disagreement mandate and an input restriction:

- **Structured disagreement.** The Adversarial Review result is that *false consensus* — agents agreeing without evidence — is the dominant multi-agent failure, mitigated only by explicitly prompting for disagreement. Require the evaluator to output, per acceptance criterion, the exact command it ran and the real output; and to name **at least one thing it could not confirm**. `UNKNOWN` is already a first-class verdict — make stating the residual mandatory rather than optional.
- **Withhold the implementer's narrative.** Hand the evaluator the Acceptance Contract, the diff, and the run ids — not the implementer's summary. Authorship labels alone shift LLM judgments bidirectionally; there is no reason to hand a known bias a free input.

**Instrument the mandate rather than believing it.** `verify_change.py`'s per-run evidence JSON explicitly lacks cross-run aggregation. Add two fields — `independent_evaluation: {invoked, verdict, findings_count}` and `escaped_defects` (defects found after the item was called done) — so that after ten or fifteen items the project has a *real measured* cost-per-verified-outcome for independent review, and the mandatory-invocation gate can be widened or narrowed on evidence instead of on this document alone.

### 3.5 Sizing, per the project's own gate (not yet added to the backlog)

Suggested backlog entries, sized with the existing rubric: skip-accounting/fail-closed **SMALL**; STATIC file-mode gate **SMALL**; outbound-request assertion convention **SMALL**; CLAUDE.md + qa-evaluator amendments **SMALL**; evidence-JSON instrumentation **SMALL**; real-topology multi-instance tier **LARGE** (first integration of its kind in this repo — the rubric's own rule forces LARGE); jqwik invariant adoption **MEDIUM**; Python TIA **MEDIUM**.

## Sources

[Beyond Functional Correctness (arXiv 2404.00971)](https://arxiv.org/pdf/2404.00971) · [When LLMs Lag Behind: Knowledge Conflicts from Evolving APIs (arXiv 2604.09515)](https://arxiv.org/html/2604.09515) · [Three Patterns Where Agent-Generated Code Quietly Fails](https://medium.com/@michael.hannecke/three-patterns-where-agent-generated-code-quietly-fails-1b9735493468) · [Why Unit Tests Fail AI-Generated Code (Testkube)](https://testkube.io/blog/system-level-testing-ai-generated-code) · [A Survey of Bugs in AI-Generated Code (arXiv 2512.05239)](https://arxiv.org/pdf/2512.05239) · [DORA 2026 / Faros telemetry](https://www.faros.ai/blog/key-takeaways-from-the-dora-report-2025) · [DORA State of AI-assisted Software Development](https://dora.dev/dora-report-2025/) · [METR early-2025 developer productivity RCT](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/) · [LLMs Cannot Self-Correct Reasoning Yet (arXiv 2310.01798)](https://arxiv.org/abs/2310.01798) · [When Can LLMs Actually Correct Their Own Mistakes? (arXiv 2406.01297)](https://arxiv.org/html/2406.01297v3) · [Agent Self-Correction: Reflexion to PRM](https://zylos.ai/zh/research/2026-05-12-agent-self-correction-reflexion-to-prm/) · [On Mitigating Code LLM Hallucinations with API Documentation (arXiv 2407.09726)](https://arxiv.org/pdf/2407.09726) · [MARIN: Hierarchical Dependency-Aware API Hallucination Mitigation (arXiv 2505.05057)](https://arxiv.org/pdf/2505.05057) · [Adversarial Review (arXiv 2608.18167)](https://arxiv.org/abs/2608.18167) · [Refute-or-Promote (arXiv 2604.19049)](https://arxiv.org/pdf/2604.19049) · [Property-Generated Solver (arXiv 2506.18315)](https://arxiv.org/html/2506.18315v1) · [Agentic Property-Based Testing (arXiv 2510.09907)](https://arxiv.org/pdf/2510.09907) · [Great Models Think Alike and this Undermines AI Oversight (arXiv 2502.04313)](https://www.alphaxiv.org/abs/2502.04313) · [Correlated Errors in LLMs (arXiv 2506.07962)](https://www.alphaxiv.org/abs/2506.07962) · [Quantifying and Mitigating Self-Preference Bias of LLM Judges (arXiv 2604.22891)](https://arxiv.org/html/2604.22891v4) · [Self- and Other-Labels Induce Bidirectional Bias in LLM Judges (arXiv 2608.18091)](https://arxiv.org/html/2608.18091) · [Do Coverage and Mutation Scores of LLM-Generated Test Suites Correlate with Effectiveness? (arXiv 2607.22880)](https://arxiv.org/html/2607.22880v1) · [Mutation Testing for AI-Generated Code (Augment)](https://www.augmentcode.com/guides/mutation-testing-ai-generated-code) · [AI-Generated Tests That Pass But Don't Assert Anything](https://getautonoma.com/blog/ai-generated-tests-pass-but-dont-assert) · [SpecBench: Measuring Reward Hacking in Long-Horizon Coding Agents (arXiv 2605.21384)](https://arxiv.org/html/2605.21384v1) · [Why AI code verification is becoming the new engineering bottleneck](https://technode.global/2026/09/15/enterprise-ai-code-verification-cognition-kevin-lee/) · [Why AI Coding Agents Need an Independent Review Layer (Futurum)](https://futurumgroup.com/insights/why-ai-coding-agents-need-an-independent-review-layer-trust-not-output-is-the-bottleneck/) · [Enterprise AI coding agent deployment in 2026 (Northflank)](https://northflank.com/blog/enterprise-ai-coding-agent-deployment) · [AI Code Review Benchmarks (Greptile)](https://www.greptile.com/benchmarks) · [Best AI PR Review Tools 2026, benchmark-backed](https://screencli.sh/blog/best-ai-pr-review-tools-2026) · [Claude Code worktrees documentation](https://code.claude.com/docs/en/worktrees)
