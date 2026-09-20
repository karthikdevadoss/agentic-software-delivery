# Data Governance — GDPR posture + audit trail

Short and honest, not a legal document: what personal data this app
actually stores, what's implemented, what's a real known gap. This is
a portfolio demo — the real personal-data risk today is low because
every `Customer` row created through the public demo is synthetic test
data entered by a recruiter/interviewer, not a real data subject. The
patterns below are documented as what a REAL production deployment of
this app would need to take seriously, honestly separated from what's
actually built today.

## What personal data exists

| Field | Where | Real PII? |
|---|---|---|
| `Customer.name`, `Customer.email` | `model/Customer.java` | Yes — direct identifiers |
| `CustomerPreference.notificationChannel` | `model/CustomerPreference.java` | Indirect — a communication preference tied to a customer |
| `ContractPlan.*` | `model/ContractPlan.java` | No — business/billing data, not personal identifiers |
| `DemoIdentity.username`, `.passwordHash` | `model/DemoIdentity.java` | No real user PII — portfolio-demo login only, BCrypt-hashed, never plaintext |

## What's implemented

- **Right to rectification (Article 16):** `PUT /customers/{id}`
  (email update) is real and tested.
- **Data minimization at the transport layer:** DTOs
  (`dto/CustomerPreferenceResponse.java` etc.) never expose more than
  the API contract needs — no accidental over-serialization of internal
  entity fields.
- **Secure storage:** the one real credential in the system
  (`DemoIdentity.passwordHash`) is BCrypt-hashed, never stored or
  logged in plaintext.

## Real, named gaps (not implemented today)

- **Right to erasure (Article 17):** there is no `DELETE /customers/{id}`
  endpoint. A `Customer` row, once created, is never deletable through
  the API today. For a real production deployment this would need a
  real deletion (or anonymization) path — and a decision about what
  happens to that customer's `ContractPlan` history and outbox event
  rows when they're erased, since those are currently designed to be
  permanent (see the audit-trail section below).
- **Explicit consent tracking:** `CustomerPreference.notificationChannel`
  functions as a lightweight communication preference, but there's no
  dedicated consent record (what was agreed to, when, under what
  version of a privacy notice) — a real gap if this app ever handled
  real marketing communications.
- **Data retention policy:** no TTL or archival job exists for any
  table. Every row lives forever by default. Fine for a portfolio demo
  with synthetic data; a real deployment needs an explicit retention
  policy per table, not an implicit "never" by omission.

## The outbox tables as a real (if incidental) audit trail

`outbox_event` (see `docs/DESIGN_PATTERNS.md`'s Transactional Outbox
entry) and `processed_event` weren't built as a compliance feature —
they exist to make Kafka delivery reliable. But they genuinely double
as a real audit trail, honestly assessed:

**What they give you for free:** every `CustomerPreferenceUpdated` and
`ContractPlanEnrolled` business event is durably recorded with a real
timestamp (`created_at`), the affected customer (`aggregate_id`), and
the full state change as JSON (`payload`) — "what changed, for whom,
when" is already queryable today, no extra instrumentation needed.

**What they don't give you:** no record of WHO made the change (no
actor/principal captured on the outbox row itself — the JWT `sub`
claim is known at request time but not currently persisted alongside
the event), and they only cover the two aggregates that currently
publish events (`CustomerPreference`, `ContractPlan`) — a direct
`PUT /customers/{id}` email change, for example, produces no event row
at all today. A real audit-trail feature (vs. this incidental byproduct)
would need to capture the actor explicitly and cover every mutating
endpoint, not just the two wired into the outbox so far.
