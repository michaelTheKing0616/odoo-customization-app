# EL-BR-EGRESS: Each flow may call only its declared hosts

ID: EL-BR-EGRESS
Title: Each flow may call only its declared hosts
Status: todo
Phase: 7
Priority: P2
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: ELR-NEXT
Depends on: EL-BAR-BR, SEC-SSRF
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 7 (C1 U1 F2 K1 V1 I1)
Context pack:
- apps/api/app/bridge/spec_import.py (private-host refusal)
- apps/api/app/bridge/delivery.py
File allow-list:
- apps/api/app/bridge/egress.py (new)
- apps/api/app/bridge/delivery.py (one check before send)
- apps/api/tests/test_bridge_egress.py (new)
Goal: Per-flow host allow-list at send time: a flow may call only the hosts it declared. The global private/loopback/metadata refusal is SEC-SSRF (handover §6.8); this card reuses it, never re-implements it.
Steps:
1. Resolve then check IPs (DNS rebinding)
2. Refusal is a dead letter with a plain reason
Acceptance criteria:
- AC1: undeclared host refused
- AC2: host resolving to 169.254.169.254 refused
- AC3: declared host passes
Test plan:
- `cd apps/api && uv run pytest -q tests/test_bridge_egress.py`
Elite design notes: SSRF guard at send time, not only at import time.
Oracle tests: docs/build-plan/elevate/ORACLES.md: EL-BR-EGRESS-1 metadata IP → refused; EL-BR-EGRESS-2 rebinding to private IP → refused
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). No existing behaviour is removed by this card; a ratchet baseline file, where present, keeps today's known gaps listed so the revert is clean.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
