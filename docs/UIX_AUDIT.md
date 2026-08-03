# UIX-5 audit — copy, states, gating (REM-12)

Date: **2026-08-03**  
Scope: post-migration kit surfaces, COPY_GUIDE compliance, gating template instances, a11y gate.

## Copy sweep (sample confirmations)

| Rule | Status | Notes |
|------|--------|-------|
| Sentence case headings | Pass | PageHeader titles use sentence case across shell pages |
| Verb-first buttons | Pass | Primary actions: "Save", "Run dry-run", "Ask Expert", "Connect" — no bare "Submit" |
| Destructive scope stated | Pass | ConfirmDialog v2 + bulk ops name record counts / risks |
| No exclamation marks in product UI | Pass | Marketing landing restrained; trial banner uses neutral tone |
| Glossary terms (Draft/Apply/Promote/Snapshot/Rollback/Sandbox) | Pass | Used consistently in nav + COPY_GUIDE surfaces |
| Error recovery hints | Partial | `ErrorNotice` on pages; toast retry wiring on bulk flows — not every toast names Expert |

## Gating template instances (what → why → options)

| Surface | Feature | Template location |
|---------|---------|-------------------|
| Nav lock | View designer (`view_inject_inherit`) | `nav.ts` → sidebar Callout on click |
| Nav lock | Website (`website` module) | `nav.ts` → sidebar Callout |
| Nav lock | Automations (`base_automation_safe_triggers`) | `nav.ts` → sidebar Callout |
| Page gate | Automations unavailable (Odoo Online / edition) | `automations/page.tsx` → `GatingCallout` from `/automations/gate` API |
| Page gate | Approvals unavailable | `automations/page.tsx` → `GatingCallout` (approvals section) |
| E2E harness | Automation caps demo | `/e2e/automation-gating` |
| Billing | Plan feature locked | `UpgradeSheet` + `GatingCallout`-style Callout (MON-4) |
| Entitlement | Feature key 403 | `upgrade-context.tsx` interceptor → upgrade sheet |

Nav gating copy (three-part):

1. **Designer** — Title: "View designer needs inherit injection" / Why: version or edition lacks safe inherit / Options: export module, upgrade major, use staging  
2. **Website** — Title: "Website module required" / Why: `website` not installed / Options: install in Apps, use native editor  
3. **Automations** — Title: "Automations are limited on this instance" / Why: safe triggers unavailable / Options: export server actions, supported Odoo version  

## Page × state matrix (8 primary operate/govern pages + shell)

Legend: **Y** = designed kit state present · **P** = partial · **—** = not applicable

| Page | Empty | Loading | Error |
|------|-------|---------|-------|
| Shell / Overview | P (tables empty when no data) | Y (react-query skeletons on hub) | Y (`ErrorNotice`) |
| Journal | Y (`EmptyState`) | Y (fetch spinner) | Y |
| Bulk Suite | P (section placeholders) | Y | Y |
| Reminders | P | Y (button loading) | Y |
| ID Generator | P | Y | Y |
| Reports | P | Y | Y |
| Housekeeping | P | Y | Y |
| Approvals | P | Y | Y |
| Import | P (stepper) | Y | Y |

**Honest gaps (UIX-4c still open):** Power Ops, Pipelines, Config, Menus, ModuleSpec, Settings — kit restyle partial; empty states not uniformly audited here.

## Icon audit

| Check | Result |
|-------|--------|
| `lucide-react` imports outside `components/ui/icons.ts` | **0** (grep 2026-08-03) |
| Icon-only buttons have `aria-label` | Pass on shell top bar (Expert, theme, palette) |
| Fixed mapping module | `src/components/ui/icons.ts` |

## Accessibility (axe)

Gate: `apps/web/e2e/a11y-primary.spec.ts` — `@axe-core/playwright` on 8 primary pages (mocked API).

Rules disabled for harness noise: `document-title`, `html-has-lang`, `label` (mock forms).

Target: zero **serious** / **critical** violations.

```bash
cd apps/web
pnpm exec playwright test e2e/a11y-primary.spec.ts
```

## Vision-verify artifacts

Gate: `apps/web/e2e/vision-verify-sweep.spec.ts` + existing designer/overlay specs.

```bash
cd apps/web
pnpm exec playwright test e2e/vision-verify-sweep.spec.ts e2e/designer-vision.spec.ts
```

Output: `docs/vision-verify/*-{light,dark}.png` — see `docs/vision-verify/README.md`.
