# BV-HARDEN: Bot-verify backend hardening (BV-04/BV-05 follow-ups)

ID: BV-HARDEN
Title: Bot-verify backend hardening (BV-04/BV-05 follow-ups)
Status: in progress
Phase: 5
Priority: P2
Type: build
Owner: backend
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: NF-EPIC-BV;NF-BV-HARDEN
Depends on: BV-04 (23d84b58), BV-05 (8853c176). D-BV-HARDEN-1 = (B): F1 moved to BV-AUDIT.
Routing: Worker: L3 (live 17–20) · Tester + Reviewer separate sessions
Context pack:
- ~/.ingenium_nf/nfwt/BV-04_reviewer_indep.md (F1, F5, F7)
- apps/api/app/bot_verify/{walkthrough,flows,flow_library,targets,store}.py
- apps/api/tests/test_nf_bot_verify_flows.py, test_nf_bot_verify_walkthrough*.py
File allow-list:
- apps/api/app/bot_verify/walkthrough.py (F7, F5)
- apps/api/app/bot_verify/flow_library.py (Odoo 20 group pin)
- apps/api/app/bot_verify/flows.py (only if the pin needs it)
- apps/api/tests/test_nf_bot_verify_flows.py (clone wait raise, pin)
- apps/api/tests/test_nf_bot_verify_walkthrough*.py (F7, F5)
Goal: Close the deferred BV-04/BV-05 follow-ups so least-privilege and cleanup hold without manual care.
Steps:
1. Read the follow-ups in BV-04_reviewer_indep.md. Build only what the ACs name.
2. Write the tests first; they must fail before the code and pass after.
3. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts the epic doc; a check would need a non-`ingenium_` DB, a forbidden port (3002, 8001, 8002, 8012, 5433, 5436, 8069–8073, 11434, 54329), a git write, an outbound call to a third party, or a new dependency; an Odoo claim proves false on any of 17–20.
Acceptance criteria:
- AC1 Odoo 20 Time Off: requester gets exactly hr_holidays.group_hr_holidays_employee resolved by xmlid (module+name), not a name LIKE; absent xmlid -> clear failure, not a silent skip. Unit + live 20.
- AC2 clone fixture: the 20×1 s post-TEMPLATE source wait raises (TimeoutError with the DB name, no secrets) when the source never comes back; unit test with a fake probe.
- AC3 F7: WalkGroups can only be built by groups_for (private sentinel/factory); direct construction with system=True raises TypeError; existing callers unchanged.
- AC4 F5: the walk user is deleted (unlink by id, read back absent), or archived with no access where Odoo refuses deletion (archive, all groups cleared, password scrambled, read back archived + no groups; Odoo 20 refuses because admin lacks delete on calendar.user — NF-owner call 2026-10-24) in a finally after every run, pass or fail; live 17–20 read-back.
Test plan: own tests; focused set; combined both orders; live 17–20 on 18117–18120 with ingenium_nf_bv_* DBs, all dropped after.
Focused set: test_safety_route_registry, test_protected_registry, test_trust7_idor, test_trust7_credentials, test_trust7_app_db_restore, test_verify, test_nf_bot_verify_*.
Combined set: test_sec_gate_scope, test_reg_np_dev, test_nf_*_contract, both orders.
Gate: own ×2 green; focused/combined no new failures (known: test_pg_dump_smoke_to_temp); live green; cleanup 0.
Evidence to log: PROGRESS line with counts; cleanup check.
Rollback: revert the touched files.
Definition of Done: ACs pass; independent Reviewer APPROVE; merged; lock released.
