# Odoo Expert — Build Plan Progress (gap audit vs. external brief)

> **2026-08-06:** Audited against the "Odoo's Native AI" build brief (Phases 0–8).
> **Do not rebuild** what Wave 5 EXP already shipped — see `plans/cards/WAVE-5-EXP.md`.

## Summary

| Phase | Status | Evidence |
|-------|--------|----------|
| 0 — Environment | **DONE** (pre-existing) | Ollama + qwen3; MiniLM via `ai_rag.py`; Postgres `expert_chunks` (JSON embeddings, not pgvector — see deviation) |
| 1 — Ingestion | **DONE** | `app/expert/ingest.py`, `fetcher.py`, `chunker.py`; `test_expert_ingest.py` |
| 2 — Live introspection | **DONE** | `app/expert/grounding.py`; `test_expert_grounding.py` |
| 3 — Retrieval & ranking | **DONE** (minor deviation) | `app/expert/retrieval.py` — vector + Jaccard fallback, version filter, source boost; no separate keyword-boost layer on embeddings |
| 4 — Generation | **DONE** | `app/expert/ask.py`; routing 8b/14b; ground-or-decline; `test_expert_ask.py` |
| 5 — Guardrails | **DONE** | PCM/protected modules in ask pipeline; adversarial tests in `test_expert_ask.py` |
| 6 — UX surfaces | **DONE** | `ExpertPanel`, `ExplainThisButton`, error mode — EXP-5; Playwright specs |
| 7 — Eval harness | **DONE** | 41-item `tests/expert_eval/eval_set.jsonl`; baseline `docs/research/expert_eval_baseline_2026-08-03.md`; 28 expert tests green |
| 8 — Competitive parity | **DONE** (this session) | `docs/research/expert_vs_odoo_native_ai_2026-08-06.md` |

## Deviations from external brief (documented, not bugs)

1. **pgvector:** Not used. Embeddings stored as JSON in `expert_chunks.embedding_json`; cosine in Python (`ai_rag.py`). Sufficient at current scale; pgvector is a future scale item only.
2. **Hybrid keyword boost:** Brief asks vector + exact-term boost; we use embedding OR Jaccard fallback (not additive hybrid). Acceptable — Jaccard handles identifier-heavy queries when embeddings off; optional enhancement deferred.
3. **Voice transcription:** Not built — accepted gap (text-only Qwen3 stack).
4. **Community Q&A scrape:** Ingestion path exists (`EXPERT_COMMUNITY_SOURCE=dir`) but scraper explicitly out of scope per WAVE-5.

## Gate commands (re-verify anytime)

```bash
cd apps/api && uv run pytest tests/test_expert_eval.py tests/test_expert_ask.py tests/test_expert_grounding.py tests/test_expert_ingest.py -q -m "not integration"
ollama list   # qwen3:8b + qwen3:14b expected locally
```

## Last verified

- **2026-08-06:** Expert test suite 28 passed (1 skipped live-only); eval set 41 lines; alembic + GEN2-8 on master.

## Wave 17 — Universal Ingestion (planned, not started)

- Orchestrator: `plans/UNIVERSAL_INGESTION_PIPELINE.md`
- Cards: `plans/cards/WAVE-17-INGEST.md`
- Token rule: reuse `data_import` + `bulk_suite/dedupe` + `invoicing_l10n`; net-new =
  classify, PDF extract, dependency graph, multi-file job, review UI.
- Next agent action: **ING-0** only (license + inventory). Do not pull VL models until decision.

## Live Demo Co-Pilot

See `docs/live-demo-copilot/PROGRESS.md` (Attendee Phase 0–1).

