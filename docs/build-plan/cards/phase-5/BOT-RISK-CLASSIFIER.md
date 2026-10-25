# BOT-RISK-CLASSIFIER: Task → risk class → controls, per-button, refuse by default

ID: BOT-RISK-CLASSIFIER
Title: Risk classifier and RF-* refusal engine with per-button resolution
Status: todo
Phase: 5
Priority: P1
Type: build
Owner: NF (backend)
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: NF-EPIC-BOT;NF-BOT-RISK-CLASSIFIER
Depends on: BV-AUDIT-WIRE (refusals are written to the wired audit store). Blocks: BOT-KILL-AUDIT, BOT-DIFF-BLAST.
Routing: Worker: L3 · Tester + Reviewer separate sessions
Context pack: ~/.ingenium_nf/taxonomy/{RISK_MODEL.md,DECISIONS.md,catalogue.csv}
File allow-list (5):
- apps/api/app/bots/risk/classifier.py (new)
- apps/api/app/bots/risk/buttons.py (new; per-button resolver)
- apps/api/app/bots/risk/rules.py (new; RF-* engine + caps/tiers policy)
- apps/api/app/bots/risk/catalogue_rows.json (new; generated from catalogue.csv)
- apps/api/tests/test_nf_bot_risk.py (new)
Goal: Every Bot task resolves to exactly one class R0–R9/R2W/R8C, its controls, and its approval tier; anything unresolved is refused.
Steps: 1. Tests first. 2. STOP-AND-ASK: a needed file is outside the allow-list; a non-`ingenium_` DB; a forbidden port (3002, 8001, 8002, 8012, 5433, 5436, 8069–8073, 11434, 54329); a git write; a new dependency.
Acceptance criteria:
- AC1 classify(task_id, ctx) returns {class, controls, tier}; an id not in the catalogue → refusal RF-ANY "unknown task" (escalate, never improvise). Evidence: test.
- AC2 Per-button: resolve a button from live ir.ui.view arch (type=object name=method) + ir.model to (model, method); class comes from a method→effect table (posting: account.move.action_post, button_validate on stock.picking, mrp button_mark_done; mail: message_post/action_send*/send_mail; delete: unlink, merge wizards) — NOT from the button label. Evidence: a button labelled "Process" calling action_post → R4; a label "Post" calling a harmless method → its true class; unknown method on account.*/stock.*/mrp/pos → R4 (fail-safe high), elsewhere → refused unclassified.
- AC3 Mapping overrides from RISK_MODEL "Mapping" (sequences R8C; auth/web.base.url/signup/database params R8; mail/sms/iap crons R5; module_* settings R7). Evidence: one test each.
- AC4 Policy: size-cap 50/batch, 500/run, tier L1/L2/L3 per class, per-client override that may only tighten unless the override itself is approved at L3. Evidence: tests incl. loosen-without-L3 refused.
- AC5 Each irrecoverable class (R3,R4,R5,R6,R8,R8C,R9) has ≥1 RF rule; one negative test per control x class, each refusal names the missing control. Evidence: parametrised test, count logged.
- AC6 Version: 17–20 only; Odoo 20 security tasks route to ir.access (no ir.model.access/ir.rule assumptions) and never select XML-RPC. Evidence: test with v20 fixture metadata.
- AC7 Every refusal is written via targets audit store (decision=refused, rule id). Evidence: rows.
- AC8 Route-aware controls: ctx.route ∈ {A RPC-only, B DB access}; hosted/RPC-only is never a refusal reason by itself. R2W/R3/R6-archive/R8/R9-metadata on A require before-image + batch-1 proven undo (BOT-SNAPSHOT-PROOF) instead of snapshot; on B snapshot-proof. Irreversible on A stay L3 + typed confirmation + stated limit, with mitigation: R4 posted move → reversal via account.move.reversal (catalogue 17–20; never button_draft/delete on prod); R4 validated picking → return picking as counter-document: 17 stock.return.picking.create_returns; 18–19 stock.return.picking.action_create_returns / action_create_returns_all; 20 (no wizard model) stock.picking.action_return → draft return picking → action_return_all → button_validate (R4); action_exchange R2W, action_clear_return R1; R5 → outbox-hold via queued mail.mail + ir.mail_server inactive on copy (17–20); R6 → archive-first (action_archive/action_unarchive 17–20), hard delete with dependents refused; R8C with transactions → refused unless L3 cites data-impact report; R8 → lockout sim on copy, keep Bot API key (res.users.apikeys 17–20); R9 → base.module.uninstall preview data-loss list (17–20) on copy first. Evidence: parametrised route x class test.
Non-goals: executing anything; UI; kill switch; blast counts (BOT-DIFF-BLAST); full button sweep beyond posting/stock/mail/delete.
Test plan: own tests x2; combined focused set both orders (fwd/rev) x2 each; test PG 54339. Live 17 + 20 (19 for stock.picking validate delta): resolve the seed buttons from real views on ingenium_nf_* DBs. Adversarial: button with context/method override in an inherited view (last-applied arch wins), server-action buttons (type=action → resolve ir.actions.server code target or refuse), same method name on two models.
What can still go wrong: Route A mitigations are counter-documents, not undo (numbering gaps, sent mail stay permanent); methods that post indirectly (wizard → action_post) are only caught if the wizard chain is resolved; the method table is hand-curated and must grow via catalogue regression fixtures.
Evidence to log: PROGRESS line; rule count; live resolution table 17/20.
Rollback: revert files (new module only).
Definition of Done: ACs pass; independent Reviewer APPROVE; merged; lock released.

