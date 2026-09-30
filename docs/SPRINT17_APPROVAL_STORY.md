# The approval story, read out of the code

Sprint 17, BL-C1, 2026-09-30.

Two public pages appeared to contradict each other:

- `agent/web/home.html:184` — **"An AI agent that cannot approve its own writes"**
- `agent/web/workbench.html:18` — **"Small, low-risk changes are implemented,
  tested, and deployed automatically — no human approval needed for this preview
  tier."**

The instruction for this task was explicit: do not resolve that by inventing a
policy. Read the execution code and report what is actually true. That is what
follows. Every claim below names the file and line it came from, and the sentence
that eventually went on the pages was written after this, not before.

---

## The short version

**Both sentences are true, and they are about different things.** The apparent
contradiction is a category error in the reader's head, not a defect in the
system — but the copy did nothing to prevent that reader from making it, which
*is* a defect in the copy.

- Home's sentence is about **MODEL AUTHORITY**. No language model anywhere in
  this system grants itself permission to write, commit, push or deploy. That is
  structurally true, not a policy anyone remembers to follow.
- Workbench's sentence is about **SYSTEM POLICY AUTHORITY**. A deterministic,
  zero-model gate authorizes a very narrow, pre-declared class of change to go
  all the way to production with no human in the loop.

And there is a third fact neither page said, which turns out to be the most
impressive one:

> On the public Workbench path, **no model is called at all.** Not a cheap model,
> not a constrained model. Zero. The pipeline that recruiters can drive end to
> end is entirely deterministic Python.

---

## What the code actually does

### 1. The public Workbench path is `/api/trainer/runs`, not `/api/runs`

`agent/web/workbench.js:955` posts to `/api/trainer/runs`. That route
(`agent/web_server.py:2297`) is `start_trainer_run`, which spawns
`_run_trainer_thread` (`agent/web_server.py:1291`).

The agent-loop path — `start_run` → `_run_agent_thread`
(`agent/web_server.py:1140`, `:616`) — is the one that calls a real model, and
**the public UI never invokes it**. That path is where
`_web_approval_prompt_factory` (`agent/web_server.py:599`) lives, and it does
block a run's thread on a real browser click:

```python
decision = decision_queue.get()   # blocks until a real POST /decide arrives
```

So the human approval gate is real, and it guards the model-driven path. It is
simply not the path a recruiter drives.

### 2. The deterministic gate that authorizes the public path

`_assess_public_demo_requirement` (`agent/web_server.py:1180`) is, in its own
words, "the single deterministic, zero-API-cost authority for the public demo
path". It runs four checks before anything happens, in this order, all pure
Python:

1. a hard character cap on the requirement text;
2. `demo_catalogue.normalize_requirement()` — the request must match one of
   **three** pre-declared operations;
3. `risk_policy.classify()` — a keyword denylist over the raw text, as defence in
   depth even on a successfully-normalized request;
4. a one-at-a-time run lock plus a cooldown.

`start_trainer_run` re-derives this server-side and never trusts the assessment
the browser displayed (`agent/web_server.py:1270`, comment: "never trust a
client-displayed assessment as the actual authorization decision").

### 3. The three operations are the whole surface

`agent/demo_catalogue.py` declares exactly three operations —
`heading_text`, `subtitle_text`, `footer_text` — each targeting one known,
unique, already-existing text field in
`app/src/main/resources/static/index.html`. Its own docstring is unambiguous:

> "The LLM may interpret natural language — it is NOT used here at all for the
> supported operations (this module never calls any model). It MUST NOT decide
> its own permissions: `normalize_requirement()` is the sole, deterministic
> authority over whether a requirement is executable."

There were five. Two (`find_button_label`, `create_button_label`) were retired on
2026-09-14 after it emerged that the buttons they targeted had not existed in the
real page for a long time.

### 4. The mutation cannot broaden, structurally

`apply_operation` (`agent/demo_catalogue.py:236`) refuses rather than guesses:

- anchor pattern matches zero times → `RuntimeError` (`:243`)
- anchor pattern matches more than once → `RuntimeError`, "refusing an ambiguous
  mutation" (`:245`)
- line count changed at all → `RuntimeError` (`:260`)
- no line differs → `RuntimeError`, refusing a no-op (`:263`)
- more than exactly one line differs → `RuntimeError` (`:265`)

The value itself is bounded to 1–100 characters with `<`, `>` and control
characters forbidden (`agent/demo_catalogue.py:39`), *and* HTML-escaped at write
time. Two independent mechanisms for the same risk, deliberately.

### 5. A second, independent file-level boundary

Even on the model-driven path, `agent/write_tools.py:42` restricts writes to:

```python
ALLOWED_WRITE_PREFIXES = ("app/src/main/java/", "app/src/test/java/",
                          "app/src/main/resources/static/")
ALLOWED_WRITE_EXTENSIONS = {".java", ".html"}
```

and binds each approval to a SHA-256 of the exact `(path, content)` pair approved
(`_binding_hash`, `agent/write_tools.py:68`), re-checked at apply time so a
mutation of either field after approval is refused rather than applied. Not
`agent/`, not `docs/`, not `pom.xml`, not build config.

### 6. What "automatically" reaches

`_run_trainer_thread` really does go all the way: real `git commit`, real
`git push`, real Railway deploy trigger, real post-deploy production assertion
(`agent/web_server.py:1004`–`1070`). "Deployed automatically" is not marketing —
it is what happens.

---

## The real invariant, stated once

> **No model in this system authorizes an action.** Authority is held by
> deterministic code: a keyword denylist, a three-operation request contract, a
> single-line diff-purity check, a write-path whitelist, and a hash binding each
> approval to exact content. Within the narrow band that code pre-approves, a
> change reaches production with no human in the loop — and that band is three
> text fields on one page, changed by a pipeline that calls no model at all.
> Everything outside it is refused with a stated reason, and the model-driven
> path that *can* touch Java source blocks on a real human click.

Note what this is **not**. It is not "every write needs a human", which would be
false — the bounded auto path is real. It is not "the LLM decides low-risk
changes are safe", which would be the actually alarming reading and is false in a
way anyone can check: `demo_catalogue.py` and `risk_policy.py` import no model
client.

---

## What changed on the pages

The engineering was already right. The copy invited the wrong reading, so the
copy changed and the behaviour did not.

| Page | Before | After |
|---|---|---|
| Home | "An AI agent that cannot approve its own writes" | Kept — it is accurate. A sentence was added naming *what* holds the authority instead, so the claim is checkable rather than merely reassuring. |
| Workbench | "implemented, tested, and deployed automatically — no human approval needed for this preview tier" | Rewritten to say *deterministic policy* authorizes a pre-declared band, and to say plainly that no model is called on this path. |

The distinction MODEL AUTHORITY vs SYSTEM POLICY AUTHORITY is now asserted
deterministically in `e2e/copy-contract.spec.js`, so neither page can drift back
to implying the model grants itself permission and neither can start claiming
every write needs a human.

---

## One thing I could not settle from the code

The Workbench copy called this a **"preview tier"**, which implies other tiers
exist with different rules. Nothing in the code defines a tier system: there is
one public path with one deterministic gate. The phrase is either aspirational or
a leftover.

I removed it rather than inventing a tier model, because a reader who asks "what
are the other tiers?" gets no answer. That is a copy decision inside this task's
scope, not a product decision — but if the Owner intends a real tier structure
later, this is where the word went missing. Recorded in
`docs/OWNER_DECISIONS_PENDING.md` as a non-blocking note.
