# BOT-CODE-AUDIT
No card existed; derived from RESOLUTION.md, MEMORY.md and t463u.
Read-only static audit of an Odoo module (zip or tree): never executed, ast + XML only.
Findings: severity, code, file:line, fix hint. Covers access/record rules, sudo, raw SQL,
eval/exec, unsafe XML/QWeb, unsafe default/domain/context, upgrade hazards, versioncaps
compatibility, perf smells, ownership (foreign = audit-only). Hostile input bounded and fail-closed.
Impl: apps/api/app/bots/code_audit.py; tests: apps/api/tests/test_nf_bot_code_audit.py (20).
T3 switches unchanged.
## Gaps
- XML line numbers best-effort (ElementTree has no positions; string search).
- No live Odoo check; versioncaps catalog only.
- t-out/markup and N+1 detection are heuristic.
- Ownership trusts caller's owned_names registry only.
- Removed-xmlid hazard is in-module only (no prior-version diff).
## CODE-AUDIT-4 status (review 2 findings H1-H11, M1-M6, L1-L2 addressed)
JS/OWL/CSS/SCSS/Sass/TS/TSX/JSX audited via pinned Node helper (acorn, postcss*, sucrase 3.35.1;
helper, lock and node_modules tree sha256-pinned). Tests: test_nf_bot_code_audit_4.py (94),
test_nf_bot_code_audit_4_probes.py (127). UNBASELINABLE codes never baselined in either gate.
## Remaining limits (honest)
- Node pin: binary + transitive dylib closure hashed and run from a private copy; absolute-path
  system libs (/usr/lib, /System) are not copied, and a small TOCTOU window remains between
  verify and exec.
- Escaped CSS at-rules (e.g. `@\69mport`) that postcss cannot parse fail closed as HIGH
  web-unaudited (no false negative, but noisy).
- .coffee/.styl have no parser: reported as unaudited (fail closed), not analysed.
- Python/JS taint is intra-module summary-based; anything the fixpoint cannot resolve is
  flagged flow-incomplete/js-flow-incomplete (HIGH), never silent.
- Stock v19 residual HIGHs: sale 1, crm 0, hr 4, website_sale 5, mail 17. True positives:
  foreign-record-edit, ir.mail_server writes, mail tainted-markup (json-loaded kwargs can set
  body_is_html). Still flagged, not cleared: __pycache__ binary-code, neutralize.sql,
  sql-injection from dynamic `_fields` column lists (mail_followers.py:415,
  hr_employee_public.py:196), one mail js-external-request. Stock web/account keep many
  HIGHs (js-eval, markup-script, script-file, test-tamper) by design: foreign code is audit-only.
