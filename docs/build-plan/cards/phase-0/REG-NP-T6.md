# REG-NP-T6: Role matrix enforced in code

ID: REG-NP-T6
Title: Role matrix enforced in code
Status: done
Phase: 0
Priority: P2
Type: regression
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: NP-T6-01;NP-T6-02;NP-T6-03;NP-T6-04;NP-T6-05;NP-T6-06;NP-T6-07;NP-T6-08;NP-T6-09;NP-T6-10;NP-T6-12
Depends on: B0-INV
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L3 separate session · Score: 6 (C2 U1 F1 K1 V1 I0)
Context pack:
- `sed -n '25,96p' docs/plans/next-phase/cards/T6_AUTH_INBOX.md`
- `sed -n '105,107p' docs/plans/next-phase/cards/T6_AUTH_INBOX.md`
- `sed -n '23p' docs/plans/next-phase/18_OPEN_QUESTIONS.md`
- `sed -n '75,103p' apps/api/tests/test_changeset_engine.py`
- docs/build-plan/FACTS.md
File allow-list:
- apps/api/tests/test_reg_np_t6.py (new)
Goal: Pin the already-fixed behaviour behind `REG-NP-T6` with a test that fails if it regresses; no product change.
Steps:
1. Read the context pack. State the fixed behaviour this regression pins, as input → expected output, one per AC.
2. Write the regression test only (product code is read-only for this card).
3. Prove it can fail: in the Worker packet name the product line whose deletion would make the test fail.
4. Run the Test plan command → green; run it in reverse/random order → green.
5. If the behaviour is already broken, stop: report the failing assertion; the Orchestrator opens a fix card.
6. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong.
Acceptance criteria:
- AC1: Role matrix enforced in code (pressure 9) (source: ledger NP-T6-01, next-phase cards/T6_AUTH_INBOX.md)
- AC2: Zero manual account linking (DoD 29; gate 6-1) (pressure 11) (source: ledger NP-T6-02, next-phase cards/T6_AUTH_INBOX.md)
- AC3: Auth events in the one hash chain (DoD 31; gate 6-3) (pressure 11) (source: ledger NP-T6-03, next-phase cards/T6_AUTH_INBOX.md)
- AC4: Inbox API binds to the fingerprint (14+ card) (pressure 14) (source: ledger NP-T6-04, next-phase cards/T6_AUTH_INBOX.md)
- AC5: Plan card render (nine sections from the engine) (pressure 10) (source: ledger NP-T6-05, next-phase cards/T6_AUTH_INBOX.md)
- AC6: R3 one approval; heavy R4 keeps two people (pressure 14) (source: ledger NP-T6-06, next-phase cards/T6_AUTH_INBOX.md)
- AC7: Client scope on the inbox (pressure 8) (source: ledger NP-T6-07, next-phase cards/T6_AUTH_INBOX.md)
- AC8: Command center home (pressure 8) (source: ledger NP-T6-08, next-phase cards/T6_AUTH_INBOX.md)
- AC9: Per-client page (pressure 7) (source: ledger NP-T6-09, next-phase cards/T6_AUTH_INBOX.md)
- AC10: Team grants UI (pressure 7) (source: ledger NP-T6-10, next-phase cards/T6_AUTH_INBOX.md)
- AC11: SAML recorded as later (pressure 1) (source: ledger NP-T6-12, next-phase cards/T6_AUTH_INBOX.md)
Worked examples:
- Pin AC1: a logged-in `client_viewer` `GET /api/connections/{other_id}` returns 404. `POST /api/inbox/plans/{hash}/decide` with `decision: "approve"` returns 403. A role the matrix allows does not get 403 on that route group.
- Pin AC2: `resolve_oauth_login` with a verified existing email and a Google `OAuthProfile` sets `result.user.id` to that user and writes one `OAuthIdentity`. The same email with `email_verified is False` raises code `oauth_unverified_collision`. There is no separate manual-link step.
- Pin AC3: `POST /api/accounts/login` with the right password writes exactly one `login` audit-chain row, `payload.result == "success"`, `payload.provider == "password"`, and the password is not in `payload_json`. A wrong password also writes one `login` row and does not store the password. `verify_db` after login, logout, and a failed login returns `(True, None)`. There is no second auth-audit table. Grant and revoke each write one typed row (AC10).
- Pin AC4: decide whose `schema_fp` differs from the card returns 409 `detail.error == "plan_stale"`. `apply_approved_plan` at or after `expires_at` raises `ApprovalExpired`. A freeze window makes approve return 409 `detail.error == "frozen"` and leaves the plan `pending`.
- Pin AC5: `render_plan_card` emits the nine `PLAN_CARD_COPY_SECTIONS` in order: goal and assumptions, each change, impact, risk and why, what is not changing, how it will be checked, how to undo, environment, plan fingerprint and expiry. Changing an assumption changes the hash.
- Pin AC6: `policy_decision("R3", "production")` is `approvers == 1`, `deny is False`, `allow is True`, `needs_simulation is False`. `self_approval_allowed("R3")` is True and `self_approval_allowed("R4")` is False. `policy_decision("R4", "production")` is `deny is True`. `policy_decision("R4", "production", heavy=True)` is `approvers == 2`, `allow is True`, `needs_simulation`, `needs_backup`, and `needs_window` all True.

