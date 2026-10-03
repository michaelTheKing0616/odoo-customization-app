# Eval harness and tier thresholds

**Status:** accepted (engineering spec, 2026-10-03). This records the bars. It does not claim the eval harness is built.

**Context:** Tier A/B/C is model trust, not an Odoo version. [02_APPROVAL_FLOW.md](../plans/next-phase/02_APPROVAL_FLOW.md) and [T8_BOT_ENGINE.md](../plans/next-phase/T8_BOT_ENGINE.md) already write how a model's trust tier caps submit, critic, and explorer work. This ADR records those bars so a later harness cannot invent a different ladder.

**Options considered:**
- One trust level for every model. Native, emulated, and local models would share the same submit cap and the same promotion path.
- Tiers A/B/C with the bars in the Decision.

**Decision:** Use A/B/C. The bars are:

- A model tier below A caps submitted risk at R2.
- Tier C cannot submit a change-set.
- L2 to L3 needs a Tier A model.
- Emulated adapters stay capped at Tier B until the eval says otherwise.
- Critic runs for Tier A when risk is at least R2 or ops are at least 5.
- Explorer sub-runs are Tier A only.
- GATE-P4-04: Tier A at least 80% on 60 scenarios.
- GATE-P6-01: at least 150 scenarios.
- GATE-P6-02: at least one Tier A model.
- GATE-P6-03: local models honestly B or C.

**Consequences:** An emulated adapter claiming Tier A becomes harder until an eval lifts the cap. A Tier C model submitting a change-set becomes harder. The harness card is still open.
