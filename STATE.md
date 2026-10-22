# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-10-21 (night) — **Build plan Stage 2 + Stage 3 → G1.** `docs/build-plan/`: 04_PHASES, 05_MODEL_ROUTING, 05_PACKETS, 06_TEST_STRATEGY, 07_UI_EXCELLENCE_PROTOCOL, 08_GATES, REFERENCE_NOTES (skeleton), STATE (orchestrator board), `phase_map.json` (all prefixes), `budget.json` phase_weights; `tools/build_cards.py` (735 generated cards, verbatim ACs), `tools/next_cards.py` (dispatch queue); `ORCHESTRATOR_PROMPT.md`. Lint: 1,194 rows, 847 cards, 0 uncovered, 0 errors.
  - Failed: 5 Elevate cards duplicated handover cards (merged); first generator pass mis-gated TOUCH-009 (keyword noise) and duplicated ACs (fixed by keying on one-lines, deduping by text).
  - Rule: before adding "next-level" cards, grep the ledger for the same capability (`rg -i <noun> ledger.csv`) and extend the existing card instead.
  - Open for Tope: G1 batch (DEC-003, 004, 005, 015, 024, 026–029, 032, 046–049).
- Date: 2026-10-21 (evening) — **Craft beyond smart buttons, live-DB grounding, Draft Studio on v3, Elevate.** `app-studio/ODOO_CRAFT.md` (K01-K44, U01-U12, Q1-Q5); Pack §6.7 + ORACLES §G (G-01..G-12); 7 new AS cards (AS-GROUND-WIRE/VIEWMAP/PLACE/EXISTS/DATA, AS-DRAFT-ADOPT, AS-PACK-RETIRE); `elevate/00_ELEVATE.md` + `elevate/ORACLES.md` + 56 cards in `cards/phase-7/` (11 cross-cutting, 19 bar, 26 next-level); `tools/amend_g1c.py` (idempotent). Ledger 1,194 rows, 0 uncovered; lint clean except the expected unwritten-phase prefixes. DEC-036..045 resolved; none open.
  - Found: the live packet flattens views to field order (no containers, labels, smart buttons or ownership), and v3 passed it only to validate_strict.
  - Failed: one lint error (AS-UPGRADES lacked the new ledger ID); fixed.
  - Rule: before planning any LLM stage, grep which grounding object reaches it (`schema_packet`) and what that object drops.
  - Open: `budget.json` phase shares sum to 1.28 and lack phase 7; fix in Stage 2 (`04_PHASES.md`).
- Date: 2026-10-21 (later) — **G0 approved; Stage 2B App Studio Pack → G1B** at `docs/build-plan/app-studio/`: `00_PACK.md` rev 2 (RC1-RC8, v3 Brief Ledger, G-TOTAL), `ORACLES.md` rev 2, `01_REVIEW.md` (independent Fable 5 review: 3 blockers + 12 majors + 11 minors, all accepted and folded in), `CODE_MAP.md`, 39 cards `cards/phase-3/AS-*.md` (new AS-V3-WIRE), `budget.json`, `UI_REFERENCE_MAP.md`, `tools/amend_g0.py` + `amend_g1b.py`. Ledger 1,179 rows, 0 uncovered, lint 0 errors, card graph has no cycles. No product code, no git writes, no DB.
  - Failed: the first card set had a dependency cycle around AS-TOTAL/AS-COMPILE. The Ledger asked models for character offsets. The contract call had no stated role in v3. The reviewer caught all three before any build. The planner caught one more: a few-shot guard that would have read the sealed holdout.
  - Rule: run a dependency-cycle check (script) and an independent review before any card pack is routed to workers.
  - Open for Tope: DEC-036, 037, 038, 039, 040, 041.
- Date: 2026-10-21 — **Build plan Stage 1 (→ G0)** at `docs/build-plan/`: HANDOVER_INDEX, 01 charter, 02 invariants, 03 ledger + `ledger.csv` (664 rows, 0 uncovered, 459 planned cards, 31 holds), 09 decisions (35), FACTS, `.cursor/rules` drafts in `drafts/`, `scripts/plan_lint.py` (smoke-tested: catches tier, elite-notes, guarded-path, and unknown-ID defects). Handover copied to `docs/specs/` (md = pdf). UI pack unzipped to `docs/design/references/ingenium-ui/` (media gitignored). No product code, no git writes, no DB.
  - Blocked: App Studio Pack (Stage 2B) needs the box specs (DEC-002). The overlap with the 2 Oct `docs/plans/next-phase/` pack needs DEC-022.
  - Rule: count with a script (`plan_lint`) before writing a total into any plan doc.
