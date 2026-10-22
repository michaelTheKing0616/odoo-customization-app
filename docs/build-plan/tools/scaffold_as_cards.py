#!/usr/bin/env python3
"""One-shot scaffold (21 Oct) for the App Studio Pack cards.

Side effects: writes docs/build-plan/cards/phase-3/AS-*.md. It refuses to overwrite a card whose
Status is no longer 'todo'. After the first run the card files are the source of truth; edit them,
not this script.
"""
from __future__ import annotations

import re
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "cards" / "phase-3"
PACK = "docs/build-plan/app-studio/00_PACK.md"
ORA = "docs/build-plan/app-studio/ORACLES.md"
CMAP = "docs/build-plan/CODE_MAP.md"
API = "apps/api"
GATE = ("Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → "
        "Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).")
EVID = ("One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label "
        "([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.")
ROLL = ("Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until "
        "AS-AUTHZ-DEFAULT, so production behaviour does not change.")
DOD = ("Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; "
       "Orchestrator updates the ledger rows; Status set to done.")
ROUTE = {"L1": "Worker: L1 (grok-4.7-xhigh) · Tester: L1 separate session · Reviewer: L2 separate session",
         "L2": "Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session",
         "L3": "Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session"}


def tier(score: int) -> str:
    return "L1" if score <= 2 else "L2" if score <= 5 else "L3"


def bullets(items: list[str]) -> str:
    return "\n".join(f"- {i}" for i in items)


def card(cid, title, *, pri, typ, cls, ledger, deps, score, parts, ctx, allow, goal, steps, acs, tests,
         elite="", oracle="", gate=GATE, evid=EVID, roll=ROLL, dod=DOD, status="todo", worker=None):
    w = worker or ROUTE[tier(score)]
    body = [f"# {cid}: {title}", "", f"ID: {cid}", f"Title: {title}", f"Status: {status}", "Phase: 3",
            f"Priority: {pri}", f"Type: {typ}",
            f"TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: {cls} (caps in budget.json). Stop at 80%.",
            f"Ledger IDs: {'; '.join(ledger)}", f"Depends on: {', '.join(deps) if deps else 'none'}",
            f"Routing: {w} · Score: {score} ({parts})",
            "Context pack:", bullets(ctx), "File allow-list:", bullets(allow), f"Goal: {goal}", "Steps:",
            "\n".join(f"{n}. {s}" for n, s in enumerate(steps, 1)), "Acceptance criteria:",
            "\n".join(f"- AC{n}: {a}" for n, a in enumerate(acs, 1)), "Test plan:", bullets(tests)]
    if elite:
        body += [f"Elite design notes: {elite}"]
    if oracle:
        body += [f"Oracle tests: {oracle}"]
    body += [f"Gate: {gate}", f"Evidence to log: {evid}", f"Rollback: {roll}", f"Definition of Done: {dod}", ""]
    path = OUT / f"{cid}.md"
    if path.exists() and "Status: todo" not in path.read_text() and status == "todo":
        print("skip (in progress or done):", cid)
        return
    path.write_text("\n".join(body))


OUT.mkdir(parents=True, exist_ok=True)
T = f"cd {API} && uv run pytest -q"

card("AS-PACK", "App Studio Design Pack (Stage 2B)", pri="P1", typ="docs", cls="XL",
     ledger=["P1-2", "AS-FAIL-A", "AS-FAIL-B", "AS-FAIL-D", "AS-FAIL-C", "AS-FIX-3", "AS-FIX-CONSERVE", "AS-FIX-EVAL", "AS-ANYBRIEF"],
     deps=["DEC-002"], score=17, parts="C3 U3 F3 K3 V3 I2", status="done",
     worker="Worker: E1 (planner, XL elite design card) · Reviewer: E2 Fable independent review (01_REVIEW.md)",
     ctx=["docs/specs/APP_STUDIO_HANDOFF.md, APP_STUDIO_FIX_PLAN.md, GAP_AUDIT.md §5; handover L863-951", CMAP],
     allow=["docs/build-plan/app-studio/**", CMAP, "docs/build-plan/cards/phase-3/AS-*.md"],
     goal="Root causes with evidence, the never-errors guarantee, the v3 design, oracles and buildable cards.",
     steps=["Read sources and code paths", "Write the Pack, oracles, CODE_MAP and cards", "Independent Fable review; fold the findings in"],
     acs=["Pack §2 names each root cause with a code or log citation", "Every AS ledger row maps to a card file that lints clean",
          "Independent review recorded in 01_REVIEW.md with dispositions"],
     tests=["`python3 scripts/plan_lint.py cards --phase 3 --prefix AS-`"],
     elite=f"{PACK} is the elite design. Main risks and dispositions are in 01_REVIEW.md.", oracle=f"{ORA} (all sections).",
     evid="docs/build-plan/app-studio/*, CODE_MAP.md, cards/phase-3/AS-*.md (21 Oct). Lint output in coverage/.",
     roll="Docs only: revert the files.")

card("AS-PROFILE", "One App Studio profile instead of 18 env flags", pri="P1", typ="build", cls="S",
     ledger=["AS-RC4"], deps=[], score=4, parts="C1 U1 F1 K1 V0 I0",
     ctx=[f"{PACK} §2 RC4, §3, §9 (first bullet)", f"{CMAP} rows: design prompt, quality adders, owner words, expansion, orphan repair, grounding"],
     allow=[f"{API}/app/ai_conversation/studio_profile.py (new)", f"{API}/app/ai_conversation/app_design.py (design_knobs only)",
            f"{API}/app/ai_conversation/brief_checklist.py (enabled only)", f"{API}/app/ai_conversation/brief_expand.py (_enabled only)",
            f"{API}/app/ai_conversation/clause_grounding.py (enabled only)", f"{API}/app/ai_conversation/orphan_repair.py (mode only)",
            f"{API}/app/ai_conversation/design_quality.py (authorizer mode read only)", f"{API}/tests/test_studio_profile.py (new)"],
     goal="A typed `StudioProfile` (frozen dataclass) with presets `legacy_v1` (exactly today's defaults) and `v3`; each old flag reader asks the profile.",
     steps=["Create `studio_profile.py`: `StudioProfile` fields = every knob in CODE_MAP (rules, gapfill, budget, temperature, checklist, clause_grounding, expand, orphan_repair, authorizer, role_reask, deadline_soft_s=30, deadline_hard_s=45, votes=3, pipeline='legacy'|'v3')",
            "`active_profile()` reads `INGENIUM_STUDIO_PROFILE` (default `legacy_v1`); individual env flags still override, but ONLY when `INGENIUM_EVAL=1`, and each override is listed in `profile.overrides`",
            "`profile.fingerprint()` = sha256 of the sorted fields, 12 hex chars",
            "Replace each flag reader's body with a profile lookup (one line each). Keep the function names",
            "Log `App Studio profile <name> <fingerprint> overrides=<…>` once per process, and put `profile` + fingerprint into `design.llm_outcome`"],
     acs=["`legacy_v1` reproduces today's defaults: a test compares each reader's return against the literal default listed in CODE_MAP",
          "Without `INGENIUM_EVAL=1`, setting `INGENIUM_DESIGN_RULES=v2` has no effect and logs a warning naming the ignored flag",
          "`llm_outcome['profile']` = {name, fingerprint, overrides} on every design",
          "`v3` preset: expand off, gapfill drop, budget none, checklist on, authorizer off (v3 does not use it), votes 3"],
     tests=[f"`{T} tests/test_studio_profile.py`", f"`{T} tests/test_studio_step2a_app_design.py` (regression, unchanged)"])

