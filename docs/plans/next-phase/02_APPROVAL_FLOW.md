# Approval, in plain English

The model never writes. Only the executor writes, and only after every step below has passed. Today the repo has connection-scoped approval rules, a Client Approver grant with negative tests, and metadata snapshots with rollback. The hash-bound plan card, the two-person R3 rule, the journal, the executor, the audit chain, and the approval inbox are specified here and are not built.

## The fifteen steps

1. **Someone asks.** A consultant, a client admin, or a bot routine describes a change in chat, a form, or a routine. The system can only read. Text from Odoo, files, the web, or another bot is data. It never acts as an instruction, never grants permission, and never changes policy (INV-08, INV-09).

2. **It checks the real database.** The engine looks up models, fields, views, menus, groups, and settings on that connection and that version, including Odoo 20 `ir.access`. A name it cannot find is rejected, with at most 3 "did you mean" suggestions. It does not invent an `x_` field to fill a gap.

3. **It writes a plan made only of approved operation types.** The request becomes a change-set: a list of typed operations from the closed catalog in `T8_BOT_ENGINE.md`. There is no "call any method" operation, no raw SQL, and no `rpc.write` (INV-02). A change-set holds at most 50 operations (Mode C default 15). Bigger asks split into work packages of about 15 operations.

4. **Nine validation checks run in order, and all of them run:**
   1. Shape. At most 50 ops. Params at most 64KB per op.
   2. Static safety.
   3. Grounding against the same-run introspection.
   4. Dependency DAG.
   5. Preconditions.
   6. Impact: rows touched, users affected.
   7. Risk and policy.
   8. Lints.
   9. A validation report.
   Any failure returns the plan for repair, at most 4 rounds, then stops and explains.

5. **Risk is assigned by code, not by the model.** The model cannot talk a class down (INV-07).

   | Class | Meaning |
   |---|---|
   | R0 | Read only |
   | R1 | Cosmetic and reversible |
   | R2 | Functional configuration |
   | R3 | Security, money, mass data, outbound messages, code, or modules |
   | R4 | Prohibited |

   Risk rises by one, and never falls, when any of these is true: the target is `protected:elevate`; more than 1,000 rows are affected or a stored-compute touches a table over 100,000 rows; the change is outbound; production has no simulation; more than 10 users or any admin is affected; the executor is Mode C. Clamp at R4.

   R4 examples: lock dates, posted accounting entries, payment secrets, module uninstall, raw delete, SQL, granting admin, group-less ACL, accounting or legal sequence changes.

6. **Policy decides who must approve.** Staging and production are different.

   | Risk | Staging | Production |
   |---|---|---|
   | R0 | allow | allow |
   | R1 | allow if autonomy ≥ L3, else 1 approval | 1 approval. Auto only at L4 inside the allow-list, or at L3 with a prior staging success and Mode T when the tenant opted in |
   | R2 | 1 approval | 1 approval + simulation. L4 only if the op is on the allow-list and passes GATE-L4-01 |
   | R3 | 1 approval | 2 approvers, plus the domain owner when the target is elevated, plus simulation, plus backup, plus an allowed window |
   | R4 | deny | deny |

   Approvals expire after 24 hours on production for R≥2 and after 7 days on staging. The approver is not the requester for R3. A freeze window blocks every apply. A model tier below A caps submitted risk at R2. Tier C cannot submit a change-set.

7. **It shows exactly what will change.** Before and after, who will see it, how many rows change, and what will not change. Database-structure changes and anything R3 run first on a neutralized staging copy. Small non-structural changes may dry-run inside a Bridge transaction that rolls back. DDL never dry-runs in place on production. A failed simulation returns to planning.

8. **The engine renders the plan card. The model does not write it.** Nine sections, in order:
   1. Goal and assumptions.
   2. Each change.
   3. Impact.
   4. Risk and why.
   5. What is not changing.
   6. How it will be checked.
   7. How to undo.
   8. Environment.
   9. Plan fingerprint and expiry.
   Changing any assumption voids the card and produces a new hash (INV-04).

