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

## Remaining limits (CODE-AUDIT-7) - all closed in CODE-AUDIT-8
- ~~Imported session keys only MEDIUM~~ closed: keys are resolved through own-module and installed-addon constants.
- ~~Taint cut at helper calls~~ closed: module-wide helper-return summaries.
- ~~`web` too large~~ closed: stock `web` is audited in full.
- The deny-by-default stock HIGH counts are intended policy, not a limit: each such record needs a reviewed shape or human approval.

### CODE-AUDIT-7 verification (2026-10-27 WAT)
- Stock HIGH/MEDIUM v17: mail 92/340, sale 57/163, crm 30/277, hr 40/243, website_sale 83/191, mrp 54/149, account 83/348, stock 112/179, portal 9/81, auth_signup 8/64, website 331/262. v19: mail 60/339, sale 47/162, crm 18/277, hr 27/241, website_sale 78/188, mrp 41/149, account 57/348, stock 81/179, portal 9/80, auth_signup 7/64, website 321/260. web-unaudited 0 everywhere; no new HIGH false-alarm class after the M5 root-cause fixes (session runtime keys, gif outbound secret, mrp/mail receiver models).
- All `tests/*code_audit*.py`: 1060 passed forward, 1060 passed reverse.
- gate_live (ODOO_LIVE=1, INGENIUM_LIVE_INFRA=1): 2 passed.
- bl_08: 4 passed. Stale 97 ids (now5.txt): 95 passed, 1 skipped (b0_iso, needs PG 5433), 0 failed, 1 gone.

## CODE-AUDIT-8 status (the three CODE-AUDIT-7 limits closed by design)
Tests: `tests/test_nf_bot_code_audit_8.py` (29). Each change has the probe, at least 2 variants and a stock-shaped benign case.
1. **Session keys across modules.** A key is resolved through module constants and from-imports (relative, absolute `odoo.addons.*`, re-exports in `__init__`, up to 4 hops). Lookup covers the audited module, then sibling addons in the installed inventory (bounded, one file each).
   - Literal loop tuples are expanded.
   - f-string, `%` and `.format` keys are reduced to a literal skeleton and matched against the identity keys. `website_{id}_layout_mode` can never be `uid`, so it stays silent.
   - MEDIUM remains only when the key is built from runtime data, such as request args, a parameter, or a skeleton that could still spell an identity key. The finding message gives the reason. That case is unknowable statically.
   - Stock: every runtime-key MEDIUM resolved. The HIGHs left are true identity writes: portal/auth_totp `session_token` and web login `uid`/`db`.
2. **Secret taint through helper returns.** A module-wide fixpoint (bounded by `MAX_FLOW_ROUNDS`) runs over every non-test function and records (returns-secret, returns-param indexes).
   - A call to a helper that returns a secret is a secret.
   - A helper that returns its argument carries that argument's taint.
   - Any other call consumes its arguments.
   - This works across files and through multi-level chains.
3. **Large addons.** The budget is now sized from measurements of all 630 stock addons: 40 MB of code, 3000 files, 4 MB per file.
   - Stock reference points: largest module `web` 25.2 MB in 1841 files, largest file 2.7 MB. Only `web` was over the old cap.
   - `web` audits in about 7 s with about 410 MB RSS.
   - Past the caps the audit still fails closed (`source too large`, `file-unaudited` HIGH).
   - Root causes fixed so that every `web` file is audited:
     - Left-deep string `+` chains (emoji_data.js) are rebalanced iteratively in the helper. Pure string concatenation is associative, so the value is unchanged; there is no stack overflow.
     - `.b64` files are strictly decoded. Font and image payloads are inert; anything else stays HIGH.
     - RPC calls whose service and method are fixed literals (web database manager) are not open proxies. Caller-chosen dispatch is still HIGH.

