# Customer App auth: claims vs. code verification (BL-102, Sprint 27, T14)

**Verdict: claims match code and live production. No correction needed.**

## What was checked

The published claim (`docs/PORTFOLIO_CAPABILITIES.yaml`'s
`security-jwt-rbac` entry, surfaced in the `senior-java-ai-transformation`
showcase): *"BCrypt + JWT authentication with USER/ADMIN RBAC and
workspace isolation."*

## Real code read

- `app/src/main/java/com/example/customer/security/DemoIdentitySeeder.java`
  — seeds 3 USER personas (each bound to its own real `Customer` row/
  workspace) and 2 ADMIN personas, idempotently (guarded by row count).
  Password hash generated via the real injected `PasswordEncoder` bean at
  seed time — never a hand-computed/hardcoded hash.
- `app/src/main/java/com/example/customer/security/DemoLoginController.java`
  — `POST /auth/login` genuinely checks username + `passwordEncoder.matches()`
  against the stored BCrypt hash server-side, throws
  `InvalidCredentialsException` on failure, issues a real signed JWT on
  success. `GET /auth/personas` exposes the real seeded usernames so the
  login UI's dropdowns are never a hardcoded frontend list.
- `app/src/main/java/com/example/customer/security/WorkspaceAccessGuard.java`
  — a USER-role token may only access the one customer bound to its own
  `cid` JWT claim; an ADMIN-role token bypasses this (by design, a
  separate, still-server-verified token, never an auth bypass).
- `app/src/main/resources/static/index.html` — the real Customer App
  login page prefills the password field with the real demo password and
  populates persona dropdowns from the real `/auth/personas` response —
  the credentials are genuinely discoverable on the page itself, not
  buried in docs only.

## Live production verification (2026-10-06)

```
GET https://agentic-delivery-customer-app-production.up.railway.app/auth/personas
-> {"user":["user1","user2","user3"],"admin":["admin1","admin2"]}

POST .../auth/login {"username":"user1","password":"Demo@123"}
-> HTTP 200, a real signed JWT with claims: role=USER, cid=23,
   scope="preference:write appointment:read contract:write customer:read
   preference:read contract:read customer:write", exp 900s TTL
```

Cross-checked against the security matrix (T11, this sprint,
`docs/SECURITY_MATRIX.md` row 5): `SecurityIntegrationTest.java` real test
names confirmed (401 on no/malformed/wrong-signature/expired/wrong-issuer/
wrong-audience token, 403 on missing scope) match this same auth design.

## Conclusion

The claim is accurate: BCrypt password hashing is real (not simulated),
JWT issuance and verification are real, USER/ADMIN RBAC is real and
scope-based, and workspace isolation is enforced server-side via the JWT's
own `cid` claim, not client-trusted. The demo password (`Demo@123`,
intentionally public by design — see `DemoIdentitySeeder`'s own Javadoc)
is already surfaced directly on the Customer App's login page, which is
the right place for it; no additional public-facing publication of the
credential is needed beyond that.

No doc correction was made because none was needed. This note itself is
the deliverable this task's own instructions call for ("verification-only"
pattern type) when the result is "nothing was wrong."
