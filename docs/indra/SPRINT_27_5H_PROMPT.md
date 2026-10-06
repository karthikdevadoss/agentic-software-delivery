# Sprint 27 — 5-hour unattended platform polish (Indra)

**Role:** Indra (implementer), Claude Code, unattended.  
**Wall clock:** ~5 hours from launch (target window ~19:55–00:55 Berlin 2026-10-06/07, or whatever start time Owner/Mahadeva actually launches).  
**Repo:** `C:\Users\Hemapriya\agentic-software-delivery`  
**Branch (to create at launch):** `indra/sprint-27-5h-platform` from `origin/master` (fetched; do not base on dirty `sprint21-portfolio-truth`).  
**Model:** Prefer Sonnet (match Sprint 25/26 pattern) unless Owner named another.

---

## Hard stop / exit rules

1. **Stop after ~5 hours wall clock OR when every startable item below is done or skipped** — whichever comes first.
2. Before exit, write **`docs/indra/SPRINT_27_RETRO.md`** with: what done, commit SHAs, test counts before/after (or per item), blockers with skip reasons, next-estimate stub for leftovers.
3. **Anti-stuck:** every item is **independent**. If blocked (needs Owner, missing secret, flaky external, unclear product decision), **SKIP immediately**, log the blocker in the retro, continue the next item. Never idle-wait. Never poll Owner.
4. **Commits OK** on the sprint branch. **Push OK** (`git push -u origin HEAD`). **No force-push.** **No secrets** in commits (tokens, `.env`, cookies, private keys).
5. **No production deploy.** No merge to `master` without Owner. No enabling feature flags that change live recruiter-facing behaviour without Owner.
6. **Forbidden this sprint:** LinkedIn scraping; job applications; WhatsApp / Teams / email sends; inventing Education or other Owner-only facts; Deep Consensus Sprint 7+; P0 Learn/Usage mega-build unless listed below.
7. Plain-language steps only (Owner hates "slice" jargon). Backlog IDs (BL-xxx) are fine.
8. Run the relevant test suite after each code change that touches tests. Do not leave the branch red. Do not delete or skip failing tests to fake green.
9. If a task needs a browser against production and credentials/network fail: write the **checklist / audit doc only** and skip the live sweep — still counts as partial progress; log it.

---

## Mission (why this sprint)

CVs / application packs are already out (career track). Owner priority tonight: **platform must stay perfect**. This sprint is ASD platform honesty, docs, evidence rules, test classification, and plain-English UI copy — work that needs **no Owner decision** and **no production deploy**.

---

## Task queue (do in order; skip independently if blocked)

Estimate minutes are wall-clock guesses sized so the queue **overflows 5 hours** on purpose (never run dry). Prefer finishing fewer items cleanly over rushing all of them.

### T1 — BL-122: Evidence rules file (~25 min)
- **What:** Write the five evidence rules into a durable repo rule file (CLAUDE.md section and/or `.claude/rules` — follow existing pattern).
- **Why:** Rules already exist in audit prose; agents and humans need one place that is enforceable.
- **Done when:** Rule file committed; references from CLAUDE.md/START_HERE if needed; no behaviour change required beyond docs/rules.
- **Skip if:** File already exists with the five rules and is current.

### T2 — BL-123: DISHONEST status on claims audits (~30 min)
- **What:** Add a `DISHONEST` status to claims audits, with a clear definition and one real first use (or a fixture-backed example if no live claim fits).
- **Why:** Separates honest UNKNOWN / PARTIAL from actively wrong claims.
- **Done when:** Status exists in code + tests assert definition and at least one path that emits it; docs mention it.
- **Skip if:** Already implemented on master.

### T3 — BL-125: Claude Code task template (~35 min)
- **What:** Commit a standard Claude Code task template: bounded production calls, stop conditions, committed reports (generalise from prior audit contracts).
- **Why:** Unattended runs need a repeatable contract shape.
- **Done when:** Template file under `docs/` (or project convention) committed; short pointer from CLAUDE.md.
- **Skip if:** Equivalent template already committed and referenced.

### T4 — BL-127: Task contracts — quality acceptance + page purpose (~30 min)
- **What:** Require task contracts to carry quality acceptance and page purpose before build starts (field + enforcement on top of existing BK-27 / template).
- **Why:** Stops building pages without a stated purpose or acceptance bar.
- **Done when:** Template/schema updated; a test or validator fails closed when fields missing (if a validator already exists — extend it; do not invent a heavy framework).
- **Skip if:** Needs a product decision on which fields are mandatory beyond what backlog already states.

### T5 — BL-128: Prompts verify facts, never assert them (~25 min)
- **What:** Add/enforce the rule that prompts must verify owner and technical facts, never assert them.
- **Why:** Audit found contract hypotheses labelled unverified and only half-right.
- **Done when:** Rule in template + CLAUDE.md / rules file; one example corrected if an existing prompt asserts a fact.
- **Skip if:** Purely editorial with no clear home file.

### T6 — BL-105: Ask Codebase metrics in plain English (~35 min)
- **What:** Explain Ask Codebase metrics in plain English on the page; keep the page equal to the latest eval output (`eval_runner.py` already produces numbers).
- **Why:** Hiring managers should read meaning, not jargon.
- **Done when:** UI/copy updated; page values match latest eval artifact; tests cover the wiring if present.
- **Skip if:** Page is behind an Owner-only flag that cannot be verified locally, or copy needs Owner taste approval for recruiter-facing wording — then do a **draft copy file** under `docs/` and skip live UI change.

