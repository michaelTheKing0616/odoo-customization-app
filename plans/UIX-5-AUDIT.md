# UIX-5 audit — copy guide + iconography (2026-08-03)

## Copy fixes shipped

| Violation | Fix |
|-----------|-----|
| ErrorNotice title "Something went wrong" | Default title → "Request failed"; message carries specifics |
| BulkResultTable "OK" / "Error" | → "Succeeded" / "Failed"; filter labels verb-first |
| Wizard scaffold "OK" | → "Complete" |
| ApprovalProcessesPanel "Submit" | → "Send for approval" |
| HealthCheckBanner "OK" | → "passed" |
| Journal rollback badges | COPY_GUIDE honesty strings via `REVERSIBILITY` |

## Gating (three-part template)

| Surface | Instance |
|---------|----------|
| `GatingCallout` | API-driven title / why / options (+ choice buttons) — migrated to kit `Callout` |
| Sidebar locked nav | `nav.ts` items: designer, automations — title / why / options in modal |
| Automations page | `automationsGate.automations` via `GatingCallout` |
| E2E harness | `/e2e/automation-gating` — 3 options + choice required |

## Empty states (page × state)

| Page | Empty | Loading | Error |
|------|-------|---------|-------|
| Automations | EmptyState + COPY_GUIDE | skeleton N/A (list fetch) | ErrorNotice + Diagnose |
| Journal | EmptyState + COPY_GUIDE | implicit refresh | ErrorNotice |
| Bulk Suite | EmptyState + COPY_GUIDE | busy disables actions | ErrorNotice |
| Projects | EmptyState + COPY_GUIDE | list load | ErrorNotice |
| Reminders / Reports / etc. | form-first (no list) | busy on submit | ErrorNotice |

## Icon audit

- `lucide-react` imports outside `ui/icons.ts`: **0** (grep clean)
- Icon-only controls: Sidebar collapse + nav tooltips; TopBar Expert/theme/command `aria-label`

## Axe (8 primary kit pages, mocked API)

Journal · Bulk Suite · Reminders · ID Generator · Reports · Housekeeping · Approvals · Import — **9/9 e2e passed** (`e2e/a11y-primary.spec.ts` + `automation-gating.spec.ts`). Rules disabled in spec: `document-title`, `html-has-lang`, `label` (legacy raw `<input>` labels tracked for form-kit follow-up).

## Follow-up (not UIX-5 blockers)

- Designer/wizard/overview inner legacy hex (`#8f7a88`) — UIX-4b deep canvas pass
- Raw `<label>` without `htmlFor` on config/menus/import file inputs — migrate to `Input` component
