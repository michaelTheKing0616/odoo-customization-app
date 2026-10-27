# B0-JUNKb: Live cleanup count, and the distDir note

ID: B0-JUNKb
Title: Live cleanup count, and the distDir note
Status: blocked
Phase: 0
Priority: P0
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: P0-3-AC4
Depends on: B0-JUNK
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L2 separate session · Score: 3 (C1 U0 F1 K1 V0 I0)
Context pack:
- docs/build-plan/cards/phase-0/B0-JUNK.md
- scripts/cleanup_test_connections.py
- docs/build-plan/FACTS.md
File allow-list:
- scripts/cleanup_test_connections.py
- apps/api/tests/test_b0_junk.py
Goal: Report the live connection count after a cleanup. Do not run `--apply` until Tope's yes in the current message, and run `pg_dump -Fc` first.
Steps:
1. AC1 stays stopped. `--apply` on a non-disposable database is off.
2. AC2 is a read. `next.config` distDir is already `[Done, live]` on B0-DIST (`P0-4-AC1` through `P0-4-AC4`). Cite the line. Do not edit that file.
3. STOP-AND-ASK: the distDir guard is missing, or a live apply is requested without a yes.
Acceptance criteria:
- AC1: After Tope's yes and `pg_dump -Fc`, `--apply` runs, then `GET /api/connections` returns only real connections and the count is reported. Until that yes, this AC stays open. (source: INGENIUM_MASTER_HANDOVER.md L476)
- AC2: The distDir guard cited from B0-DIST is still in the repo, with the file and line in the Worker packet. No edit. (source: INGENIUM_MASTER_HANDOVER.md L189)
Test plan:
- Do not run `--apply`. AC2 is the cited line.
Gate: D (destructive step needs Tope's explicit yes; `pg_dump -Fc` first). `--apply` stays off.
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md` when AC1 has a count.
Rollback: Revert the allow-list files only. Do not drop a database this card did not create.
Definition of Done: AC1 has Tope's count, or stays blocked; AC2 cites the line; no file outside the allow-list changed.
