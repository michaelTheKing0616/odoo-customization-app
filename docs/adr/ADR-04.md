# Tool-call emulation ladder

**Status:** accepted (engineering spec, 2026-10-03)

**Context:** Providers differ in whether they emit native tool calls. The rest of the engine consumes the one canonical shape from ADR-03: text plus zero or more tool calls, each with an id, a name, parsed args, and the raw argument string. Hosts that cannot emit native calls still need a path that lowers into that shape, and that path must not invent a tool call from a partial or ambiguous action.

**Options considered:**
- Native tool calls only. Refuse any host that cannot emit provider-native function calls. Local and long-tail models would be excluded.
- Three-step ladder. Try native first, then `emulated_json`, then `emulated_text`. Both emulated adapters emit the same canonical tool calls as native.

**Decision:** The ladder, in that order: native, then `emulated_json`, then `emulated_text`. Emulated adapters emit the same canonical tool calls. Emulated modes stay capped at Tier B until an eval says otherwise. After lowering, the canonical schema is checked. Arguments are parsed as JSON and never evaluated.

**Consequences:** Promoting an emulated adapter above Tier B is harder: it waits on an eval, not a registry edit. Treating a partial or ambiguous action as a tool call is harder: `parse_emulated_json` rejects those payloads and they are never executed. A host that cannot emit the canonical shape through any rung cannot call tools.

**How to revisit:** An eval that lifts an emulated adapter above Tier B, or a host that cannot reach the canonical shape on any rung of the ladder.
