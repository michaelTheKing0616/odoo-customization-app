# LLM gateway build vs LiteLLM

**Status:** accepted (engineering spec Part 5.1, 2026-10-02). Tope confirmed this on 2026-10-03.

**Context:** The bot needs one canonical message and tool schema across Claude, OpenAI, Gemini, and local models. A third-party router hides tool-call and streaming bugs. D8 asked whether to wrap LiteLLM instead.

**Decision:** Thin in-house gateway in `apps/api/app/llm_gateway`. Provider-specific code stays in adapters. LiteLLM is not a dependency. The existing `app.llm_provider` path used by generation stays in place; this package does not replace it.

**Consequences:** Conformance tests run against a scripted adapter. A live provider adapter is added only with cassette tests. Revisit LiteLLM only if a long-tail host cannot be expressed as an adapter behind the same canonical types.

**How to revisit:** A new host that needs a feature the canonical types cannot carry.