## Item 4 — change-store integration (suite runs via shared change-set gates)
- New `app/suite_changeset.py`: step→op mapping (install/country_package→module.install per module, setting→setting.set, create/units→data.create_batch, update→data.update_batch with id/match domain, import→data.import_upsert split at the 1000-row cap, remove→data.unlink); int `depends_on`; ≤50 ops per change-set.
- `gate()` = shared `validate` (9 stages) + `policy_for_op` deny; dry-run stores `check.changeset` and blocks only refused steps; run pre-flights the gate (409 `changeset_refused`); request-approval also posts plan cards via `store.submit_plan` (`inbox_cards`). Writes stay in `apply_step` → runs/receipts/undo unchanged.
- Harvest over all suite test plans: 13/13 accepted, 0 behaviour change. Tests: `test_suite_changeset_gate.py` (5) + suite/plan-card suites: 103 passed.
- Q2-track batch 28: greeting uses saved display name only (users.display_name + alembic z6a7b8c9d0e1, PATCH /accounts/me/display-name, Settings 'What should we call you?'); FaviconBridge + CommandCenterTile counts via shared request() for API-key sessions. tsc clean; vitest 1534 pass (Tooltip.test flaked under full run, passes alone).
- Q2-track batch 29: 96 Model explorer placeholder 'Try: <real model>' (custom first); 97 stakes line in ConfirmDialogV2 (lib/stakes, guessed test copy never 'safe'); 110 Expert launcher quiet teal dot only when page/model-specific prompts exist (API test pins generic ids); 67 automations empty state offers up to 3 starters from this DB's models (fills composer, nothing saved until Create); 140 lib/optimistic + Code Runner tests save instantly with rollback toast. tsc clean; 782 vitest + 2 pytest pass.
- Q2-track batch 30: 49 PageMove in AppShell (side crossfade / deeper +6px / back reverse, no remount, reduced-motion fade); 128 lib/readiness one-time intros (density day 3, Code Runner day 6; nothing hidden); 154 generated model.py gets plain docstring header (generator 82 pass; 5 API generation failures pre-exist, verified by revert). 127 blocked: welcome letter needs Tope's own words. tsc clean; 632 vitest pass.
- Q2-track batch 31: 127 WelcomeLetter on Overview, UNPUBLISHED placeholder (renders nothing until Tope's text + published=true); 80 records editor List/Board toggle (board by stage_id, else state; shared selection survives switch; board fetches its field). 124 skipped: lives in Live Demo Co-Pilot (other worker's area). alembic drift test passes (4). tsc clean; suite+overview vitest pass.
- Q2-track batch 32: 136 SR copy guard test (no bare status words in live regions) + 2 fixes ('Updating the report/email preview…'); 85 already built (recent, preview pane, per-item actions via Tab); 133 receipt-quality HTML twin for verify/reset/invite emails (one teal button, link fallback, no images, color-scheme light dark), send_email(html=) multipart. pytest 28 pass; report-designer vitest pass.
- Q2-track batch 33: 156 'Prepared with Ingenium.' footer on Bridge handbooks: free plans always, paid may remove (?footer=false), white-label never shows Ingenium (agency-name substitution pending: no agency brand field yet). 84 pytest pass.
- Q2-track batch 34: 71 stone dust (12 ink particles, 0.6s, once on keystone milestone; reduced motion = still). 160 blocked: needs step timings/approver recorded inside publish write paths (other worker's A5 area). Full vitest 1556 pass; tsc clean.
- Q2-track batch 35: email subjects 'Odoo Custom'->'Ingenium' (3); 9 LogoConstruction on home (R100/r46/springing/baseline/±15° joints draw, then stones fill; once per browser; reduced motion = finished mark); 35 lib/morph shared-element morph: Connect card grows into the database page (View Transitions, plain nav fallback). Rows->record sheet and script->editor not yet hosted. tsc clean; tests pass.
- Q2-track batch 36: 58 Bridge TransitMap (app / Ingenium / Odoo lines, stations per trace step, failed stations red, full text for screen readers) above the trace list. NOTE: no production code calls bridge flows.trace() yet, so traces stay empty until the runtime records steps.
- Q2-track batch 37: 35 finished: record row opens into a read-only record sheet (morphInPlace, Esc/Close), Code Runner library card morphs into the editor. tsc clean; suite/code-runner tests pass.
- Q2-track batch 38: 98 Ingenium icon layer (8 icons: model, field, view, automation, approval rule, Bridge flow, numbering, history; Lucide 24-grid/2px/round; exported from ui/icons; not yet swapped into nav). 101 ArchDrawing (ink elevation/plan hairlines + one cinnabar keystone), default art in EmptyState when no icon (43 call sites). 99 deferred: true 15° terminals need outlined-stroke drawing. Full vitest 1559 pass; tsc clean.
- Q2-track batch 39: 101 placed in onboarding (FirstRunCard) and Bridge handbooks (docs/arch.svg + header image). 125 onboarding builds the arch: stones laid per finished step, keystone drops in when all done. 99 icons outlined with 15° terminals (generator scripts/icons/gen_ingenium_icons.py, shapely); 98 swapped app-wide via ui/icons aliases (Models, Fields, Views, Automations, Approvals, IdGenerator, Snapshots; IconBridge added). tsc clean; full vitest 1560 pass; bridge pytest 84 pass.
- Q2-track batch 40: 104 bot avatar state machine (idle/thinking/working/done/needs_you, canMove guard, keystone hovers+breathes, stones fill when working, fine cinnabar outline when needs you; CSS not Rive). 126 app/sample_company: Adebayo & Sons Furniture (Lagos addresses, NGN prices, 7.5% VAT), seed() refuses non-ingenium_* DBs; not wired to UI. 130 generated reports get print-grade CSS (orphans/widows 3, hyphens, tabular right-aligned money; hanging-punctuation only where renderer supports). 132 email preview framed as Gmail/Outlook/iPhone Mail/dark (approx.); 'Send me a test' not built: needs a send path. Tests: generator 82, report pytest 83 (+1 pre-existing pdf04 fail), report-designer vitest pass.
- Q2-track batch 41: 104 screens now pass working (Ask after first real step; runs while running), done, needs_you; states preview shows all five. 126 'Load sample company' (GET/POST /connections/{id}/sample-company; only ingenium_* or is_test_copy=true; guard_record_create per model before any write; two-step confirm card on Overview, hidden elsewhere). 132 'Send me a test' (POST emails/engine/test-send): server picks the signed-in user's own address, Ingenium mailer (send_email html), no recipient field. Existing Odoo-mail typed-address test relabelled 'Send a test to this address'. NOTE: test_alembic_drift now fails on ix_integration_events_ordering_key (not mine; Bridge/other worker). tsc clean; pytest 6 + vitest pass.
- Q2-track batch 42: 134 sealed handover PDF (UAT report): cover with fingerprint, contents with page numbers, keystone seal drawn on the last page + SHA-256 fingerprint; ?sealed=false for the old plain PDF. QR deferred: no QR library in the venv (segno would be a new dependency). pytest 57 pass.
- Q2-track batch 43: 142 instant shell (lib/shellCache: connection + list paint from device cache via placeholderData, credentials scrubbed). 143 local-first search (schema cached on device for Find anything; recent records saved when a record sheet opens, listed under 'Recent records', open via ?model=&open=). 145 e2e/smoothness.spec.ts (CPU 4x; fails if >10% frames over 50 ms or any over 120 ms) on theme switch, approvals scroll, connect scroll: 3 pass; zero-layout-shift 4 pass; :3010 freed. Typecheck errors at EmailDesigner:226 were transient (fixed 16:00), tsc clean.
- Q2-track batch 44: 142 hydration fix (useHydrated; shellCacheHydration.test) + WCAG AA contrast test (lib/a11y/contrast.test.ts: token pairs, every bg+text className, CSS rules; light+dark). Fixed 19 failures: dark --accent accent4->accent6 + dark --on-accent, odoo-primary to match; --on-brand dark ink both themes; Sidebar teal chip (accent on accent-subtle 1.73 -> pass); o2m th + plan-note fallbacks to tokens; two bg-accent/15 chips -> text-accent-hover. tsc clean, vitest 1568 pass (Tooltip timing flake passes alone).
- Q2-track batch 45: e2e shell-paint.spec (142 shell <100 ms on repeat visit + no hydration error, prod) pass; Connect form responsiveness e2e (5 cases: saved conns, arriving from a connection, reload, all densities, hit-test every control, Add another) - could not reproduce the freeze, tests kept; contrast.test polarity rule (bg lum>0.4 => fg lum<0.2), CSS literals/alpha/scope vars/--contrast-on; new --on-success/--on-danger/--on-warning tokens; fixed 15 CSS rail/check marks + history count, 4 class pairs (text-white on success/danger/accent/ink); sidebar ConnectionSwitcher (menu, keyboard, Live/Test + version, All connections, Add connection -> /connect#new focuses form) + Cmd-K Connections group; e2e connection-switcher.spec 3 pass. tsc clean, vitest 1571 pass.
