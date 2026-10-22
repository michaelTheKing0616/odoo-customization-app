#!/usr/bin/env python3
"""G1C amendments (21 Oct, Tope's sixth message): live-DB grounding cards, Draft Studio on v3, Elevate.

Side effects (idempotent):
- adds ledger rows (never edits existing ones) to docs/build-plan/ledger.csv
- adds the "EL-" prefix (phase 7) to docs/build-plan/phase_map.json
- writes docs/build-plan/cards/phase-<n>/<ID>.md for each card below, skipping files that exist
- rewrites docs/build-plan/elevate/ORACLES.md from the `oracles` entries below
After the first run, the card files are the source of truth; edit them, not this script.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

PLAN = Path(__file__).resolve().parents[1]
LEDGER = PLAN / "ledger.csv"
PHASE_MAP = PLAN / "phase_map.json"
EL_ORACLES = PLAN / "elevate" / "ORACLES.md"

CHARTER = "TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: {b} (caps in budget.json). Stop at 80%."
GATE = ("Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → "
        "Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).")
EVIDENCE = ("Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · "
            "label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.")
DOD = ("Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; "
       "Orchestrator updates the ledger rows; Status set to done.")
ROLLBACK_AS = "Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT."
ROLLBACK_EL = ("Rollback: Revert this card's diff (allow-list files only). No existing behaviour is removed by this card; "
               "a ratchet baseline file, where present, keeps today's known gaps listed so the revert is clean.")
UI_BAR = ("UI: every screen this card touches meets handover §5 + `UI_REFERENCE_MAP.md` + `07_UI_EXCELLENCE_PROTOCOL.md` "
          "(Tope: the absolute best design on every screen): designed empty/loading/error/offline states, tokens only, "
          "Base UI + Sonner, motion < 300 ms transform/opacity with reduced-motion, plain copy that passes the jargon guard. "
          "UI checkpoints only: baseline, after, final (one contact sheet per screen).")
LIVE = "Live checks run only on disposable `ingenium_*` sandboxes for 17, 18, 19 (and 20 once its stack exists); drop what you create (INV-03)."
WEB_TEST = "cd apps/web && pnpm vitest run {f}"
E2E = "cd apps/web && pnpm playwright test {f} (isolated build: own distDir, port 3100; never 3002)"
API_TEST = "cd apps/api && uv run pytest -q {f}"
RATCHET = ("Ratchet: today's failures are written once to the baseline file named in the allow-list; the test fails on any new "
           "failure and on any baseline entry that now passes (so the list only shrinks). Each feature's EL-BAR card removes its entries.")


def c(**kw):
    kw.setdefault("phase", 7)
    kw.setdefault("pri", "P2")
    kw.setdefault("oracles", [])
    kw.setdefault("ui", False)
    kw.setdefault("elite", "")
    return kw


CARDS = [
    # ---- Phase 3: App Studio built against the connected database (Pack §6.7) ----
    c(id="AS-GROUND-WIRE", phase=3, pri="P1", title="One live schema packet per v3 run, used by every stage",
      ledger="AS-GROUND", deps="AS-V3-WIRE", b="M", tier="L3", score="6 (C2 U1 F1 K1 V1 I0)",
      ctx=["docs/build-plan/app-studio/00_PACK.md §6.7 item 1", "apps/api/app/live_schema_context.py L130-300 (build/studio packet)",
           "apps/api/app/ai_conversation/understand.py L1428-1462 (how the intent call prepends the packet today)"],
      allow=["apps/api/app/ai_conversation/v3_pipeline.py", "apps/api/app/ai_conversation/ground_v3.py (new)",
             "apps/api/tests/test_ground_v3.py (new)"],
      goal="Build the packet once at t=0 (parallel with N) for contract/retrieval hosts plus direct relations; give K and L the fenced render, C/D/A/preview the structured packet.",
      steps=["`ground_v3.packet_for_run(connection, hosts, profile) -> SchemaPacket` wraps `studio_schema_packet`; records its fingerprint on the run",
             "K and L prompts get `fence_untrusted(render_schema_packet(p))`; C, D, A and the preview receive the same object",
             "Connection present + empty or stale packet → `StudioOutcome.degraded` with a plain reason; no design emitted",
             "After `install_step` (GND-MOD) rebuild the packet before the next stage; log both fingerprints",
             "Prompt text carries names and counts only, never record contents (INV-17)"],
      acs=["ORACLES G-01, G-02, G-03 and G-12 pass unmodified", "No v3 stage reads Odoo structure from anywhere but the run's packet (import-graph test)"],
      test=API_TEST.format(f="tests/test_ground_v3.py"),
      elite="Pack §6.7. The packet is the only door to Odoo structure for the LLM stages; a second read path is a defect.",
      oracles=["app-studio/ORACLES.md G-01, G-02, G-03, G-12"]),
    c(id="AS-GROUND-VIEWMAP", phase=3, pri="P1", title="View map: the real structure of each host view, per major",
      ledger="AS-GROUND", deps="AS-GROUND-WIRE", b="L", tier="L3", score="7 (C2 U2 F1 K1 V1 I0)",
      ctx=["docs/build-plan/app-studio/00_PACK.md §6.7 item 2", "apps/api/app/live_schema_context.py L437-555 (`_view_field_order`, `_packet_model`)",
           "packages/odoo-client/src/odoo_client/schema_graph.py L103 (`combined_arch` = `get_view`)"],
      allow=["apps/api/app/view_map.py (new)", "apps/api/app/live_schema_context.py (add `view_maps` to PacketModel; render cap)",
             "packages/odoo-client/src/odoo_client/schema_graph.py (add read-only `view_inherit_chain`)",
             "apps/api/tests/test_view_map.py (new)", "apps/api/tests/fixtures/view_map/ (new; recorded arches per major)"],
      goal="Per host model and view type: anchor tree (header, button_box + its smart buttons, named groups, pages, chatter), each field's container path, label, widget, invisible/readonly, selection values, and owning module + view xml-id.",
      steps=["Parse the combined arch with the existing XXE refusal (`arch_has_xxe`); build `ViewMap{anchors, fields, smart_buttons}`",
             "Ownership: `ir.ui.view` search_read on model + type (inherit_id, mode, priority) joined to `ir.model.data` for xml-ids [Inferred API, verify on each major]",
             "Labels and help from the database are untrusted: run `classify_injection`; render only inside the fence",
             "Render under a named constant cap per model (`VIEW_MAP_RENDER_CHAR_CAP`), truncating deterministically with an \"n more omitted\" line",
             "Record fixtures for `sale.order`, `res.partner`, `crm.lead`, `account.move` forms on disposable 17/18/19 sandboxes; 20 when its stack exists. " + LIVE],
      acs=["ORACLES G-04 and G-05 pass unmodified", "Existing packet tests stay green (field order unchanged)",
           "Render stays under the cap on every fixture"],
      test=API_TEST.format(f="tests/test_view_map.py"),
      elite="Version facts (17 `<tree>`, 18+ `<list>`, chatter markup per major) come from the recorded fixtures, never from memory; any fact not seen in a fixture is [Inferred] and skipped.",
      oracles=["app-studio/ORACLES.md G-04, G-05"]),
    c(id="AS-GROUND-PLACE", phase=3, pri="P1", title="Place by meaning, verify by re-reading Odoo",
      ledger="AS-GROUND", deps="AS-GROUND-VIEWMAP, AS-CRAFT-APPLY", b="L", tier="L3", score="7 (C2 U1 F2 K1 V1 I0)",
      ctx=["docs/build-plan/app-studio/00_PACK.md §6.7 item 3", "apps/api/app/live_schema_context.py L644-683 (`resolve_form_anchor`)",
           "apps/api/app/view_engine.py (existing name-based xpath builder; reuse, do not fork)"],
      allow=["apps/api/app/ai_conversation/ground_place.py (new)", "apps/api/tests/test_ground_place.py (new)"],
      goal="Owner placement words resolve against labels and containers; output name-based xpath on the host's primary view; after apply, re-read and roll back any node that landed elsewhere.",
      steps=["Resolve phrase → anchor by label, then technical name, then alias; containers by page/group label",
             "Emit `//field[@name]`, `//page[@name]`, `//div[@name='button_box']`, `//header` only; unnamed anchor → nearest named ancestor (reason logged)",
             "Never `replace` on stock; never positional; inherit the primary view of that type",
             "Post-apply: `combined_arch` re-read; node not in the planned container → roll back that view, `left_out` with a plain reason",
             "Live: 3 extension eval briefs on disposable 17-19 sandboxes (20 when built). " + LIVE],
      acs=["ORACLES G-06, G-07 and G-11 pass unmodified", "Live: 100% of placed nodes in the planned container on every major run",
           "No positional xpath and no `replace` in any emitted view (property)"],
      test=API_TEST.format(f="tests/test_ground_place.py"),
      elite="Pack §6.7. Placement is deterministic code over the view map; the LLM only supplies the owner's phrase, quoted.",
      oracles=["app-studio/ORACLES.md G-06, G-07, G-11"]),
    c(id="AS-GROUND-EXISTS", phase=3, pri="P1", title="Know what already exists before adding anything",
      ledger="AS-GROUND", deps="AS-GROUND-VIEWMAP, AS-COMPILE", b="M", tier="L3", score="6 (C2 U1 F1 K1 V1 I0)",
      ctx=["docs/build-plan/app-studio/00_PACK.md §6.7 item 4, §6.3 (host_fit)", "docs/build-plan/cards/phase-3/AS-COMPILE.md"],
      allow=["apps/api/app/ai_conversation/ground_exists.py (new)", "apps/api/app/ai_conversation/ledger_compile.py (one call site)",
             "apps/api/tests/test_ground_exists.py (new)"],
      goal="Reuse stock fields matched by label+type(+selection), earlier Ingenium `x_` fields and existing smart buttons; name the installed app that already does the ask; each reuse is an undoable assumption.",
      steps=["Match on normalised label + type (+ selection values); ties go to the stock field", "Earlier Ingenium fields: `x_` fields whose lineage marker is ours",
             "Smart buttons: same target relation already in `button_box` → no new button", "Write each reuse as an assumption with the owner's quote and an Undo"],
      acs=["ORACLES G-08, G-09 and G-10 pass unmodified", "Zero duplicate fields or smart buttons across the extension eval set"],
      test=API_TEST.format(f="tests/test_ground_exists.py"),
      elite="A wrong reuse is worse than a duplicate: below the match threshold, ask (Q stage) rather than reuse silently.",
      oracles=["app-studio/ORACLES.md G-08, G-09, G-10"]),
    c(id="AS-GROUND-DATA", phase=3, pri="P2", title="Data shape facts that change what gets built",
      ledger="AS-GROUND", deps="AS-GROUND-WIRE", b="S", tier="L2", score="4 (C1 U1 F1 K1 V0 I0)",
      ctx=["docs/build-plan/app-studio/00_PACK.md §6.7 item 5", "apps/api/app/routers/builder.py (existing fill-rate endpoint `/models/{m}/fill`)"],
      allow=["apps/api/app/ai_conversation/ground_data.py (new)", "apps/api/tests/test_ground_data.py (new)"],
      goal="Read-only facts for D and C: multi-company on/off, active currencies, installed languages, host stages/sequences present, fill rates of candidate anchors.",
      steps=["Counts and flags only; never record contents (INV-17)", "Feed K12 (company/currency) and translation rows only when the fact says so"],
      acs=["AC1: Facts object has only booleans, counts and technical names (property)", "AC2: Multi-company off → no company field emitted by craft"],
      test=API_TEST.format(f="tests/test_ground_data.py")),
    c(id="AS-DRAFT-ADOPT", phase=3, pri="P1", title="Draft Studio runs the App Studio v3 pipeline; no domain packs",
      ledger="AS-DRAFT-V3", deps="AS-RELEASE-BARS, AS-V3-WIRE", b="L", tier="L3", score="7 (C2 U1 F2 K1 V1 I0)",
      ctx=["docs/build-plan/09_DECISIONS_FOR_TOPE.md DEC-043", "apps/api/app/ai_pipeline.py L87-170 (`seed_unpacked_draft`, `seed_studio_draft`), L699 (`run_staged_pipeline`)",
           "handover §3.17 (what packs do today)"],
      allow=["apps/api/app/ai_pipeline.py (route generation to `v3_pipeline` under profile v3)", "apps/api/tests/test_draft_studio_v3.py (new)",
             "docs/build-plan/app-studio/PACK_PRESERVATION.md (new)"],
      goal="Once v3 passes its release bars, Draft Studio's generate path calls `v3_pipeline`; no `ai_domain_pack*` module is reachable from it; everything packs did for users still exists.",
      steps=["Write PACK_PRESERVATION.md first (INV-05): each pack behaviour → where it lives under v3 (stock_first_rework → host_fit + AS-GROUND-EXISTS; \"Use stock app X\" → stock_reuse card; industry seed CSVs → K42 import templates / AS-TRYIT; curated provenance → retired with the packs)",
             "Route Draft Studio generate through `v3_pipeline` when the profile is v3; legacy profile unchanged",
             "Import-graph test: from the Draft Studio v3 entry, no `ai_domain_pack` module is importable",
             "On ship, the Orchestrator asks Tope to approve the AGENTS.md Draft Studio pack sentence edit (rules file)"],
      acs=["AC1: Draft Studio eval subset under v3 meets the AS-RELEASE-BARS numbers", "AC2: import-graph test passes",
           "AC3: every row of PACK_PRESERVATION.md names a live replacement or a Tope-approved retirement", "AC4: \"Use stock app X\" still shown for restaurant / project / retail briefs"],
      test=API_TEST.format(f="tests/test_draft_studio_v3.py"),
      elite="DEC-043: Tope approved dropping packs from Draft Studio once v3 works. File deletion is AS-PACK-RETIRE, not this card.",
      oracles=["AC2 and AC4 are locked: Tester writes them from this card before the Worker starts"]),
    c(id="AS-PACK-RETIRE", phase=3, pri="P2", title="Retire domain pack code after Draft Studio and App Studio both run v3",
      ledger="AS-DRAFT-V3", deps="AS-DRAFT-ADOPT, AS-NO-PACKS", b="M", tier="L2", score="5 (C1 U1 F1 K1 V1 I0)",
      ctx=["docs/build-plan/app-studio/PACK_PRESERVATION.md", "handover §3.17"],
      allow=["apps/api/app/ai_domain_pack*.py (removal only, after Tope's yes)", "the 57 importers of pack modules (remove dead imports only)",
             "apps/api/tests/ (delete pack-only tests; keep provenance tests until the last importer is gone)"],
      goal="Remove pack modules and their imports once no supported profile uses them, with every behaviour accounted for.",
      steps=["Stop and ask Tope for an explicit yes in the current message before deleting any file (INV-05, INV-18)", "Delete in one importer at a time; full api suite after each batch"],
      acs=["AC1: `rg ai_domain_pack apps/api/app` returns nothing", "AC2: full api suite green", "AC3: Tope's yes quoted in the Tester packet"],
      test="cd apps/api && uv run pytest -q"),

    # ---- Phase 7: cross-cutting Elevate cards ----
    c(id="EL-X-BAR", pri="P1", title="Feature Excellence scorecard", ledger="ELR-BAR", deps="none", b="M", tier="L2", score="5 (C1 U1 F1 K1 V1 I0)",
      ctx=["docs/build-plan/elevate/00_ELEVATE.md §1", "handover §5.8-5.14 (states, copy, a11y, dark mode, budgets, visual QA)"],
      allow=["scripts/excellence_scorecard.py (new)", "docs/build-plan/elevate/route_map.json (new)", "apps/api/tests/test_excellence_scorecard.py (new)"],
      goal="One command prints a red/green row per §1 check for a feature (`--feature connect`) or all, by running the existing tools and the EL-X tests.",
      steps=["route_map.json: feature → web routes, components dirs, API routers (from handover §3 'Built' lists)",
             "Each check shells out to an existing tool (vitest states preview, axe e2e, jargon guard, token lint, EL-X tests)",
             "A check with no tool yet prints `not measured` and counts as red, never green"],
      acs=["AC1: `--feature connect` prints every §1 check with a result", "AC2: unmeasured checks are red (test)", "AC3: exit code non-zero on any red"],
      test=API_TEST.format(f="tests/test_excellence_scorecard.py")),
    c(id="EL-X-AUTHZ", pri="P1", title="Every API route declares who may call it", ledger="ELR-SEC", deps="EL-X-BAR", b="S", tier="L3", score="7 (C1 U1 F2 K1 V1 I1)",
      ctx=["apps/api/app/main.py (router registration)", "apps/api/app/auth.py, apps/api/app/workspace_auth.py (existing dependencies)", "AGENTS.md App API auth (Phase 7)"],
      allow=["apps/api/tests/test_route_authz.py (new)", "apps/api/tests/authz_public_routes.json (new; each public route with a reason)",
             "apps/api/tests/authz_baseline.json (new; ratchet)"],
      goal="A test walks `app.routes` and fails on any route without an access dependency, unless it is listed as public with a reason.",
      steps=["Collect dependencies recursively per route (router-level and endpoint-level)", RATCHET],
      acs=["AC1: a planted route with no dependency fails the test", "AC2: public list entries each carry a non-empty reason",
           "AC3: baseline entries listed in the Tester packet with owning feature"],
      test=API_TEST.format(f="tests/test_route_authz.py"),
      elite="Detection only; fixes land in each feature's EL-BAR card. Never weaken an existing dependency to make the test pass.",
      oracles=["EL-X-AUTHZ-1 planted unguarded route → fail", "EL-X-AUTHZ-2 public route without reason → fail"]),
    c(id="EL-X-TENANT", pri="P1", title="Account A can never see or change account B's data", ledger="ELR-SEC", deps="EL-X-AUTHZ", b="M", tier="L3", score="8 (C2 U1 F2 K1 V1 I1)",
      ctx=["apps/api/app/auth.py (api_key mode, hashed `app_api_keys`)", "apps/api/app/routers/connections.py, history.py, ai_studio.py, code_runner.py, bridge.py"],
      allow=["apps/api/tests/test_tenant_isolation.py (new)", "apps/api/tests/tenant_baseline.json (new; ratchet)"],
      goal="With two accounts in `AUTH_MODE=api_key`, every list and by-id endpoint for connections, drafts, runs, flows, scripts and history hides B's rows from A and refuses A's writes to B's ids.",
      steps=["Fixture: two accounts, one connection each, on the app's disposable test database", "Parametrise over routes from route_map.json", RATCHET],
      acs=["AC1: cross-account read returns 404 (not 403, no existence leak)", "AC2: cross-account write refused and nothing changes", "AC3: baseline listed per feature"],
      test=API_TEST.format(f="tests/test_tenant_isolation.py"),
      elite="Test-only card. INV-03: the app test DB is disposable; no client DB is touched.",
      oracles=["EL-X-TENANT-1 A lists B's connection → absent", "EL-X-TENANT-2 A writes B's draft id → 404, row unchanged"]),
    c(id="EL-X-WRITE-AUDIT", pri="P1", title="Prove every Odoo write goes through the write gate", ledger="ELR-SEC", deps="EL-X-BAR", b="M", tier="L3", score="7 (C2 U1 F2 K1 V1 I0)",
      ctx=["apps/api/app/write_gate.py", "apps/api/tests/test_write_gate.py", "handover §2.3"],
      allow=["apps/api/tests/test_write_gate_coverage.py (new)", "apps/api/tests/write_gate_baseline.json (new; ratchet)"],
      goal="AST scan of `apps/api/app` and `packages/odoo-client`: every call that sends create/write/unlink/action_* to Odoo is reached only through the write gate and returns a receipt with Undo.",
      steps=["Find RPC call sites by method-name literal; resolve the enclosing function; require a write-gate entry on the path", RATCHET],
      acs=["AC1: a planted direct `write` call fails", "AC2: baseline lists each ungated call site with its feature"],
      test=API_TEST.format(f="tests/test_write_gate_coverage.py"),
      elite="Read-only over write_gate.py (INV-14): this card never edits the gate.",
      oracles=["EL-X-WRITE-AUDIT-1 planted ungated write → fail"]),
    c(id="EL-X-INJECT", pri="P1", title="Hostile database text cannot steer any LLM surface", ledger="ELR-SEC", deps="EL-X-BAR, AS-GROUND-VIEWMAP", b="M", tier="L3", score="7 (C2 U1 F2 K1 V1 I0)",
      ctx=["apps/api/app/ai_client/guards.py L43 (`fence_untrusted`), L181 (`classify_injection`)", "docs/plans/next-phase/cards/T1_LIVE_CONTEXT.md GND-GATE (surface list)"],
      allow=["apps/api/tests/injection_corpus/ (new; hostile names, labels, help, chatter, file names)", "apps/api/tests/test_llm_surface_injection.py (new)",
             "apps/api/tests/inject_baseline.json (new; ratchet)"],
      goal="For each LLM surface, a fake provider records the prompt: hostile database strings appear only inside the fence and are flagged; outputs that obey them are rejected by the validator.",
      steps=["Surfaces = GND-GATE list plus App Studio K/L and View Designer AI edit", RATCHET],
      acs=["AC1: zero unfenced corpus strings in any recorded prompt", "AC2: a model reply that follows an injected instruction is rejected"],
      test=API_TEST.format(f="tests/test_llm_surface_injection.py"),
      elite="Grounding (Pack §6.7) moves Odoo data into prompts; this card is the matching guard. Corpus contains no real PII.",
      oracles=["EL-X-INJECT-1 label 'ignore previous instructions' → fenced + flagged", "EL-X-INJECT-2 reply adding a model named in the injection → rejected"]),
    c(id="EL-X-ERRORS", pri="P1", title="One error shape and plain error messages everywhere", ledger="ELR-REL", deps="EL-X-BAR", b="M", tier="L2", score="5 (C1 U1 F1 K1 V1 I0)",
      ctx=["apps/api/app/main.py (no exception handlers today [Verified 21 Oct])", "apps/web/src/lib/api-error.ts, format-fetch-error.ts", "apps/web/src/components/ui/ErrorNotice.tsx"],
      allow=["apps/api/app/errors_catalog.py (new)", "apps/api/app/main.py (register handlers only)", "apps/api/tests/test_errors_catalog.py (new)",
             "apps/web/src/lib/api-error.ts", "apps/web/src/components/ui/ErrorNotice.tsx", "apps/web/src/lib/api-error.test.ts"],
      goal="Every API error returns `{code, message, fix, retryable, request_id}`; the web shows message + fix + Retry; no stack trace reaches a user.",
      steps=["Catalog: code → owner sentence + fix, jargon-guarded", "Handlers for HTTPException, validation errors and the unhandled case (logs request_id, never secrets)",
             "Web maps codes to ErrorNotice; unknown codes get the generic catalog entry"],
      acs=["AC1: an unhandled exception returns the envelope with a request_id and no traceback", "AC2: every catalog message passes the jargon guard", "AC3: web test renders fix + Retry"],
      test=API_TEST.format(f="tests/test_errors_catalog.py") + " ; " + WEB_TEST.format(f="src/lib/api-error.test.ts"), ui=True),
    c(id="EL-X-RESILIENT", pri="P2", title="Nobody loses work: offline banner, retries, autosave", ledger="ELR-REL", deps="EL-X-ERRORS", b="M", tier="L2", score="5 (C1 U1 F1 K1 V1 I0)",
      ctx=["apps/web/src/lib/api.ts", "apps/web/src/components/shell/AppShell.tsx (existing online/offline handling)",
           "apps/web/src/components/view-designer/useViewDesigner.ts, report-designer/useReportDesigner.ts (existing offline hooks)"],
      allow=["apps/web/src/lib/autosave.ts (new)", "apps/web/src/lib/autosave.test.ts (new)", "apps/web/src/lib/api.ts (retry with backoff for idempotent calls)",
             "apps/web/src/components/shell/AppShell.tsx"],
      goal="Idempotent requests retry with backoff; a calm offline banner with Retry; brief, view, report, script and flow drafts autosave locally and offer restore.",
      steps=["Retry only GET and calls carrying an idempotency key", "Autosave keyed by connection + editor + record; cleared on successful save", "Restore prompt names what and when"],
      acs=["AC1: non-idempotent POST is never retried (test)", "AC2: autosave restores after reload (test)", "AC3: offline banner announced via live region"],
      test=WEB_TEST.format(f="src/lib/autosave.test.ts"), ui=True),
    c(id="EL-X-OBS", pri="P2", title="See reliability: events, SLOs and a System health view", ledger="ELR-REL", deps="EL-X-ERRORS", b="M", tier="L2", score="5 (C1 U1 F1 K1 V1 I0)",
      ctx=["apps/api/app/routers/admin.py", "apps/web/src/app/admin/"],
      allow=["apps/api/app/observability.py (new)", "apps/api/app/routers/admin.py (one read-only endpoint)", "apps/api/tests/test_observability.py (new)",
             "apps/web/src/app/admin/health/ (new page)", "apps/api/pyproject.toml (add opentelemetry-sdk, Apache-2.0)"],
      goal="Structured events per feature (latency, outcome, error code); SLO per feature in one table; admin page shows p95, error rate and queue depth from the App DB, local only.",
      steps=["OpenTelemetry SDK with a local exporter only; no SaaS (no paid dependency)", "No secrets or PII in attributes (existing scrub)"],
      acs=["AC1: every router emits an event per request (test over route_map)", "AC2: attributes pass the scrub test", "AC3: page shows real numbers or says 'No data yet'"],
      test=API_TEST.format(f="tests/test_observability.py"), ui=True),
    c(id="EL-X-FIDELITY", pri="P1", title="One harness proving previews match real Odoo", ledger="ELR-FID", deps="EL-X-BAR, AS-GROUND-VIEWMAP", b="M", tier="L3", score="6 (C2 U1 F1 K1 V1 I0)",
      ctx=["packages/odoo-client/src/odoo_client/schema_graph.py L103", "apps/web/src/lib/design-preview.ts", "apps/api/app/routers/preview_proxy.py"],
      allow=["apps/api/app/fidelity.py (new)", "apps/api/tests/test_fidelity.py (new)"],
      goal="render → apply on a sandbox → re-read combined arch → compare structure (containers, field order, buttons) with what the preview showed; used by App Studio, View Designer, Wireframe and Report proof.",
      steps=["Structure diff over the view map, not pixels", "One report shape: matched, moved, missing, extra. " + LIVE],
      acs=["AC1: identical structures → zero diff", "AC2: a moved field is reported as moved with both paths", "AC3: live run on 17-19 for one design per consumer"],
      test=API_TEST.format(f="tests/test_fidelity.py"),
      elite="Pure diff over two ViewMaps; the RPC part is the existing combined_arch read.",
      oracles=["EL-X-FIDELITY-1 same arch → empty diff", "EL-X-FIDELITY-2 field moved between pages → one 'moved' row"]),
    c(id="EL-X-EDGE-RECORDS", pri="P2", title="Edge-case records for any preview", ledger="ELR-FID", deps="EL-X-BAR", b="S", tier="L2", score="4 (C1 U1 F1 K1 V0 I0)",
      ctx=["packages/odoo-client/src/odoo_client/schema_graph.py (`search_read` with ROW_CAP)"],
      allow=["apps/api/app/edge_records.py (new)", "apps/api/app/routers/views.py (one read-only endpoint)", "apps/api/tests/test_edge_records.py (new)"],
      goal="For a model: ids of the record with the longest name, the most empty fields, the most lines, an archived one, another currency, a right-to-left partner language, each when it exists.",
      steps=["Read-only, capped queries; return ids and reasons only", "Missing case → reason 'none in this database', never a fake record (INV-15)"],
      acs=["AC1: returns only ids + reasons (property)", "AC2: no write RPC on any path (test)"],
      test=API_TEST.format(f="tests/test_edge_records.py")),
    c(id="EL-X-IMPACT-GATE", pri="P1", title="Show everything that breaks before a delete, rename or type change", ledger="ELR-REL", deps="EL-X-BAR", b="M", tier="L3", score="6 (C2 U1 F1 K1 V1 I0)",
      ctx=["packages/odoo-client/src/odoo_client/schema_graph.py L83 (`find_usages`)", "apps/api/app/routers/builder.py (field delete/rename)", "apps/web/src/components/ConfirmDialog.tsx"],
      allow=["apps/api/app/impact_gate.py (new)", "apps/api/app/routers/builder.py (call the gate before destructive ops)", "apps/api/tests/test_impact_gate.py (new)",
             "apps/web/src/components/ConfirmDialog.tsx (impact list slot)"],
      goal="Before a destructive schema op, list views, automations, reports, server actions, Bridge mappings and saved scripts that use the field; block until the owner confirms with the list on screen.",
      steps=["Odoo-side usages from `find_usages`; Ingenium-side usages from the App DB (mappings, scripts)", "API requires the existing advanced confirmation flag plus the impact hash the owner saw"],
      acs=["AC1: delete without the matching impact hash → refused", "AC2: list shows Odoo and Ingenium usages", "AC3: copy passes the jargon guard"],
      test=API_TEST.format(f="tests/test_impact_gate.py"), ui=True,
      elite="Confirmation binds to the exact impact list (hash) so a stale screen cannot authorise a bigger change.",
      oracles=["EL-X-IMPACT-1 stale impact hash → refused", "EL-X-IMPACT-2 field used by a Bridge mapping → listed"]),
]

# ---- Phase 7: one bar card per feature ----
BAR = [
    ("HOME", "Home and Command center", "3.1", ["apps/web/src/components/overview/", "apps/web/src/app/command/", "apps/api/app/routers/command_center.py"]),
    ("CONN", "Connect", "3.2", ["apps/web/src/components/connect/", "apps/web/src/app/connect/", "apps/api/app/routers/connections.py"]),
    ("VD", "View Designer", "3.4", ["apps/web/src/components/view-designer/", "apps/web/src/components/designer/", "apps/api/app/routers/view_engine*.py"]),
    ("RPT", "Report and email designer", "3.5", ["apps/web/src/components/report-designer/", "apps/api/app/routers/view_engine_reports2.py"]),
    ("WEB", "Website builder", "3.6", ["apps/web/src/components/website/", "apps/web/src/app/connections/[id]/website/", "apps/api/app/routers/website.py"]),
    ("SUITE", "Configuration Suite", "3.7", ["apps/web/src/components/suite/", "apps/web/src/app/connections/[id]/suite/", "apps/api/app/routers/suite*.py"]),
    ("IMP", "Imports (Bring data in)", "3.8", ["apps/web/src/components/import/", "apps/web/src/components/ingest/", "apps/api/app/routers/data_import.py", "apps/api/app/routers/ingest.py"]),
    ("BR", "Bridge", "3.9", ["apps/web/src/components/bridge/", "apps/web/src/app/bridge/", "apps/api/app/routers/bridge.py"]),
    ("CR", "Code Runner", "3.10", ["apps/web/src/components/code-runner/", "apps/web/src/app/connections/[id]/code-runner/", "apps/api/app/routers/code_runner.py"]),
    ("BOT", "Bots and Expert", "3.11", ["apps/web/src/components/expert/", "apps/web/src/components/suite/BotAvatar.tsx", "apps/api/app/routers/expert.py"]),
    ("LDC", "Live Demo Co-Pilot", "3.12", ["apps/web/src/components/live-demo-copilot/", "apps/web/src/app/live-demo-copilot/", "apps/api/app/routers/live_demo_copilot.py"]),
    ("WF", "Wireframe", "3.13", ["apps/web/src/components/wireframe/", "apps/web/src/app/connections/[id]/wireframe/", "apps/api/app/routers/wireframe.py"]),
    ("APR", "Approvals", "3.14", ["apps/web/src/components/approvals/", "apps/web/src/app/approvals/", "apps/api/app/routers/approvals.py", "apps/api/app/routers/inbox.py"]),
    ("HIST", "History", "3.15", ["apps/web/src/components/history/", "apps/web/src/components/journal/", "apps/api/app/routers/history.py", "apps/api/app/routers/snapshots.py"]),
    ("CMDK", "Cmd-K (Find anything)", "3.16", ["apps/web/src/components/command/", "apps/web/src/components/shell/"]),
    ("BUILD", "Models, menus, access, automations, numbering", "3.18", ["apps/web/src/components/builder/", "apps/web/src/components/menus/", "apps/web/src/components/access/",
                                                                     "apps/web/src/components/automations/", "apps/web/src/components/id-generator/", "apps/api/app/routers/builder.py",
                                                                     "apps/api/app/routers/menus_builder.py", "apps/api/app/routers/access.py", "apps/api/app/routers/automations.py"]),
    ("JOB", "Job Autopilot", "3.18", ["apps/web/src/components/job-autopilot/", "apps/web/src/app/connections/[id]/job/", "apps/api/app/routers/job_autopilot.py"]),
    ("SET", "Settings, team, billing, admin", "3.18", ["apps/web/src/components/settings/", "apps/web/src/components/billing/", "apps/web/src/app/settings/", "apps/web/src/app/admin/",
                                                      "apps/api/app/routers/billing.py", "apps/api/app/routers/accounts.py", "apps/api/app/routers/admin.py"]),
    ("CLIENT", "Client portal", "3.18", ["apps/web/src/app/connections/[id]/client/", "apps/api/app/routers/workspaces.py"]),
]
for code, name, sec, files in BAR:
    CARDS.append(c(
        id=f"EL-BAR-{code}", title=f"{name}: pass the Feature Excellence Bar", ledger="ELR-BAR",
        deps="EL-X-BAR, EL-X-AUTHZ, EL-X-WRITE-AUDIT, EL-X-ERRORS", b="L", tier="L2", score="5 (C1 U1 F1 K1 V1 I0)",
        ctx=[f"handover §{sec} (this feature)", "docs/build-plan/elevate/00_ELEVATE.md §1", f"`python3 scripts/excellence_scorecard.py --feature {code.lower()}` output"],
        allow=[f + " (and co-located tests)" for f in files] + ["the EL-X baseline files (remove this feature's entries only)"],
        goal=f"Every §1 check is green for {name} on every route and endpoint it owns.",
        steps=["Run the scorecard; paste the red rows into the Worker packet", "Fix one red row at a time inside the allow-list; re-run the scorecard after each",
               "A fix that needs a guarded path (INV-14) or another feature's files stops and becomes a new card", "UI checkpoints: baseline, after, final"],
        acs=[f"AC1: scorecard for `{code.lower()}` exits 0", f"AC2: this feature's entries are gone from every EL-X baseline file",
             "AC3: keyboard-only walkthrough of the main task passes (Playwright)", "AC4: Tope rates each screen ≥ 8 at the final checkpoint"],
        test=f"python3 scripts/excellence_scorecard.py --feature {code.lower()}", ui=True))

# ---- Phase 7: next-level features ----
NEXT = [
    dict(id="EL-HOME-SINCE", title="Since you were last here", deps="EL-BAR-HOME", b="M", tier="L2", score="5 (C1 U1 F1 K1 V1 I0)",
         ctx=["handover §3.1", "apps/api/app/routers/command_center.py", "apps/api/app/schema_freshness.py"],
         allow=["apps/api/app/since_last_visit.py (new)", "apps/api/app/routers/command_center.py", "apps/api/tests/test_since_last_visit.py (new)", "apps/web/src/components/overview/SinceLastVisit.tsx (new)"],
         goal="Per database, what changed since this person's last visit: apps added/removed, failed scheduled jobs, drift, Bridge dead letters, expiring keys; each row has one action.",
         steps=["Diff stored snapshots by code; no LLM numbers (INV-15)", "Empty → 'Nothing changed since <time>' state"],
         acs=["AC1: every row links to the tool that resolves it", "AC2: counts match the App DB in a fixture test"], test=API_TEST.format(f="tests/test_since_last_visit.py"), ui=True),
    dict(id="EL-HOME-HEALTHX", title="A health score you can act on", deps="EL-BAR-HOME", b="S", tier="L2", score="4 (C1 U1 F1 K1 V0 I0)",
         ctx=["handover §3.1 (A27)", "apps/web/src/components/overview/"],
         allow=["apps/api/app/health_explain.py (new)", "apps/api/tests/test_health_explain.py (new)", "apps/web/src/components/overview/HealthExplain.tsx (new)"],
         goal="Each point lost names the cause and links to the fix; a 30-day trend from stored daily scores.",
         steps=["Score components sum exactly to the shown score (test)"], acs=["AC1: components sum to the score", "AC2: every component has a fix link"],
         test=API_TEST.format(f="tests/test_health_explain.py"), ui=True),
    dict(id="EL-CONN-LEASTPRIV", title="Rights advisor: connect with the least access Ingenium needs", deps="EL-BAR-CONN", b="M", tier="L3", score="6 (C1 U1 F2 K1 V1 I0)",
         ctx=["handover §3.2", "apps/api/app/routers/connections.py (`/live-check`)"],
         allow=["apps/api/app/rights_advisor.py (new)", "apps/api/tests/test_rights_advisor.py (new)", "apps/web/src/components/connect/RightsAdvisor.tsx (new)"],
         goal="Read the connected user's groups; say which Ingenium features each group enables; recommend a dedicated integration user with only the needed groups, with a step-by-step guide. Never changes users itself.",
         steps=["Read-only `res.users` / `res.groups` for the connected user [Inferred field names per major, verify]", "Guide opens Odoo's own user screen; Ingenium never mints keys or edits users"],
         acs=["AC1: no write RPC on any path", "AC2: admin user → 'more access than needed' with the exact list", "AC3: copy passes jargon guard"],
         test=API_TEST.format(f="tests/test_rights_advisor.py"), ui=True,
         elite="Advice only. Group-to-feature map lives in one table with a test per feature.",
         oracles=["EL-CONN-LEASTPRIV-1 admin user → over-privileged verdict", "EL-CONN-LEASTPRIV-2 any path → zero write calls"]),
    dict(id="EL-CONN-DOCTOR", title="Connection doctor in the background", deps="EL-BAR-CONN, AS-GROUND-WIRE", b="M", tier="L2", score="5 (C1 U1 F1 K1 V1 I0)",
         ctx=["apps/api/app/schema_freshness.py", "apps/api/app/routers/health_check.py"],
         allow=["apps/api/app/connection_doctor.py (new)", "apps/api/tests/test_connection_doctor.py (new)"],
         goal="Scheduled read-only check per connection: Odoo version change, apps added/removed, key expiry; refreshes the schema catalog and raises a 'Needs you' item.",
         steps=["Runs on the existing queue (RQ/arq)", "Version change triggers the existing upgrade check"],
         acs=["AC1: a changed module list invalidates the schema catalog", "AC2: version change creates one 'Needs you' item"], test=API_TEST.format(f="tests/test_connection_doctor.py")),
    dict(id="EL-VD-WHO-ELSE", title="Who else touches this spot", deps="EL-BAR-VD, AS-GROUND-VIEWMAP", b="M", tier="L2", score="5 (C1 U1 F1 K1 V1 I0)",
         ctx=["handover §3.4", "apps/api/app/view_map.py (AS-GROUND-VIEWMAP)"],
         allow=["apps/api/app/view_conflicts.py (new)", "apps/api/tests/test_view_conflicts.py (new)", "apps/web/src/components/view-designer/WhoElsePanel.tsx (new)"],
         goal="For a selected element: every module view that inherits at that anchor, with module and priority; warn before an edit that would collide.",
         steps=["Ownership from the view map", "Warning names the other module in plain words"], acs=["AC1: fixture with two inheriting modules lists both", "AC2: colliding edit shows a warning before publish"],
         test=API_TEST.format(f="tests/test_view_conflicts.py"), ui=True),
    dict(id="EL-VD-EDGE", title="Preview the screen with edge-case records", deps="EL-BAR-VD, EL-X-EDGE-RECORDS", b="S", tier="L2", score="4 (C1 U1 F1 K1 V0 I0)",
         ctx=["apps/web/src/components/odoo-preview/"], allow=["apps/web/src/components/view-designer/EdgeRecordPicker.tsx (new)", "apps/web/src/components/view-designer/EdgeRecordPicker.test.tsx (new)"],
         goal="A picker to preview with the longest-name, emptiest, most-lines or archived record, with layout warnings.",
         steps=["Uses EL-X-EDGE-RECORDS ids", "'None in this database' shown honestly"], acs=["AC1: each case switches the preview record", "AC2: missing case shows the honest state"],
         test=WEB_TEST.format(f="src/components/view-designer/EdgeRecordPicker.test.tsx"), ui=True),
    dict(id="EL-VD-GROUNDED-AI", title="Edit with AI places by labels and verifies", deps="EL-BAR-VD, AS-GROUND-PLACE", b="M", tier="L3", score="6 (C2 U1 F1 K1 V1 I0)",
         ctx=["apps/api/app/view_engine_ai.py", "apps/api/app/ai_conversation/ground_place.py (AS-GROUND-PLACE)"],
         allow=["apps/api/app/view_engine_ai.py", "apps/api/tests/test_view_engine_ai_grounded.py (new)"],
         goal="View Designer AI edits resolve placement through ground_place and are re-read after publish, same as App Studio.",
         steps=["AI proposes typed ops with the owner phrase; code places them", "Post-publish fidelity check (EL-X-FIDELITY)"],
         acs=["AC1: 'put X after Payment Terms' → xpath on `payment_term_id`", "AC2: misplaced node rolled back with a plain reason"],
         test=API_TEST.format(f="tests/test_view_engine_ai_grounded.py"),
         elite="Shares AS-GROUND-PLACE; no second placement engine.", oracles=["app-studio/ORACLES.md G-06, G-11 run against view_engine_ai"]),
    dict(id="EL-RPT-EDGE", title="Report proof against worst-case records", deps="EL-BAR-RPT, EL-X-EDGE-RECORDS", b="S", tier="L2", score="4 (C1 U1 F1 K1 V0 I0)",
         ctx=["handover §3.5", "apps/api/app/view_engine_pdf.py"], allow=["apps/web/src/components/report-designer/ProofCases.tsx (new)", "apps/web/src/components/report-designer/ProofCases.test.tsx (new)"],
         goal="One click proofs the report on the record with most lines, longest names, another currency and another language; page checks run on each.",
         steps=["Reuse the existing proof + page checks"], acs=["AC1: each case renders a proof or the honest 'none' state"], test=WEB_TEST.format(f="src/components/report-designer/ProofCases.test.tsx"), ui=True),
    dict(id="EL-RPT-DELIVER", title="Email deliverability check", deps="EL-BAR-RPT", b="M", tier="L2", score="5 (C1 U1 F1 K1 V1 I0)",
         ctx=["handover §3.5 (Send me a test)"], allow=["apps/api/app/mail_deliverability.py (new)", "apps/api/tests/test_mail_deliverability.py (new)", "apps/web/src/components/report-designer/DeliverabilityCard.tsx (new)"],
         goal="Before 'Send me a test': SPF, DKIM and DMARC of the sending domain (DNS read), broken links, image weight, a plain verdict with fixes.",
         steps=["DNS lookups only (no mail sent by this check)", "Use `dnspython` (ISC) if not present"], acs=["AC1: fixture domains give pass/warn/fail correctly", "AC2: no outbound mail on any path"],
         test=API_TEST.format(f="tests/test_mail_deliverability.py"), ui=True),
    dict(id="EL-SUITE-BASELINE", title="Approved configuration baseline and drift", deps="EL-BAR-SUITE", b="L", tier="L3", score="6 (C2 U1 F1 K1 V1 I0)",
         ctx=["handover §3.7 (ideas 25, 39)", "apps/api/app/suite_insights.py", "apps/api/app/suite_change.py"],
         allow=["apps/api/app/suite_baseline.py (new)", "apps/api/tests/test_suite_baseline.py (new)", "apps/web/src/components/suite/BaselinePanel.tsx (new)"],
         goal="Save 'how this database should be set up' (settings, taxes, journals, sequences, access); show changes made directly in Odoo since; restore any of them through a Change batch with Check and Undo.",
         steps=["Snapshot via existing config_as_code readers", "Restore = a Change batch through the write gate; money items under the money guard"],
         acs=["AC1: a settings change made in Odoo appears as drift", "AC2: restore runs Check first and records Undo", "AC3: money items require the money guard"],
         test=API_TEST.format(f="tests/test_suite_baseline.py"), ui=True,
         elite="Extends suite idea 25 and Home drift; restore never bypasses Check/Run/Review.",
         oracles=["EL-SUITE-BASELINE-1 drift detected after direct change", "EL-SUITE-BASELINE-2 restore of a tax item without money guard → refused"]),
    dict(id="EL-IMP-RECONCILE", title="Import control totals", deps="EL-BAR-IMP", b="M", tier="L3", score="6 (C1 U1 F2 K1 V1 I0)",
         ctx=["handover §3.8", "apps/api/app/suite_import.py"], allow=["apps/api/app/import_reconcile.py (new)", "apps/api/tests/test_import_reconcile.py (new)"],
         goal="After import: counts and sums by key columns in the file versus what Odoo now holds (by Ingenium external ids), in the import report.",
         steps=["Read-only after-read by `__ingenium_import__` ids", "Mismatch → plain list of rows with the difference"],
         acs=["AC1: matching import → all totals equal", "AC2: one dropped row → named in the report"], test=API_TEST.format(f="tests/test_import_reconcile.py"),
         elite="Money columns compare with Decimal; currency per row.", oracles=["EL-IMP-RECONCILE-1 one missing row → reported with its key"]),
    dict(id="EL-BR-REPLAY", title="Replay last week before rolling out a flow", deps="EL-BAR-BR", b="L", tier="L3", score="7 (C2 U1 F2 K1 V1 I0)",
         ctx=["handover §3.9", "apps/api/app/bridge/flows.py", "apps/api/app/bridge/reliability.py (sandbox run)", "apps/api/app/bridge/delivery.py"],
         allow=["apps/api/app/bridge/replay.py (new)", "apps/api/tests/test_bridge_replay.py (new)", "apps/web/src/components/bridge/ReplayDiff.tsx (new)"],
         goal="Run a proposed flow version against the last N recorded events in sandbox mode and show per-event differences against the current version before any rollout step.",
         steps=["Events from `integration_events`, PII-masked (existing scrub)", "Sandbox mode only; no outbound calls, no Odoo writes"],
         acs=["AC1: identical versions → zero differences", "AC2: changed mapping → per-event field diff", "AC3: zero outbound HTTP on any path (test)"],
         test=API_TEST.format(f="tests/test_bridge_replay.py"), ui=True,
         elite="Replay is read-only by construction: the executor is the sandbox runner, never delivery.", oracles=["EL-BR-REPLAY-1 any path → no outbound HTTP"]),
    dict(id="EL-BR-EGRESS", title="Each flow may call only its declared hosts", deps="EL-BAR-BR", b="M", tier="L3", score="7 (C1 U1 F2 K1 V1 I1)",
         ctx=["apps/api/app/bridge/spec_import.py (private-host refusal)", "apps/api/app/bridge/delivery.py"],
         allow=["apps/api/app/bridge/egress.py (new)", "apps/api/app/bridge/delivery.py (one check before send)", "apps/api/tests/test_bridge_egress.py (new)"],
         goal="Outbound requests are checked against the flow's declared host list after DNS resolution; private, loopback and metadata addresses are always refused.",
         steps=["Resolve then check IPs (DNS rebinding)", "Refusal is a dead letter with a plain reason"],
         acs=["AC1: undeclared host refused", "AC2: host resolving to 169.254.169.254 refused", "AC3: declared host passes"], test=API_TEST.format(f="tests/test_bridge_egress.py"),
         elite="SSRF guard at send time, not only at import time.", oracles=["EL-BR-EGRESS-1 metadata IP → refused", "EL-BR-EGRESS-2 rebinding to private IP → refused"]),
    dict(id="EL-CR-LIMITS", title="Hard limits on the script process", deps="EL-BAR-CR", b="M", tier="L3", score="8 (C2 U1 F2 K1 V1 I1)",
         ctx=["handover §3.10", "apps/api/app/code_runner/child.py (own process, import allow-list)"],
         allow=["apps/api/app/code_runner/child.py", "apps/api/tests/test_code_runner_limits.py (new)", "apps/api/tests/code_runner_escapes/ (new corpus)"],
         goal="CPU time, memory and wall-clock limits on the child; no network except the Odoo connection; escape corpus (import tricks, `__builtins__`, introspection) all refused.",
         steps=["`resource` limits set before user code; wall clock enforced by the parent", "Limit hit → plain message with the limit name"],
         acs=["AC1: infinite loop stops at the CPU limit", "AC2: memory bomb stops at the memory limit", "AC3: every escape in the corpus is refused"],
         test=API_TEST.format(f="tests/test_code_runner_limits.py"), elite="macOS and Linux differ on RLIMIT_AS; test both behaviours and document the one that applies.",
         oracles=["EL-CR-LIMITS-1 `while True: pass` → stopped", "EL-CR-LIMITS-2 escape corpus → 0 successes"]),
    dict(id="EL-CR-EXPLAIN", title="What this run did, in plain words", deps="EL-BAR-CR", b="S", tier="L2", score="4 (C1 U1 F1 K1 V0 I0)",
         ctx=["apps/api/app/code_runner/runs.py"], allow=["apps/api/app/code_runner/explain.py (new)", "apps/api/tests/test_code_runner_explain.py (new)"],
         goal="From the observed changes: records touched per model, fields changed, money amounts moved, as a short summary computed by code.",
         steps=["No LLM; template sentences"], acs=["AC1: summary counts equal the observed diff"], test=API_TEST.format(f="tests/test_code_runner_explain.py"), ui=True),
    dict(id="EL-BOT-EVAL", title="Every bot has a check suite and shows its score", deps="EL-BAR-BOT", b="M", tier="L2", score="5 (C1 U1 F1 K1 V1 I0)",
         ctx=["handover §3.11", "apps/api/app/bots/grant.py"], allow=["apps/api/evals/bots/ (new golden tasks)", "apps/api/tests/test_bot_evals.py (new)"],
         goal="Golden tasks plus grant-violation attempts per bot, run with a fake provider in CI and live on demand; the bots page shows 'passes n of m checks'.",
         steps=["Grant violations must be refused by code, not by the model"], acs=["AC1: every grant violation refused", "AC2: score shown equals the last run"], test=API_TEST.format(f="tests/test_bot_evals.py"), ui=True),
    dict(id="EL-BOT-HANDOFF", title="When a bot can't, it opens a ready draft in the right tool", deps="EL-BAR-BOT", b="M", tier="L2", score="5 (C1 U1 F1 K1 V1 I0)",
         ctx=["apps/api/app/bots/grant.py", "apps/web/src/components/expert/"], allow=["apps/api/app/bots/handoff.py (new)", "apps/api/tests/test_bot_handoff.py (new)"],
         goal="Out-of-grant asks produce a draft (App Studio brief, Suite plan, Bridge flow) with the owner's words and context, opened for review; nothing runs.",
         steps=["Draft text is the owner's words, quoted"], acs=["AC1: out-of-grant ask → draft link, zero writes"], test=API_TEST.format(f="tests/test_bot_handoff.py"), ui=True),
    dict(id="EL-LDC-REPLAY", title="Meeting replay bench", deps="EL-BAR-LDC", b="M", tier="L2", score="5 (C1 U1 F1 K1 V1 I0)",
         ctx=["handover §3.12", "apps/api/app/live_demo_copilot/pipeline.py", "stage1_filter.py, stage2_answer.py"],
         allow=["apps/api/evals/ldc_replay/ (new; synthetic transcripts with timing, no real people)", "apps/api/tests/test_ldc_replay.py (new)"],
         goal="Feed timed transcripts through the full pipeline offline; score question detection, label accuracy and answer latency without a live meeting.",
         steps=["Client-side vs presenter speakers marked in fixtures", "Fake provider in CI; live provider only under the call budget"],
         acs=["AC1: report prints precision, recall, label accuracy, p95 latency", "AC2: presenter questions never answered (property)"], test=API_TEST.format(f="tests/test_ldc_replay.py")),
    dict(id="EL-LDC-SHOWME", title="'Show me' link on every whispered answer", deps="EL-BAR-LDC", b="S", tier="L2", score="4 (C1 U1 F1 K1 V0 I0)",
         ctx=["apps/api/app/live_demo_copilot/db_grounding.py"], allow=["apps/api/app/live_demo_copilot/show_me.py (new)", "apps/api/tests/test_ldc_show_me.py (new)"],
         goal="An 'In your demo' answer carries a deep link to the exact menu/action in the demo database; other labels carry none.",
         steps=["Link built from installed menus/actions only"], acs=["AC1: only 'In your demo' answers get a link", "AC2: link targets exist in the demo DB"], test=API_TEST.format(f="tests/test_ldc_show_me.py"), ui=True),
    dict(id="EL-WF-ROUNDTRIP", title="Sketch versus built screen", deps="EL-BAR-WF, EL-X-FIDELITY", b="M", tier="L2", score="5 (C1 U1 F1 K1 V1 I0)",
         ctx=["handover §3.13", "apps/api/app/wireframe/review.py", "apps/web/src/components/wireframe/StockMapPanel.tsx"],
         allow=["apps/api/app/wireframe/roundtrip.py (new)", "apps/api/tests/test_wireframe_roundtrip.py (new)", "apps/web/src/components/wireframe/RoundtripOverlay.tsx (new)"],
         goal="After install, re-read the built screen and lay it over the sketch: each region matched, moved or missing.",
         steps=["Uses EL-X-FIDELITY diff"], acs=["AC1: every sketch region has a status"], test=API_TEST.format(f="tests/test_wireframe_roundtrip.py"), ui=True),
    dict(id="EL-APR-RISK", title="Risk-ranked approvals inbox", deps="EL-BAR-APR", b="M", tier="L2", score="5 (C1 U1 F1 K1 V1 I0)",
         ctx=["handover §3.14", "apps/api/app/approval_service.py"], allow=["apps/api/app/approval_risk.py (new)", "apps/api/tests/test_approval_risk.py (new)"],
         goal="Each item scored by code: records affected, money involved, can it be undone, how long it has waited; inbox sorts by it and shows why.",
         steps=["Score components shown, not just the number"], acs=["AC1: irreversible money change ranks above a reversible label change"], test=API_TEST.format(f="tests/test_approval_risk.py"), ui=True),
    dict(id="EL-HIST-WHY", title="Why does this look like this?", deps="EL-BAR-HIST, AS-GROUND-VIEWMAP", b="M", tier="L2", score="5 (C1 U1 F1 K1 V1 I0)",
         ctx=["handover §3.15", "apps/api/app/audit_chain.py", "apps/api/app/view_map.py"],
         allow=["apps/api/app/history_why.py (new)", "apps/api/tests/test_history_why.py (new)", "apps/web/src/components/history/WhyPopover.tsx (new)"],
         goal="Click an element in any Odoo preview: which change, tool, person and time put it there (or 'stock Odoo, module X'), with Undo.",
         steps=["Join view-map ownership with History receipts"], acs=["AC1: Ingenium-added field → its receipt", "AC2: stock field → owning module"], test=API_TEST.format(f="tests/test_history_why.py"), ui=True),
    dict(id="EL-CMDK-FRECENCY", title="Cmd-K learns what you use", deps="EL-BAR-CMDK", b="S", tier="L1", score="2 (C1 U0 F0 K1 V0 I0)",
         ctx=["apps/web/src/components/command/"], allow=["apps/web/src/lib/frecency.ts (new)", "apps/web/src/lib/frecency.test.ts (new)"],
         goal="Rank results by frequency and recency per person and database, stored locally.", steps=["Decay with a named half-life constant"],
         acs=["AC1: recent frequent item ranks first (test)"], test=WEB_TEST.format(f="src/lib/frecency.test.ts")),
    dict(id="EL-AUTO-BACKTEST", title="Automation backtest before going live", deps="EL-BAR-BUILD", b="M", tier="L3", score="6 (C2 U1 F1 K1 V1 I0)",
         ctx=["handover §3.18 (Automations)", "apps/api/app/routers/automations.py"], allow=["apps/api/app/automation_backtest.py (new)", "apps/api/tests/test_automation_backtest.py (new)"],
         goal="For a draft automation: 'would have fired n times in the last 30 days on these records', read-only, using the trigger domain and dates.",
         steps=["Read-only search with the trigger domain; time triggers evaluated over the window", "Python-backed triggers: say 'can't predict code' honestly"],
         acs=["AC1: fixture with 3 matching records → 3", "AC2: zero writes on any path"], test=API_TEST.format(f="tests/test_automation_backtest.py"), ui=True,
         elite="Domain evaluation goes through Odoo search, never a local re-implementation.", oracles=["EL-AUTO-BACKTEST-1 any path → zero writes"]),
    dict(id="EL-JOB-GOLIVE", title="Go-live readiness check", deps="EL-BAR-JOB", b="M", tier="L2", score="5 (C1 U1 F1 K1 V1 I0)",
         ctx=["handover §3.18 (Job Autopilot)", "apps/api/app/routers/production_readiness.py"], allow=["apps/api/app/golive_readiness.py (new)", "apps/api/tests/test_golive_readiness.py (new)"],
         goal="One checklist computed from the database: users invited, access tested, numbering set, outgoing mail working, opening balances, backups; signed readiness report.",
         steps=["Extend the existing production_readiness checks; no duplicate logic"], acs=["AC1: each item has pass/fail with the evidence", "AC2: report hash recorded in History"], test=API_TEST.format(f="tests/test_golive_readiness.py"), ui=True),
    dict(id="EL-SET-SIGNIN", title="Sign-in hardening: two-step codes, sessions, single sign-on", deps="EL-BAR-SET", b="L", tier="L3", score="8 (C2 U1 F2 K1 V1 I1)",
         ctx=["handover §2.8, §3.14 (named approvers need sign-in)", "apps/api/app/auth.py", "apps/api/app/oauth_service.py"],
         allow=["apps/api/app/auth_totp.py (new)", "apps/api/app/auth.py", "apps/api/tests/test_auth_totp.py (new)", "apps/web/src/app/settings/security/ (new)"],
         goal="TOTP two-step codes (pyotp, MIT) with recovery codes; list and revoke sessions; optional OIDC single sign-on (Authlib, BSD); unlocks named approvers.",
         steps=["Secrets encrypted at rest with the existing key", "Recovery codes hashed; shown once"],
         acs=["AC1: wrong code refused, rate-limited", "AC2: revoked session can't call the API", "AC3: no secret in logs (scrub test)"], test=API_TEST.format(f="tests/test_auth_totp.py"), ui=True,
         elite="Guarded path (auth): L3 Worker and a separate L3 Reviewer (INV-14). Never roll custom crypto.", oracles=["EL-SET-SIGNIN-1 replayed code refused", "EL-SET-SIGNIN-2 revoked session → 401"]),
]
for n in NEXT:
    CARDS.append(c(ledger="ELR-NEXT", **n))

# Stage 2 reconcile (21 Oct): these duplicated existing handover cards; their extra checks moved there
# (build_cards.py EXTRA_ACS). Never re-create them.
MERGED = {"EL-X-TENANT": "SEC-TENANCY", "EL-X-INJECT": "SEC-REDTEAM-EXT", "EL-X-WRITE-AUDIT": "REL-STATIC-WRITE",
          "EL-X-OBS": "OBS-HEALTH", "EL-CR-LIMITS": "V-SEC-CR-SANDBOX"}
CARDS = [x for x in CARDS if x["id"] not in MERGED]
for x in CARDS:
    for old, new in MERGED.items():
        x["deps"] = x["deps"].replace(old, new)


def render(card: dict) -> str:
    is_as = card["id"].startswith("AS-")
    lines = [f"# {card['id']}: {card['title']}", "", f"ID: {card['id']}", f"Title: {card['title']}", "Status: todo",
             f"Phase: {card['phase']}", f"Priority: {card['pri']}", "Type: build", CHARTER.format(b=card["b"]),
             f"Ledger IDs: {card['ledger']}", f"Depends on: {card['deps']}",
             f"Routing: Worker: {card['tier']} (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: {card['tier']} separate session · Score: {card['score']}",
             "Context pack:"] + [f"- {x}" for x in card["ctx"]] + ["File allow-list:"] + [f"- {x}" for x in card["allow"]]
    lines += [f"Goal: {card['goal']}", "Steps:"] + [f"{i}. {s}" for i, s in enumerate(card["steps"], 1)]
    if card["ui"]:
        lines.append(f"{len(card['steps']) + 1}. {UI_BAR}")
    lines += ["Acceptance criteria:"]
    for i, a in enumerate(card["acs"], 1):
        lines.append(f"- {a}" if a.startswith("AC") else f"- AC{i}: {a}")
    lines += ["Test plan:", f"- `{card['test']}`"]
    if card["elite"]:
        lines.append(f"Elite design notes: {card['elite']}")
    if card["oracles"]:
        where = "docs/build-plan/app-studio/ORACLES.md" if is_as else "docs/build-plan/elevate/ORACLES.md"
        lines.append(f"Oracle tests: {where}: " + "; ".join(card["oracles"]))
    lines += [GATE, EVIDENCE, ROLLBACK_AS if is_as else ROLLBACK_EL, DOD, ""]
    return "\n".join(lines)


LEDGER_ROWS = [
    ("AS-GROUND", "Tope 21 Oct; Pack §6.7", "v3 builds against the connected DB: one packet per run for every stage, view map, placement by meaning verified by re-read, reuse of what exists, data-shape facts", "build", "P1", "Partial", "AS-GROUND-WIRE;AS-GROUND-VIEWMAP;AS-GROUND-PLACE;AS-GROUND-EXISTS;AS-GROUND-DATA", ""),
    ("AS-DRAFT-V3", "Tope 21 Oct; DEC-043", "Draft Studio drops domain packs and runs the App Studio v3 pipeline once v3 passes its release bars; pack code retired after", "build", "P1", "Missing", "AS-DRAFT-ADOPT;AS-PACK-RETIRE", "DEC-043"),
    ("AS-UPGRADE-ALL", "Tope 21 Oct; DEC-044", "every matching upgrade is offered (top 3 inline, rest under More suggestions); none dropped by a count", "build", "P1", "Missing", "AS-UPGRADES", "DEC-044"),
    ("ELR-BAR", "Tope 21 Oct; elevate/00_ELEVATE.md §1", "every feature passes the measured Feature Excellence Bar (UI, UX, security, reliability, fidelity, usability, performance)", "build", "P1", "Missing", "", "DEC-045"),
    ("ELR-SEC", "Tope 21 Oct; elevate §2", "route authz, tenant isolation, write-gate coverage and LLM injection proofs across the whole app", "test", "P1", "Missing", "EL-X-AUTHZ;EL-X-TENANT;EL-X-WRITE-AUDIT;EL-X-INJECT", "DEC-045"),
    ("ELR-REL", "Tope 21 Oct; elevate §2", "one error shape, resilience (retry/autosave/offline), observability with SLOs, impact gate before destructive schema changes", "build", "P1", "Missing", "EL-X-ERRORS;EL-X-RESILIENT;EL-X-OBS;EL-X-IMPACT-GATE", "DEC-045"),
    ("ELR-FID", "Tope 21 Oct; elevate §2", "shared Odoo fidelity harness and edge-case records for every preview", "build", "P1", "Missing", "EL-X-FIDELITY;EL-X-EDGE-RECORDS", "DEC-045"),
    ("ELR-NEXT", "Tope 21 Oct; elevate §3", "next-level features per feature beyond spec (proposals approved in principle; Tope may strike any)", "build", "P2", "Missing", "", "DEC-045"),
]


def main() -> int:
    rows = list(csv.DictReader(LEDGER.open()))
    fields = list(rows[0].keys())
    ids = {r["ID"] for r in rows}
    bar_ids = ";".join(x["id"] for x in CARDS if x["id"].startswith("EL-BAR-")) + ";EL-X-BAR"
    next_ids = ";".join(x["id"] for x in CARDS if x["ledger"] == "ELR-NEXT")
    added = 0
    for rid, src, line, typ, pri, st, cards, dec in LEDGER_ROWS:
        if rid in ids:
            continue
        cards = cards or (bar_ids if rid == "ELR-BAR" else next_ids)
        rows.append(dict(zip(fields, [rid, src, line, typ, pri, st, cards, dec])))
        added += 1
    with LEDGER.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    pm = json.loads(PHASE_MAP.read_text())
    pm.setdefault("EL-", 7)
    PHASE_MAP.write_text(json.dumps(pm, indent=2) + "\n")

    written = 0
    for card in CARDS:
        out = PLAN / "cards" / f"phase-{card['phase']}" / f"{card['id']}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            continue
        out.write_text(render(card))
        written += 1

    lines = ["# Elevate oracle tests (locked; generated by tools/amend_g1c.py from the card definitions)", "",
             "Tester writes each row as a test before the Worker starts; the Worker may not edit them.", "",
             "| Card | Oracle |", "|---|---|"]
    for card in CARDS:
        if card["id"].startswith("EL-"):
            for o in card["oracles"]:
                lines.append(f"| {card['id']} | {o} |")
    EL_ORACLES.write_text("\n".join(lines) + "\n")
    print(f"ledger +{added} rows ({len(rows)} total); cards written {written}/{len(CARDS)}; phase_map EL- -> 7")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
