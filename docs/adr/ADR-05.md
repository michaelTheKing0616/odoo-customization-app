# Union tools vs family tools

**Status:** accepted (2026-10-03). The visible tool shape is family lists. GATE-P6-04 has not been run. That eval is later evidence for this shape. It is not the decider.

**Context:** The agent runtime must not give the model an apply tool. Tool calls use the ADR-03 shape (text plus zero or more calls, each with an id, a name, parsed args, and the raw argument string) and the ADR-04 ladder (native, then `emulated_json`, then `emulated_text`). About twenty tools are visible at a time, drawn from the inspection, planning, and post-submit read-only lists.

**Options considered:**
- One union catalog. The model sees a single deterministically sorted list of every tool that is currently visible.
- Tools grouped by family. The model sees the inspection list, the planning list, or the post-submit read-only list that matches the current phase.

**Decision:** Use family lists. During inspection the model sees the inspection list. During planning it sees the planning list. After submit it sees the post-submit read-only list. About twenty tools are visible for the current phase. No list includes an apply tool.

**Consequences:** A later phase's tools stay off the current list, so an apply tool cannot appear beside inspection tools. GATE-P6-04 still has to measure this shape. If that eval misses its bar, this ADR is reopened. Prompts and cassettes written for a union catalog would have to be rewritten to match the family lists.

**How to revisit:** GATE-P6-04 misses its bar, or a phase needs a tool that cannot be expressed inside its family list.
