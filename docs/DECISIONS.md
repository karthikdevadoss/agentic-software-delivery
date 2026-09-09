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