9. **A human approves that exact fingerprint.** Choices are approve, deny, or deny and stop the run. A Client Approver sees only their client's cards. Any other client returns 404, not 403. Slack, Teams, and Odoo chatter may only link to the approval page. R2 and above are never approved from a chat button. A reaction emoji is not an approval. On a narrow viewport, R3 shows the full diff (GATE-P5B-10).

10. **Apply time rechecks everything.** The executor locks the database (one apply per database). It recomputes the plan hash and the schema fingerprint and re-reads policy. It refuses when the database changed (status STALE), the approval expired, a freeze is on, or the kill switch is set. Destructive, billable, or R3 production applies also require a snapshot reference recorded immediately before apply. No snapshot, no apply (master DoD 28).

11. **It writes one operation at a time and journals first.** Each op writes INTENT, then BEFORE, then RESULT. A heartbeat lands every 5 seconds. Mode T (Bridge) is one transaction. Mode C (plain RPC) applies one by one and compensates in reverse on failure. Mode C warns that it is not atomic, which is why it adds one risk level. Writes are never retried blindly. If the process crashes, a recovery job finds an APPLYING row whose heartbeat is older than 60 seconds and resumes or compensates from the journal. Stale APPLYING is detected within 2 minutes (SLO).

12. **Deterministic checks confirm the result.** Code checks each postcondition, the expected fingerprint diff, view rendering as the requester, as a low-privilege user, and as portal, access regressions, and that no unexpected mail or automation fired. The model may describe the outcome. It cannot mark a failure as success (INV-16). VERIFY_FAILED rolls back automatically for R≥2 when a hard postcondition failed. Otherwise the change-set is NEEDS_HUMAN with a runbook.

13. **Undo is a new change-set.** The inverse is computed at plan time. Undo runs through the same pipeline, then a metadata snapshot is compared. Exact inverse restores metadata. Soft inverse applies when people have typed data into a new field: undo hides the field and reports the data that remains. Deleting that data is a separate, higher-risk approval. If the snapshot does not match, the result is NEEDS_HUMAN, not a silent rewind.

14. **One tamper-evident chain records it.** Logins, grants, approvals, applies, rollbacks, bot handoffs, and routine runs append to the same hash-chained audit log (master DoD 31). Secrets never appear. The entry shape is in `11_LOGGING_AUDIT_OBSERVABILITY.md`.

15. **Autonomy is earned, and it can be lost.**

    | Level | What it may do |
    |---|---|
    | L0 | Ask only |
    | L1 | Plan only, no submit |
    | L2 | Apply with approval. This is the GA default |
    | L3 | R1 automatically on staging. Production R1 only with a prior staging success, Mode T, and an admin opt-in |
    | L4 | Allow-listed R1 and narrow R2 on production, under GATE-L4-01–12 in `01_LOCKS_DECISIONS_CONFLICTS.md` |

    Ladder evidence: L1→L2 needs ≥10 successful reviewed plans and either Bridge or staging. L2→L3 needs ≥50 R1/R2 applies, 0 verify failures, ≤2% rollback over 30 days, a Tier A model, and an admin opt-in. L3→L4 needs GATE-L4-08. Any verify failure, policy violation, or Odoo major change demotes automatically.

    A routine's Test button is a dry run with zero writes and zero outbound calls (EV-BOT-07). Standing rules cover R0–R1, plus the narrow R2 band only at L4. Default expiry is 90 days, and 30 days at L4 (GATE-L4-05). A standing rule for R2 outside L4, or for R3, is rejected (EV-BOT-13, RT-42).

## Lifecycle states

DRAFT → VALIDATED → SIMULATED → PENDING_APPROVAL → APPROVED → APPLYING → APPLIED → VERIFYING → VERIFIED.

Failure terminals: INVALID, SIM_FAILED, REJECTED, EXPIRED, FAILED → ROLLING_BACK → ROLLED_BACK or PARTIALLY_ROLLED_BACK or NEEDS_HUMAN, VERIFY_FAILED.

## What "approve" is not

- Not a Test button. Test never touches the target.
- Not an Always button that survives a hash change.
- Not a Slack reaction.
- Not the model saying the policy allowed it.
- Not a second run of an expired card.
