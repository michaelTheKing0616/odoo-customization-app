# BOT-PROCESS-FITGAP

Goal: any client process document -> true flow -> fit-gap vs stock Odoo (connected db's
version, edition, installed/installable modules) -> Odoo-native mapping; only genuine
gaps become custom. Read-only; the plan is a dry run (execution = BOT-SPINE-WIRE).

Build (new files only, `apps/api/app/bots/process/`):
- `ingest.py` deterministic parsers -> `FlowGraph` (steps, edges + confidence, locators):
  xlsx cells + DrawingML shapes/connectors (linked by id, unlinked by nearest edge, arrow
  direction, position fallback), docx, PDF text, text, vsdx, BPMN, draw.io. Low confidence
  -> one render marker (soffice -> pdf -> pdftoppm) and at most ONE vision read via the
  shared AI client (`get_llm_provider_for_tier`), same schema, validated. Tests inject fakes.
- `fitgap_table.json` reviewed concept table (module, min major, edition, setup actions,
  patterns) + known custom gaps; `fitgap.py` classifier, env check, verdicts, questions.
- `plan.py` stock mapping -> guarded dry-run plan (catalogue task + `plan_tier` L-tier);
  gaps -> App Studio module-spec draft (`draft_dict_to_module_spec`).
- `report.py` plain business summary + UI JSON.
- No UI. API endpoint: follow-up.

Fixture: synthetic EXAMPLE of a rice-mill "Manufacturing Process Flow Diagram" xlsx
(Zyn Mills style; shapes only in drawing1.xml, connectors mostly unlinked). Not client data.

Tests: `tests/test_nf_bot_process_fitgap.py`.

## Results
- 21 tests (`test_nf_bot_process_fitgap.py`): xlsx shapes (unlinked/linked/reversed arrow,
  title dropped), shape-only -> one vision read, cells, BPMN, draw.io plain/unlinked/compressed,
  vsdx, docx, text, PDF, image, DTD/zip refusal, Zyn Mills E2E (Enterprise: exactly 4 gaps
  weighbridge, moisture pricing, tempering gate, yield dashboard; Community: quality steps
  flagged Enterprise-only), unknown -> human, no-env questions, read_env one read, table drift
  vs catalogue, module-spec through `draft_dict_to_module_spec`, budget (0 calls when confident,
  max 1 otherwise). Forward + reverse ids pass; with kill_audit + risk suites 2102 passed,
  6 skipped, both file orders. Ruff clean. No raw-RPC exemption (read-only).

Honest gaps:
- Real render (soffice/pdftoppm) and `gateway_vision` are untested here (no tools/model; fakes
  injected). Vision uses the shared AI client tier "fast"; no image-specific allowlist found.
- Classifier is keyword-based; plan dedupes per action, blast count = matched steps.
- Settings toggles, module installs and quality points have no catalogue task: marked for a human.
- Not wired: API endpoint, UI, live `read_env` against 17-20 sandboxes (follow-ups).

## Review round 1 (BLOCK -> fixed)
- M1 bomb: `inflate()` bounded decompressobj (raw/zlib/gzip), zip members read with a cap
  (declared sizes not trusted); 300 MB draw.io bomb refused with bounded memory. PDF relies on
  pypdf 6.18 own stream limits (ZLIB_MAX_OUTPUT_LENGTH) + 30-page cap.
- M2 keywords: word-start matching, strong/weak per pattern in `fitgap_table.json`, global
  negative words (payment, invoice, email, software, ...), lone weak keyword -> needs human
  unless a material word is in the step or the document has >=3 strong steps. Zyn Mills result
  unchanged. 24 adversarial phrases (incl. Spanish/French/Japanese/German) -> needs human.
- Lows: DTD/ENTITY refused anywhere; soffice gets its own temp profile, own process group
  killed on timeout, temp dir removed (remote linked-image fetch NOT disabled: run without
  egress); repeated list labels stay distinct (arrow chains still share nodes); no database ->
  Enterprise features "needs Enterprise unless confirmed" (custom, fail closed); module installs
  map to catalogue `mod:<x>:install` (R7) with its tier.
- The Zyn Mills workbook is a synthetic fixture built in the test; the render path (soffice,
  pdftoppm) and the real vision call are untested on real files.
- Tests: 57 (+ probe p01-p06 pass); both orders; with kill_audit, lockout_sim, risk suites
  2174 passed, 6 skipped both file orders; ruff clean.

Merge: apps/api/app/bots/process/{__init__,ingest,fitgap,plan,report}.py,
apps/api/app/bots/process/fitgap_table.json, apps/api/tests/test_nf_bot_process_fitgap.py,
this card. Leave out: __pycache__, review probe.

Tracking: `BOT-PROCESS-FITGAP | done (nf2, uncommitted) | app/bots/process/* | 88 unit, review rounds 1-3 fixed`

## Review round 2 (fixed)
- MEDIUM 1: document-level ">=3 strong steps" relaxation removed; weak keyword needs a strong hit or an operations-vocabulary (`context`) word in the same step.
- MEDIUM 2: weak never confirms weak; the matched span never counts as its own context; unconfirmed -> needs human. Zyn Mills verdict kept via new strong patterns (return to supplier, mill machines, lot code/number, depot distribution, inter-warehouse). Property test: 27 weak verbs x 22 office nouns -> no stock verdict; 19 office phrases alone and inside the mill doc.
- LOW: shape/edge count refused before connecting (drawio, vsdx, bpmn, xlsx); nearest-edge matching bounded by spatial grid (runtime test); zip member-count cap test.
- Results: process tests 81 passed (forward and reversed ids); probes proc1+proc2 pass; process+kill_audit+lockout_sim+risk* 2198 passed, 6 skipped in both file orders; ruff clean.
- Gaps: vocabulary is a reviewed static list; new industries need vocabulary review, else they fall to needs-human (fail-closed).

## Review round 3 (fixed)
- Honest output: summary opens with a header saying the verdicts are suggestions from a keyword match and a person confirms each before anything is set up. Each stock / stock-with-config step is listed with "suggested from keywords in your document, please confirm". The counts line reads "N look like they work as is (suggested), N after setup (suggested)".
- JSON: each step carries `match_confidence` = strong pattern | strong + context | weak + context | needs human, for the UI. Gap and unknown steps are "needs human".
- New table list `office` (report, newsletter, conduct, brochure, office, match, football, street, photo, manager, flyer, training, learning, workshop, visit, interview, review, policy, presentation, speech, cabinet, contract, files/filing). An office word in a step beats every concept pattern, strong ones included (warehouse, mill, inter-warehouse, mill machines, lot code, return to supplier), so the step goes to needs human. Office words block concept matches only, not named gaps, so "Milling Yield / Loss Report" still maps to its gap. Payment/email words remain in `negative`.
- Tests: the 6 phrases from the review were added to OFFICE (tested alone and inside the mill doc); a summary/JSON suggestion test; probe proc3 passes. Zyn Mills verdict and gaps are unchanged.
- Results: process tests 88 passed (forward and reversed ids); probes proc1-3 pass; process+kill_audit+lockout_sim+risk* 2205 passed, 6 skipped in both file orders; ruff clean.
- By design: keyword matching cannot be perfect. Remaining false positives are labelled suggestions and are never applied unconfirmed. BOT-SPINE-WIRE and the UI MUST show every stock / stock-with-config step as a "confirm" item, using `match_confidence`.
