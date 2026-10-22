# EL-CONN-LEASTPRIV: Rights advisor: connect with the least access Ingenium needs

ID: EL-CONN-LEASTPRIV
Title: Rights advisor: connect with the least access Ingenium needs
Status: todo
Phase: 7
Priority: P2
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: ELR-NEXT
Depends on: EL-BAR-CONN, SEC-LEASTPRIV
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 6 (C1 U1 F2 K1 V1 I0)
Context pack:
- handover §3.2
- apps/api/app/routers/connections.py (`/live-check`)
File allow-list:
- apps/api/app/rights_advisor.py (new)
- apps/api/tests/test_rights_advisor.py (new)
- apps/web/src/components/connect/RightsAdvisor.tsx (new)
Goal: Extends SEC-LEASTPRIV (handover §6.3/§6.4 guide) with a live check: read the connected user's groups; say which Ingenium features each group enables; recommend a dedicated integration user with only the needed groups, with a step-by-step guide. Never changes users itself.
Steps:
1. Read-only `res.users` / `res.groups` for the connected user [Inferred field names per major, verify]
2. Guide opens Odoo's own user screen; Ingenium never mints keys or edits users
3. UI: every screen this card touches meets handover §5 + `UI_REFERENCE_MAP.md` + `07_UI_EXCELLENCE_PROTOCOL.md` (Tope: the absolute best design on every screen): designed empty/loading/error/offline states, tokens only, Base UI + Sonner, motion < 300 ms transform/opacity with reduced-motion, plain copy that passes the jargon guard. UI checkpoints only: baseline, after, final (one contact sheet per screen).
Acceptance criteria:
- AC1: no write RPC on any path
- AC2: admin user → 'more access than needed' with the exact list
- AC3: copy passes jargon guard
Test plan:
- `cd apps/api && uv run pytest -q tests/test_rights_advisor.py`
Elite design notes: Advice only. Group-to-feature map lives in one table with a test per feature.
Oracle tests: docs/build-plan/elevate/ORACLES.md: EL-CONN-LEASTPRIV-1 admin user → over-privileged verdict; EL-CONN-LEASTPRIV-2 any path → zero write calls
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). No existing behaviour is removed by this card; a ratchet baseline file, where present, keeps today's known gaps listed so the revert is clean.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
