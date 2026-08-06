# Universal Ingestion Pipeline — Orchestrator Plan (token-efficient)

> **Mission:** One pipeline (classify → extract → map → order → dry-run → commit) for
> CoA, BoMs, catalogs, contacts, price lists, rosters, etc. — **mostly wiring existing
> Document 5/6/7 machinery**, not six new systems.
>
> **Execution rule:** Workers get ONLY the card section from
> `plans/cards/WAVE-17-INGEST.md` + named INPUT paths. This file is for the session lead.
> Update `/PROGRESS.md` (root) and `plans/PROGRESS.md` after each gated card.

## Token discipline (bind every session)

1. **Audit before write.** If a capability exists under §Reuse, extend it — never fork a
   parallel importer.
2. **One producer schema.** All extractors emit `IngestBatch` / `IngestTable` (canonical).
   Stages 3–6 never see CSV vs PDF differences.
3. **Domain logic only in Stages 1–2.** Stages 3–6 stay document-type-agnostic.
4. **No LLM for parseable tables.** CSV/XLSX → `data_import.parse_tabular`; LLM only for
   header→field guess and classify/extract on semi/unstructured sources.
5. **Hard gates.** Do not start card N+1 until card N’s GATE is green in PROGRESS.
6. **Privacy default.** Local Ollama only for classify/extract; never send company docs to
   cloud APIs in v1.

## Reuse map (DO NOT REBUILD)

| Stage | Existing asset | Action |
|-------|----------------|--------|
| Parse CSV/XLSX | `apps/api/app/data_import.py` (+ router/UI) | **Reuse** — wrap as extractor |
| Field meta / required | `data_import._field_meta` (`ir.model.fields`) | **Reuse** |
| Upsert / natural keys | `data_import.dry_run_or_commit` (create\|upsert) | **Reuse** as Stage 6 writer |
| Dedupe / merge | `apps/api/app/bulk_suite/dedupe.py` | **Extend** — call pre-commit + batch-internal |
| Dry-run + confirm | import router `dry_run` + advanced confirm phrase | **Reuse** |
| Batch write pacing | `bulk_suite/executor.py` patterns | **Reuse** |
| l10n / CoA gate | `invoicing_l10n.py`, `protected_modules.py` | **Reuse** — never invent fiscal packages |
| Live grounding | `expert/grounding.py` patterns | **Reuse** introspection style |
| Product/partner seeds | `industry_seeds.py`, import UI seed packs | **Reuse** as exemplars |
| Image attach | `image_import.py` | **Reuse** for photo→attach only |
| Conversational onboarding | `expert/ask.py` | **Extend** last — interview → same `IngestBatch` |

**Net-new only:** document classifier, PDF/OCR extractors (per type), dependency graph,
multi-file job orchestration, review UI for multi-doc plans, layout-template cache,
qwen3-vl license gate + optional vision tier.

## Pipeline (canonical)

```
CLASSIFY → EXTRACT → MAP+XREF → DEPENDENCY ORDER → VALIDATE/DRY-RUN → COMMIT
  (type)    (rows)     (live schema)   (topo-sort)      (human)         (batched RPC)
```

### Canonical data (`IngestBatch` — define once in ING-1)

```
IngestJob { id, connection_id, status, files[], tables[], graph, plan, review, commit_log }
IngestFile { id, filename, mime, doc_type, confidence, warnings[] }
IngestTable { model, rows[{values, confidence, source_ref}], natural_key_fields[], refs[] }
IngestRef { from_table, field, to_model, unresolved? }
IngestPlan { ordered_steps[{model, table_ids[], parallel_ok}], gaps[] }
```

Stages 3–6 consume only `IngestTable` / `IngestPlan`.

## Wave order (critical path)

```
ING-0 license + model inventory
  └─▶ ING-1 schema + job store + orchestrator skeleton
        ├─▶ ING-2 classify (closed vocab)          ┐
        ├─▶ ING-3 extract CSV/XLSX (wire existing)  ├ parallel after ING-1
        └─▶ ING-4 extract PDF/vision (gated)       ┘
              └─▶ ING-5 map + dedupe xref
                    └─▶ ING-6 dependency order
                          └─▶ ING-7 dry-run review UI
                                └─▶ ING-8 commit + idempotent re-upload
                                      └─▶ ING-9 Expert interview feed (optional)
```

**Parallelize:** ING-2 / ING-3 / ING-4 after ING-1. Prefer ING-3 before ING-4 so CSV
path proves Stages 3–8 without OCR cost.

## Vertical slices (ship value early)

| Slice | Docs | Models (typical) | Unlocks claim |
|-------|------|------------------|---------------|
| **A (MVP)** | contacts, products, price list (CSV/XLSX) | `res.partner`, `product.template`/`product.product`, `product.pricelist.item` | Multi-file order + dry-run + upsert |
| **B** | CoA (+ opening TB later) | `account.account` via l10n-aware map; TB via Odoo opening-balance path only | Fiscal caution |
| **C** | BoM (PDF + nested) | `mrp.bom` / `mrp.bom.line` + product xref | Nested extract |
| **D** | Employee roster (org only) | `hr.employee` fields; **no wage/payroll columns** | Protected boundary |
| **E** | Expert interview → same batch | synthetic tables | No-document onboarding |

Do not start Slice C until A’s GATE is green. Slice B requires PCM + l10n checks every commit.

## Guardrails (non-negotiable)

- **Payroll / compensation:** extract org fields only; never auto-write wage/tax fields
  (PCM Tier-1 / Doc 3 §19).
- **Opening balances:** never raw `account.move.line` create from extract — route through
  Odoo’s opening-balance mechanism + explicit human confirm.
- **CoA:** offer align-to-`l10n_*` for company country; flag legacy numbering mismatches;
  do not silently invent accounts that break fiscal localization.
- **UoM:** resolve against live `uom.uom` (category-aware) before commit.
- **Low confidence:** classify/extract below threshold → user confirm (ground-or-decline).
- **qwen3-vl license:** Tongyi Qianwen — resolve EU/deploy constraints in ING-0 before any
  vision dependency ships to customers.

## Success metrics (honest “weeks → minutes”)

Measure: time-to-reviewed-plan for a 3-file batch (partners + products + pricelist) on
docker-19 vs manual CSV import sequencing. Human review remains mandatory for financial
slices. Do not claim zero-touch CoA/BoM commit.

## Card file

Executable checklists: `plans/cards/WAVE-17-INGEST.md`.

## Session start prompt (paste for agents)

```
Execute the next unchecked card in plans/cards/WAVE-17-INGEST.md.
Read plans/UNIVERSAL_INGESTION_PIPELINE.md §Reuse map first.
Do not rebuild data_import, bulk_suite/dedupe, or invoicing_l10n.
Emit/consume IngestBatch only. Flip checkboxes honestly. Run the card GATE.
Update plans/PROGRESS.md + root PROGRESS.md. No commit until I approve.
```
