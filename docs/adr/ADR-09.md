# Memory model and injection-safe persistence

**Status:** accepted (engineering spec, 2026-10-03). Implementation card [T8-MEM](../plans/next-phase/cards/T8_ENGINE_CORE.md) is still open. This ADR records the model; it does not claim the code exists.

**Context:** Later turns need durable memory so the engine can reuse tenant facts without rediscovering them. Untrusted Odoo data, files, and role notes can look like instructions if they are written into a trusted store. T8-MEM already copies the four classes; this ADR locks that model so injection-safe persistence is specified before the card is built.

**Options considered:**
- Auto-write everything the model says into tenant memory. Every claim, note, or tool observation would become a confirmed tenant fact on the next turn, with no human gate and no class split.
- Four memory classes. Working memory is engine-owned and trusted. Tenant or database memory is human-confirmed. Global knowledge enters only through a pull request plus eval. Episodic memory is never auto-injected.

**Decision:** Use the four classes. Working memory is engine, trusted. Tenant or database memory is human-confirmed. Global knowledge is pull request plus eval. Episodic memory is never auto-injected. `memory_propose` creates a pending item that a human confirms. Untrusted data stays only inside tool results. Memory budget is at most 5% of the context window. RT-47 (memory poisoning through role notes) is refused. No extra stores.

**Consequences:** Injecting episodic notes into the prompt becomes harder: they are never auto-injected. Treating a model proposal as already confirmed becomes harder: `memory_propose` only creates a pending item until a human confirms. Role notes cannot poison tenant memory (RT-47). Untrusted content cannot be promoted by wrapping it as memory. The 5% budget caps how much confirmed memory can occupy a turn. T8-MEM remains the implementation card.
