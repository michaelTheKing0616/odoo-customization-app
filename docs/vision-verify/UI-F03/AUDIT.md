# UI-F03 — EmptyState and Skeleton evidence (2026-10-05)

Scope: the six surfaces changed in this UI-F03 batch.

- Connection shell loading: `AppShell` while the connection loads, plus the `connections/[id]/layout.tsx` Suspense fallback.
- `/settings`
- `/settings/billing`
- `/settings/trust-safety`
- `/admin`
- `/pipelines`

Evidence comes from `apps/web/e2e/a11y-ui-f03.spec.ts`. It ran against `pnpm dev` on `:3002` with the API mocked by `mockConnectionApi` plus spec overrides. Reduced motion was emulated. Desktop is 1440×900 and narrow is 390×844, both full page.

## axe (wcag2a/aa, 21a/aa; same rule set as `a11y-primary.spec.ts`)

Raw results: `axe-results.jsonl`.

| Route / state | Desktop | 390 |
|---|---|---|
| Connection shell loading | 0 | 0 |
| `/settings` (populated: 1 audit row) | 1 critical, `aria-required-children` | same |
| `/settings` loading | 0 | 0 |
| `/settings` empty (keys + audit) | 0 | 0 |
| `/settings/billing` (plan) | 0 | 0 |
| `/settings/billing` loading | 0 | 0 |
| `/settings/billing` empty (no plan) | 0 | 0 |
| `/settings/trust-safety` | 0 | 0 |
| `/settings/trust-safety` loading | 0 | 0 |
| `/admin` (empty lists) | 0 | 0 |
| `/admin` loading | 0 | 0 |
| `/pipelines` (empty list) | 0 | 0 |
| `/pipelines` loading | 0 | 0 |

The one critical violation is pre-existing and was not introduced by UI-F03. In the shared `components/ui/DataTable.tsx`, the wrapper `<div role="grid">` contains a native `<table>`, which `grid` does not allow as a child. It fires on any page where a DataTable has rows. It shows on `/settings` here only because the audit row was mocked. Fixing it belongs to the table card (UI-F11), not this one. The spec keeps the assertion and stays red until that fix lands.

## Screenshots

For each route the default state is `<slug>-desktop.png` and `<slug>-390.png`. Loading and empty states add `-loading` or `-empty` before the width.

- `connection-shell-loading-{desktop,390}.png`
- `settings-{desktop,390}.png`, `settings-loading-*`, `settings-empty-*`
- `settings-billing-{desktop,390}.png`, `settings-billing-loading-*`, `settings-billing-empty-*`
- `settings-trust-safety-{desktop,390}.png`, `settings-trust-safety-loading-*`
- `admin-{desktop,390}.png`: the default mock is empty, so this is the empty state. Also `admin-loading-*`.
- `pipelines-{desktop,390}.png`: the default mock is empty, so this is the empty state. Also `pipelines-loading-*`.

The `layout.tsx` Suspense fallback is not reachable in a real render. SSR and hydration both get past it, and with JS blocked the server HTML already shows AppShell's pending branch. The vitest `connections/[id]/layout.test.tsx` covers it.

## UX audit (12 rows, `T7_UI_MOTION_COPY.md`)

| Area | Result | Note |
|---|---|---|
| Hierarchy | Pass | Each empty state has one action (Name a key, Name a pipeline, Sign in) or none where no add action exists (admin, audit). Skeletons keep the real heading in place, so reading order does not jump. |
| IA | Pass | Page titles and section headings stay visible during loading. Empty titles reuse the section noun ("No pipelines yet" under "Pipelines"). |
| Interaction | Pass | Empty-state actions are `Button size="sm"` (≥ 24 px). "Sign in" is a real link styled as a button through `asChild`. |
| Feedback | Pass | Every loading block is `role="status"` with sr-only text ("Loading pipelines.", for example), and the skeleton shapes are hidden from screen readers. Announcement timing is not observable in a screenshot. |
| Errors | Pass | Trust & safety and admin no longer show a skeleton or "No … yet" when the request failed. The error notice stands alone. |
| Accessibility | Issue | axe is clean on every state I introduced. The pre-existing DataTable `aria-required-children` is still present, as noted above. Focus order and focus visibility are not observable here. Focus after "Name a key" and "Name a pipeline" is proven in vitest. |
| Cognitive load | Pass | Empty copy says what will appear, so nothing has to be remembered. The action moves focus to the field that fixes the empty state. |
| Trust | Pass | No invented numbers. Billing empty copy was corrected to drop "seats", which the page does not show. The shell keeps the honest port-8001 hint after 3 s. |
| Copy | Pass | See the critique below. No 1 on Accuracy or Ethics. |
| Forms | Not observable | No form fields were changed. The name inputs gained ids; the settings key input gained `aria-label="Key name"`. |
| Performance | Pass | Skeletons render on first paint with no spinner and no delay. With reduced motion, `base.css` cuts the pulse animation to 0.01 ms. |
| Business goal | Pass | Operators see the page structure right away and are pointed at the one step that fills the list. |

Not observable from screenshots: keyboard traps, screen-reader output, latency.

## Copy critique (9 dimensions, scored 1/3/5)

Scores are in this order: Clarity, Task fit, Actionability, Accuracy, Tone, Concision, Accessibility, Ethics, Slop-free.

| String | Scores |
|---|---|
| "No API keys yet" / "Keys you create appear here with their prefix and a Revoke button." + **Name a key** | 5 5 5 5 5 5 5 5 5 |
| "No audit entries yet" / "Each POST, PUT, PATCH, or DELETE request to this API appears here with its status and duration." | 5 5 3 5 5 3 5 5 5 |
| "No plan to show" / "Your plan, status, and project slots appear here after you sign in with an account." + **Sign in** | 5 5 5 3 5 5 5 5 5 |
| "No users yet" / "Accounts appear here after someone signs up, with their verification status." | 5 5 3 5 5 5 5 5 5 |
| "No workspaces yet" / "Workspaces appear here once a user creates one, with beta partner and write-pause controls." | 5 5 3 5 5 3 5 5 5 |
| "No workspaces to report on" / "Each workspace appears here with its bulk runs, refusals, aborts, and restores, starting at zero." (revised: the API returns one row per workspace, zeros included) | 5 5 5 3 5 3 5 5 5 |
| "No pipelines yet" / "Pipelines you create appear here with their staging and prod connections." + **Name a pipeline** | 5 5 5 5 5 5 5 5 5 |
| sr-only loading lines ("Loading the audit log.", "Loading this connection.", and so on) | 5 5 3 5 5 5 5 5 5 |

- **Biggest problem: the billing empty state.** It also shows when entitlements fail for a reason other than being signed out, such as a 500, so Accuracy scores 3. Revision: show "No plan to show" only on 401 and route other failures to an error notice. That needs a small `useEntitlements` error-kind change, which is out of scope here. Confidence is medium. What would settle it: the API's status code contract for `/api/billing/entitlements`.
- **Telemetry, Accuracy 3.** It is unverified whether a workspace with zero activity returns a row. Revision if it does: "Bulk runs, refusals, aborts, and restores appear here for each workspace." Confidence is low. What would settle it: one call to `/api/admin/trust-telemetry` on a fresh workspace.
- **Audit and admin, Actionability 3.** They have no add action by design. That is acceptable under "one action if one exists".