### CODE-AUDIT-8 verification (2026-10-27 WAT)
- Stock HIGH/MEDIUM, v17:

  | Module | HIGH/MEDIUM |
  |---|---|
  | mail | 92/340 |
  | sale | 57/162 |
  | crm | 30/277 |
  | hr | 40/243 |
  | website_sale | 83/187 |
  | mrp | 54/149 |
  | account | 83/348 |
  | stock | 112/179 |
  | **web** | **189/489** |
  | portal | 9/81 |
  | auth_signup | 8/63 |
  | website | 331/261 |

- Stock HIGH/MEDIUM, v19:

  | Module | HIGH/MEDIUM |
  |---|---|
  | mail | 60/339 |
  | sale | 47/161 |
  | crm | 18/277 |
  | hr | 27/241 |
  | website_sale | 78/184 |
  | mrp | 41/149 |
  | account | 57/348 |
  | stock | 81/179 |
  | **web** | **187/489** |
  | portal | 9/80 |
  | auth_signup | 7/63 |
  | website | 321/259 |

- Correction (CODE-AUDIT-10): only the HIGH whole-file `web-unaudited`/`file-unaudited` codes were 0. MEDIUM `data-file-unaudited` (106 per version), `web-unaudited` (web 1) and `owl-expr-unaudited` (web 1, website 1) were not counted. See CODE-AUDIT-10.
- All `tests/*code_audit*.py`: 1089 passed forward, 1089 passed reverse.
- gate_live (ODOO_LIVE=1, INGENIUM_LIVE_INFRA=1): 2 passed.

## CODE-AUDIT-9 status (REVIEW-CODE-AUDIT-7: 7 HIGH, 4 MEDIUM, 1 LOW, all closed)

- H3: secrets returned through helpers are still caught (covered by CA8 2536273c); test added for the review's probe.
- H1/H2: a secret read is caught however the field is named: `rec['password']`, `rec[fld]` with a folded or local constant, `getattr`/`attrgetter`, `.get`/`.mapped`/`.read([...])`. The value must come from a recordset; request input (`kw['password']`) stays quiet.
- H4 (Python) and H5 (JS): a domain counts as unbounded unless it is provably constrained. Each domain gets a three-way result: matches everything, matches nothing, or truly constrained. The check covers:
  - leaves such as `(1,'=',1)`, `('id','!=',0)`, `('id','>',0)` and `('create_date','!=',False)`;
  - `&`, `|` and `!` operators;
  - domains built through local names, module constants, helper returns, `expression.AND`/`OR`, `Domain.and`, concatenation and spreads.
  - Names that are mutated, parameters or loop targets count as runtime values (constrained). A `limit=N` batch is bounded.
- H6: requests to ORM endpoints (`/web/dataset/call_kw`, `call_button`, `/jsonrpc` including `execute_kw`) are graded by their body with the same rules as `orm`/`rpc`. This covers fetch, XMLHttpRequest `open`+`send`, sendBeacon (including Blob bodies), axios and `$.ajax`. A body that can't be resolved is MEDIUM `js-raw-orm-request`.
- H7: results of an unbounded search are tracked through array, object and nested destructuring, spreads, ternaries and `await`.
- M1: HTML entities in OWL templates are decoded before the checks (numeric, hex, named, nested `&amp;`). Quotes stay encoded.
- M2: `static template = T` and `A.template = ...` are analysed when the value is an inline string, backtick or concatenated template.
- M3: `atob`, `decodeURIComponent`, `decodeURI` and `unescape` of a literal fold to the literal. The request is then graded as if the decoded URL were written out: an external URL is HIGH.
- M4: new MEDIUM `route-attachment-idor`. It fires when a public route returns `ir.attachment` `raw`/`datas` under sudo for an id taken from the request, with no access_token or ownership check.
- L1: `str*int` padding now folds (bounded), so `'UPDATE res_users ...' + 'a'*200000` stays HIGH `core-table-dml`.

### CODE-AUDIT-9 verification (2026-10-28 WAT)
- `tests/test_nf_bot_code_audit_9.py`: each finding has its probe, at least 2 variants and a benign stock-like case.
- Stock HIGH/MEDIUM, v17 and v19, including `web`: identical to CODE-AUDIT-8 in all 24 runs. The search_fetch coverage briefly added one mail mass-change; it was removed by the limit rule.
- All `tests/*code_audit*.py`: 1171 passed forward, 1171 passed reverse.
- gate_live (ODOO_LIVE=1, INGENIUM_LIVE_INFRA=1): 2 passed. bl_08: 4 passed. 97-id stale rerun: 95 passed, 1 skipped.

