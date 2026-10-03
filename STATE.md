# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
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
2. Continued through the open tracks that can be tested without a live Shopify shop or a running Odoo 20 image. Config plans apply idempotently. Red-team cases RT-01, RT-17, and RT-18 pass. MCP writes are refused. L4 policy is coded and stays ineligible until 200 clean applies over 60 days. Eleven tests passed. The 45-screen restyle, the 188 skills, and a live Shopify run are still open.
3. Still open: D8 (gateway), GATE-L4 numeric confirm, pen-test, Mac §9. D1–D7, D9–D12 are closed.

## Docket
- Mac §9 UI open; agent offline+sandbox green; JSON-2 PR-J1/J2 code done.
