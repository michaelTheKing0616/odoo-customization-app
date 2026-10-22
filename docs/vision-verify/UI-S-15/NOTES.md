# UI-S-15 · Automations (Studio-bar visual leap)

Status: Studio-bar visual leap on page + harness. **Not marked DONE.**

`au-honesty` chips folded into bar (Option A / promote). AutomationSessionBar unchanged.

Gaps: gating Callout for Online plans remains situational in paper.


---

## Prior elevate notes (archive)

# UI-S-15 · Automations (Studio-bar visual leap)

Status: Studio-bar visual leap on page + harness. **Not marked DONE.**

au-honesty chips folded into bar. AutomationSessionBar unchanged.

Gaps: Online gating Callout remains situational in paper.


---

## Prior elevate notes (archive)

# UI-S-15 Automations: vision notes

Pressure 8. Route `/connections/[id]/automations`, harness `/e2e/automations?state=…` plus `/e2e/automation-caps` and `/e2e/automation-gating`.
Primary CTA: **Create automation** / **Save** / **Generate module zip** (teal). One filled primary per view.

## Design read
Operate-mode list → composer. Basalt chrome, one teal accent, amber only for unsaved session chrome. Cinnabar never appears in UI. Completeness ≠ Cert ≠ Autopilot honesty chips stay visible. Python/`state=code` is Option A only (module → sandbox → promote). Live `code_live` is not listed. Webhooks keep advanced confirmation.

## Playbook rules applied
- One filled primary per view (Create / Save / Generate module zip).
- No eyebrow kickers. No em dashes in Automations-authored copy.
- Inset hairline list for rules and snapshots instead of stacked boxed cards.
- Conversational prompt box craft at the top of the composer (local parse only).
- Empty and Option A / webhook / gate states use what/why/next guides.
- Dark mode via tokens (`composer-dark` shots).

## States captured (`after-*`)
| State | What to verify |
|-------|----------------|
| detail | Selected rule, teal Save, hairline list selection |
| composer | Prompt craft, When / Apply on / Then panels, Create automation |
| empty | what/why/next empty guide, Create automation primary |
| code | Option A guide + three steps, Generate module zip, no live Python CTA |
| webhook | Webhook advanced confirmation guide + URL fields |
| gate | GatingCallout three-options + gate guide |
| online | Option A + Online honesty (no live Python install claim) |
| composer-dark | Dark tokens, contrast |

Desktop is 1440 wide and mobile is 390. Prefer overflowX=0 on harness shots.

## Capture
```bash
cd apps/web
PLAYWRIGHT_E2E_BUILD=1 NEXT_PUBLIC_E2E=1 npx next dev --turbopack -H 127.0.0.1 -p 3015
NODE_PATH=$PWD/node_modules node ../../docs/vision-verify/UI-S-15/capture.cjs   http://127.0.0.1:3015 ../../docs/vision-verify/UI-S-15 after
```

## Tests
```bash
cd apps/web
npx vitest run src/components/automations src/lib/automationForm.test.ts src/components/AutomationActionKindSelect.test.tsx
# harnesses: e2e/automation-caps.spec.ts e2e/automation-gating.spec.ts e2e/automations-prod.spec.ts
```

## Gaps
- Prompt parser is deterministic heuristics only (no LLM). Multi-sentence briefs may need manual edits.
- Production Automations page still loads real APIs; vision shots are harness-only except where prod e2e mocks apply.
- `code_live` remains in API types and ADVANCED_CONFIRM_COPY for server errors, but the UI never offers it.
- GatingCallout option copy still follows the locked COPY_GUIDE three-options template (may contain em dashes from that template).

## Must not
- Em dashes or eyebrow kickers in Automations-authored UI copy
- Orange or cinnabar CTAs, or Odoo purple
- Live Python / `state=code` applied from this screen
- More than one filled primary
- Claim Completeness = Cert = Autopilot

## Smoke results (2026-10-05 Lagos)
- Vitest: 23/23 green (`automations` components + `automationForm` + ActionKindSelect).
- Vision: 16 PNGs, all harness shots overflowX=0 (desktop 1440 + mobile 390, including composer-dark).
- Live harness smoke on `:3016`: `/e2e/automations`, `/e2e/automation-caps`, `/e2e/automation-gating` HTTP 200.
- Caps: Odoo 16 greys `update_field`; `code_live` option count=0; `python_module` present; Odoo 19 enables update_path.
- Gating: title + 3 options render.
- Full Playwright suite via config webServer was not re-run here (config triggers `next build` which fails on unrelated eslint elsewhere). Caps/gating behavior verified via direct Playwright against the E2E dev server.
