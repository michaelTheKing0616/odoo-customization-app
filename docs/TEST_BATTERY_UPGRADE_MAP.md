# Test battery — upgrade-map / multi-major regression

How to re-run the rigorous suite that covers the upgrade-map arc (caps, encoders, view adapters, Power Ops `min_major`, kanban arch, Playwright harness).

**Checker (2026-07-28):** PASS — [Checker grade test rigor](ea740884-aca9-41f1-84e9-90649bed2922). Spot re-run: `uv run pytest` multimajor suites **54 passed**; vitest `capabilities.test.ts` **51 passed**.

## Commands

```bash
# odoo-client multimajor encoders + view adapters
cd packages/odoo-client && uv run pytest tests/test_automation_encoders_multimajor.py tests/test_views_adapters_multimajor.py -q

# Web capability helpers
cd apps/web && pnpm exec vitest run src/lib/capabilities.test.ts

# Broader unit (when stacks not required)
cd packages/odoo-client && uv run pytest tests/ -q -m "not integration"
cd apps/api && uv run pytest tests/ -q -m "not integration"

# Playwright automation-caps + production Automations route
cd apps/web && pnpm exec playwright test e2e/automation-caps.spec.ts e2e/automations-prod.spec.ts

# Live M2/A4 finish smokes (Odoo 19 :8069)
cd packages/odoo-client && uv run pytest tests/test_integration_m2_a4_live.py -m integration -v
```

Live integration (`@pytest.mark.integration`) needs Docker majors up (19→8069 … 16→8072). Skipped when stacks are down.

## What is covered strictly

| Area | Assert style |
|------|----------------|
| Caps helpers | fail-closed, majors 15–19, `mutationAllowed`, currency/scaffold gates |
| `automation_v16` | `UnsupportedOnOdoo16Error` + exact message fragments; v17–19 encode `update_path` |
| View adapters / list vs tree | 16–19 matrix; manifest normalization |
| Power Ops | `probe_recipe` `min_major` exact reason strings |
| Kanban arch | adversarial parse / inherit unwrap |
| Playwright | `/e2e/automation-caps` + `automations-prod` — grey-out + unprobed fail-closed |
| M2/A4 live | activity + form attrs + webhook/followers/sms + on_message trigger; map/gantt/cohort skip when type absent |

## Honest gaps

- Enterprise live RPC requires an EE Docker image (not in CE gate) — string `+e` + Studio warn only
- Playwright covers **production** Automations route (`e2e/automations-prod.spec.ts`) with mocked API
- `currency_field` live inject covered in `test_integration_currency_field_live.py` (19 persist / 16 omit)
- Odoo 18 live suite deepened (list models, view arch, ACL)
- Map/Gantt/Cohort **view type** may be absent on stock CE — Designer still emits arch; live create skips honestly

Maker must not claim EE live closed without an Enterprise instance.
