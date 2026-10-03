# Who approves, two-person rule, expiry

**Status:** accepted as the proposal in [02_APPROVAL_FLOW.md](../plans/next-phase/02_APPROVAL_FLOW.md). L4 stays off until Tope confirms the thresholds.

**Context:** The model never writes; only the executor writes, and only after the steps in that file. R3 covers security, money, mass data, outbound messages, code, or modules. This ADR records who must approve, the two-person rule, and expiry, without treating L4 as on.

**Options considered:**
- Single approver for every risk. One person could approve any class the same way, including production R3, with no second person, no domain-owner step, and no separate simulation, backup, or window.
- Risk-banded rules in [02_APPROVAL_FLOW.md](../plans/next-phase/02_APPROVAL_FLOW.md). Production R3 needs 2 approvers, plus the domain owner when the target is elevated, plus simulation, backup, and an allowed window. The approver is not the requester for R3. Approvals expire after 24 hours on production for R at or above 2, and after 7 days on staging.

**Decision:** Follow [02_APPROVAL_FLOW.md](../plans/next-phase/02_APPROVAL_FLOW.md). L4 numeric thresholds still need Tope's confirm before L4 is enabled.

**Consequences:** Slack, Teams, and Odoo chatter may only link to the approval page; a chat button or emoji is not an approval, so approving R3 from chat becomes harder. The requester cannot approve their own R3. L4 stays off until Tope confirms the thresholds.
