# UI-S-16 · Approvals (Studio-bar visual leap)

Status: Studio-bar visual leap on page + harness. **Not marked DONE.**

`ap-honesty` chip stack folded into OperateStudioBar via approvalsHonestyGuide. Inbox link in title actions. Legacy `approvals-honesty` sr-only for e2e.

Gaps: processes engine strip inside processes pane unchanged.


---

## Prior elevate notes (archive)

# UI-S-16 · Approvals (Studio-bar visual leap)

Status: Studio-bar visual leap on page + harness. **Not marked DONE.**

ap-honesty chip stack folded into OperateStudioBar. Inbox link in title actions.

Gaps: processes engine strip inside processes pane unchanged.


---

## Prior elevate notes (archive)

# UI-S-16 Odoo approval rules: vision notes

Pressure 6. Route `/connections/[id]/approvals`, harness `/e2e/approvals?state=…`.
Primary CTA: **Deploy a rule** (teal). One filled primary per view.
Copy labels the screen **Odoo approval rules** so it is not confused with `/approvals` plan inbox (UI-S-50).

## Design read
Operate-mode rules list + composer. Basalt chrome, one teal accent, amber only for pending / draft badges. Cinnabar never appears in UI. Honesty chips show Community vs Studio engine. An inbox note links to Approval inbox without merging the two products.

## Playbook rules applied
- One filled primary per view (Deploy a rule / Create draft request / Approve on pending entries).
- No eyebrow kickers. No em dashes in Approvals-authored copy.
- Inset hairline lists for rules, entries, types, and requests instead of stacked boxed cards.
- Empty and error states use what/why/next guides.
- Dark mode via tokens (`default-dark` shots).

## States captured (`after-*`)
| State | What to verify |
|-------|----------------|
| default | Title Odoo approval rules, teal Deploy a rule, hairline rules list, honesty chips |
| empty | what/why/next empty guide, Deploy a rule primary |
| error | alert guide with Retry |
| loading | skeleton rows matching layout |
| processes | processes tab, Create draft request primary, types/requests lists |
| studio | Studio engine chip |
| pending | pending entry with Approve primary + Reject secondary |
| default-dark | Dark tokens, contrast |

Desktop is 1440 wide and mobile is 390. Prefer overflowX=0 on harness shots.

## Capture
```bash
cd apps/web
PLAYWRIGHT_E2E_BUILD=1 NEXT_PUBLIC_E2E=1 npx next dev --turbopack -H 127.0.0.1 -p 3016
NODE_PATH=$PWD/node_modules node ../../docs/vision-verify/UI-S-16/capture.cjs \
  http://127.0.0.1:3016 ../../docs/vision-verify/UI-S-16 after
```

## Tests
```bash
cd apps/web
npx vitest run src/lib/approvalScreen.test.ts src/components/approvals
```

## Gaps
- Production page still loads real APIs; vision shots are harness-only.
- No separate deploy endpoint beyond createApprovalRule; Deploy a rule maps to create.
- Processes panel still links to Wizard templates (out of scope to redesign wizard).
- Nav label updated to "Odoo approval rules"; sidebar width may truncate on narrow shells.

## Must not
- Em dashes or eyebrow kickers in Approvals-authored UI copy
- Orange or cinnabar CTAs, or Odoo purple
- Confuse this screen with `/approvals` plan inbox
- More than one filled primary per view
- Touch wizard, access, menus, automations, job, designer, website, mail, qweb, studio, or the inbox

## Smoke results (2026-10-05 Lagos)
- Vitest: 10/10 green (`approvalScreen` + `approvals` components).
- Vision: 16 PNGs (7 states × desktop/mobile + default-dark × 2). All harness shots overflowX=0 after padding/clip fix.
- Live harness smoke on `:3016`: `/e2e/approvals?state=…` HTTP 200.
- Primary CTA label is **Deploy a rule** (teal). Page title and nav label are **Odoo approval rules**. Inbox disambiguation note + link present.
- Empty guide opens the composer via secondary "Open new rule form" so the composer keeps the single filled primary.
- Row Approve / Refuse stay secondary so button-rules and processes views each keep one filled primary.