card("AS-FRESH-BYPASS", "Answer cache honours x-ingenium-fresh", pri="P1", typ="build", cls="S",
     ledger=["P1-1-AC5"], deps=[], score=3, parts="C1 U1 F1 K0 V0 I0",
     ctx=["handover L520 (P1-1 AC5, quote it verbatim in the test docstring)", f"{CMAP} rows: design orchestration (`_DESIGN_CACHE`), providers"],
     allow=[f"{API}/app/ai_conversation/app_design.py (`_DESIGN_CACHE` read/write sites only)", f"{API}/app/ai_client/** (cache bypass read only)", f"{API}/tests/test_fresh_bypass.py (new)"],
     goal="A request carrying `x-ingenium-fresh` makes its own LLM calls at every layer (ai_client cache, `_DESIGN_CACHE`, contract cache).",
     steps=["Find every cache read on the App Studio path (`rg -n \"_CACHE|cache_get|ai_cache\" app/ai_conversation app/ai_client`)",
            "Thread one `fresh` contextvar from the header (existing) to each read; skip the read, still write",
            "Fake provider counts calls in the test"],
     acs=["P1-1 AC5 verbatim: \"the answer cache honours `x-ingenium-fresh` (rerun extend_sales k=3 with `--fresh`; every rep makes its own LLM calls and latency is not 0.5 s)\" (offline: 3 runs → 3× the provider calls; live part is run by AS-CONTRACT-EVAL)",
          "Without the header the second identical request is a cache hit (no regression)"],
     tests=[f"`{T} tests/test_fresh_bypass.py`"])

card("AS-CONTRACT-QUOTES", "Contract quotes come only from the owner's words", pri="P1", typ="test", cls="XS",
     ledger=["P1-1-AC1"], deps=[], score=2, parts="C0 U1 F1 K0 V0 I0",
     ctx=["handover L516 (P1-1 AC1)", f"{CMAP} rows: owner words, contract call"],
     allow=[f"{API}/tests/test_contract_quotes.py (new)"],
     goal="Prove AC1 with a unit test (the handover says the behaviour is already in code).",
     steps=["Fake provider returns a contract whose one row quotes 'Create a Widget model'", "Owner words do not contain it; the expansion does",
            "Call `_call_intent_contract` with `set_original(owner)`; assert the row is dropped or re-quoted from the owner's words"],
     acs=["P1-1 AC1 verbatim: \"contract quotes come only from the owner's original words; AI expansion is context only and never quotable\"",
          "If the test fails, the card stops and reports; the fix belongs to AS-SRC-BRIEF"],
     tests=[f"`{T} tests/test_contract_quotes.py`"])

card("AS-SRC-BRIEF", "Designer, budget and outline read the owner's words only", pri="P0", typ="build", cls="S",
     ledger=["AS-RC1"], deps=["AS-PROFILE"], score=5, parts="C1 U1 F2 K1 V0 I0",
     ctx=[f"{PACK} §2 RC1", f"{CMAP} rows: create session, owner words, design prompt, outline fallback"],
     allow=[f"{API}/app/ai_conversation/app_design.py (`design_user_prompt`, `build_app_design` budget line, `outline_from_brief` call)", f"{API}/tests/test_src_brief.py (new)"],
     goal="Close RC1 everywhere: the expansion is labelled context, never the brief. This ships to legacy too, behind the profile flag `src_brief_only` (on in v3; on in legacy only after AS-EXP-X0 passes).",
     steps=["In `design_user_prompt`, when `profile.src_brief_only`: `Operator brief (full)` = `source_brief(prompt)`; append `expansion_context(prompt)` (already labels it context-only)",
            "`model_budget_for(source_brief(prompt))` in `build_app_design`",
            "`outline_from_brief(source_brief(prompt), …)`",
            "Do not touch `routers/ai_studio.py`: the session still stores the expansion for display"],
     acs=["With the flag on, an expansion that adds 'Alert Rule' and 'Community' never appears in the `Operator brief` section of the designer prompt (string assert)",
          "Budget computed from the 20-word owner brief, not the 200-word expansion (assert value)",
          "With the flag off, prompt text is byte-identical to today (golden string)"],
     tests=[f"`{T} tests/test_src_brief.py`"])

card("AS-CONTRACT-ROLES", "Every contract model row has a role", pri="P1", typ="build", cls="S",
     ledger=["P1-1-AC2"], deps=[], score=3, parts="C1 U1 F1 K0 V0 I0",
     ctx=["handover L517 (P1-1 AC2)", f"{CMAP} row: contract call (`_repair_model_roles` L1238)"],
     allow=[f"{API}/app/ai_conversation/app_design.py (`_repair_model_roles` only)", f"{API}/tests/test_contract_roles.py (new)"],
     goal="Legacy path: a missing or unknown role is repaired deterministically (no LLM re-ask unless `role_reask`).",
     steps=["Allowed roles {record, attribute, dimension, context, future, rule, access}", "Missing → from `decision` (declined→future if the quote is in left_out, else context; metadata→record if kind=model, else attribute)", "Unknown string → same mapping, log the original"],
     acs=["P1-1 AC2 verbatim: \"every model row in the contract has a role from `{record, attribute, dimension, context, future, rule, access}`; a missing role is repaired deterministically\"",
          "Idempotent: repair(repair(x)) == repair(x)"],
     tests=[f"`{T} tests/test_contract_roles.py`"])

card("AS-HARNESS", "Eval harness: isolation, seeds, versions, cost meter, ledger recording", pri="P1", typ="build", cls="M",
     ledger=["P1-2", "AS-8.5-HARNESS", "REL-7.1"], deps=["AS-PROFILE", "AS-FRESH-BYPASS"], score=5, parts="C2 U1 F1 K1 V0 I0",
     ctx=[f"{PACK} §9", f"{CMAP} rows: eval harness", "handover §8.5 'Eval harness' bullet (L924)"],
     allow=[f"{API}/evals/v2/score.py", f"{API}/evals/v2/replay.py", f"{API}/evals/v2/metrics.py (cost fields only)", f"{API}/evals/v2/tests/test_harness.py (new)"],
     goal="Every run is fresh (new session, `--fresh`), on a named disposable DB, with `seed=hash(brief_id,repeat)` where honoured, and records profile + fingerprint, prompt version, model id, tokens and cost.",
     steps=["`score.py --profile <name> --k N --split dev,dev2` sets `INGENIUM_STUDIO_PROFILE` for the API it starts (port 8002, never 8001) and refuses `holdout_fresh` unless `EVAL_UNSEAL=yes`",
            "Per run, write {brief_id, repeat, seed, profile, fingerprint, prompt_versions, model_ids, llm_calls, input/output tokens, usd (price table in one dict), latency, outcome kind}",
            "`INGENIUM_RECORD_DIR` captures raw ledger samples (v3) and pre-authorizer designs (legacy) for replay",
            "`replay.py --profile v3` replays V/C/A offline from recordings at 0 LLM calls"],
     acs=["A run against `holdout_fresh` without `EVAL_UNSEAL=yes` exits non-zero before any request",
          "Two runs with the same profile and recordings replay to byte-identical scores",
          "Every result row has profile, fingerprint, tokens, usd and outcome kind (schema test)"],
     tests=[f"`{T} evals/v2/tests/test_harness.py`"])

