# Applications Review → Mahadeva apply handoff

**Automation Sprint 13 (2026-10-06).** Owner reviews packs on the phone page and taps **Approve** once. Mahadeva (parent / automation seat) then submits the application. The web process **never** applies.

## Owner (phone)

1. Open the gated review URL from `DEVADOSS/storage/personal/CONTACT.md`  
   `https://agentic-platform-backend-production.up.railway.app/applications?k=…`
2. Expand a pack: CV (PDF), cover letter, JD / posting.
3. Tap **Approve**. That records `owner_approved` + `approved_at` and sets queue status to **`pending_apply`**.
4. Nothing is emailed or posted to an employer from that tap.

## Mahadeva apply step (after Approve only)

1. **Poll** `GET /applications/queue?k=<APPLICATIONS_REVIEW_TOKEN>` (same token as the page; live value only in CONTACT.md / Railway env — never commit it).
2. For each item with `status: pending_apply` and `owner_approved: true`:
   - Open the pack’s **employer careers / Greenhouse / etc. URL** (`item.url`) or an **email apply link** documented in the pack posting.
   - Attach / paste CV + cover letter from the review pack (PDF via gated `/applications_pdf/…?k=` or DEVADOSS storage copies).
   - Submit via that employer route only.
3. **Forbidden:** LinkedIn scrape, LinkedIn Easy Apply automation, applying without an Approve tap, inventing career facts, sending from the web Approve handler.
4. **Record proof** with  
   `POST /applications/queue/update?k=…`  
   body example:
   ```json
   {
     "pack_id": "<id>",
     "status": "applied",
     "proof": {
       "method": "employer_form",
       "url": "https://…",
       "confirmation": "<reference or screenshot path>",
       "applied_at_note": "2026-10-06T…"
     }
   }
   ```
   On failure use `"status": "failed"` and `"error": "<reason>"`.
5. Mirror the same outcome into `DEVADOSS/storage/career/` (e.g. APPLY_LOG) when that tree is available — Railway disk may reset on redeploy.

## Queue status machine

| Status | Meaning |
|---|---|
| `approved` | Reserved; Owner Approve currently writes `pending_apply` directly with `approved_at` set |
| `pending_apply` | Owner yes recorded; waiting for Mahadeva |
| `applied` | Mahadeva submitted; proof filled |
| `failed` | Attempted; error + optional proof |

## APIs (all require `?k=` gate; wrong/missing → plain 404)

| Method | Path | Who |
|---|---|---|
| GET | `/applications` | Owner UI |
| GET | `/applications.json` | Owner UI |
| GET | `/applications_pdf/{name}` | Owner / Mahadeva |
| POST | `/applications/approve` | Owner tap (`{"pack_id"}`) |
| GET | `/applications/queue` | Owner UI + Mahadeva |
| POST | `/applications/queue/update` | Mahadeva status/proof |

Queue file default: `agent/applications_apply_queue.json` (override `APPLICATIONS_APPLY_QUEUE_PATH`).

## Standing Interview

Unchanged. Applications Review stays out of public nav and does not load `nav.js`.
