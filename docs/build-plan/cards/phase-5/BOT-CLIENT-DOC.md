# BOT-CLIENT-DOC — client documents around an Odoo build

Merges CLARIFY-DOC and HANDOFF-PACK. Package `apps/api/app/bots/client_doc/`.

## What it does
- `clarification(spec, review, fit, caps_ctx)`: plain-language questions from what the design could not decide.
  Categories (fixed order): duplicate-ref, conflict, needs-review, needs-custom, missing-value, low-confidence, version-or-edition, other-review.
  Each question has why, options, and a fail-closed default ("leave it unconfigured; nothing is changed").
- `handoff(spec, run, verify, cards, caps_ctx)`: configured (run outcome + verify status), how to test (record lookup + expected values from the spec), not done (blocked/skipped/pending/not run with reason; catalogue reason when available), known limits (verify not matching, truncated, partial company view), undo: only for `executed` steps of this session (run `undo`, else "to be confirmed"); resumed steps say "to be confirmed (earlier session)"; `already-done` says "nothing was written; nothing to undo". Card `undo_how` is never shown.
- `render_markdown`, `render_html`. No .docx (python-docx not installed).

## Rules
- Read-only pure functions over supplied data: no RPC, network, or model calls (AST import-ban test). Only reads the local versioncaps catalogue.
- Every line has a `source` tag (`spec:item:<ref>`, `design:review:<n>`, `fitgap:step:<id>`, `run:step:<slot>`, `verify:<ref>`, `card:<ref>`, `caps:<major>:<model>`, `input:<name>`, `derived:none`).
- Unknown stays "to be confirmed"; missing inputs give "not provided" lines.
- Deterministic: sorted by ref/slot/step id, no clocks. Version claims only when `caps_ctx = {edition, installed}` and `odoo_major` are given.
- Untrusted values: newlines folded, 300-char cap, Markdown backslash-escaped plus HTML-escaped; HTML fully escaped. 1500-line cap with `truncated` flag.

## Known limits
- How-to-test steps are generic record lookups, not screen-by-screen walkthroughs.
- Expected values come from the spec, not from what was actually applied.
- A conflict replaces a needs-review question only when the message starts with "conflict on <ref>: " (longest matching ref wins); unmatched conflicts keep every needs-review question. Fit-gap `needs_human`/`gap` count as low confidence.
- Any value whose encoding or `__str__` fails (any exception) renders as "unreadable value"; ZWJ (U+200D) is kept only between two emoji.
- Renderers accept any input (non-mapping documents, sections or lines) and skip non-mapping lines; never raise.
- Odd values (cycles, very deep nesting) render as "unreadable value"; Unicode Cc/Cf characters are stripped.

## Entry points and input contracts (for BOT-SPINE-WIRE / UI)
- `client_doc.clarification(spec, review, fit, caps_ctx)`: `spec`/`review` = `Design.to_dict()` and its `["review"]`; `fit` = `FitGap.to_dict()`; `caps_ctx` = `{"edition": str, "installed": [module names]}`.
- `client_doc.handoff(spec, run, verify, cards, caps_ctx)`: `run` = `OperatorFlow.run()` (`steps[]` with status, slot, ref, undo, resumed, verified, needs_review, note); `verify` = `configverify.verify()`; `cards` = `[StepCard.to_dict()]` (accepted but ignored; kept for the contract).
- `render_markdown(doc)`, `render_html(doc)` -> str. Export/storage is the caller's job.

## Out of scope
- Variance metrics: left out (not needed for the documents; add if a UAT pack should show them).
- Export, storage, delivery to the client: BOT-SPINE-WIRE or the UI.

## Tests
`tests/test_nf_bot_client_doc.py` (13), fixtures `tests/fixtures/client_doc/generic.json` and optional `industry_mfg.json`.

## Review follow-ups
1. A dict subclass whose get/items raise still escapes as RuntimeError, because `_m` (doc.py ~56) passes any Mapping through. Fix: return the input only when it is a plain dict, otherwise try dict(x) and fall back to {}; wrap the renderers' line loop the same way. Real producers emit plain dicts, so no dishonest output is possible.
2. No .docx output (python-docx not installed).
3. Variance metrics are left out.
4. How-to-test steps are generic lookups, and expected values come from the spec, not from what was applied.
5. A ref containing ': ' in a conflict message is matched by longest prefix, so an unusual conflict text may leave a conflict unmatched (needs-review questions are kept then).
6. Cf stripping turns some joiner sequences into separate characters, except emoji ZWJ.
7. Feed the real DB edition and installed modules via caps_ctx from SPINE-WIRE/UI; export/store the documents, plus a UI to collect client answers and feed them back into the design.
