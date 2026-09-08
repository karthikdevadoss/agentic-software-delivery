# Engineering Rules

Simple rules for this project. These will later be fed to a RAG system
so agents can follow project conventions automatically.

1. Keep the package structure flat: `model`, `repository`, `service`,
   `controller`. Do not add extra layers unless there is a clear need.
2. Every new REST endpoint must have a corresponding test.
3. Business logic belongs in the service layer, not in controllers.
4. Return standard HTTP status codes: `404` for not found, `409` for
   conflicts, `201` for successful creation.
5. Do not catch exceptions silently; either handle them meaningfully or
   let them propagate to a controller-level exception handler.
6. Prefer constructor injection over field injection.
7. Keep entities free of business logic; entities describe data only.
8. Write plain, readable code over clever abstractions.
9. Do not introduce new dependencies without a clear, stated reason.
10. Any change to the database schema must include an updated seed data
    strategy if seed data is affected.
