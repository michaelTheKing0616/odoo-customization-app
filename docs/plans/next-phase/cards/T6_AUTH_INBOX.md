# Cards — T6 auth, approval inbox, command center

Self-contained. Gates 6-1 to 6-4 and the role model: `../T6_AUTH_COMMAND_CENTER.md`. Approval rules: `../02_APPROVAL_FLOW.md`. D6 (self-hosted Authlib + TOTP) and D9 (Client Approver is a connection grant; out of scope returns 404) are closed.

**Shared do-not:** do not weaken a lock in `../01`; no secrets in logs (OAuth tokens, TOTP seeds, recovery codes, session ids are secrets); no customer database; `:8001` does not reload; never loosen a test; no live LLM in PR tests; stay inside "Change". **T6-specific:** do not replace the login stack; no Clerk, WorkOS, or Auth0; no second auth log (DoD 31); out-of-scope connections return 404, never a 403 with a body that confirms existence; the requester may approve their own R3; on the heavy R4 gate the requester cannot be both approvers; Slack, Teams, or chatter carry a link only, never an approve action for R ≥ 2; a reaction emoji is never an approval; SAML is later and does not block 6-1.

**Roles (copied):** Owner / Admin = workspace. Consultant = one or more named clients. Client Approver = one connection grant; sees that client's cards; approves and refuses; nothing else. Client Viewer = same scope, no approve.

**Already built (do not rebuild):** `users`, `workspaces`, `workspace_memberships`, `user_sessions`, `connection_access_grants`, `oauth_identities`, TOTP routes, `login_workspace`, Microsoft provider settings, `OAuthProviderButtons`, `client_access.py`. Change-set inbox seed: `apps/api/app/changeset/inbox.py`, `store.py`, `plan_card.py`, `routers/inbox.py` (`GET /api/inbox/plans`, `POST /api/inbox/plans`, `POST /api/inbox/plans/{plan_hash}/decide`), migration `q7r8s9t0u1v2_plan_cards`. Web seeds: `apps/web/src/app/approvals/page.tsx` (98 lines), `apps/web/src/app/command/page.tsx` (34 lines, static tiles).

**Shared commands:**

```bash
cd apps/api && ../../.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_client_approver_isolation.py tests/test_accounts.py tests/test_changeset_inbox.py \
  tests/test_plan_card_store.py tests/test_changeset_engine.py
pnpm --filter @odoo-custom/web test -- src/app/approvals
pnpm --filter @odoo-custom/web test:e2e e2e/a11y-primary.spec.ts
```

**Audit events:** `login`, `logout`, `grant`, `revoke`, `totp`, `approval`, `error`.

---

### T6-01 — Role matrix enforced in code
- **Status:** SEEDED (grants `client_approver` / `client_viewer` in `client_access.py`; owner/admin/consultant in workspace memberships).
- **Pressure:** C2 U1 F2 K2 V1 I1 +0 = 9 → Grok standard
- **Read first:** `apps/api/app/client_access.py`, `apps/api/app/workspace_auth.py`, `apps/api/app/account_models.py`.
- **Steps:** write one table constant `ROLE_CAPABILITIES` (role → allowed route groups) and a parametrized test that hits one route per group as each role.
- **Acceptance:** [ ] four roles × route groups matrix test; [ ] Client Viewer gets 403 on approve and 404 on other clients.
- **Negative:** Client Viewer `POST /api/inbox/plans/{hash}/decide` refused.

### T6-02 — Zero manual account linking (DoD 29, gate 6-1)
- **Status:** PARTIAL (Google, GitHub, Microsoft OAuth wired; TOTP mandatory status to verify).
- **Pressure:** C2 U2 F2 K2 V2 I1 +0 = 11 → Grok high effort
- **Read first:** `apps/api/app/oauth_service.py`, `apps/api/app/routers/accounts.py`, `apps/web/src/components/auth/OAuthProviderButtons.tsx`.
- **Steps:** (1) mocked OAuth callback tests for Google and Microsoft: new user, existing email user (auto-link by verified email only), second provider on the same user; (2) email + password + TOTP enrol + TOTP login; (3) one recorded live attempt per provider by the operator.
- **Acceptance:** [ ] the three paths need zero manual linking steps; [ ] linking only happens on a provider-verified email.
- **Negative:** an unverified provider email does not link to an existing account.
- **Do not:** log the OAuth code or token.

### T6-03 — Auth events in the one hash chain (DoD 31, gate 6-3)
- **Status:** PARTIAL. The HTTP audit middleware (`audit.py` → `audit_chain.append_entry`) writes an `http_mutation` chain row for mutating requests, which includes login POSTs. Typed kinds `login`, `logout`, `grant`, `revoke`, `totp` are not written.
- **depends_on:** 5A-05
- **Pressure:** C2 U1 F3 K2 V1 I2 +0 = 11 → Grok high effort; reviewer recommended (audit chain family)
- **Steps:** call `append_entry(kind=...)` at the success and failure points of login, logout, grant create/revoke, TOTP enrol/disable, role change. Payload: actor, target user, provider, result. Never the token.
- **Acceptance:** [ ] each event produces exactly one typed row in `audit_chain_entries`; [ ] `verify_db` stays green; [ ] no second table.
- **Negative:** a failed login writes a row without the attempted password (redaction test).

