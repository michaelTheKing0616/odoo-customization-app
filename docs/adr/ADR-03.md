# Canonical message and tool schema

**Status:** accepted (engineering spec Part 5.2, 2026-10-02)

**Context:** Every provider returns tool calls in a different shape. The rest of the system needs one shape.

**Decision:** A response is text plus zero or more tool calls. Each tool call has an id, a name, parsed args, and the raw argument string. Stop reasons are the closed set in `app.llm_gateway.types.STOP_REASONS`. Arguments are parsed as JSON. They are never evaluated. The canonical schema is checked after any provider-specific lowering.

**Consequences:** Missing call ids are synthesized. Malformed arguments become `malformed_tool_call` and are not executed. Provider reasoning blobs are not part of this schema yet.

**How to revisit:** A provider feature that cannot round-trip through this shape without losing a safety check.