## Worker result (2026-10-25, after reviewer rounds 1-7; Reviewer APPROVE round 7)
Files: apps/api/app/bots/risk/{classifier.py,buttons.py,rules.py,catalogue_rows.json}; apps/api/tests/test_nf_bot_risk.py (incl. live 17/20 return flow); apps/api/tests/test_nf_bot_risk_adversarial.py (reviewer probes rounds 1-6, + property/drift tests). Generator: ~/.ingenium_nf/taxonomy/gen_risk_rows.py (catalogue.csv + fields_inventory.csv -> catalogue_rows.json, sha256 of both).
Design (one floor layer on every path; final class = MAX(path class, floor)):
- Derived model/method/unlink/param/module floors from every catalogue row R4-R9 (rules.derive_floors); field floors from fields_inventory.csv structure (rules.field_rule): sensitive comodels (R8/R8C), mail models/comodels (R5), mail.alias*/fetchmail.*, mail.template text, website domain/url, publish flags, website.rewrite redirects, credential name tokens (secret/key/token/password/api/oauth/environment/terminal/webhook, provider_ref), `state` on credential-holding models (R8), identity (partner email/phone/vat/bank_ids, bank, employee) R8, valuation (location usage, uom factor, product cost) R4. Drift tests recompute both; hand extras only add.
- Credentials fail closed (round 5): lowercased substring stems (pass, pwd, secret, token, key, cert, pem, signature, otp, bic, iban, swift, acc/account_number, client_id/identifier, endpoint, cdn, smtp_user/ssl; url on ir.mail_server/website/peppol) -> R8 unless in the reviewed CREDENTIAL_SAFE list (model prefix + stem + reason: SEO keywords, certification skills, counters, KPI toggles, accounting grouping keys, ...). Sweep drift test over fields_inventory.csv. SENSITIVE_MODELS (mail/fetchmail servers, banks, payment provider/token, oauth/passkey, carrier, POS payment method, website.rewrite, calendar credentials/provider config, push devices, IAP, LDAP, res.users.settings, *peppol*): every field takes R8 unless in SENSITIVE_SAFE_FIELDS (name, sequence, active, display_name, color).
- Security switches (round 6): extra stems auth_, authoriz, signup, invite, sid, redirect, force_, lock, hash, totp, 2fa, portal, public, private_; scoped stems domain (website/mail/settings), session (res.users/ir./auth/settings), allow_/enable_ (settings); url on ir.attachment -> R8. force_*hash -> R4 irr. Inventory re-swept 17-20 by prefix; harmless hits SAFE-listed with reasons (residual amounts, sidebar/UI, kanban blocked states, send-now/tax/address options, public holidays/categories, authorized amounts, POS session links). 'certif' SAFE no longer covers res.users.
- Unknown field set (non-literal vals/**kwargs) refused on code paths; fields not in the inventory floor to the model's worst field, refused when the model has none (both catalogue and code paths, incl. opt-in models).
- Default-deny: code-path writes allowed only on rules.REVIEWED_LOW_RISK (24 label models, rationale each, structurally checked); EXTRA_LOW_RISK grows via fixtures only.
- R8C irreversible (chart/fiscal country, l10n install): L3 + typed confirm, refused on route A without duplicate_db_route. action_return_all kept R4 (conservative).
Decisions (safe choice, flagged): D1 unresolved buttons/actions refused; D2 overrides never below hard floors, looser policy needs L3; D3 R4 without counter-document refused; D4 bulk verbs excluded when deriving the low-risk list; D5 group_*/l10n_* prefix rules; D6 credential detection by name tokens is conservative (may over-floor).

## Follow-ups (low, from reviewer round 7; still open)
- mail_server_id choices on mail.template, mailing.mailing, survey.invite; settings mass_mailing_*server and external_email_server_default.
- Settings ldaps, shared_user_account, sfu_server_url; alias_domain on teams/projects; hr.employee.certificate.
- Per-button derivation from live metadata (method table is still hand-curated).
- XML-RPC remnants: code_runner/testing.py, routers/view_engine.py, database_backup.py, suite_import.py, bridge/export.py.
