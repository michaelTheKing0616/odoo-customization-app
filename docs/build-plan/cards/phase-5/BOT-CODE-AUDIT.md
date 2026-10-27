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

## CODE-AUDIT-5 status (review 4: H1-H15, M1-M8, L1-L4)
All review-4 reproducers are caught or graded (probe harness: 6 of ~270 probes still return no
finding, each a documented limit below). Tests: test_nf_bot_code_audit_5.py.
- Node (H1/M1): the pinned binary and its whole non-sealed dylib closure are copied, each copy
  compared with its own pinned sha256, relinked to private paths (install_name_tool), ad-hoc
  signed, and kept in an owner-only cache (~/.cache/ingenium-node/<pin>) whose every file is
  re-verified against the pinned post-relink hashes before each use (rebuilt when it differs).
  Linux runs node through the pinned, copied ELF interpreter with --library-path.
- Operator step (L3): a fresh checkout has no node.pin.json, so every JS/CSS file is HIGH
  web-unaudited (fail closed). Pin once per host after npm ci:
  `cd apps/api && python -m app.bots.code_audit_web --pin-node [/path/to/node]`
  (exit 0 = pinned; 1 = Node missing/too old/closure unresolvable; 2 = usage). Re-pin after
  any Node upgrade.
## Remaining limits (CODE-AUDIT-5, honest)
- View attrs/invisible/readonly expressions and field context are evaluated client-side
  (domain/py.js, no server code): not flagged (probes x-view-attrs-expr, x-view-field-context).
- Default-value JSON on non-core fields, json/markdown modules, static/tests JS (loaded only
  in test bundles) are LOW or unflagged by design.
- owl-url-attr: URL-controlled HIGH, record data MEDIUM, props/state LOW (flagged, not silent).
- Same-user TOCTOU between the verify of the private Node cache and exec remains (the cache is
  owner-only; any attacker able to write it can also rewrite the pin).
- web emoji_data: stack overflow in the helper fails closed as HIGH web-unaudited (stock).
- Stock HIGHs kept by policy: web js-eval (v17 14 / v19 22, incl. assets.js script textContent),
  markup-script, script-file, test-tamper on threading; foreign-record-edit on base groups;
  binary-code __pycache__ (image artifact); sql-data-file neutralize.sql; mrp uninstall_hook
  mass write (true positive of the hook rule); account sql-injection 2 (account_move 1642,
  aml 741, conservative); mail tainted-model on thread_model route params; mail js-markup
  MEDIUM x2.

## CODE-AUDIT-6 status (deny-by-default; H1-H16, M1-M6, L1-L3, six silent probes)
All items fixed with a dedicated test each in `tests/test_nf_bot_code_audit_6.py` (236 tests). mrp `js-flow-incomplete` root-caused (prototype-inherited sink keys) and fixed; mrp unsafe-expression and js-flow-incomplete now 0 on stock v17/v19.

## Remaining limits (CODE-AUDIT-6, honest)
- Node helper TOCTOU: the owner uid is the trust boundary (no fexecve on macOS; a same-uid process can rewrite anything). Fail-closed: helper and deps copied to a fresh 0700 mkdtemp and re-verified each run, Node closure re-hashed before every use, any mismatch => `web-unaudited` HIGH.
- Deny-by-default means stock modules still report HIGH `sensitive-data-unapproved` for ACL/rule/group/server-action records outside approved shapes (e.g. sale 45-56, website_sale 66-68). Intended: every such record needs a reviewed shape or human approval.
- Undecidable inputs are flagged, never passed: non-JSON ir.default (`default-value-unaudited`), unresolved LESS interpolation (`css-dynamic-url`), unparsed expressions and non-UTF-8 web files (unbaselinable), flow non-convergence (`FlowIncomplete`, audit fails).
- ~~Session identity only via attribute writes~~ corrected in CODE-AUDIT-7: `request.session['uid']`, subscript/alias/`update`/`setdefault`/`__setitem__` writes of identity keys are HIGH `session-auth-write` too (keys folded through module constants); a key not resolvable in the file is MEDIUM, never silent. web's login controller reports HIGH by design; portal's `session_token` refresh after a password change is HIGH (true identity write).
- Tooling: no ruff/rg/timeout on the dev Mac; lint not run.

### CODE-AUDIT-6 verification (2026-10-27 WAT)
- Audit suites 1/3/4/4_probes/5: 698 passed; audit_6: 236 passed.
- test_nf_bot_* forward 5362 passed / 200 skipped; reverse 5362 passed / 200 skipped.
- gate_live (ODOO_LIVE=1, INGENIUM_LIVE_INFRA=1): 2 passed. bl_08: 4 passed.
- Stale 97 ids: 68 passed, 28 failed, 1 gone. 27 are AI-generator behaviour assertions (generator last changed in da79fe37, outside this audit work; none import code_audit). 1 is b0_iso, which needs PG on 5433 (environment).

## CODE-AUDIT-7 status (review 6: H1-H17, M1-M6, L1-L3)
Root-cause policy, not per-probe patches; each finding has the exact probe, >=2 variants and a stock-shaped benign test in `tests/test_nf_bot_code_audit_7.py`.
- Deny-by-default action/record context privilege defaults (XML, CSV and Python `with_context`/dict context).
- ir.rule / ir.model.access / res.users auth overrides (`auth-override`; super() + literal domain HIGH); privilege vals injected by core create/write overrides (`sensitive-override-write`).
- Routes reaching the RPC dispatcher (`rpc-proxy`, HIGH public/none, MEDIUM user, through helpers, async too); secret reads returned from any route (`route-secret-read`); secrets consumed by an outbound call are not "returned".
- SQL.identifier / psycopg2 Identifier DML folding; receiver model through mapped()/relation hops (field hops and other method results never inherit a core model); `.new()` with privilege vals; related secret fields.
- JS: id lists from empty-domain search/searchRead/orm.call/rpc payloads into unlink/write; javascript:/vbscript:/data:text/html sinks on unknown elements; OWL js-URL href/src and srcdoc.
- View modifiers (invisible/readonly/required/column_invisible) parsed: unparsable MEDIUM, env/sudo/ORM HIGH. document.domain and code-shaped .po plural forms MEDIUM.

## Remaining limits (CODE-AUDIT-7, honest)
- Session keys imported from another module cannot be folded per file: MEDIUM review, not HIGH.
- Taint through arbitrary helper calls is cut at the call (a helper that echoes a secret back is not followed); direct returns and make_response/render/dumps are.
- `web` addon is too large for one audit (`source too large`, fails closed).
- Deny-by-default stock HIGH (`sensitive-data-unapproved`, `sensitive-model-write`, `version-list`) unchanged in kind.

### CODE-AUDIT-7 verification (2026-10-27 WAT)
- Stock HIGH/MEDIUM v17: mail 92/340, sale 57/163, crm 30/277, hr 40/243, website_sale 83/191, mrp 54/149, account 83/348, stock 112/179, portal 9/81, auth_signup 8/64, website 331/262. v19: mail 60/339, sale 47/162, crm 18/277, hr 27/241, website_sale 78/188, mrp 41/149, account 57/348, stock 81/179, portal 9/80, auth_signup 7/64, website 321/260. web-unaudited 0 everywhere; no new HIGH false-alarm class after the M5 root-cause fixes (session runtime keys, gif outbound secret, mrp/mail receiver models).
- All `tests/*code_audit*.py`: 1060 passed forward, 1060 passed reverse.
- gate_live (ODOO_LIVE=1, INGENIUM_LIVE_INFRA=1): 2 passed.
