# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
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