card("AS-EVAL-FAIR", "Metrics that can steer: ITT, alignment, CIs, built vs folded", pri="P1", typ="build", cls="M",
     ledger=["AS-FIX-EVAL"], deps=["AS-HARNESS"], score=6, parts="C2 U1 F2 K1 V0 I0",
     ctx=[f"{PACK} §9", f"{ORA} §E", "docs/specs/APP_STUDIO_FIX_PLAN.md (c) items 3-6", f"{CMAP} rows: eval harness"],
     allow=[f"{API}/evals/v2/metrics.py", f"{API}/evals/v2/score.py (scoring functions only)", f"{API}/evals/v2/align.py (new)", f"{API}/evals/v2/tests/test_metrics_v3.py (new)"],
     goal="Scores that a renamed-but-correct entity, an unreached brief or a suggestion cannot distort.",
     steps=["`align.py`: pure-Python Hungarian (n ≤ 30) over design models ↔ gold entities; cost = 1 − (0.6·span-overlap + 0.3·attribute-overlap + 0.1·name n-gram); pairs with cost > 0.8 are not aligned",
            "ITT: unreached → coverage 0; `questions` auto-answered with defaults by the harness",
            "Counts: built, folded, suggested, left_out; `false_fold_rate`; `promote_recoverable`",
            "Paired hierarchical bootstrap (existing `hboot`, `paired`), B=2000, report point + 95% CI",
            "Refuse comparisons across different profile fingerprints"],
     acs=["Oracles E-01..E-06 pass unmodified", "Report prints every §8.6 metric with CI", "Gold without `spans:` falls back to names + attributes and says so in the report"],
     tests=[f"`{T} evals/v2/tests/test_metrics_v3.py`"],
     elite=f"{PACK} §9. Alignment weights are fixed constants in `align.py` with a one-line reason each. They are not tuned on holdout_fresh (INV-16).",
     oracle=f"{ORA} §E (E-01..E-06).")

card("AS-GOLD-SPANS", "Gold files get verbatim spans", pri="P1", typ="test", cls="M",
     ledger=["AS-GOLD-SPANS-ROW"], deps=[], score=3, parts="C1 U1 F1 K0 V0 I0",
     ctx=[f"{PACK} §9", f"{API}/evals/v2/dev/*.md + *.gold.yaml, dev2/*"],
     allow=[f"{API}/evals/v2/dev/*.gold.yaml", f"{API}/evals/v2/dev2/*.gold.yaml", f"{API}/evals/v2/tests/test_gold_spans.py (new)"],
     goal="Each gold entity and attribute gets `spans:` (exact substrings of its brief), so alignment does not depend on stems.",
     steps=["For each of the 28 briefs: add `spans:` lists under each entity and attribute (copy text exactly; no offsets needed, the test finds them)",
            "Never open `holdout_fresh/` (INV-16)", "Mark the file `spans_status: DRAFT` for Tope's review (DEC-026)"],
     acs=["Every span is a verbatim substring of its brief (test)", "No file under `holdout_fresh/` changed (git diff --stat check in the Tester packet)"],
     tests=[f"`{T} evals/v2/tests/test_gold_spans.py`"])

card("AS-CH-BRIEF", "Headline briefs: Customer Health file + reconstructed briefs flagged", pri="P1", typ="test", cls="XS",
     ledger=["AS-CH-BRIEF", "AS-RECON-BRIEFS"], deps=[], score=1, parts="C0 U0 F1 K0 V0 I0",
     ctx=[f"{API}/tests/fixtures/customer_health_brief.md", f"{API}/evals/v2/dev/bakery_ng.gold.yaml (header only)"],
     allow=[f"{API}/evals/v2/dev/customer_health.md (new)", f"{API}/evals/v2/dev/customer_health.gold.yaml (new, DRAFT)", f"{API}/evals/v2/HEADLINE.md (new)"],
     goal="The five headline briefs are files, and the reconstructed ones are flagged for Tope's exact words (DEC-039).",
     steps=["Copy the fixture verbatim to `dev/customer_health.md`", "Draft the gold from the brief's own headings (status DRAFT, reviewer Tope)",
            "`HEADLINE.md` lists the five paths + their status (ACCEPTED / DRAFT / RECONSTRUCTED)"],
     acs=["`customer_health.md` is byte-identical to the fixture", "HEADLINE.md names all five and flags bakery_ng + event_hire as RECONSTRUCTED"],
     tests=["`cmp` of the two files; YAML loads"])

card("AS-EXP-X0", "Experiment X0: does the expansion leak drive invention?", pri="P0", typ="test", cls="S",
     ledger=["AS-RC1"], deps=["AS-SRC-BRIEF", "AS-HARNESS", "AS-EVAL-FAIR"], score=4, parts="C1 U2 F1 K0 V0 I0",
     ctx=[f"{PACK} §10 X0", "AS-HARNESS usage line in PROGRESS"],
     allow=[f"{API}/evals/v2/experiments/x0.md (new; results only)"],
     goal="Paired measure of legacy_v1 vs legacy_v1 + `src_brief_only`, on salon_voice-like dev briefs that expand, plus rental_casual and bakery_ng.",
     steps=["Pick from dev/dev2 the briefs where `not_vague_reason` returns None (they expand); add rental_casual and bakery_ng; at most 6 briefs",
            "k=5 per arm with common seeds; disposable v20 DB; `--fresh`", "Report invented, false folds, coverage ITT and stability with paired CIs"],
     acs=["Report written with CIs and the call count (stay within the DEC-040 budget)",
          "If invented falls and the CI excludes 0: Orchestrator proposes turning `src_brief_only` on in legacy (Tope yes)",
          "Otherwise the report says so; nothing ships"],
     tests=["n/a (measurement card); the Tester re-computes two numbers from the raw JSON"],
     gate="GATE-A: live LLM spend inside DEC-040; Tester re-computation matches; Reviewer checks no holdout_fresh access.")

card("AS-ROBUST-FUZZ", "Never-errors test suite (written before the code)", pri="P0", typ="test", cls="M",
     ledger=["AS-ANYBRIEF", "AS-RC6"], deps=["AS-PROFILE"], score=5, parts="C2 U1 F1 K1 V0 I0",
     ctx=[f"{PACK} §1 G-TOTAL, §7", f"{ORA} §T"],
     allow=[f"{API}/tests/test_studio_outcome_total.py (new)", f"{API}/tests/fakes/fake_llm.py (new)", f"{API}/pyproject.toml (dev dependency `hypothesis` only; MPL-2.0)"],
     goal="Encode T-01..T-09 as tests that fail today and define done for AS-TOTAL.",
     steps=["`FakeLLM` with the 12 fault kinds × 3 positions", "Hypothesis strategy for briefs (unicode incl. RTL and emoji, 0-60k chars, CSV/JSON/SQL/code pastes, injections)",
            "Drive both routes through FastAPI TestClient with a fake snapshot; no Odoo, no network",
            "Mark the suite `xfail(strict=True)` until AS-TOTAL lands, so it cannot silently pass"],
     acs=["T-01..T-09 exist exactly as written in ORACLES §T", "Running today: they xfail (proves they test something)", "Suite runs offline in < 60 s"],
     tests=[f"`{T} tests/test_studio_outcome_total.py`"])

