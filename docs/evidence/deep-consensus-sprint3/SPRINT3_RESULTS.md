# Deep Consensus — Sprint 3 results

Branch `deep-consensus-sprint3`. Not pushed, not deployed, no tunnel, no
ChatGPT connection.

Goal: run Deep Consensus on subscriptions Karthik already pays for, with no
mandatory pay-per-call API spend. **Claude Max works. ChatGPT/Codex is
blocked on a login only he can do.**

---

## 1. Spend

| | |
|---|---|
| **Paid API calls** | **0** |
| **Subscription model turns used** | **~9** (Claude Max) |
| Metered spend incurred | **$0.00** |

No `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` or `XAI_API_KEY` was used for any
model call. The Sprint 2 dollar ledger was not touched, because this sprint
spends subscription turns rather than money — the governor's usage control
here is a **provider-turn cap (max 4 per review)**, not a dollar budget.

**On the cost figure the CLI prints.** `claude -p --output-format json`
reports `total_cost_usd` (observed: `0.141574` on a trivial probe) with
per-model `costBasis: "list"` *even on a Max subscription*. That is a
list-price equivalent, not money charged. It is recorded as
`provider_notional_cost_usd` with `billed_cost =
NOT_APPLICABLE_SUBSCRIPTION`, and where the basis cannot be established the
answer is `UNKNOWN` — never zero.

---

## 2. Claude transport — WORKS

| | |
|---|---|
| CLI version | `2.1.268 (Claude Code)` |
| Auth proof | `claude auth status --json` → `{"loggedIn": true, "authMethod": "claude.ai", "apiProvider": "firstParty", "subscriptionType": "max"}` |
| Billing | **SUBSCRIPTION** (verified, not assumed) |
| Requested model | `claude-sonnet-5` (pinned) |
| Reported model | `claude-sonnet-5` — read back from the response, not assumed |
| Headless | `claude -p --output-format json`, prompt on **stdin** |
| Tool restriction | `--restricted` (removes Bash/PowerShell/REPL/WebFetch, ignores user/project/local settings) + `--strict-mcp-config` + `--no-session-persistence` + explicit `--disallowed-tools` |
| API key stripped | **yes**, proven below |

**`--bare` is deliberately never used.** Its own help text says that under
`--bare` "Anthropic auth is strictly ANTHROPIC_API_KEY or apiKeyHelper ...
(OAuth and keychain are never read)". It is the single flag that would turn
this into a metered call, and a test asserts it is absent from the argv.

### The strongest single piece of no-paid-fallback evidence

A real `claude -p` call was made **with an invalid fake `ANTHROPIC_API_KEY`
present in the parent environment**. It succeeded, and `claude auth status`
still reported `authMethod: claude.ai`. A call that had actually used that
fake key would have failed authentication. So the child demonstrably did not
use it.

---

## 3. Codex / ChatGPT transport — BLOCKED

| | |
|---|---|
| CLI version | `codex-cli 0.159.3` (installed this sprint) |
| Login state | **Not logged in** |
| `codex doctor` | `auth mode = none`, `auth file = C:\Users\Hemapriya\.codex\auth.json`, `reachability mode = ChatGPT auth` |
| Result | **`BLOCKED_SUBSCRIPTION_TRANSPORT`** |

**Owner action required — one command:**

```
codex login
```

Plain browser flow. **Not** `--with-api-key`, which exists and is exactly
what must never be used: it is metered OpenAI API billing, not the ChatGPT
subscription.

The adapter is written and its argv is tested, against the **real verified
CLI surface** (`codex exec --json -s read-only --ephemeral
--ignore-user-config --ignore-rules --skip-git-repo-check -C <tempdir> -o
<file> -`, prompt on stdin). `--ignore-user-config`'s own help confirms
"auth still uses CODEX_HOME", so config is skipped without breaking
subscription auth. It has never been exercised against a live ChatGPT
account, and that is stated rather than implied.

**Grok: `GROK_P1_DEFERRED`** — not attempted. P1, and never via
`XAI_API_KEY`.

---

## 4. The no-paid-fallback invariant — three layers