| Risk | Environment | Flags | Decision |
|---|---|---|---|
| R3 | production or staging | requester may approve | 1 approver, allowed, no simulation |
| R4 | production or staging | not heavy | `deny is True` |
| R4 | production | `heavy=True` | 2 approvers, simulation, backup, window |
- Pin AC7: `client_approver` and `client_viewer` `GET /api/connections/{other_id}` returns 404, not a 403 body that names the other connection.
- Pin AC8: workspace role `client_approver` with one connection `conn-granted` replaces the route with `/approvals?connection_id=conn-granted` and does not render `command-tile-clients`. A slow `/api/command/tiles/pending-approvals` leaves `command-tile-pending-approvals-skeleton` up and does not blank the other tiles.
- Pin AC9: connection client page for "Acme Odoo" shows one open plan "Add invoice note field", snapshot label "sale.order.form", id "snap-latest", and `connection-client-bot-roster` text matching "not available yet".
- Pin AC10: `POST /api/accounts/connection-grants` with an existing verified email and role `client_approver` returns 201 and one `grant` row with `result == "success"`. An unknown email returns 404 and one `grant` row with `result == "failure"`. `DELETE /api/accounts/connection-grants/{id}` returns 204 and one `revoke` row with `result == "success"`. `ConnectionTeamGrantsPanel` calls `api.createConnectionGrant` and `api.deleteConnectionGrant`.
- Pin AC11: `docs/plans/next-phase/18_OPEN_QUESTIONS.md` row `OQ-SAML` says SAML is not decided and "T6-12 records it as later". `apps/api/app` has no SAML symbol. Do not add one.
Test plan:
- `cd apps/api && uv run pytest -q tests/test_reg_np_t6.py` → pass
- `cd apps/api && uv run pytest -q tests/test_reg_np_t6.py` in reverse/random order → pass
Common mistakes: direct `execute_kw` outside the write gate; LLM calls outside `app/ai_client`; positional xpath; `attrs`; `<tree>` vs `<list>` by major; tests touching a non-`ingenium_` DB; restarting `:8001` (it runs without --reload).
Elite design notes: Sign-in (handover §6.1): Argon2id hashes; cookies HttpOnly + Secure + SameSite=Lax; rotation on login; idle 12 h; CSRF token on every state-changing cookie request; same response for known and unknown emails; rate-limited login/reset/MFA. Use existing libraries only (never custom crypto); if a needed library is not in `apps/api/pyproject.toml`, STOP-AND-ASK (licence must be FOSS, INV-09). Self-approval is allowed for any requester and audited (Tope 21 Oct, SEC-SELFAPPROVE inverted). Pitfall: auth checks in the UI only; every check is server-side.
Oracle tests: Oracle-first: a separate L3 Oracle session writes red tests in `apps/api/tests/test_reg_np_t6.py` (one positive + one negative per AC, named `test_ac<n>_...`) before the Worker starts; locked (Worker may not edit); E1 reviews them when score ≥ 10 (DEC-046).
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