card("AS-TOTAL", "Total-function boundary: one outcome for every brief and every failure", pri="P0", typ="build", cls="L",
     ledger=["AS-ANYBRIEF", "AS-RC6"], deps=["AS-ROBUST-FUZZ"], score=8, parts="C2 U1 F2 K2 V1 I0",
     ctx=[f"{PACK} §1, §7", f"{ORA} §T", f"{CMAP} rows: create session, clarify/generate, LLM call, outline fallback"],
     allow=[f"{API}/app/ai_conversation/studio_outcome.py (new)", f"{API}/app/ai_conversation/brief_normalise.py (new)", f"{API}/app/routers/ai_studio.py (create + generate routes: wrap only)",
            f"{API}/app/ai_conversation/app_design.py (`_call_llm` exception list; `build_app_design` return type under v3)", f"{API}/tests/test_studio_outcome_total.py (remove xfail only)"],
     goal="Both routes return a `StudioOutcome` (proposal | questions | declined | degraded) for every input and fault; never a 5xx.",
     steps=["`studio_outcome.py`: Pydantic discriminated union as in Pack §1 table; `degraded.cause` plain text from `_fallback_reason`",
            "`brief_normalise.py`: NFC, control chars, size classes (Pack §7), fence helper",
            "`_call_llm`: also catch `URLError`, `JSONDecodeError`, `ValidationError`, `KeyError`, `TypeError`, `ValueError` from parsing; map to status `failed` with the class name",
            "Deadline: `concurrent.futures` with soft/hard values from the profile; partial votes used at soft",
            "Route boundary: one `except Exception` → `degraded` + `logger.exception` + request id; a counter increments (the fuzz asserts 0)",
            "Legacy keeps its response shape plus a new `outcome` key (additive), so the UI is not broken"],
     acs=["T-01..T-09 pass with xfail removed", "No route in ai_studio.py returns 5xx under the fault matrix", "The boundary catch-all fires 0 times in the suite",
          "Existing studio tests unchanged and green"],
     tests=[f"`{T} tests/test_studio_outcome_total.py tests/test_studio_step2a_app_design.py tests/test_studio_step3_design_build.py`"],
     elite=f"{PACK} §7. The catch-all is a safety net and a test target: any real failure class found must get its own mapping. Do not widen the exception list beyond the names in Steps without a Reviewer note.",
     oracle=f"{ORA} §T (T-01..T-09), written by AS-ROBUST-FUZZ; this card may only remove the xfail markers.")

card("AS-DECODE", "Constrained decoding on Gemini + validation + one repair", pri="P1", typ="build", cls="M",
     ledger=["P1-2", "AS-8.5-DECODE", "AS-RC5"], deps=["AS-PROFILE"], score=6, parts="C1 U2 F1 K1 V1 I0",
     ctx=[f"{PACK} §2 RC5, §5 (schema line)", f"{CMAP} row: providers", "handover L921 + §8.7 AC3"],
     allow=[f"{API}/app/llm_provider.py (`GeminiProvider.generate_json` only)", f"{API}/app/ai_conversation/schema_tools.py (new)", f"{API}/tests/test_gemini_schema.py (new)"],
     goal="Gemini receives the Pydantic-derived schema; malformed output never reaches compile.",
     steps=["`schema_tools.to_gemini(schema)`: inline `$ref`, drop unsupported keywords (`additionalProperties`, `default`, `title`, `$defs`), keep `propertyOrdering`",
            "Probe once on a 3-field schema with a live call (1 call; GATE-A): try `responseJsonSchema`, then `responseSchema`; record which works in FACTS.md [Verified]",
            "`generate_json(format_schema=…)` sets `responseMimeType: application/json` + the working key",
            "Caller validates with Pydantic; on failure, one repair call with the error list; then outline fallback"],
     acs=["§8.7 AC3 verbatim: \"structured output plus validation; a fuzz test of malformed model output never reaches compile\"",
          "`to_gemini` output contains none of the dropped keywords (unit test over BriefLedger and AppDesign schemas)",
          "Live probe result recorded with date and model id"],
     tests=[f"`{T} tests/test_gemini_schema.py`"],
     elite="Gemini's schema subset is [Inferred] from docs and must be verified by the probe. If neither key works, keep mime-type JSON and rely on validation + repair; record that and continue.",
     oracle="Fuzz: 200 malformed JSON variants (truncation, wrong types, extra keys) → validator rejects or repairs; compile is never called on an invalid object.")

card("AS-LEDGER-SCHEMA", "Brief Ledger models and validators", pri="P1", typ="build", cls="M",
     ledger=["AS-LEDGER"], deps=[], score=6, parts="C2 U1 F2 K1 V0 I0",
     ctx=[f"{PACK} §4", f"{ORA} §L", f"{CMAP} row: authorizer (`norm`; reuse it)"],
     allow=[f"{API}/app/ai_conversation/brief_ledger.py (new)", f"{API}/tests/test_brief_ledger.py (new)"],
     goal="Pure Pydantic models + `validate(ledger, brief) -> (ledger, report)` implementing L1-L8.",
     steps=["Models exactly as Pack §4", "One normaliser shared by brief and spans (NFC + casefold for compare; offsets on the NFC text)",
            "L1-L8 in order; each emits report codes (`span_not_verbatim`, `demoted_context`, …)", "`BriefLedger.model_json_schema()` exported for AS-DECODE"],
     acs=["Oracles L-01..L-12 pass unmodified", "validate is idempotent and pure (no I/O; test with monkeypatched open/socket)"],
     tests=[f"`{T} tests/test_brief_ledger.py`"],
     elite=f"{PACK} §4. Offsets index the NFC-normalised brief; comparisons are casefolded. Never use stems here.",
     oracle=f"{ORA} §L.")

card("AS-RETRIEVE", "Per-connection retrieval of stock candidates", pri="P1", typ="build", cls="M",
     ledger=["P1-2", "AS-8.5-RETRIEVE"], deps=[], score=6, parts="C2 U1 F1 K1 V1 I0",
     ctx=["handover L920 + §8.7 AC2", f"{CMAP} rows: snapshot, stock routing"],
     allow=[f"{API}/app/ai_conversation/retrieval.py (new)", f"{API}/tests/test_retrieval.py (new)"],
     goal="Top-k stock model candidates per noun phrase from the live snapshot (keyword + field-name match; embeddings later), refreshed on install.",
     steps=["Index = installed models' `_description`, technical name tokens and field strings from the snapshot (no new Odoo calls)",
            "`candidates(nouns, snapshot, k=5) -> {noun: [model…]}`; BM25-style scoring in pure Python",
            "Invalidate on snapshot fingerprint change (install_step re-reads the snapshot)",
            "`retrieval_block()` renders candidates for the Ledger prompt"],
     acs=["§8.7 AC2 (retrieval part) verbatim: \"retrieval indexes are built per connection and refreshed on module install; the mapper cannot choose a model or field outside the retrieved set or 'new'\" (the 'cannot choose' half is enforced by L4 in AS-LEDGER-SCHEMA)",
          "'customer' → res.partner in top 3; 'appointment' → calendar.event in top 3 when calendar is installed (fixture snapshots for 17 and 20)"],
     tests=[f"`{T} tests/test_retrieval.py`"],
     elite="Keyword first: it is deterministic, free and explainable. pgvector is a later option (PostgreSQL licence) only if X2 shows recall misses.",
     oracle="Fixture snapshots v17/v20: 10 noun→model expectations listed in the test, written before the code.")

