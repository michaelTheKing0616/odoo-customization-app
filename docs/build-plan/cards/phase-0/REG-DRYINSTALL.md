# REG-DRYINSTALL: regression: install dry_run reads only

ID: REG-DRYINSTALL
Title: regression: install dry_run reads only
Status: done
Phase: 0
Priority: P0
Type: regression
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: H-2.9-DRYINSTALL
Depends on: B0-INV
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L2 separate session · Score: 5 (C1 U0 F1 K0 V2 I1)
Context pack:
- `sed -n '177p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- docs/build-plan/FACTS.md
File allow-list:
- apps/api/tests/test_reg_dryinstall.py (new)
Goal: Pin the already-fixed behaviour behind `REG-DRYINSTALL` with a test that fails if it regresses; no product change.
Steps:
1. Read the context pack. State the fixed behaviour this regression pins, as input → expected output, one per AC.
2. Write the regression test only (product code is read-only for this card).
3. Prove it can fail: in the Worker packet name the product line whose deletion would make the test fail.
4. Run the Test plan command → green; run it in reverse/random order → green.
5. If the behaviour is already broken, stop: report the failing assertion; the Orchestrator opens a fix card.
6. Live checks run only on disposable `ingenium_*` sandboxes for 17, 18, 19 (and 20 once its stack exists); drop what you create (INV-03).
7. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong.
Acceptance criteria:
- AC1: Install allow-list: the Community allow-list was hard-coded "19.0"; it is now version-aware, and for majors without a list it uses the live module's LGPL licence. OEEL modules are always refused. `dry_run` on install was ignored (a "preview" really installed); it now reads only. [Done, live on 20 only; 17 to 19 stacks were down] (source: INGENIUM_MASTER_HANDOVER.md L177)
Symbols: `install_community_module` in `apps/api/app/routers/export_sandbox.py`. `InstallCommunityModuleBody.dry_run` in `apps/api/app/schemas.py` (default `False`). `load_vendored_community_modules` and `_normalize_odoo_version` in `apps/api/app/protected_modules.py`.
Worked example:
- Example AC1: module `sale` is in the vendored list for that major, the live `ir.module.module` row has `state="uninstalled"`, and `dry_run=True` → `InstallCommunityModuleOut(ok=True, module="sale", module_state="uninstalled", message="Would install sale (now uninstalled). Nothing was changed.")`. `install_module_by_name` is not called.
Decision table (`install_community_module`):
| Condition | Result |
| live `license` startswith `OEEL` | HTTP 400, `{name!r} is not a known Community app — refuse non-CE install here` |
| name is in `load_vendored_community_modules(f"{major}.0")`, or is `l10n_ng`, `l10n_generic_coa`, or startswith `l10n_` | Community |
| that list is empty and live `license` startswith `LGPL` | Community |
| otherwise | HTTP 400, same refuse detail |
| Community and no live row | HTTP 404, `{name!r} isn't available on this database.` |
| Community and `dry_run=True` | the worked example; no install |
| Community and `dry_run=False` | `client.install_module_by_name(name)` |
STOP-AND-ASK before asserting major 20 has an empty vendored list: `_normalize_odoo_version("20.0")` returns `"19.0"`, so `load_vendored_community_modules("20.0")` reads `community_modules_19_0.json`.
Test plan:
- `cd apps/api && uv run pytest -q tests/test_reg_dryinstall.py` → pass
- `cd apps/api && uv run pytest -q tests/test_reg_dryinstall.py` in reverse/random order → pass
- live: L2-HARNESS runner `--card REG-DRYINSTALL --matrix 17,18,19,20` on disposable `ingenium_*` DBs → pass per major (Phase 2 on)
Common mistakes: direct `execute_kw` outside the write gate; LLM calls outside `app/ai_client`; positional xpath; `attrs`; `<tree>` vs `<list>` by major; tests touching a non-`ingenium_` DB; restarting `:8001` (it runs without --reload).
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
