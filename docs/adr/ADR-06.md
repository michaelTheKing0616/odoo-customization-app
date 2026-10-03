# Executor Mode T vs Mode C

**Status:** accepted (engineering spec, 2026-10-03)

**Context:** The executor applies an approved change-set either as one transaction or as one operation at a time. Those paths differ on dry-run, rollback, which ops they accept, and how risk is counted. T8 already named Mode T and Mode C; this ADR records that both exist and that Mode C adds one risk level.

**Options considered:**
- One mode only. Every apply would be Mode T, or every apply would be Mode C. A change-set that cannot meet the chosen mode would be refused, or the engine would have to treat a per-op apply as one transaction.
- Both modes. Mode T for one-transaction applies; Mode C for per-op applies that compensate in reverse. Mode C adds one risk level.

**Decision:** Both exist. Mode C adds one risk level.

Mode T: one transaction, dry-run for non-DDL, native rollback then inverse, default 50 ops.

Mode C: per-op, no dry-run, compensate in reverse, only reversible E or S and idempotent, default 15 ops, risk +1.

**Consequences:** Treating a Mode C plan as one transaction is harder: Mode C applies per-op, has no dry-run, and compensates in reverse. Lowering Mode C risk to match Mode T is harder: Mode C adds one risk level. The executor and approval flow must keep the two modes distinct.

**How to revisit:** A change to the Mode T or Mode C rules in [T8_BOT_ENGINE.md](../plans/next-phase/T8_BOT_ENGINE.md), recorded as a new ADR.
