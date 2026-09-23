---
name: devils-advocate
description: Dispatch a genuinely independent, fresh-context adversarial check on a claim, decision, or piece of the accumulated record — for when the Owner explicitly wants a real devil's-advocate pass, not the main session's own inline self-critique.
---

# /devils-advocate

Invoke with what to check: `/devils-advocate the Marsh role-vs-implementer framing` or
`/devils-advocate whether BL-076 duplicates anything NRG already covers` or with nothing, meaning "the
most recent standing decision this session made about itself."

## What this skill does, step by step

1. **Identify the specific claim or decision to check.** If the Owner named one, use it. If not, ask
   which recent decision he wants checked — never guess silently, since a vague target produces a vague,
   unfalsifiable review.
2. **Gather the REAL primary source paths** the claim rests on — the actual private-repo master file
   section, the actual public-repo doc, the actual quoted words, the actual code/config file. Do not
   write a summary of what these say; the dispatched agent reads them itself.
3. **Write a NEUTRAL dispatch prompt — this is the part most likely to be done wrong, so check it
   carefully before sending.** A leading brief ("we concluded X because Y, please confirm this is
   right") defeats the entire purpose of a fresh-context check. The correct shape is: "Here is [claim/
   decision]. Here are the real source files: [paths]. Independently determine PROCEED / STOP AND
   REVERIFY / GENUINELY UNCERTAIN." Never include the reasoning that led to the original decision, never
   include "I think this is fine," never pre-frame the expected answer.
4. **Dispatch via the Agent tool** with `subagent_type: "devils-advocate"` (a real, separate, fresh agent
   — never `"fork"`, which would inherit this conversation's context and defeat the whole point) and the
   neutral prompt from step 3, including the file paths from step 2.
5. **Relay the verdict to the Owner plainly, in full**, including the mandatory "could not resolve"
   item even on a PROCEED verdict — never summarize away a finding to make it sound more settled than it
   is.
6. **If the verdict is STOP AND REVERIFY**: stop forward progress on whatever depended on that claim.
   Present the specific finding and evidence, and do not resume until the Owner has actually resolved it
   — reverifying is his call to make, this skill's job ends at surfacing the finding clearly, not at
   arguing him out of it or minimizing it.
7. **If GENUINELY UNCERTAIN**: say so plainly and ask the Owner whether he wants to treat it as an open
   gap (same as any other "don't recall" item) or dig further.

## Cost note

Each invocation spawns one real subagent on the strongest model tier, deliberately — this check exists
specifically for moments where getting it right matters more than the cost of asking properly, and it
only runs when explicitly requested, never automatically or repeatedly. See [[feedback-cost-and-model-policy]]
for the general "no agent unless asked" rule this is a deliberate, Owner-approved exception to.
