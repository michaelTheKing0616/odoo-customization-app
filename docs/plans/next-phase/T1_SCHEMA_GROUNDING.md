# Track 1 — schema grounding

Sources: Claude response 2026-09-22, tiered architecture handoff, plan addendum. The tiered architecture wins on grounding. PR-F.0 runs before PR-A (`04_SEQUENCE.md`).

## Minimal invariants

1. **Closure.** Every field, many2one, one2many, and menu is traceable to a cue or to `approved_craft`.
2. **Single source of truth** for one2many and menu counts, computed once from `GenerateIR` after `build_ir`. Downstream never adds uncued nodes.
3. **Same entrypoint** for the test harness and the Studio Generate button. Assert the final XML.

## Pre-flight (answer in the progress log before PR-A)

| ID | Check |
|---|---|
| PF-1 | Has PR-1 (`GenerateIR` / `build_ir`) landed? Baseline says yes (`ai_generate_ir.py`). Re-confirm the symbol. |
| PF-2 | Has any PR-A→F work landed? Reconcile; do not rebuild it. |
| PF-3 | Has `AI_IR_TRACE` run on the Maintenance brief, and is the scrub-key hypothesis confirmed or refuted? |
| PF-4 | Does the pipeline call live RPC for schema, or only static structures? |
| PF-5 | Can the box mirror run `-i <module> --test-enable` non-interactively with parseable errors? |
| PF-6 | Has PR-J1 landed? Transport exists. Live `/doc` smoke is still operator. |

## Verdicts T1–T12 (do not relitigate)

| ID | Verdict |
|---|---|
| T1 | Keep |
| T2 | Diagnosis only |
| T3 | Not a completion signal |
| T4 | Structurally unsound |
| T5 | Harmful if automatic. Stop |
| T6 | Package presence is not a cue |
| T7 | Keep, but it should fire on under 5% of thin briefs |
| T8 | Miscalibrated goldens |
| T9 | Keep the ops loop |
| T10 | Over-relied UX |
| T11 | Not the bottleneck |
| T12 | Harmful. Stop blocklist growth |

Stop on day one: automatic T5, T12 blocklist growth, trusting a green battery before F.0 and F, and a single-brief "class fix" without the sibling golden.

## Known defects the goldens must still catch

L1 meta wrong golden stage. L2 many2one spray. L3 Rate Line one2many. L4 install grammar victim. L5 sibling menus. L6 Date versus Datetime.

## PR-F.0 (blocking)

Trace Studio Generate → API → function. Confirm `_finish_seed_draft` does not add nodes after the presumed entrypoint. If it does, retarget the goldens. Until F.0 is written up, any green battery is provisional.

## Instrumentation

`AI_IR_TRACE=1` dumps after every pass. Record the scrub-key hypothesis in the progress log.

## PR-A `schema_client`

- `model_exists`, `fields_get`, `relation_ok` have positive and negative tests (addendum A2).
- Catalog TTL: a stale snapshot yields an empty or deny client (addendum A3). TTL today is 15 minutes in `ai_schema_client.py`. Do not lengthen it silently.
- `field_is_writable` is built or the deferral is written in the progress log.
- `view_has_field` follow-up, checked 2026-10-02: `LiveSchemaClient` parses `get_views` and `FakeSchemaClient` uses `view_fields`. `DenySchemaClient` and `CatalogSchemaClient` return false. Do not delete the Live/Fake parser. Do not extend Catalog past the stub. Card T1-A4 is verification only.

## PR-B `merge_proposals`

Admit only when (a) the node is cued, or (b) it is on the structural allowlist, or (c) it is schema-verified reuse. The allowlist is readable in one sitting.

Named regression, must reject: generic many2one to `res.partner`, and a Rate Line / maintenance lexical with no one2many cue (addendum A4).

## PR-C `approved_craft`

Checklist UI defaults off. Toggling a row changes the output. A non-technical user can tell what the row will add.

## PR-D `sandbox_verify_and_repair`

At most 3 repair iterations. A broken module never becomes `install_ready`. A clean module is `install_ready` on the first pass. Log Odoo errors verbatim. `prove_status=proved` still requires `run_tests=True` (D2). Do not stamp `proved` from a smoke install.

## PR-E harness and CI

Tier 1 and Tier 2 fail on schema-invalid output. Tier 3 is slow CI and does not block the fast suite. D2 is already answered; the card records the encoding, it does not reopen the decision.

## PR-F goldens

- Maintenance passes.
- Service-cards passes with the same code path. Zero brief-specific branches.
- At least one Option A module reaches `install_ready` through a real sandbox.

## Retirement

Delete `scrub_uncued_*` only after two consecutive runs with zero scrub removals. Keep one release as a CI no-op assert. Date, Datetime, and money move to `approved_craft`. Then run the full battery and the live grade.

## Gates that stay even if the code already exists

- Closure holds on a brief that used to spray.
- The sibling golden fails if someone special-cases Maintenance.
- `schema_client` deny-on-stale is tested, not commented.
- No new `if display_name == "..."` surface denylist (repo lock: new failures add a property).
