# Union tools vs family tools

**Status:** open. Blocking question: whether the model sees one union tool list or separate family tool lists. That is decided by eval GATE-P6-04, which has not been run.

**Context:** The agent runtime must not give the model an apply tool. Tool calls use the ADR-03 shape (text plus zero or more calls, each with an id, a name, parsed args, and the raw argument string) and the ADR-04 ladder (native, then `emulated_json`, then `emulated_text`). How the visible names — about twenty at a time from the inspection, planning, and post-submit read-only lists — are presented to the model is still open.

**Options considered:**
- One union catalog. The model sees a single deterministically sorted list of every tool that is currently visible.
- Tools grouped by family. The model sees separate lists for inspection, planning, and post-submit read-only tools, and may see only the family that matches the current phase.

**Decision:** None yet. GATE-P6-04 has not been run. This ADR does not pick a winner.

**Consequences:** Until the eval, shipping a tool surface as if the shape were settled stays harder. Changing the shape after prompts and cassettes exist also stays harder: both prompt layers and recorded conformance tapes would have to be rewritten.

**How to revisit:** Run GATE-P6-04. Accept this ADR only from that eval.
