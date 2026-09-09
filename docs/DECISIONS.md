# Architecture Decisions

- Original Ticket-to-Implementation-Plan Agent is V1 of a larger Agentic Software Delivery System.
- Real Spring Boot Customer application is used as the target system.
- Update Email intentionally remains unimplemented so we have a visible before/after agent ticket.
- V2 uses bounded direct repository context.
- V2 is NOT RAG.
- RAG should be introduced when selective retrieval becomes justified.
- Browser UI exists so agent-driven changes can be visibly verified.
- Human approval remains required before production deployment.
- V3 uses direct client-side Anthropic tool calling (list_repository_files, read_file, search_code) rather than an MCP server. MCP remains deferred until multiple tools/agents actually need to share a common protocol — introducing it earlier would be speculative infrastructure with no current consumer.
- V3's read-only tool set has no write capability by design. Any file-modifying capability is a distinct, higher-risk decision (V4) requiring its own explicit review of write boundaries and approval gates — it does not follow automatically from V3 being verified.
- Introduced docs/LESSONS.md as a separate small file for durable, reusable technical gotchas (e.g. API/tooling edge cases), distinct from DECISIONS.md (why we chose an approach) and PROJECT_STATE.json (current status). Why: by V3 enough concrete, reusable lessons had accumulated (thinking-block handling, tool_result batching, stop_reason pitfalls) that leaving them buried in code comments risked future sessions rediscovering the same failures.
- Enriched verification_state in PROJECT_STATE.json from plain booleans to {status, as_of_commit, evidence} objects instead of creating a separate verification-tracking file. Why: this gives future sessions enough to judge whether a "verified" claim might be stale (by comparing as_of_commit against later changes to the same files) without duplicating the same facts across two files.
