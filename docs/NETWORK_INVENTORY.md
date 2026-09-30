# First-load network inventory

**GENERATED FILE** — `python agent/network_inventory.py`, read out of the two
capture manifests. Facts only: it classifies what each public page actually
fetched on load and recommends nothing.

## Classes

| Class | Meaning | Acceptable? |
|---|---|---|
| same-origin | the application's own pages, assets and APIs | yes, this is the app working |
| third-party font | a typeface fetched from another host | **no** — asserted zero by `e2e/third-party-network.spec.js` |
| tracker / analytics | a known analytics, session-replay or ad host | **no** — asserted zero |
| other third-party | anything else off-origin | must be looked at; none exist today |

An outbound LINK to GitHub or LinkedIn is not a request and does not appear
here. Only what the page actually fetches counts, which is why this is read from
real request events rather than from grepping the HTML for hostnames.

## BEFORE (production, before Sprint 17)

Base URL `https://agentic-platform-backend-production.up.railway.app`, captured 2026-09-30T09:21:21.571Z, 27 page/viewport records.

| Page | same-origin | third-party font | tracker | other third-party |
|---|---|---|---|---|
| `/` | 3 | **1** | 0 | 0 |
| `/workbench` | 10 | **3** | 0 | 0 |
| `/triage` | 7 | **3** | 0 | 0 |
| `/ask-codebase` | 6 | **3** | 0 | 0 |
| `/showcase/senior-java-ai-transformation` | 8 | **3** | 0 | 0 |
| `/usage` | 9 | **3** | 0 | 0 |
| `/standing-interview` | 5 | **3** | 0 | 0 |
| `/case-study/durable-agent` | 3 | **1** | 0 | 0 |
| `/dashboard` | 7 | **3** | 0 | 0 |
| **total (one row per page, not per viewport)** | **58** | **23** | **0** | **0** |

Third-party hosts contacted, with request counts:

- `fonts.gstatic.com` — 14 request(s)
- `fonts.googleapis.com` — 9 request(s)

## AFTER (local sprint17 branch)

Base URL `http://127.0.0.1:8420`, captured 2026-09-30T10:32:04.683Z, 27 page/viewport records.

| Page | same-origin | third-party font | tracker | other third-party |
|---|---|---|---|---|
| `/` | 3 | 0 | 0 | 0 |
| `/workbench` | 10 | 0 | 0 | 0 |
| `/triage` | 7 | 0 | 0 | 0 |
| `/ask-codebase` | 6 | 0 | 0 | 0 |
| `/showcase/senior-java-ai-transformation` | 8 | 0 | 0 | 0 |
| `/usage` | 9 | 0 | 0 | 0 |
| `/standing-interview` | 5 | 0 | 0 | 0 |
| `/case-study/durable-agent` | 3 | 0 | 0 | 0 |
| `/dashboard` | 7 | 0 | 0 | 0 |
| **total (one row per page, not per viewport)** | **58** | **0** | **0** | **0** |

**No third-party host was contacted by any page.** Every request on every
public surface was same-origin.

## What changed, as a number

| | BEFORE | AFTER |
|---|---|---|
| third-party font requests | 69 | 0 |
| tracker / analytics requests | 0 | 0 |
| other third-party requests | 0 | 0 |

The figure above counts every RECORD, so a page captured at three viewports
contributes three times. Per unique page the BEFORE counts were 1 on Home and
Case Study and 3 on the other seven.

What those requests actually were, read out of the manifest rather than assumed
(an earlier version of this paragraph guessed `preconnect` and was wrong):

- **1 request** = the `fonts.googleapis.com/css2?...` stylesheet. Home and Case
  Study stopped there because neither page's CSS ever *used* any of the nine
  families it declares, so the browser had no face to download. They were
  paying a round trip for nothing.
- **3 requests** = that stylesheet plus two real `.woff2` font files from
  `fonts.gstatic.com` — on Workbench, `inter/v20/...woff2` and
  `sora/v17/...woff2`. Those are genuine typeface downloads blocking first
  paint.

`preconnect` appears in the HTML and is not in these counts: it opens a
connection rather than fetching a resource, so it raises no request event.
Removing the `<link>` tags removed the preconnects too.

## Known limitation

This is **first load only**, with no interaction. A request a page makes after a
click, a form submission or a model-backed action is outside what these packs
captured, by design — the capture never interacts with anything. A page that
fetched a tracker only after a button press would not appear here, and nothing
currently checks for that.