card("AS-LEDGER-CALL", "The Ledger call: prompt, chunks, k parallel samples", pri="P1", typ="build", cls="M",
     ledger=["AS-LEDGER", "AS-FAIL-B"], deps=["AS-LEDGER-SCHEMA", "AS-DECODE", "AS-RETRIEVE", "AS-TOTAL"], score=7, parts="C2 U2 F2 K1 V0 I0",
     ctx=[f"{PACK} §3, §5 (prompt word for word), §7 size classes", f"{CMAP} rows: owner words, providers"],
     allow=[f"{API}/app/ai_conversation/ledger_call.py (new)", f"{API}/tests/test_ledger_call.py (new)"],
     goal="`sample_ledgers(owner_words, snapshot, profile) -> list[BriefLedger]`: k samples in parallel, each validated, raw output recorded.",
     steps=["Prompt text exactly as Pack §5 (copy, don't paraphrase); fence owner words", "Size class: normal = 1 call/sample; long = ≤6 chunks/sample by headings, merged by `ledger_vote.align` (same entity across chunks)",
            "k = profile.votes (3), `ThreadPoolExecutor`, provider default temperature", "Each sample → `brief_ledger.validate`; failed samples dropped and counted",
            "Write raw samples to `INGENIUM_RECORD_DIR` when set"],
     acs=["With the fake provider: 3 samples → 3 validated ledgers; 1 garbage sample → 2 ledgers + a counted failure", "The prompt string equals the Pack text (golden test)",
          "Owner words appear only inside the fence; the expansion appears nowhere", "Customer Health fixture → size class normal, 1 call per sample"],
     tests=[f"`{T} tests/test_ledger_call.py`"],
     elite=f"{PACK} §5. Votes give stability; never lower temperature to fake stability. Long-brief merging reuses V's alignment so there is one identity algorithm.",
     oracle="Golden prompt test; fake-provider sample counts; fence test with an injection string.")

card("AS-PROMPT-CONTRACT", "Contrastive few-shot pairs + manifest guard", pri="P1", typ="build", cls="S",
     ledger=["AS-FIX-3"], deps=["AS-LEDGER-CALL"], score=3, parts="C1 U1 F1 K0 V0 I0",
     ctx=[f"{PACK} §5 (few-shot line)", f"{API}/evals/v2/FEWSHOT_MANIFEST.json"],
     allow=[f"{API}/app/ai_conversation/ledger_fewshot.py (new)", f"{API}/evals/v2/FEWSHOT_MANIFEST.json", f"{API}/tests/test_fewshot_manifest.py (new)"],
     goal="Two contrastive pairs (dimension vs record) from domains absent from every eval split, with a guard test.",
     steps=["Write the 2 pairs as tiny briefs + their expected ledgers", "Add their domains and n-gram fingerprints to the manifest",
            "Test: no few-shot sentence shares a 6-gram with any eval brief (dev, dev2, holdout, unseen); holdout_fresh is checked by hash only, never read"],
     acs=["Guard test passes", "Few-shot text is injected into the Ledger system prompt after the rules"],
     tests=[f"`{T} tests/test_fewshot_manifest.py`"])

card("AS-STABILITY", "Vote and align samples (self-consistency)", pri="P1", typ="build", cls="M",
     ledger=["AS-FAIL-B"], deps=["AS-LEDGER-SCHEMA"], score=7, parts="C2 U1 F2 K1 V1 I0",
     ctx=[f"{PACK} §6.1", f"{ORA} §V"],
     allow=[f"{API}/app/ai_conversation/ledger_vote.py (new)", f"{API}/tests/test_brief_ledger_vote.py (new)"],
     goal="`vote(samples) -> VotedLedger` and `align(a, b)`, pure and canonical.",
     steps=["Pure-Python Hungarian on 1 − Jaccard(mention intervals)", "Clusters kept at ≥ 2/k; majority role; ties → `unsure` with the conservative default order",
            "Fact attachment by majority; confidence = votes/k", "Canonical sort by first-mention offset"],
     acs=["Oracles V-01..V-08 pass unmodified (hypothesis for V-01..V-04)", "k=1 input passes through with confidence 0.5 on every entity"],
     tests=[f"`{T} tests/test_brief_ledger_vote.py`"],
     elite=f"{PACK} §6.1. The conservative order is the anti-invention guarantee under disagreement; it must not be changed without an Elite note.",
     oracle=f"{ORA} §V.")

card("AS-COMPILE", "Compile the voted Ledger into an AppDesign", pri="P1", typ="build", cls="L",
     ledger=["AS-COMPILE-ROW", "AS-FAIL-A"], deps=["AS-STABILITY", "AS-RETRIEVE"], score=8, parts="C2 U1 F2 K2 V1 I0",
     ctx=[f"{PACK} §6.3", f"{ORA} §C (C-01..C-11, C-14)", f"{CMAP} rows: data shapes, repair/validate, automations"],
     allow=[f"{API}/app/ai_conversation/ledger_compile.py (new)", f"{API}/app/ai_conversation/app_design.py (v3 branch at the top of `build_app_design` only)", f"{API}/tests/test_ledger_compile.py (new)"],
     goal="Deterministic mapping table of Pack §6.3; under profile v3 `build_app_design` runs N → S → L → V → Q → C → A and skips the RC2 adders.",
     steps=["Implement the mapping table row by row; technical names via `_model_name`/`_field_name`", "Folded items keep a full `DesignModel` in `left_out[].proposal`",
            "`structure_hash(design)`", "v3 branch: `if profile.pipeline == 'v3': return v3_design(...)` at the top of `build_app_design`; legacy code below it unchanged",
            "Run `dedupe_fields`, `scope_and_limits`, `validate_and_repair(strict_refs=True)`; never `strengthen_design`, `_merge_outline`, `_cover_sections`, `complete_from_brief`"],
     acs=["Oracles C-01..C-11 and C-14 pass unmodified", "Compile never yields a model without a ledger id or assumption id in `requirement_ids` (property test)",
          "Legacy path byte-identical when the profile is legacy_v1 (golden design test on 3 recorded briefs)"],
     tests=[f"`{T} tests/test_ledger_compile.py tests/test_studio_step2a_app_design.py`"],
     elite=f"{PACK} §6.3. Typed facts: money → monetary + currency_id; file → binary (image when the owner says photo/picture/foto). Selection only from ≥ 2 verbatim values.",
     oracle=f"{ORA} §C.")

card("AS-COMPUTE-MATRIX", "Counts, sums and latest values without custom Python", pri="P1", typ="build", cls="S",
     ledger=["AS-FAIL-D"], deps=["AS-COMPILE"], score=5, parts="C1 U1 F1 K1 V1 I0",
     ctx=[f"{PACK} §6.3 (report row)", "docs/specs/APP_STUDIO_FIX_PLAN.md 'D/C shared cause'"],
     allow=[f"{API}/app/ai_conversation/ledger_compile.py (report rules only)", f"{API}/tests/test_compute_matrix.py (new)"],
     goal="A report rule becomes a pivot/graph measure, list sum, group-by or related field; `python_needed` stays empty unless the contract says option_a.",
     steps=["Table: count→pivot count + graph; sum/total→list sum + pivot measure; average→pivot avg; latest→related field on the parent or a sorted o2m", "Live count on the parent form → left_out 'not built: needs custom code' with quote (metadata-only lane)"],
     acs=["C-08 passes", "Across the 28 dev briefs replayed (recordings), `python_needed` count = 0 except option_a rows"],
     tests=[f"`{T} tests/test_compute_matrix.py`"])