### T6-04 — Inbox API binds to the fingerprint (14+ card)
- **Status:** SEEDED (`routers/inbox.py`; `test_submit_renders_a_card_and_hides_other_connections`, `test_r4_is_not_queued`, `test_other_connection_is_not_found`).
- **depends_on:** 5A-03
- **Pressure:** C2 U2 F3 K3 V2 I2 +0 = 14 → frontier
- **Read first:** `routers/inbox.py` (lines 34–70), `changeset/store.py`, `changeset/plan_card.py`, `../02_APPROVAL_FLOW.md` steps 7–9.
- **Open delta:** (1) the decide body must carry `plan_hash` and `schema_fp`; a mismatch returns 409 `plan_stale`; (2) approvals expire (production 24 h, staging 7 d); (3) choices are approve, deny, deny-and-stop; (4) a freeze window blocks approve.
- **Acceptance:** [ ] 409 on hash mismatch; [ ] expired approval refused at apply (RT-19); [ ] freeze blocks (RT-20).
- **Negative:** RT-17 (replay an approval on a modified plan) refused.

### T6-05 — Plan card render (nine sections from the engine)
- **Status:** SEEDED (`plan_card.render_plan_card`; `test_every_catalog_op_has_a_nine_section_card`).
- **depends_on:** T6-04
- **Pressure:** 10 → Grok high effort
- **Sections (copied):** goal and assumptions; each change; impact; risk and why; what is not changing; how it will be checked; how to undo; environment; plan fingerprint and expiry.
- **Acceptance:** [ ] the web page renders the nine sections from the API payload with no client-side text generation; [ ] snapshot test of the JSON (GATE-P3-10).
- **Negative:** changing an assumption produces a new hash and voids the old card.

### T6-06 — R3 one approval; heavy R4 keeps two people (14+ card, reviewer)
- **Status:** RETARGETED 2026-10-04. Tope: a consultant's everyday R3 work is one approval, and that approver may be the requester. The old two-person gate moves to heavy R4. Hard stop stays on raw SQL, `rpc.write`, payment secrets, posted entries, lock dates, and a group-less access rule.
- **depends_on:** T6-04
- **Pressure:** C2 U2 F3 K3 V2 I2 +0 = 14 → frontier + reviewer
- **Acceptance:** [ ] production R3 is approved by one person, who may be the requester; [ ] heavy R4 on production needs two distinct people, the domain owner when protected, a passed simulation, a backup, and an allowed window; [ ] hard-stop R4 is refused; [ ] the inbox decide route can carry a heavy-R4 approval.
- **Negative:** one user with Google and Microsoft identities approving twice counts once on the heavy gate. The requester cannot be both of the two heavy-gate approvers.

### T6-07 — Client scope on the inbox
- **Status:** SEEDED (`test_other_connection_is_not_found`, `test_connection_inboxes_do_not_leak_cards`).
- **Pressure:** 8 → Grok standard
- **Acceptance:** [ ] a Client Approver lists only their connection's cards; any other plan hash returns 404 "not found"; [ ] gate 6-2 extended to the inbox.

### T6-08 — Command center home
- **Status:** DONE. vitest command page 3 passed and approvals page 1 passed. pytest tile tests 2 passed.
- **depends_on:** T6-03, UI-F02, UI-F03
- **Pressure:** 8 → Grok standard
- **Acceptance:** [x] tiles for clients, pending approvals, failed jobs, drift, each with its own skeleton so a slow source does not blank the page; [x] a Client Approver opening `/command` is sent to their inbox.
- **Negative:** a Client Approver opening `/command` lands on their inbox, not a consultant page with hidden buttons.

### T6-09 — Per-client page
- **Status:** DONE. vitest `src/app/connections/[id]/client/page.test.tsx` — 2 passed.
- **depends_on:** T6-08
- **Pressure:** 7 → Grok standard
- **Acceptance:** [x] connection, open change-sets, last snapshot, and (when T8 exists) bot roster for one connection. The roster says it is not available yet.

### T6-10 — Team grants UI
- **Status:** OPEN (API exists: `POST /api/accounts/connection-grants`).
- **depends_on:** T6-01
- **Pressure:** 7 → Grok standard
- **Acceptance:** [ ] grant and revoke from the UI; each writes `grant` / `revoke` audit rows (T6-03).

### T6-11 — 14b live five-track dashboard (DoD 32, gate 6-4)
- **Status:** OPEN
- **depends_on:** T6-03, T6-07, and tracks emitting data
- **Pressure:** C3 U2 F2 K2 V2 I0 +0 = 11 → Grok high effort
- **Acceptance:** [ ] one screen shows live data from Tracks 1–5 in one environment at once (T1 generate jobs, T2 protocol per connection, T3 Bridge events, T4 progress or dashboards, T5 audit chain verify status).
- **Negative:** a Client Approver sees only their connection's rows.

### T6-12 — SAML recorded as later
- **Status:** DONE (`../18` OQ-SAML).
- **Pressure:** 1 → cheap. No code.

### T6-13 — Approval links in channels
- **Status:** OPEN (lands with T8-BOT-SLACK)
- **Pressure:** 6 → Grok standard
- **Acceptance:** [ ] Slack, Teams, and chatter cards contain a link to `/approvals/<hash>` and no approve button for R ≥ 2; [ ] mobile R3 shows the full diff (GATE-P5B-10).