1. **Preflight.** Subscription auth must be *proven* before dispatch. An
   account that merely *declares* `billing=SUBSCRIPTION` is not eligible;
   `eligible_for_p0` requires declared subscription **and** verified
   subscription auth. Anything unrecognised returns `UNVERIFIED`, which
   blocks — defaulting to "probably subscription" is how an unknown billing
   route gets used.
2. **Child environment.** Built from a 30-entry **allowlist**, not a
   denylist, so a billing variable invented tomorrow is excluded
   automatically. A denylist *and* a regex family (`API_?KEY`,
   `ACCESS_?TOKEN`, `BASE_?URL`, `^AWS_`, `^AZURE_`, ...) then **assert**
   nothing billing-shaped survived, and refuse to dispatch if it did.
   Karthik's machine keys stay exactly where they are; the child is
   sanitised.
3. **Post-run.** A result whose metadata shows metered infrastructure
   (`provider: bedrock|vertex|foundry`) raises `BILLING_VIOLATION`, the
   result is **discarded**, that provider is stopped, and it is never
   retried through an API.

**Honest limit of layer 3:** neither CLI exposes a field saying "this call
was billed to an API key". So the guarantee really rests on layers 1 and 2.
Layer 3 can only catch a redirect onto metered infrastructure. That is a real
gap, stated rather than covered with a check that looks stronger than it is.

Tested with **real injected keys** (`ANTHROPIC_API_KEY`,
`ANTHROPIC_AUTH_TOKEN`, `OPENAI_API_KEY`, `CODEX_API_KEY`, `XAI_API_KEY`,
`ANTHROPIC_BASE_URL`, `CLAUDE_CODE_USE_BEDROCK`, `AWS_ACCESS_KEY_ID`) placed
in the parent environment and proven absent from the child.

---

## 5. CLI security envelope

These CLIs are agents. Every invocation is reduced to a constrained
inference call:

| Property | Mechanism | Proven by |
|---|---|---|
| fresh temp workdir outside the repo | `tempfile.mkdtemp` per call | a child reports its cwd; the repo path is absent |
| argv **list**, never a shell string | a string argv raises `TypeError` | asserted |
| prompt via **stdin** | never in argv | a prompt containing `" && echo PWNED; rm -rf /; $(whoami)` round-trips inertly |
| allowlisted env | §4 | injected keys absent |
| timeout | `communicate(timeout=)` | a 60s sleep is killed in ~2s |
| **process-tree** kill | `taskkill /T /F` first, then `kill()` | a *grandchild* pid is confirmed dead |
| output cap | byte cap on stdout | 200 KB output truncated to 5 KB |
| tool restriction | verified CLI flags | argv asserted |

Terminating only the launched CLI leaves its node/worker children alive on
Windows — they keep the socket open and keep consuming the subscription
turn. `taskkill /T` is the primary mechanism for that reason, not a fallback.

---

## 6. The minimum-call governor

| Path | Calls | Verified |
|---|---|---|
| no material conflict | **exactly 2** | asserted exactly, not "at most" |
| material conflict | **exactly 4** | both models challenged, in parallel |
| hard maximum | **4** | a 5th call is never made, even when the conflict stands |

Stage 2 (local claim comparison) costs **0 model calls**. On the agreement
path neither model is asked to agree again — the thing Sprint 2 spent a whole
round on.

The challenge carries **only disputed material**: a test asserts the agreed
subject is absent from the challenge prompt while the disputed one is
present.

**Both models are challenged, not only the claim's author.** The 3-call
author-first variant is cheaper and is recorded as a backlog experiment, not
deleted — but challenging only the author puts the pressure on exactly one
party, which invites one-sided concession.

---

## 7. Claim-level convergence

Whole-answer text hashing is **no longer** the convergence rule; hashes are
kept for audit identity only. A test confirms two textually unrelated
answers can converge, because convergence is now about **claims**.

Claim states: `AGREED`, `CORRECTED_AND_AGREED`, `UNRESOLVED`, `UNKNOWN`,
`CONTRADICTED`. Each is tested, including the three that matter most:

- **mutual concession is UNRESOLVED, not agreement.** If both models concede
  to each other, they have swapped positions and settled nothing. A naive
  implementation would call that agreement.
- **a missing or out-of-vocabulary decision is UNRESOLVED.** Silence must
  not read as agreement.