### T7 — BL-106: Role Showcase jargon cleanup (~75 min)
- **What:** Jargon cleanup; surface Sprint 13 verified work; two honest per-requirement showcases (capability registry / validators already exist after BL-096).
- **Why:** Showcase must read as honest proof, not marketing.
- **Done when:** Copy cleaned; two showcase configs added/updated; existing validators pass; no new unverifiable claims.
- **Skip if:** Would invent Sprint 13 claims not already in evidence/registry — then only do jargon cleanup and skip new showcases.

### T8 — BL-116: Classify tests by oracle type (~90 min)
- **What:** Classify every test in this repository by oracle type (derive from assertions, not name patterns). Persist labels in a durable map/manifest the project can extend.
- **Why:** Part of standing-interview / test-architecture honesty.
- **Done when:** Manifest committed covering the suite (or a clear % complete with a script to continue); short README of oracle categories; no test behaviour changed unless a mislabelled orphan is found and fixed safely.
- **Skip if:** Suite discovery is broken locally after 15 min of setup — write the category scheme + script stub and move on.

### T9 — BL-100 (scoped): Public-page checklist doc (~90 min)
- **What:** Write purpose + 3–5 checks per public surface (read-only audit checklist). Live Playwright sweep against production is **optional**; if production base URL / auth fails, **do not block** — ship the checklist doc.
- **Why:** Gives a repeatable human/agent browser audit without requiring deploy.
- **Done when:** Checklist markdown committed under `docs/`; surfaces enumerated from START_HERE / public routes; each has purpose + checks.
- **Skip if:** Docs already contain an equivalent current checklist — refresh dates/status only.

### T10 — BL-104: Usage — one run step-by-step from ledger (~75 min)
- **What:** One-run, step-by-step view from correlated ledger events; never call it "tracing" in user-facing copy.
- **Why:** Usage should explain a single run honestly, including UNKNOWN.
- **Done when:** Query + UI (or honest stub with UNKNOWN) committed; tests for correlation / UNKNOWN handling.
- **Skip if:** Requires production ledger data or Owner design choice between layouts — then implement the query layer + tests only, document UI follow-up.

### T11 — BL-121: Security matrix (controls × attacks) (~60 min)
- **What:** Matrix of which controls are actually tested against which attacks; honest empty cells.
- **Why:** Makes gaps visible instead of assumed covered.
- **Done when:** Matrix doc committed; empty cells explicit; no false "covered" claims.
- **Skip if:** None — always startable as docs from reading tests.

### T12 — BL-119: Flag tests never observed failing first (~60 min)
- **What:** Durable per-test record / flag for fail-first evidence (prose today).
- **Why:** Fail-first is a real rule but not mechanical.
- **Done when:** Storage design + initial population script or annotation for a meaningful subset; document how to extend.
- **Skip if:** Storage design is ambiguous after 20 min — write an ADR-style proposal under `docs/` and skip implementation.

### T13 — Docs / state brief freshness (~40 min)
- **What:** Refresh `docs/PROJECT_STATE.json` / `PROJECT_STATUS.md` / related brief so they match git + runtime evidence on this branch (no aspirational claims).
- **Why:** Stale state docs are a recurring honesty defect.
- **Done when:** State files updated only where evidence supports; contradictions listed in retro if unresolved.
- **Skip if:** File is governance-locked or update would require Owner adjudication — list contradictions in retro instead.

### T14 — BL-102 (verification only): Auth design vs code (~30 min)
- **What:** Read customer-app auth code; compare to published claims; correct the **docs/claims** side if wrong. Do **not** invent or publish new live credentials unless already present in repo docs.
- **Why:** Demo auth claims must match code.
- **Done when:** Short verification note committed; doc corrections if needed.
- **Skip if:** Would require changing production secrets or Owner-only credential policy.

### T15 — Buffer / harvest (~20 min, always last before retro)
- **What:** Re-read backlog statuses for items you completed; mark done in `docs/BACKLOG.json` only if project convention allows agents to flip status; otherwise list IDs for Mahadeva in the retro.
- **Why:** Prevents finished work looking open.
- **Done when:** Retro lists ID → SHA mapping.
- **Skip if:** Never — always do a minimal version.

---

## Explicitly out of scope (Mahadeva / Owner / other agents)

- WhatsApp / personal automation / email apply  
- LinkedIn scraping or applicant-count fetching  
- Job applications / pack sending  
- Education GAP facts (Owner-only)  
- Production deploy / merge to master  
- DEVADOSS B1b–B5 and posting-date ranking (career repo) — **not this branch**; note as next DEVADOSS sprint stub in retro if time leftover in writing only  

---

## End deliverable

`docs/indra/SPRINT_27_RETRO.md` must include:

1. Start/end local time (Berlin label)  
2. Branch name + tip SHA  
3. Table: task ID → done / skipped / blocker → SHA(s) → tests  
4. Full suite count if run  
5. Push status  
6. Next-estimate stub for unfinished items  

Then exit cleanly. Do not wait for Mahadeva.