- Date: 2026-10-03 — **T2-J4 honest docs:** JSON-2 transport, mapper, and production probe in `packages/odoo-client` (commits a67877a, 603523c); Odoo 19 Online and 20 use JSON-2; 17, 18, and self-hosted 19 use XML-RPC or JSON-RPC. Live probe on https://aonb.odoo.com and https://aonb-mirror.odoo.com (build odoo/20.0) recorded in `docs/verified-facts.md` (`search_read`, `fields_get`, empty create → 422 missing `vals_list`; bad key 401; string domain 500). T2-J2 (f626a00): local ephemeral Odoo 19 `board` install via `ensure_module_installed` — XML-RPC 6.151 s, JSON-2 4.053 s; sandbox default still xmlrpc; Online not installed to. T2-J3 (1cf4417): `test_no_direct_xmlrpc.py` 2 passed. **Still open:** T2-J1 `/doc` text match (website owns route — not verified); T2-SMOKE (three Online methods recorded on aonb in verified-facts; no Online module install). Mac §9 UI paste operator. Promote human. L4 unconfirmed.
- Date: 2026-10-02 (late) — **Pack v2:** 330 work cards in `docs/plans/next-phase/cards/` (BL, T1–T6, T7 foundation, T8 core/suites/bots, T9) plus screen cards UI-S-01–62 in `13`. `14` is now the generated index; v1 cards kept in `cards/_LEGACY_14_v1.md`. `03` §B re-measure: 62 ops (not 63 or ~55), 188 skills, 129 oracle tests listed in `17`, and the spec's Q6/Q13/Q14/Q17 added to `18`. No product code.
  - Failed: `test_no_mcp_write.py` scans `.pytest_cache` (BL-07). Most of the tree is uncommitted (BL-08 needs Tope's yes). A concurrent agent is editing `changeset/*`, so T8 statuses must be re-measured. No independent checker was run on v2 (the user asked to wrap up).
  - Rule: re-run counts with a script against code (`len(OP_CATALOG)`) before writing a number into the pack.
- Date: 2026-10-02 — Build pack written at `docs/plans/next-phase/`. D10 L4, D11 Odoo 20 GA, D12 Base UI + Sonner + motion. Checker passed ID counts. No product code. Mac §9 **UI paste still operator**.
- Date: 2026-10-02 — Next-phase folder ingested. Skills installed globally.
- Date: 2026-09-23 — Mac §9 **agent path** advanced; **UI paste still operator**.
- **Agent evidence (not Mac UI):** `studio_generate_offline_finish` Maintenance + Service-cards → score **7.54**, `live_apply_ready=True`, invent-outside-admit **[]**, spray **[]**, checklist+parts O2Ms + root menus; zips under `.cache/mac9_agent/`. Ephemeral sandbox Install **ok** (`maintenance_tickets`, `service_cards`, Odoo 19). API `:8001` without `--reload`; health ok.
- **JSON-2 local tip:** `/doc` **404**; password login → XML-RPC ok; Bearer without API key → **401 Invalid apikey** (expected). Live `/doc` + API-key smoke still operator.
- **Accepted debt:** POS / `law_firm` honesty (Wave 8). Scorecard still flags thin line fields (done/product/qty nouns) + line-model menu noise — Install bar was menus/O2Ms/no spray.

## Mac §9 — still open (operator UI paste)
Agent cannot claim §9 done. Still need Studio UI Generate on Mac + paste scorecards into DOCKET (or chat). Agent sandbox Install ≠ UI walkthrough.

Optional JSON-2: Preferences → API key on tip/Online; open `/doc` if present; confirm `search_read` / `create` / `fields_get`.

## Next
1. Operator Mac §9 UI paste (closes §9). Unchanged.
2. **T2-J1:** `/doc` parameter text match — not verified (public website owns `/doc` on the probed Online hosts; do not guess signatures). The JSON-2 track stays open for that reason.
3. **T2-SMOKE:** the three Online methods are recorded in `docs/verified-facts.md` (aonb, 20.0): `search_read`, `fields_get`, and `create`. No further Online call is required for that card. An Online module install was not part of it and was not run.
4. Still open: D8 (gateway), GATE-L4 numeric confirm, pen-test, L4 unconfirmed. D1–D7, D9–D12 are closed.

## Docket
- **Mac §9:** UI paste still operator; agent offline + sandbox Install evidence unchanged.
- **JSON-2 shipped (client):** transport, mapper, production probe (a67877a, 603523c). Majors: 19 Online + 20 → JSON-2; 17, 18, self-hosted 19 → XML-RPC or JSON-RPC. Probes use `search_read` + `fields_get` only (no row insert); JSON-2 create uses `vals_list`, legacy create uses positional `vals`.
- **Verified live (docs):** aonb + aonb-mirror Online probes in `docs/verified-facts.md`. T2-J2 local install timing (f626a00). T2-J3 direct-transport grep (1cf4417).
- **Operator / open:** T2-J1 `/doc` match is not verified, so the JSON-2 track stays open. T2-SMOKE method record is met in `docs/verified-facts.md`. Sandbox default xmlrpc. Promote human.

## Retro — new-features planning (22 Oct, planning architect)
- Shipped: `docs/build-plan/NEW_FEATURES_INDEX.md`, `docs/build-plan/new-features/` (baseline + 8 epic docs), 269 cards under `docs/build-plan/cards/phase-4..6/`, 296 ledger rows, DEC-050..074 in `09_DECISIONS_FOR_TOPE.md`, 27 `phase_map` prefixes, 13 umbrella-card edits.
- Lint: `plan_lint.py all` reports 1,490 rows, 0 uncovered, 0 errors. Existing ledger rows are byte-identical.
- Failed and fixed: four guessed card IDs did not exist; one cross-phase dependency was inverted (FA-A28); engine cards had an empty Test plan (`{T}` path filter); the index linked to slug anchors instead of the docs' code anchors.
- Rule: generated cross-references (IDs, anchors, test paths) get a checker run against the real files before the first write.
- Next: Tope answers DEC-050 (scope) and DEC-051 (phases). The Orchestrator does not dispatch NF cards before DEC-050.