- **`UNKNOWN` never becomes an invented value**, and never adopts the other
  model's value by default. One model not knowing does not make the other
  right.

`has_unknowns` and `unknown_claims` are always present, because `CONVERGED`
must never be read as "all questions answered".

**A consequence worth knowing:** a material claim only *one* model made
(`ONE_SIDED`) is neither AGREED nor CORRECTED, so it **blocks** `CONVERGED`.
That is conservative and spec-compliant — a claim one model never addressed
is not an agreed claim — and §9 shows it doing real work.

---

## 8. Live evidence: the pipeline caught the system's own Sprint 1 error

Case `S3-1`, both workers real Anthropic subscription models. **Same family —
not a cross-family run.**

| Worker | Lock mode claimed | Correct? |
|---|---|---|
| `claude-sonnet-5` | **SHARE** | ✅ matches primary source |
| `claude-haiku-4-5` | **ACCESS EXCLUSIVE**, blocks reads AND writes | ❌ — *the exact Sprint 1 error* |

Ground truth (recorded **before** the run, from
<https://www.postgresql.org/docs/current/explicit-locking.html>): SHARE,
acquired by `CREATE INDEX` without `CONCURRENTLY`; reads continue, writes
block.

What the system did: detected the conflict on `CREATE INDEX lock mode`,
spent its 4 turns, challenged both — **both maintained** — and returned
`UNRESOLVED` with the dispute surfaced.

**Sprint 1 published this falsehood as fact. Sprint 3 refused to.** That is
the mechanism working, and it is the single most useful result of the sprint.

**Two honest caveats.** It did not say *which* model was right — by design,
the local engine must never adjudicate facts — so the user gets a flagged
dispute rather than the answer. And haiku held a demonstrably wrong position
under direct challenge, which is a measurable stubbornness signal worth
feeding into the self-advocacy eval.

---

## 9. Live evidence: the pairing is the weak link (the real finding)

Case `S3-3`, Spring Boot Java baseline. Ground truth (recorded first, from
<https://docs.spring.io/spring-boot/system-requirements.html>): Spring Boot
**4.1.1**, minimum **Java 17**, compatible up to **Java 26**.

Both models were **stale** — A said Spring Boot 3.5.x / max Java 23, B said
3.3 / max Java 21. Neither is current. More importantly:

```
status: UNRESOLVED   stop_reason: no_material_disagreement_early_stop
turns: 2/4   agreed: 0   conflicts: 0   one-sided: 7
```

**The pipeline detected neither the agreement nor the disagreement**, because
the two models decomposed the question into differently-named subjects:

| Slot A subject | Slot B subject | Same thing? |
|---|---|---|
| `min_java_version` = "Java 17" | `Spring Boot 3.3 minimum Java version` = "Java 17" | yes — **agreement missed** |
| `max_java_version_documented` = "Java 23" | `Spring Boot 3.3 maximum tested Java version` = "Java 21" | yes — **conflict missed** |

Subject strings diverged below the 0.60 lexical overlap threshold, so
everything fell through to `ONE_SIDED`, the governor saw no material conflict
and early-stopped at 2 calls.

**This is the most important engineering finding of Sprint 3.** The
minimum-call governor is only as good as the pairing, and lexical
subject-name matching is too weak when two models name the same thing
differently. It fails in both directions: it under-reports agreement *and*
it misses real conflicts — the second being the dangerous one, because a
missed conflict looks exactly like "nothing to discuss".

The conservative design saved the output anyway: because one-sided material
claims block `CONVERGED` (§7), the run returned `UNRESOLVED` rather than a
false convergence. The safety net held; the detector did not.

**This is precisely what P1 local embeddings for claim PAIRING addresses**,
and it is now the next technical blocker rather than a nice-to-have. Note it
is pairing only — embeddings must never decide whether claims *agree*.

---

## 10. Tests

| Suite | Command | Result |
|---|---|---|
| Sprint 3 | `python deep_consensus/test_sprint3.py` | **90 passed** |
| Sprint 2 | `python deep_consensus/test_sprint2.py` | **70 passed** |
| Sprint 1 | `python deep_consensus/test_deep_consensus.py` | **59 passed** |
| Agent CI | `python agent/ci_python_tests.py` | **831 tests, 0 failures, 0 errors, exit 0 — PASS** |

Run **last, on a deliberately idle tree**, as the Phase-0 carry-over
required. That mattered: the same suite reported a spurious
`test_rag_index` failure twice before, both times because a file was
edited while it was building a repository index. The fix was the
discipline, now recorded in `docs/LESSONS.md`, not a change to the test.

The one RED is the pre-existing **non-blocking** quality monitor
(`test_si_answer_quality_monitor`, documented KNOWN RED, SI-19/BL-149).
It does not set the exit code and is unrelated to this sprint.

Sprint 3 begins and ends from a clean regression baseline.

Concurrency is proven with a `threading.Barrier(2)` plus a **sequential
control** that confirms sequential execution genuinely *fails* the barrier,
so the proof cannot pass for the wrong reason.

### Mutation testing — six guards, each observed failing

| Mutation | Detected by | Verdict |
|---|---|---|
| API-key stripping removed (child inherits parent env) | 3 tests | CAUGHT |
| leak assertion neutered | 4 tests | CAUGHT |
| eligibility ignores whether auth was proven | 5 tests | CAUGHT |
| conflict detection disabled (`values_agree` → True) | 21 tests | CAUGHT |
| 4-call hard cap removed | 1 test | CAUGHT |
| unresolved no longer blocks convergence | 7 tests | CAUGHT |

Tree restored clean after each.

### Two real bugs the tests found in my own code

1. **`"40,000,000"` canonicalised to `40`.** `normalize_text` turns
   punctuation into spaces, so the number regex matched only the leading
   group — a silent factor-of-a-million error that would have reported two
   models as disagreeing when they said the same thing. Fixed by collapsing
   thousands separators on the raw value.
2. **`3.2` and `3.3` compared EQUAL.** Same root cause, worse consequence:
   `.` became a space, the version regex matched only `3`, and two different
   framework versions were reported as agreeing — exactly the error class
   this product exists to catch. **The suite did not catch this**, because I
   had only written the matching case. The negative case now exists.

---

## 11. MCP

Public surface unchanged: **exactly one tool, `deep_review`.** No internal
stage is exposed (`deep_review_claims` → "Unknown tool").

| | |
|---|---|
| **MCP_PROTOCOL** | **PASS** — raw v3 probe, 11/11 asserted checks, in mock mode and again over the real subscription transport |
| **MCP_INSPECTOR_CLI** | **ENVIRONMENTAL_FAILURE** on the invalid-request path — same libuv `UV_HANDLE_CLOSING` teardown crash as Sprints 1–2, after printing correct output |

A separate v3 probe was written rather than loosening the Sprint 2 probe,
which remains the evidence for Sprint 2.

---

## 12. Known limitations

1. **No cross-family run.** `cross_family_real = false` everywhere. One
   `codex login` away.
2. **Claim pairing is the weak link** (§9) — misses both agreement and
   conflict when subject names diverge. Now the top blocker.
3. **The Codex adapter has never run live.** Written against the verified
   CLI surface, argv tested, model/token extraction written defensively
   against an undocumented JSONL schema with `UNKNOWN` fallbacks — but
   unexercised.
4. **Layer 3 of the billing guard is weak** by necessity (§4).
5. **Both models were stale on the version case**, and the system cannot
   detect a shared error — the same-wrong-answer limitation, which is why
   every result carries *"Independent model agreement is not external
   verification."*
6. **Smoke evaluation is 2 cases run of 5 recorded**, same-family, N=1. The
   correctness-per-family and errors-caught-by-second-family metrics are
   deliberately **not computed**, because with one family they would measure
   something other than their names.
7. **Case `S3-4`'s ground truth is a design judgement**, graded against this
   project's own position; `S3-5` cites a secondary source. Both flagged in
   the case file.
8. **All evidence is `MODEL_ONLY`.** Cited sources are stored and marked
   `UNVERIFIED`. No web verification.
9. **No second challenge round**, so a conflict the single round cannot
   settle stays `UNRESOLVED` by design.


---

# ADDENDUM — Sprint 3 FINAL (Grok landed, status PASS)

Written after the SuperGrok subscription transport became available. The
sections above were written while Codex was the intended Provider B and
Grok did not exist in the run; this addendum supersedes their "no
cross-family run" conclusion.

## Sprint 3 FINAL STATUS: **PASS**

| PASS condition | Result |
|---|---|
| Claude subscription transport real | ✅ `authMethod=claude.ai`, `subscriptionType=max` |
| Grok subscription transport real | ✅ `auth_mode=oidc`, issuer `https://auth.x.ai` |
| `cross_family_real=true` | ✅ 8 cross-family runs (anthropic × xai) |
| zero paid API calls | ✅ 0 |
| no-paid-fallback proven | ✅ both transports, with fake keys injected |
| sealed initial answers proven | ✅ tests + live |
| claim-level comparison working | ✅ MATCH/AGREED and CORRECTED_AND_AGREED live |
| disagreement path working | ✅ S3-2 cross-family, 4 turns, 2 corrected claims |
| unresolved claims visible | ✅ |
| no material unresolved labelled CONVERGED | ✅ |
| real smoke cases executed | ✅ 4 cross-family cases |
| tests green | ✅ 98 + 70 + 59 |

## Grok transport — verified, not assumed

| | |
|---|---|
| CLI | `grok 1.0.46 (2765805b9442)`, `@xai-official/grok` |
| Transport | `GROK_SUBSCRIPTION_CLI` |
| Billing | `SUBSCRIPTION` |
| Requested model | `grok-4.6` |
| **Reported model** | **`grok-4.6-build`** — they differ, and both are recorded |
| Headless | `grok --prompt-file <file> --output-format json` |
| Restriction | `--max-turns 3 --disable-web-search --no-subagents --no-plan --verbatim --cwd <tempdir>` |
| Structured output | `--json-schema <inline>`, response read from `structuredOutput` |

**Two independent auth proofs:**

1. `grok models` prints *"You are logged in with grok.com."* and succeeds
   **with `XAI_API_KEY` stripped from the child** and an **invalid fake**
   `XAI_API_KEY` sitting in the parent. A call using that key would have
   failed.
2. `~/.grok/auth.json` records `auth_mode: "oidc"`, `oidc_issuer:
   "https://auth.x.ai"`, `principal_type: "User"`, `refresh_token` present.
   An API-key credential has none of those. Only non-secret discriminator
   fields are read — never the `key` or `refresh_token` values.

**Cost: `billed_cost = UNKNOWN`, deliberately different from Claude.** The
Grok envelope carries `total_cost_usd` (observed `0.01206116`) but **no
`costBasis` field**. Claude's says `costBasis: "list"`, which is positive
evidence of a list-price equivalent, so Claude gets
`NOT_APPLICABLE_SUBSCRIPTION`. Grok has no such evidence, and OIDC auth does
not establish how xAI meters a subscription. Treating the two identically
would be inventing evidence for one of them. Neither is ever recorded as
money charged.

**Not used, because not verifiable:** `--sandbox <PROFILE>` (profile enum
not discoverable), `--disallowed-tools` (tool-name enum not discoverable),
`--no-auto-update` (**absent from this version's `--help`** — not used
despite being reported as working, because an undocumented flag this build
may be silently ignoring is not something to depend on).

## Three real defects found and fixed during the Grok integration

**1. `--max-turns 1` captured only Grok's preamble.** Grok narrates intent
on turn 1 and acts on turn 2, so a 1-turn cap returned *"I'll confirm the
PostgreSQL lock mode ... from the official docs"* and nothing else. A
genuine per-CLI behavioural difference from Claude, not a prompt problem.
Fixed: `--max-turns 3`, tools still off.

**2. Unconstrained output was unparseable.** Fixed with the CLI's own
`--json-schema` (inline JSON — a file path exits 1), and the result is read
from the CLI's parsed `structuredOutput` rather than re-parsed by us. The
schema is the only argv-borne content and it is a constant **we** author;
the user's question still goes via `--prompt-file`, so the no-injection
property is unaffected.

**3. Grok burned turns narrating lookups it could not perform.** On
"what is the current version" and "review this plan", it answered with
*"Looking up the current Spring Boot release..."* and no claims — twice.
Fixed in the shared instruction: tools are disabled, answer from your own
knowledge, and if you cannot establish a value, the correct output is
`UNKNOWN` rather than an attempt to go and look. After the fix both cases
produced real claims.

## THE pairing fix — the Sprint 3 blocker, now partly resolved

Three live cross-family runs paired **nothing**. The mechanical cause was
not semantics; it was tokenisation. `normalize_text` keeps `_` and `-` as
word characters, so `spring_boot_min_java_version` and
`self-invocation-transactional` were each a **single token** and could never
overlap with anything.

Three small, deterministic, truth-agnostic changes:

1. **Split subjects on `_ - / .`** — subjects are machine-ish identifiers as
   often as prose.
2. **Containment instead of symmetric overlap** — `|A∩B| / min(|A|,|B|)`.
   Two models describe the same subject at different lengths (`lock_mode`
   vs `plain CREATE INDEX table lock mode`); dividing by the longer set
   punishes that and refuses the pair.
3. **Pair within a type GROUP** — `{FACT, REASONING, RECOMMENDATION}` and
   `{NUMBER, VERSION}`. Models routinely type the same assertion
   differently; requiring an exact match meant those never paired. Across
   groups is still refused.

Plus crude, deterministic de-pluralisation (`reads` ≡ `read`).

| Real observed subject pair | Score | Pairs? |
|---|---|---|
| `lock_mode` ↔ `plain CREATE INDEX table lock mode` | 1.00 | ✅ |
| `spring_boot_min_java_version` ↔ `Spring Boot 3.3 minimum Java version` | 0.80 | ✅ |
| `self-invocation-transactional` ↔ `inner @Transactional self-call starts transaction` | 0.67 | ✅ |
| `SHARE lock read behavior` ↔ `CREATE INDEX vs reads` | 0.33 | ❌ residual |

And **no false pairs**: four unrelated subject pairs all score `0.00`.

**The residual is recorded, not hacked around.** The 0.33 case shares one
token. The threshold is deliberately **not** lowered to catch it, because
0.33 is close to noise and would start manufacturing false pairs. That case
needs semantics and is reported as a limitation. A test asserts it still
fails, so the honesty is enforced.

Effect on real runs: S3-2 went from **0 pairs** to **1 agreed + 2
CORRECTED_AND_AGREED**, exercising the full 4-turn cross-family
disagreement path for the first time.

## Cross-family smoke results (4 cases, ground truth recorded first)

| Case | Status | Turns | Outcome |
|---|---|---|---|
| S3-1 CREATE INDEX | UNRESOLVED | 2 | Both families **correct** (SHARE, reads allowed). Lock-mode claim MATCHED → AGREED. 3 material one-sided claims blocked CONVERGED. |
| S3-2 Spring self-invocation | UNRESOLVED | **4** | Both **correct**. 1 AGREED + **2 CORRECTED_AND_AGREED** — the disagreement path working live, cross-family. |
| S3-3 Spring Boot Java baseline | **CONVERGED** | 2 | 3 AGREED, **2 UNKNOWN surfaced**. ⚠️ see below. |
| S3-4 agent-plan review | UNRESOLVED | 2 | Both identified the host-controlled-skippable flaw; prose subjects did not pair. |

**⚠️ S3-3 is the most important result in the sprint, and it is a negative
one.** Both families CONVERGED on **Spring Boot 3.5, Java 17–24**. Ground
truth (fetched from docs.spring.io *before* the run) is **Spring Boot 4.1.1,
Java 17–26**. Minimum Java 17 was right; the release and the ceiling were
both **stale**. Two independent model families agreed, confidently, on an
out-of-date fact — and Deep Consensus cannot detect an error both models
share.

This is exactly the same-wrong-answer limitation, demonstrated live rather
than asserted, and it is precisely why every result carries
*"Independent model agreement is not external verification."* Partial
mitigation: both models independently marked the **currency** of their
answer `UNKNOWN`, and those UNKNOWNs are surfaced in the governed output.

## Turn economics

| | |
|---|---|
| Subscription turns inside `deep_review` runs | **25** |
| Runs recorded | 13 (8 cross-family) |
| Stopped at **2 turns** | **11 / 13 (85%)** |
| Required 4 turns | 2 / 13 |
| Paid API calls | **0** |

The minimum-call governor is doing its job: most reviews cost 2 turns.