## CODE-AUDIT-10: zero unaudited on stock

Root causes (identical on v17 and v19):

| Module | Code | Count | Cause | Fix |
|---|---|---|---|---|
| hr / website_sale / mrp / sale / stock / mail | data-file-unaudited | 42 / 41 / 13 / 2 / 2 / 1 | `file=` binary images were left out of the inventory, so they looked missing | The magic bytes of the inert asset are checked against its extension (`_inert_ref_ok`) |
| account | data-file-unaudited | 5 | `base/static/img/onboarding_*` lives in the core addons path | Core `odoo/addons` added to the sibling roots. Symlink, `..` and size checks apply. |
| web | web-unaudited | 1 | hoot `index.html` `<script type="importmap">` was parsed as JS | Script types importmap, speculationrules and `*json` are parsed as JSON. A remote or `data:` importmap target is HIGH. |
| web | owl-expr-unaudited | 1 | Outer `${…}` in `xml``…`` became an empty `${}` | A parseable placeholder is used. The outer JS audits the real expression. |
| website | owl-expr-unaudited | 1 | `t-on-click="delete"` (reserved word) | A bare reserved word becomes a ctx lookup |

These inputs still fail closed:
- Bad magic bytes, a missing file, or a foreign addon that isn't available give MEDIUM `data-file-unaudited`.
- Invalid JSON in a script gives HIGH `web-unaudited`.
- An unparseable OWL expression gives `owl-expr-unaudited`.

Why CA8 was wrong: CA8 checked only the HIGH whole-file codes. `stock.py` had no unaudited assertion. Two gates now catch this:
- `/tmp/ca7/stock.py` asserts unaudited == 0.
- `tests/test_nf_bot_code_audit_stock_gate.py` runs when `INGENIUM_STOCK_AUDIT=1` is set and `STOCK_ODOO_ADDONS` points at the stock addons. Its run passed 24 of 24.

Stock results (HIGH/MEDIUM, unaudited = 0 in every module). The only change from CA9 is the removed unaudited findings.

| Module | v17 | v19 |
|---|---|---|
| mail | 92/339 | 60/338 |
| sale | 57/160 | 47/159 |
| crm | 30/277 | 18/277 |
| hr | 40/201 | 27/199 |
| website_sale | 83/146 | 78/143 |
| mrp | 54/136 | 41/136 |
| account | 83/343 | 57/343 |
| stock | 112/177 | 81/177 |
| web | 189/487 | 187/487 |
| portal | 9/81 | 9/80 |
| auth_signup | 8/63 | 7/63 |
| website | 331/260 | 321/258 |

Audit suites: forward and reverse order both gave 1194 passed and 24 skipped (the stock gate is opt-in). gate_live: 2 passed.

## CODE-AUDIT-11: provably-bounded inversion (REVIEW-CODE-AUDIT-8: 12 HIGH, 5 MEDIUM, 2 LOW, all closed)

Rule: a sink is safe only when its input is provably bounded. Unprovable means flagged.

- Recordsets (Python, server actions, `<function>`, JS): write/unlink/_write/archive/toggle_active/update and sudo-write sinks are HIGH `mass-change` / `server-mass-change` / `xml-function-destructive` / `js-mass-change` unless the recordset is provably selective. Unknown domains, runtime limits, negations, ranges over literals, `%`/empty like, full selections, `json.loads`/`JSON.parse`, `TRUE_DOMAIN` and derived recordsets (filtered/mapped/browse of `_search`) are unbounded. Flow is per-function and flow-sensitive. JS ids taint flows through `.then`, object properties, push/spread and for-of. A JS domain held in view state (`this.domain`) is the user's own selection and counts as bounded. (H4–H7, H12)
- Secrets on public routes: comprehension/loop targets, `__getitem__`, runtime getattr names, and helper returns from lambdas, staticmethods and model methods are HIGH `route-secret-read`. (H1–H3)
- `fetch(new Request(...))` and path-form call_kw URLs are graded like orm calls. HTML forms and `formAction` aimed at ORM endpoints give MEDIUM `js-raw-orm-request`. (H8, L2)
- URL schemes are checked the way browsers parse them: TAB/LF/CR are stripped after entity decoding. Concatenation, `t-attf` literals and state-held `javascript:` literals are folded. The string folder covers split/reverse/join and `new URL(path, base)`, and computed `static template` strings. (H9, M2, M4)
- SQL is checked after removing comments, quotes and schema, with CTE bodies scanned and f-string/`%`/`+` table names folded through constants. (H10)
- `<function>`: a destructive method gives HIGH unless the ids are provably bounded. A method that neither the module nor its on-disk dependency closure defines gives MEDIUM `xml-function-unknown`. (H11)
- Public-route IDOR: a sudo read of a personal-data record (mail.message, res.partner, res.users, ...) or an ir.binary stream for a caller-chosen id gives MEDIUM `route-record-idor`. An access token, `_document_check_access`, or a session/user comparison suppresses it. (M3)
- M1: a type-matched in-module binary gives no finding. Only real unknowns fire (CA10 fix A; regression tests added).
- L1: nested inline OWL expressions beyond the audit depth give `owl-expr-unaudited` (fail closed).
- Tests: `tests/test_nf_bot_code_audit_11.py` covers each probe, at least 3 variants, and benign twins. Twins changed to match the spec: test_7 h15neg (bounded domain) and test_3 H2-function-ok (the module defines the method).

M5: how the stock counts are measured
- Source tree: `/Users/temitopeolaitanmichael/ODOO_CUSTOMIZATION_TUTORIALS/odoo/addons`, git `bbe85efc259fd864d99fbfcf6d523ee8e91ea074`, clean, odoo/release.py 19.0. v17 and v19 are the audit rule sets (`version=`) applied to this one tree.
- Command (from apps/api): `STOCK_ODOO_ADDONS=<path above> PYTHONPATH=.:../../packages/module-generator/src python scripts/stock_audit_counts.py out.json`
- Opt-in pytest gate: `INGENIUM_STOCK_AUDIT=1 STOCK_ODOO_ADDONS=<path> pytest tests/test_nf_bot_code_audit_stock_gate.py`
- Earlier cards' counts were measured on this tree with `/tmp/ca7/stock.py`. The reviewer's `~/.ingenium_nf/agent_runs/t3/stock` set is a different tree, so its counts differ.
- Reviewer note: a fresh worktree needs `node.pin.json` and `node_modules` copied into `apps/api/app/bots/code_audit_js/` before the JS helper runs.

Stock results from that command (HIGH/MEDIUM, unaudited = 0 everywhere, GATE OK):

| Module | v17 | v19 |
|---|---|---|
| mail | 96/338 | 64/337 |
| sale | 57/160 | 47/159 |
| crm | 30/277 | 18/277 |
| hr | 40/201 | 27/199 |
| website_sale | 84/145 | 79/142 |
| mrp | 56/136 | 43/136 |
| account | 83/343 | 57/343 |
| stock | 115/177 | 84/177 |
| web | 189/487 | 187/487 |
| portal | 9/81 | 9/80 |
| auth_signup | 8/63 | 7/63 |
| website | 334/260 | 324/258 |

What changed since CA10: the new HIGHs are genuine whole-model or unprovable operations:
- `mass-change`: mail discuss_channel_member, mail_push, mail_push_device and res_users; website_sale website; mrp/stock/website `__init__` hooks; stock res_company; website_page_properties.
- `xml-function-destructive`: the mrp demo writes to `stock.warehouse` over `search([])`.

Two false-alarm root causes were fixed, not allow-listed: web `dynamic_list.js` (view-state domain) and `website_sale` shop_payment_validate (session-ownership comparison).

Audit suites: forward and reverse order both gave 1327 passed and 24 skipped.