card("AS-CONSERVE", "Conservation audit and orphan repair", pri="P1", typ="build", cls="M",
     ledger=["AS-FIX-CONSERVE"], deps=["AS-COMPILE"], score=6, parts="C2 U1 F2 K1 V0 I0",
     ctx=[f"{PACK} §6.4 step 1", f"{ORA} C-12", f"{CMAP} row: orphan repair"],
     allow=[f"{API}/app/ai_conversation/conservation.py (new)", f"{API}/app/ai_conversation/orphan_repair.py (accept ledger orphans as input)", f"{API}/tests/test_conservation.py (new)"],
     goal="Precision (every element has lineage) and recall (every in-scope ledger item is realized) are checked; a miss gets one repair call, then an honest left_out.",
     steps=["`audit(design, voted, brief) -> {unlicensed:[…], unrealized:[…]}`", "Unlicensed elements are removed + logged (never shown as 'built')",
            "Unrealized → `orphan_repair.repair_step` with only those spans (1 call max) → re-compile those items → still missing → left_out `not_built_yet` with quote"],
     acs=["C-12 passes", "Property: after audit, unlicensed = [] and every unrealized item is in left_out"],
     tests=[f"`{T} tests/test_conservation.py`"],
     elite=f"{PACK} §6.4. This is the coverage-by-construction mechanism for failure C; it must run after compile and before polish.",
     oracle=f"{ORA} C-12 plus the two properties in the ACs.")

card("AS-AUTHZ", "Authorizer v3: span evidence by offset, stem rules retired under v3", pri="P1", typ="build", cls="M",
     ledger=["P1-2", "AS-FAIL-A", "AS-8.5-AUTHZ", "AS-FIX-2"], deps=["AS-COMPILE"], score=7, parts="C2 U1 F2 K1 V1 I0",
     ctx=[f"{PACK} §2 RC3, §6.4 step 2", f"{CMAP} row: authorizer", "handover §8.7 AC4 (L945)"],
     allow=[f"{API}/app/ai_conversation/model_authorizer.py (new function `authorize_v3` + helpers; existing functions unchanged)", f"{API}/tests/test_model_authorizer_v3.py (new)"],
     goal="Under v3 the authorizer is an invariant checker over ledger spans (rules 0, 1, 6, 7) with no stem binding; legacy rules stay for legacy_v1.",
     steps=["`authorize_v3(design, voted, force_keep)`: evidence = ledger mention spans (offset-verified); rule 0 promoted → keep; 1 future → suggest; 6 orphan → drop; 7 fold uses the ledger fact kind (link → m2o, dimension ≥ 2 values → selection, else char)",
            "No `stems()` call in `authorize_v3` (grep test)", "Return the same `AuthResult` shape so `apply_calls` is reused"],
     acs=["§8.7 AC4 verbatim: \"authoriser rules each have unit tests with positive and negative cases from real briefs\" (FIX_PLAN 'Verification' list: service history kept, services list kept, salon service folded, NGO pack type + community folded, Stylist Schedule / Generator Log / Resident Share dropped, Loyalty suggested)",
          "Pidgin case (bakery_ng 'wetin dem order') keeps Order Line without lexical overlap", "Legacy `authorize_models` behaviour unchanged (existing tests green)"],
     tests=[f"`{T} tests/test_model_authorizer_v3.py tests/test_model_authorizer.py`"],
     elite=f"{PACK} §2 RC3. Lexical overlap between owner words and LLM-written labels is the false-fold engine; v3 removes it rather than tuning it.",
     oracle="The FIX_PLAN verification cases as fixtures (hand-written ledgers), plus the noun-swap metamorphic case (V-07) applied end to end.")

card("AS-REPAIR", "Polish step that cannot change structure", pri="P1", typ="build", cls="M",
     ledger=["P1-2", "AS-8.5-CRITIQUE"], deps=["AS-COMPILE"], score=5, parts="C1 U1 F1 K1 V1 I0",
     ctx=[f"{PACK} §6.3 (structure hash), §3 P", "handover L923", f"{ORA} C-11"],
     allow=[f"{API}/app/ai_conversation/ledger_polish.py (new)", f"{API}/tests/test_ledger_polish.py (new)"],
     goal="One optional LLM call improves labels, help text and view grouping; any structural change is discarded; max 2 loops inside the soft deadline.",
     steps=["Input = compiled design JSON + owner words; output schema = labels/help/groups only", "Apply → recompute `structure_hash`; differs → discard + log `polish_structure_change`",
            "Skip when the soft deadline is reached or profile.polish is False"],
     acs=["C-11 passes", "Polish off → identical design; polish on with fake output → only label/help fields differ"],
     tests=[f"`{T} tests/test_ledger_polish.py`"])

card("AS-HOST-PREINSTALL", "Stock host fit before install (wrong host fix)", pri="P1", typ="build", cls="M",
     ledger=["AS-WRONGHOST"], deps=["AS-RETRIEVE", "AS-COMPILE"], score=5, parts="C1 U1 F2 K1 V0 I0",
     ctx=["handover §3.3 L242", "docs/specs/APP_STUDIO_FIX_PLAN.md 'Host-fit check'", f"{CMAP} rows: stock routing, install"],
     allow=[f"{API}/app/ai_conversation/host_fit.py (new)", f"{API}/app/ai_conversation/ledger_compile.py (call site only)", f"{API}/tests/test_host_fit.py (new)"],
     goal="A stock host is used only when its app is installed (or installable via the install step) and its required fields can be filled from the brief; otherwise the next candidate or a new model.",
     steps=["Required fields from the snapshot; satisfiable if a ledger fact or a default covers each", "Not installed but installable → install step (GND-MOD flow, one confirmation)", "Neither → next candidate; none → new record model with a note"],
     acs=["generator_lure: fleet.vehicle.log.fuel rejected (needs vehicle) → Fuel Purchase model", "CRM brief before CRM install → install step, not res.partner"],
     tests=[f"`{T} tests/test_host_fit.py`"])

card("AS-QUESTIONS", "At most three questions, each with a default", pri="P1", typ="build", cls="M",
     ledger=["AS-QUESTIONS-ROW", "AS-8.7-AC7"], deps=["AS-STABILITY"], score=5, parts="C1 U1 F2 K1 V0 I0",
     ctx=[f"{PACK} §6.2, §8 items 2-3", "handover §8.7 AC7 (L948)"],
     allow=[f"{API}/app/ai_conversation/ledger_questions.py (new)", f"{API}/app/routers/ai_studio.py (clarify route: v3 branch only)", f"{API}/tests/test_ledger_questions.py (new)"],
     goal="Questions come only from voted doubts that change structure, ranked by impact, max 3, with owner-plain copy and a default; 'Use my defaults' resolves all.",
     steps=["Rank as Pack §6.2", "Copy templates per role pair (record vs fact, record vs line, future vs record) in plain words; no technical names (jargon guard)", "Answers become `owner_override` and re-run V→C→A with no LLM call"],
     acs=["Never more than 3 questions (property)", "Every question has a default and 'Use my defaults' produces a proposal", "§8.7 AC7 verbatim: \"owner UI: questions at most 3, each with a default; the assumption ledger is editable; every proposed item shows the owner's quote it came from; plain words only\" (API half; UI half is UI-APPSTUDIO-BUILD)"],
     tests=[f"`{T} tests/test_ledger_questions.py`"])

