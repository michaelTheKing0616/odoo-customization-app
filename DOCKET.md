# ingenium docket

## Any-customization contract (north star)
ingenium owns **ANY** Odoo customization (LLM + hard gates). Brief → correct grain → LLM authors under gates → sandbox proof → **human** promote on a capable host.

**Completeness ≠ Cert ≠ Autopilot. Promote stays human.**

Class-wide — never one-off for CBN / markup+WHT / one delivery note. Those three are proof **exemplars of classes**.

### Two host lanes
| Lane | Hosts | What lands |
|------|-------|------------|
| `online_metadata` | Odoo Online | Studio / metadata / data-XML only — **no** custom Python promote |
| `module_sh_or_self` | Odoo.sh / self-host | Option A installable modules (Python / QWeb / OWL) after sandbox prove |
| `external_connector` | any (alt) | FX/HTTP rate providers when Online cannot take Python |

### Grains (exactly one primary)
Stock/Config/Batch · Prefer `field_pack` · Residual `full_app` · Option A module · Report layout (metadata) · External connector · Refuse/escalate

Never Prefer when Option A required; never Online Python promote.

### Phased plan
| Phase | Focus | Status |
|-------|-------|--------|
| **P0** | Contract docs · intent class routes · `delivery_lane`/`artifact_kind`/`prove_status` stamps · Online+Python host gate · goldens | **done** (this tip) |
| **P1** | Job 1 FX/CBN rate CLASS + Job 2 markup+WHT + Job 3 report scrub | **done** |
| **P2** | Build spine — one entry, mode chips, handoff without re-briefing | **done** |
| **P3** | (was Job1) — closed under P1 | **done** |
| **P4** | Atlas elite | out of scope this tip |

## Done

- [x] **Intent → feature router (Expert)** — 2026-09-21  
  Plain language → best-fitting feature + can/can't. Expert UI (`IntentRouterPanel`), `POST /connections/{id}/expert/route` (+ `/batch-os/intent-route`). Deterministic catalog (YAML/JSON + Atlas + recipes); `AI_INTENT_LLM` optional only.

- [x] **P2 Build spine** — 2026-09-22  
  One Build entry with mode chips (Prefer / Residual / Option A / Stock Autopilot / Report / Connector). Handoff Draft↔App↔Autopilot carries brief + Diagnosis/Contract + delivery_lane stamps. Capability gaps always propose Option A scaffold when Live cannot finish. Expert routes into spine. Rubric battery green (184 no_app_db).

- [x] **P1 Job 1 FX / rate-provider sync CLASS** — 2026-09-22  
  CBN gold shortcut inside class (`currency_rate_cbn`); generic provider → Option A scaffold writing `res.currency.rate`; Online → `external_connector` runbook. Never Prefer / Nigeria Autopilot stock_reuse alone for live HTTP.

- [x] **P1 Job 2 sale markup % + WHT CLASS** — 2026-09-22  
  Option A fiscal/compute on sale.order: markup % drives amounts; WHT base = markup only; never purchase; Prefer/Studio % alone on Online = incomplete interim. Class scaffold + static prove.

- [x] **P1 Job 3 report layout scrub CLASS** — 2026-09-22  
  Parameterized QWeb address scrub (delivery slip / picking / invoice / sale). Option A seed + static prove (`partner_name_scrubbed`). Prefer Contacts delivery-notes excluded. Online checklist stays `online_metadata`; module zip `module_sh_or_self`.

- [x] **P0 any-customization class spine** — 2026-09-22  
  Class-wide intent routes (FX/CBN, markup+tax, report scrub, Prefer fields, residual app, python/owl cues). Contract/Diagnosis/generation IR stamps. Online+Python promote block with .sh/self-host/connector alternatives. Product name **ingenium** (lowercase).

## Batch OS (complete)
Money path + master data + all 8 Atlas classes + settings/access/automation/housekeeping recipes. See journal `?tab=batch|invoices|master` and Config Atlas.


## P2 rubric matrix (2026-09-22)

Release gates for Build spine — `AI_INTENT_LLM=off`, `apps/api/scripts/run_p2_rubric_battery.sh` + web vitest.

| Gate | Result |
|------|--------|
| Prefer Sales / Prefer Contacts stay Prefer (never residual-reshape Prefer) | **pass** |
| Residual full_app identity lock (never Prefer-reshape; no foreign pack canvas) | **pass** |
| Invent gates: uncued Type/Priority/Rate/Selection; one cue→one field; notes surface | **pass** |
| Pack adoption: positive product cues; shared workflow tokens ≠ pack identity | **pass** |
| Grain + delivery_lane stamps Prefer / residual / Option A / report / FX | **pass** |
| Online + Python Option A: promote blocked + honest alternatives | **pass** |
| Completeness ≠ Cert ≠ Autopilot | **pass** (honesty copy + stamps) |
| Job1/2/3 class acceptance goldens | **pass** |
| Intent: report scrub ≠ Contacts Prefer; markup+WHT ≠ Prefer-only; FX ≠ Nigeria Autopilot alone | **pass** |
| Flash-free / AI_INTENT_LLM=off deterministic floor | **pass** |
| Prefer Must-do constraint AST (Prefer + Delivery notes + automation/filter/reuse) | **pass** (root-fixed this tip) |
| Build spine handoff without re-briefing (brief + stamps) | **pass** |

**Battery:** 184 pytest passed (`no_app_db`). Web: 9 vitest passed (build-spine + handoff + bar).
