# Ideas (unresolved possibilities — not yet committed)

Distinct from docs/ROADMAP.md (ordered, accepted strategic direction) and
docs/DECISIONS.md (decisions already made, with rationale). Everything
here is a possibility worth remembering, not a plan. Do not build from
this file without an explicit task, and do not treat presence here as
authorization for anything. This is not a chat transcript dump — only
durable, still-unresolved ideas belong here; resolve or promote an idea
to ROADMAP.md/DECISIONS.md when it's actually decided, and remove it from
this file at that point.

## Independent credibility audit — mechanics unresolved

docs/ROADMAP.md's near-term item 5 commits to *doing* an independent
credibility audit; it does not yet specify: what exactly goes into the
"sanitized evidence package" (which files, how secrets/paths are
redacted), which fresh model/account reviews it first, and what an
"external-model audit" would concretely mean (a different provider's
model? a human reviewer? both?). Needs a decision before item 5 becomes
actionable, not just aspirational.

## karthikdevadoss.com content credibility review

The existing personal site (protected — see docs/COMPANY_VISION.md, do
not modify without a separate explicit task) may contain older AI-related
claims made before this project's evidence-backed discipline existed.
Whether/when to review and correct that content is unresolved — noted
here so it isn't forgotten, not scheduled.

## SMS-based owner authorization (after email)

docs/ROADMAP.md's two-tier Workbench model commits to email-based
one-code-per-requirement authorization first. SMS as a secondary/parallel
channel was mentioned as a "later" enhancement with no concrete design
(provider, cost, opt-in mechanics) — genuinely open, not scheduled.

## YogaCRM pilot specifics

docs/ROADMAP.md records the accepted safe *progression* for a future
YogaCRM pilot. Completely unresolved: repository access, actual
technology stack, credentials, CI/CD tooling, staging environment
availability, and production permissions. None of these should be
assumed — ask the owner when the pilot actually becomes active.

## Future candidate agent roles

docs/ROADMAP.md's "Multi-agent roadmap" section already lists candidate
future agents (orchestrator, requirement/business analyst, coding,
build/test, reviewer, security, release/deploy, FinOps/model router,
etc.) with the explicit rule that none should exist without measured
benefit. Separately, docs/CONSTITUTION.md §15 raises CEO/CTO/CFO/
Quality-Evidence as organizational *roles* that could — someday, if
justified — become real agents rather than logical lenses over shared
evidence. Whether/when either list actually produces a real agent is
unresolved; this note exists so the two lists aren't confused with each
other or with a commitment to build.

## Enterprise domain expansion sequencing

docs/ROADMAP.md's "Target application growth" lists many possible future
business areas (billing, payments, notifications, auth, audit,
integrations, etc.) for the Customer app. The *order* in which these
should be added, and which ones best serve near-term interview/portfolio
value vs. long-term platform realism, is unresolved — to be decided
requirement-by-requirement per the constitution's "smallest useful step"
principle, not pre-planned in bulk.