card("AS-PROMOTE", "Promote and demote without an LLM call", pri="P1", typ="build", cls="M",
     ledger=["AS-PROMOTE-ROW"], deps=["AS-COMPILE"], score=4, parts="C1 U1 F1 K1 V0 I0",
     ctx=[f"{PACK} §6.5", f"{ORA} C-13"],
     allow=[f"{API}/app/routers/ai_studio.py (new route `POST /{{id}}/override`)", f"{API}/app/ai_conversation/ledger_compile.py (apply overrides)", f"{API}/tests/test_promote.py (new)"],
     goal="`{item, action: promote|demote}` re-runs C and A only; the result is stable on re-run.",
     steps=["Store overrides in session `resolved_answers['_owner_overrides']`", "Promote restores `left_out[].proposal`; demote folds a model onto its host as selection/char", "Return the new outcome in < 1 s (fake provider asserts 0 calls)"],
     acs=["C-13 passes", "0 provider calls (assert)", "Override survives a regenerate"],
     tests=[f"`{T} tests/test_promote.py`"])

card("AS-STOCKCARD", "'Use stock app X' as a first-class recommendation", pri="P1", typ="build", cls="S",
     ledger=["AS-STOCKCARD"], deps=["AS-RETRIEVE"], score=4, parts="C1 U1 F1 K1 V0 I0",
     ctx=["handover §3.3 L244, §3.17 L412", f"{CMAP} row: stock routing"],
     allow=[f"{API}/app/ai_conversation/ledger_compile.py (stock_suggestions only)", f"{API}/tests/test_stockcard.py (new)"],
     goal="When retrieval finds an installable stock app that covers most records (restaurant → POS, project_tracker → Project, retail → Sales/Inventory), the outcome carries a recommendation card first.",
     steps=["Coverage = share of record entities whose top candidate belongs to one stock app", "≥ 0.6 → recommendation with plain reasons; owner can still choose custom"],
     acs=["3 fixture briefs produce the expected stock app recommendation", "Recommendation never blocks the custom path"],
     tests=[f"`{T} tests/test_stockcard.py`"])

card("AS-IR", "Versioned AppDesign schema as the only compile input", pri="P1", typ="build", cls="M",
     ledger=["P1-2", "AS-8.5-IR"], deps=["AS-COMPILE"], score=6, parts="C2 U1 F1 K1 V1 I0",
     ctx=["handover L919 + §8.7 AC1", f"{CMAP} row: data shapes"],
     allow=[f"{API}/app/ai_conversation/app_design.py (`AppDesign` schema_version + lineage fields only)", f"{API}/app/ai_conversation/design_schema.py (new: Pydantic mirror + JSON Schema export)", f"{API}/tests/test_design_schema.py (new)"],
     goal="`AppDesign` carries `schema_version`, lineage on every element, and a generated JSON Schema; install and export consume only a validated AppDesign.",
     steps=["Pydantic mirror (`TypeAdapter` over the dataclasses) → `docs/build-plan/app-studio/appdesign.schema.json` generated by a script", "Every model/field/automation has `requirement_ids` or `assumption_ids` (validator)", "Grep test: install/export entrypoints take `AppDesign` and call `validate_design()` first"],
     acs=["§8.7 AC1 verbatim: \"the IR schema exists, is versioned, and every compiled artefact is generated only from it\"", "Schema export is reproducible (golden file)"],
     tests=[f"`{T} tests/test_design_schema.py`"],
     elite="The UI never says 'IR'. Keep the dataclasses (no big refactor); the Pydantic mirror is the schema and validator.",
     oracle="Golden schema file + a lineage-missing fixture that must fail validation.")

card("AS-LATENCY", "v3 speed: parallel graph, streamed read-back", pri="P1", typ="build", cls="M",
     ledger=["AS-LATENCY-ROW"], deps=["AS-LEDGER-CALL", "AS-COMPILE", "AS-TOTAL"], score=5, parts="C2 U1 F1 K1 V0 I0",
     ctx=[f"{PACK} §3, §7 deadline, §8 item 1", f"{CMAP} row: create session"],
     allow=[f"{API}/app/ai_conversation/v3_pipeline.py (new)", f"{API}/app/routers/ai_studio.py (NDJSON stream endpoint `POST /stream`, v3 only)", f"{API}/tests/test_v3_latency.py (new)"],
     goal="Snapshot and k samples run concurrently; the read-back (records, facts, rules with quotes) streams as soon as V finishes; no critic/second look/conflict look on the blocking path.",
     steps=["One orchestrator function with a timing record per stage", "NDJSON events: understood → questions? → proposal", "Fake provider with 2 s per call: total ≤ 2.5 s for k=3 (parallel proof)"],
     acs=["Parallel proof passes", "Stage timings land in `llm_outcome.timings`", "Live p95 measured by AS-CONTRACT-EVAL (bar < 45 s)"],
     tests=[f"`{T} tests/test_v3_latency.py`"])

card("AS-COVERAGE", "Coverage miss audit (failure C)", pri="P1", typ="verify", cls="M",
     ledger=["AS-FAIL-C"], deps=["AS-EVAL-FAIR", "AS-CONSERVE"], score=4, parts="C1 U2 F1 K0 V0 I0",
     ctx=[f"{PACK} §2 RC8", "docs/specs/APP_STUDIO_FIX_PLAN.md 'Coverage'"],
     allow=[f"{API}/evals/v2/coverage_audit.py (new)", f"{API}/evals/v2/experiments/coverage.md (new; results)"],
     goal="Classify every missed need on legacy and v3 recordings as unreached / scorer-miss / true miss, so fixes target the real cause.",
     steps=["Run on recordings only (0 LLM calls)", "Scorer-miss = aligned by span but not by stems", "Write counts per class and the 10 largest true misses with their quotes"],
     acs=["Report exists with the three counts for both profiles", "Each true miss names the missing element kind (model, field, automation, access)"],
     tests=["The Tester re-derives one count by hand from the raw JSON"])

card("AS-CONTRACT-EVAL", "Experiments X1-X4: v3 against legacy, paired", pri="P1", typ="test", cls="M",
     ledger=["P1-1-AC3", "P1-1-AC4", "AS-LIVE-BUDGET"], deps=["AS-HARNESS", "AS-EVAL-FAIR", "AS-GOLD-SPANS", "AS-LEDGER-CALL", "AS-COMPILE", "AS-CONSERVE", "AS-AUTHZ", "AS-QUESTIONS", "AS-LATENCY"], score=5, parts="C1 U2 F1 K1 V0 I0",
     ctx=[f"{PACK} §10 X1-X4", "handover L518-519 (P1-1 AC3, AC4)"],
     allow=[f"{API}/evals/v2/experiments/x1_x4.md (new; results only)"],
     goal="Measure v3 vs legacy_v1 on dev + dev2 with the same seeds, ITT, paired CIs; decide go/no-go for shadow.",
     steps=["X1 ledger reliability (offline validators on 28×3 samples)", "X2 paired k=3 per arm on a disposable v20 DB; then a k=5 subset of 10 briefs on 17-19", "X3 stability k=5 on 10 briefs", "X4 latency/cost from the harness meter",
            "Stop at the DEC-040 call budget; report the spend"],
     acs=["P1-1 AC3 verbatim: \"the offline check and a subset k=5 re-record on dev plus dev2 run on a disposable v20 DB with the same seeds for both arms. Report with hierarchical bootstrap 95 percent CIs.\"",
          "P1-1 AC4 verbatim: \"gates (from APP_STUDIO_FIX_PLAN): invented models per run down with CI upper bound below the baseline; false_fold_rate at most 0.10 (point and CI upper); ITT coverage drop above 0.05 on at most one brief; exclusion recall stays 1.0.\"",
          "The kill rules of Pack §10 are applied and written down"],
     tests=["Tester recomputes 3 headline numbers from the raw JSON"],
     gate="GATE-A: Tope approves the DEC-040 budget before the first live call; Tester recomputation matches; Reviewer confirms holdout_fresh untouched.")

