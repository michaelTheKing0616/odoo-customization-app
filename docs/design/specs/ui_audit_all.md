# UI audit all (card UI-AUDIT-ALL)

Tope verdict (21 Oct): the shipped UI is **really really poor**. This index holds the audit **method** only (≤120 lines). Every score row and every design-touch line lives under `docs/design/specs/ui_audit/<NN>-<area>.md`. Baseline contact sheets are ui-build work; until a sheet exists the path is `missing` and the score stays `below` (never `at`).

## Job

Score each named route in `docs/build-plan/UI_REFERENCE_MAP.md` L31–44 against its pack area bar (`07_UI_EXCELLENCE_PROTOCOL.md` Stage 2). One primary action per screen; gap list feeds the owning ui-build card. This card does not implement screens or touches.

## References

Per row: the two products on that area’s map row (L9–27). Paste `REFERENCE_NOTES.md` entries when UI-REF-STUDY lands; until then treat pack `MANIFEST.md`, `motion/MOTION_NOTES.md`, and area `_contact/` as sources. Adopt 3–5 patterns per screen on ui-build; keep Ingenium identity deliberate.

## States

Rate every §3 state in each ui-build spec: **loading** (skeleton, honest verbs), **empty** (starter actions), **partial**, **error** (fix path), **offline**, **no permission**, **too much data**, **read-only**, **success** (stake-sized). Plain words only.

## Motion

Borrow measured targets from the pack (menus/Cmd-K ~133–200 ms; route change skeleton with fixed sidebar ~67–100 ms; row hover tint only). Enter 100–250 ms ease-out; leave ~140 ms; no spinner-only page loads; reduced motion → fades, no keystone drop.

## Keyboard

Document per-screen maps on ui-build; global craft from areas 02 and 09 (Cmd-K, go-to pairs, list J/K, Esc ladder). Hold Cmd/Ctrl for hint keycaps where applicable.

## Accessibility

Axe-clean, focus ring token, screen-reader copy reviewed, contrast via paired on-* tokens (light-ish surfaces → dark ink), hit targets in Dense mode.

## Responsive

Plan at **390 / 768 / 1024 / 1440 / 1920**; shell and tables must not clip; mobile rules from area 18 apply everywhere.

## Density

Comfortable default; Compact and Dense where lists dominate; never shrink text below legible sizes; per-area memory on ui-build.

## Dark

Basalt surfaces, limestone text, chart desaturation; parity checks at 1440×900 and 390×844 on ui-build contact sheets.

## F1 shared components (compose only)

§3 foundation: state kit, virtualised tables, database switcher, Cmd-K, ConfirmDialog (target naming), ErrorNotice, Undo toast. Cross-cutting cards: **F1-CMDK** (02), **F1-NAV / F1-SWITCHER** (03), **F1-STATES** (17), **F1-RESPONSIVE** (18), **UI-CHARTS-*** (16). Re-implementing on a screen card → send back.

## Split rows (Tope, 25 Oct)

`/` and `/connections/[id]` each have two score rows on purpose. Area 01 is the shell frame. Area 04 is the page content. Read them as a split, not as a duplicate owner.

## Score row index

| Area | File | Rows | Ref A · Ref B |
|---:|---|---:|---|
| 01 | `ui_audit/01-shell-lists-history.md` | 19 | Linear · Stripe Dashboard |
| 02 | `ui_audit/02-cmd-k.md` | 0 | Linear · Vercel |
| 03 | `ui_audit/03-sidebar-switcher.md` | 0 | Arc · Vercel |
| 04 | `ui_audit/04-home-agency.md` | 3 | Stripe · Vercel |
| 05 | `ui_audit/05-approvals.md` | 3 | Superhuman · Linear Inbox |
| 06 | `ui_audit/06-connect-onboarding.md` | 7 | Stripe · Vercel |
| 07 | `ui_audit/07-app-studio.md` | 7 | Claude app · Cursor |
| 08 | `ui_audit/08-designer-canvas.md` | 9 | Figma · Framer |
| 09 | `ui_audit/09-records-tables.md` | 11 | Attio · Notion |
| 10 | `ui_audit/10-flow-canvas.md` | 4 | n8n · Make |
| 11 | `ui_audit/11-code-runner.md` | 3 | Zed · Cursor |
| 12 | `ui_audit/12-bots.md` | 0 | Claude app · Cursor agent |
| 13 | `ui_audit/13-copilot-panel.md` | 2 | Granola · Fathom |
| 14 | `ui_audit/14-money-guard.md` | 6 | Stripe · Mercury |
| 15 | `ui_audit/15-settings-billing.md` | 3 | Linear · Stripe |
| 16 | `ui_audit/16-charts.md` | 0 | Stripe · Vercel |
| 17 | `ui_audit/17-empty-states.md` | 0 | Things 3 · Arc |
| 18 | `ui_audit/18-mobile.md` | 0 | Linear · Superhuman |
| 19 | `ui_audit/19-docs.md` | 3 | Stripe docs · Linear docs |

**80** score rows total (78 `page.tsx` routes outside `/e2e`, plus a second row for `/` and for `/connections/[id]`: area 01 frame, area 04 content). `redirect-only` rows: DEC-024 fold/retire/hide/redirect routes in areas 01, 08, 09, 11.

## Design touches (AC2)

**162** touches (APPROVED 17 Oct): one line each in area files — section *N* → area *N* file; sections **20–21** → area **19**. Format: `proposed UI-TOUCH-NNN` until an ui-build card lands the touch. Implementing touches is **not** this card.

## AC status (this card)

AC1/AC2 **not** marked done here. AC3 method sections above; row-level refs in area files.
