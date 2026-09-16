# Config Command Center — UI walkthrough (tested)

Verified on `premium-local-tip` with vitest + API catalog tests.

## Path

Operate → **Instance Config** (`/connections/:id/config`)

## Flow (happy path)

1. **Home grid** — recipe cards load from `GET /config/recipes` (`data-testid=config-command-center`, `recipe-card-*`).
2. **Day-1** — Open → company fields prefilled from `listCompanies` → **Dry-run** shows `recipe-plan-preview` → Confirm phrase → Apply.
3. **Document numbering** — select keys → dry-run → apply pack.
4. **Apps pack** — pick pack → Preview deps → Install.
5. **Import / Bulk** — P1 cards deep-link to `/import?gallery=1` and `/bulk-suite?recipes=1`.
6. **Settings board / Multi-company / Master packs** — P2 panels with dry-run → confirm → apply.
7. **Expert controls** — Disclosure below Command Center keeps legacy expert form.

## Automated coverage

| Check | Suite |
|-------|--------|
| Recipe cards + Day-1 dry-run | `apps/web/src/components/config/ConfigCommandCenter.test.tsx` |
| Online URL / hosting helpers | `apps/web/src/lib/odoo-hosting.test.ts` |
| Normalize Online deep links + parse `19.4` | `packages/odoo-client/tests/test_models.py` |
| Recipe catalog API | `apps/api/tests/test_config_recipes.py` |

## Manual spot-check (founder)

- [ ] Cards render premium density on dark/light
- [ ] ConfirmDialogV2 phrase gate on Apply
- [ ] Import gallery highlight with `?gallery=1`
- [ ] Bulk recipe chips with `?recipes=1`
- [ ] Online connect tip appears for `*.odoo.com` URL