card("AS-BRIEFS-NEW", "Twenty or more new messy briefs with gold", pri="P1", typ="test", cls="M",
     ledger=["AS-8.5-BRIEFS"], deps=[], score=3, parts="C1 U1 F1 K0 V0 I0",
     ctx=["handover L925", f"{PACK} §9 sets"],
     allow=[f"{API}/evals/v2/dev3/*.md", f"{API}/evals/v2/dev3/*.gold.yaml", f"{API}/evals/v2/dev3/README.md"],
     goal="≥ 20 briefs: Pidgin, Yoruba, Hausa, Igbo mixes; voice-note run-ons; negation; extension of existing apps; very short; very long; money; injected instructions. Gold DRAFT with spans, for Tope's review (DEC-026).",
     steps=["Write blind to failure cases (don't open holdout_fresh)", "Each brief has gold with spans and a style tag", "README lists the strata counts"],
     acs=["≥ 20 briefs covering every stratum named in handover L925", "Every gold span verbatim (reuse test_gold_spans)"],
     tests=[f"`{T} evals/v2/tests/test_gold_spans.py`"])

card("AS-SHADOW", "Shadow week: v3 beside legacy on real sessions", pri="P1", typ="build", cls="M",
     ledger=["AS-SHADOW", "AS-FIX-5"], deps=["AS-CONTRACT-EVAL"], score=6, parts="C1 U1 F2 K2 V0 I0",
     ctx=[f"{PACK} §10 X5", "DEC-009"],
     allow=[f"{API}/app/ai_conversation/v3_shadow.py (new)", f"{API}/app/routers/ai_studio.py (call shadow after legacy returns; never awaits it)", f"{API}/tests/test_v3_shadow.py (new)"],
     goal="For real sessions, run v3 in a background thread after legacy answers; log verdict summaries only (no owner-visible change).",
     steps=["Log: brief hash, counts (built/folded/suggested), structure hash, timings; never brief text or record values (INV-17)", "Kill switch in the profile", "Promote clicks on legacy sessions recorded to estimate false folds"],
     acs=["Owner response time unchanged (test: shadow raising or sleeping does not delay the route)", "No brief text in shadow logs (scrub test)"],
     tests=[f"`{T} tests/test_v3_shadow.py`"],
     elite="Real-session data is customer data: log counts and hashes only. The shadow never writes to Odoo and never calls install paths.",
     oracle="A shadow worker that raises and one that sleeps 60 s: the route returns in normal time both ways; the log contains no text from the fixture brief.",
     gate="GATE-A: Tope's go to start the week (DEC-009). Then the normal card gate.")

card("AS-RELEASE-BARS", "Release report against every §8.6 bar", pri="P1", typ="test", cls="S",
     ledger=["AS-8.6-COV", "AS-8.6-INV", "AS-8.6-FOLD", "AS-8.6-RECALL", "AS-8.6-STAB", "AS-8.6-EXCL", "AS-8.6-LAT", "AS-8.6-COST", "AS-8.6-RATING", "AS-8.6-INSTALL"],
     deps=["AS-CONTRACT-EVAL", "AS-SHADOW"], score=4, parts="C1 U1 F1 K1 V0 I0",
     ctx=["handover §8.6 table (L928-939)", "experiments/x1_x4.md"],
     allow=[f"{API}/evals/v2/experiments/release_bars.md (new)"],
     goal="One table: each bar, today's value with CI, pass/fail, and the evidence path; Tope's rating of the five headline briefs recorded.",
     steps=["Collect from experiment reports; install-clean from the live 17-20 harness (P1-3)", "Tope rates the five headline outputs 1-10 (DEC-035 briefs)"],
     acs=["Every §8.6 row present with evidence or 'not measured' (never blank)", "Ratings recorded with date"],
     tests=["Tester checks each number against its source file"])

card("AS-AUTHZ-DEFAULT", "Turn profile v3 on by default", pri="P1", typ="build", cls="XS",
     ledger=["P1-1-AC6"], deps=["AS-RELEASE-BARS"], score=3, parts="C0 U1 F2 K0 V0 I0",
     ctx=["handover L521 (P1-1 AC6)", "experiments/release_bars.md"],
     allow=[f"{API}/app/ai_conversation/studio_profile.py (default name only)"],
     goal="Default `INGENIUM_STUDIO_PROFILE` becomes v3 after the bars pass (or written exceptions) and Tope agrees.",
     steps=["One-line default change", "Restart is Tope's (`:8001` runs without --reload)"],
     acs=["P1-1 AC6 (adapted to v3; the legacy authorizer is superseded): \"authorizer turned on by default only after AC4 passes and Tope agrees\"", "Rollback = set the env var to legacy_v1 (documented in the PR text)"],
     tests=[f"`{T} tests/test_studio_profile.py`"],
     gate="GATE-R input: Tope's written yes in the current message (INV-18).")

card("AS-HOLDOUT-RUN", "Final proof on the sealed holdout (once)", pri="P1", typ="test", cls="S",
     ledger=["AS-HOLDOUT", "AS-FIX-6"], deps=["AS-AUTHZ-DEFAULT"], score=3, parts="C0 U1 F2 K0 V0 I0",
     ctx=[f"{PACK} §10 X6", "handover §3.3 L233"],
     allow=[f"{API}/evals/v2/experiments/holdout_fresh_final.md (new)"],
     goal="Run holdout_fresh once with `EVAL_UNSEAL=yes`, k=3, fresh, disposable v20; report every bar.",
     steps=["Tope says go in the current message", "Verify the MANIFEST hash before the run", "Single run; no re-runs to 'improve' numbers"],
     acs=["Manifest hash matches handover L233", "Report has every §8.6 bar", "Exactly one run logged"],
     tests=["Tester verifies the manifest hash and the single-run log"],
     gate="GATE-R: Tope's go; Reviewer confirms no earlier read of holdout_fresh in session logs.")

card("AS-DRAFTFOLD", "Fold Draft Studio under App Studio", pri="P2", typ="build", cls="S",
     ledger=["AS-DRAFTFOLD"], deps=[], score=3, parts="C1 U0 F1 K1 V0 I0",
     ctx=["handover §3.3 L247; FEATURE_AUDIT 14", "DEC-024", "docs/build-plan/UI_REFERENCE_MAP.md area 07"],
     allow=["apps/web/src/app/connections/[id]/studio/**", "apps/web/src/app/connections/[id]/projects/**", "apps/web/src/components/studio/**", "apps/web/src/lib/nav.ts"],
     goal="Saved drafts and the app plan live inside App Studio (Saved drafts; Advanced: app plan); old routes redirect; every feature preserved (INV-05).",
     steps=["List what Draft Studio and Projects do today (INV-05 table in the PR text)", "Move entry points; add redirects", "Jargon guard + states (empty/loading/error) per the UI protocol"],
     acs=["Every listed feature reachable from App Studio", "Old routes redirect (Playwright)", "UI protocol checklist passes (side-by-side vs the area 07 references)"],
     tests=["`cd apps/web && pnpm vitest run src/components/studio`", "Playwright redirect spec"])
print("cards written:", len(list(OUT.glob("AS-*.md"))))
