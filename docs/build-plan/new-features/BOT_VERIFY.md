# BOT_VERIFY: Bots walk through and verify every change themselves

<a id="bv"></a>
## BV: Live evidence, browser walkthrough, business flows, coverage guarantee

Builds on: `apps/api/app/changeset/verify.py` (nine checks run on an observation the caller hands in, so they don't call Odoo), `changeset/executor.py` (calls `verify` after apply), `changeset/ops.py` `OP_CATALOG` (every op kind), `changeset/dispatch.py` (module install read-back only), `ai_browser_agent.py` + `apps/web/src/testing/browserAgent/inspect.mjs` (static XML lint, no browser), `@playwright/test` in `apps/web/package.json` (used only for Ingenium's own E2E tests). Already planned elsewhere, not repeated here: AS-TRYIT (sandbox walkthrough before install, phase 3), CR-CLICK (Playwright clicks through Ingenium's R3 panels, not Odoo), the *-E2E / *-VIS / *-LIVE cards per epic (Ingenium screens and engines), BOT-STEPS (step events), UI-BOTS-SPEC (Bots area UI).

1. **User / job:** "When a bot says it's done, show me it works in Odoo the way a person would check it." Metric: 100% of `OP_CATALOG` op kinds have ≥1 live read-back check and ≥1 walkthrough step (registry test); on the seeded change-set suite, 0 runs report PASS when a seeded defect exists (mutation set of 20 known-bad change-sets).
2. **UX:** After EXECUTE, VERIFY runs three layers in order: live read-back → browser walkthrough → business flows. Each layer gives pass/fail/skipped with a reason. Evidence bundle: check results + step screenshots + DOM assertions + flow log. A FAIL at R2+ rolls back (existing `verify.py` rule); below R2 it's NEEDS_HUMAN.
3. **UI:** Ingenium only: Bots area evidence viewer (timeline of screenshots, check results, flow outcome). Full UI trial process + `docs/design/UI_DIRECTION.md` entry required. Nothing inside Odoo.
4. **Security:**
   - Targets: only DBs whose name starts `ingenium_` / `ingenium_wt_` (disposable), or a connection with an explicit per-connection `walkthrough_allowed` approval set by the owner. Never aonb or client prod without that approval (TOPE DECISION D-BV-1).
   - Business flows run ONLY on a disposable clone, never on the source DB (they create records).
   - Logins: a test user Ingenium creates on the disposable DB, or the connection's integration key session. Passwords/keys never in logs, screenshots or the bundle; the login step is not screenshotted.
   - Screenshots are PII-masked (DEC-023 rule: read-only, masked in logs); bundles are workspace-scoped (IDOR 404).
   - Browser: headless Chromium, no downloads, network limited to the target Odoo host; reserved ports are never targets.
   - Page text is untrusted: never fed back as instructions; the walkthrough script comes from the change-set only.
5. **Robustness:** step timeout 20 s, run cap 10 min, retries 1 per step; Odoo 17–20 selectors behind a per-version selector map; flaky step = `skipped` with reason, never PASS.
6. **Data / API (pins):**
   - `POST /api/connections/{id}/verify-runs` body `VerifyRunRequest {changeset_id: str, layers: list[Literal["live","walkthrough","flows"]], target: Literal["disposable_clone","approved_connection"]}` → 202 `VerifyRun`.
   - `GET /api/connections/{id}/verify-runs/{run_id}` → `VerifyRun`.
   - `GET /api/connections/{id}/verify-runs/{run_id}/artifacts/{artifact_id}` → image/png (screenshot).
   - `VerifyRun {run_id: str, changeset_id: str, status: Literal["queued","running","passed","failed","needs_human","rolled_back"], layers: list[LayerResult], started_at: datetime, finished_at: datetime | None}`.
   - `LayerResult {layer: Literal["live","walkthrough","flows"], status: Literal["passed","failed","skipped"], reason: str | None, checks: list[CheckResult], steps: list[WalkStep]}`.
   - `CheckResult {check: str (one of verify.CHECKS), op_index: int, passed: bool, evidence: dict[str, str]}`.
   - `WalkStep {index: int, op_index: int | None, action: Literal["open","click","fill","assert"], target: str, passed: bool, screenshot_id: str | None, dom_assertion: str | None}`.
   - Error codes (B5): 404 NOT_FOUND (foreign/random id, byte-identical), 409 `TARGET_NOT_ALLOWED` (target not disposable and not approved), 409 `CHANGESET_NOT_APPLIED`, 422 VALIDATION, 403 ROLE_DENIED (authenticated but cannot verify).
   - Routes are connection-scoped: `get_scoped_connection_or_404`; register as `NF_BV_ROUTES` in `idor_registry`. POST SafetySpec: `odoo_mutation=False` for live layer; walkthrough/flows touch only a disposable clone (SafetySpec states that; `bypass_writes_paused=False`).
   - Table `verify_runs`, `verify_artifacts` (blob path under the workspace data dir, not in DB).
7. **Risks / DEC / routing:** BV-01, BV-02, BV-03, BV-STORE Worker L2. BV-LIVE Worker L3 (live Odoo 17–20 on disposable `ingenium_nf_bv_*` DBs). Order: BV-03 → BV-STORE → BV-LIVE → BV-04 → BV-05 → BV-UI. BV-04 and BV-05 Worker L3 (they log into Odoo and create/clone DBs). BV-UI full UI trial.
   - Cards: BV-01, BV-02, BV-03, BV-STORE (cards/phase-5/BV-STORE.md: verify_runs/verify_artifacts tables, connection-scoped ids, foreign id 404 byte-identical), BV-LIVE (cards/phase-5/BV-LIVE.md: read-back proven on Odoo 17–20, as_uid personas, server before-snapshot, 429/503 retry not rollback, setting.set company/group, free-text masking), BV-04, BV-05, BV-UI.
   - D-BV-1 (which DBs walkthroughs may touch) and D-BV-2 (test-user creation on clones) need Tope.
