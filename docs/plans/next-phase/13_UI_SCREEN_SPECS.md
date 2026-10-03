# 13 — UI screen specs and screen cards (UI-S-01 … UI-S-62)

**This file is also the card file for every screen card.** A worker given `UI-S-nn` loads only this file. It reads the Global rules, the Card template, and its own block. Route list measured on 2026-10-02 from `apps/web/src/app/**/page.tsx`. The line count shown is the size of `page.tsx`.

## Global rules (apply to every block)

**States.** Every operate route must cover:
- default, hover, focus-visible, active, disabled;
- loading: a skeleton that matches the layout, and no spinner flash under 400 ms;
- empty: one sentence plus one action;
- error: what happened, why, and the next step, without blame, in the reader's language;
- success;
- offline-queued, if the action writes;
- stale, when the plan fingerprint no longer matches. Show "This plan changed. Review again." and void the approval.

A block lists only the states it adds or the ones that matter most.

**Motion (operate routes).**

| Event | Timing |
|---|---|
| Row hover | 80 ms |
| Save confirmation | 150 ms |
| Dropdown | 150–250 ms |
| Modal | 200–300 ms |
| Press | 100–160 ms `scale(0.97)` |

- Drawers use `cubic-bezier(0.32, 0.72, 0, 1)`. Enter and exit use `cubic-bezier(0.23, 1, 0.32, 1)`. An exit takes about 75% of its enter time.
- Animate `transform` and `opacity` only. Motion must be interruptible.
- No scroll-reveal, and no stagger in tables.
- The command palette opens instantly.
- With reduced motion, use opacity only, at 0.2 s or less.
- All values come from the UI-F09 constants file.

**Copy.**
- Sentence case. Errors follow "what, why, next step".
- Buttons are verbs that name the result, such as "Save the view" rather than "Submit".
- No "Oops", no exclamation marks, and nothing like "AI magic".
- Risk wording is honest. Write "This deletes 412 records. Undo is partial." and never "safe" unless a gate proved it.
- Numbers come from the API, never invented.

**Prime skills always loaded.** These live at `~/.cursor/skills/prime/<name>/SKILL.md`. Read each one, don't just name it.
- `ui-craft-dense-dashboard` (operate routes only)
- `accessibility`
- `feedback-patterns`
- `error-handling-ux`
- `no-ai-slop`
- `ux-copy`

A block's **Skills** line adds to this list.

**Accessibility, every route.**
- axe reports zero serious or critical issues.
- Every control is reachable by keyboard, in a logical order.
- Focus is visible, with at least 3:1 contrast.
- Color is never the only signal: the diff shows +/− signs and text labels.
- Targets are at least 24×24 px.
- Live regions use `polite`, except for blocking errors.
- At 390 px the page reflows without horizontal scroll, except for data tables, which scroll inside their own container.

**Vision.**
- Save `docs/vision-verify/UI-S-nn/desktop.png` at 1440×900 and `narrow.png` at 390×844.
- Add more state shots when the block asks for them.
- Then run the `skills/vision-verify-ui.md` check and record the 12-row UX audit table in the progress log.

**Shared do-not.**
- Do not weaken a lock in `01`. No business logic in components; it belongs in `src/lib/`.
- Do not change API contracts in a screen card.
- Restyle and split are separate cards. If the block says "split first", the UI-SP card must be DONE.
- Never loosen, delete, or re-baseline a test to go green.
- No new colors outside the tokens, no purple, and no pie charts.
- Cards nest at most two deep.
- Do not remove an honesty banner, an Option A warning, a gate callout, or a destructive-action confirmation.
- The typecheck error count must not go up.

**Commands.**

```bash
pnpm --filter @odoo-custom/web typecheck 2>&1 | rg -c "error TS"
pnpm --filter @odoo-custom/web test -- src/app/<route>
pnpm --filter @odoo-custom/web test:e2e e2e/a11y-primary.spec.ts
pnpm --filter @odoo-custom/web test:e2e e2e/vision-verify-sweep.spec.ts
```

The `/e2e/<name>` harness pages render the same components without a live Odoo connection. Use the harness twin named in the block for axe and screenshots.

## Card template (fill from the block)

```
ID: UI-S-nn   Track: T7   Title: Restyle <route>
depends_on: UI-F03, UI-F04, UI-F08, UI-F09 (+ split card if named)
Escalation pressure: from the block (default C1 U1 F1 K2 V2 I0 = 7 → Grok standard)
Read first: skills listed; the page file; its tests; the harness twin
Change: the page file and components it owns
Steps: 1 screenshot the current state (before) · 2 apply Global rules + block · 3 run tests · 4 axe · 5 after shots · 6 audit table
Acceptance:
 [ ] primary action is the visually dominant control and its label matches the block
 [ ] every state in Global + block reachable (Vitest or harness) and screenshotted where the block asks
 [ ] motion values from the constants file; reduced-motion test passes
 [ ] copy rules pass the 9-dimension critique (no 1 on Accuracy or Ethics)
 [ ] axe clean; keyboard walk recorded
 [ ] typecheck count unchanged; existing tests unchanged and green
Negative tests: the block's "Must not" line
Audit events: none (UI). Build log: before/after shot paths, audit table, critique
Rollback: revert the card's commit
Evidence of done: shot paths + test output + audit table in the progress log
```

---

## Marketing and auth (not dense; marketing motion allowed: hero fade ≤ 400 ms, no parallax)

### UI-S-01 `/` — landing (144)
- **Primary:** Connect your Odoo. **Skills:** `frontend-design`, `landing-page`. **Pressure:** 6.
- **States:** default only; any proof number comes from a measured source or is removed.
- **Copy:** say what it does in one line (customize Odoo Community through its public API, with a sandbox before production). Do not claim Enterprise Studio parity.
- **Must not:** stock illustrations, fake logos, fake testimonials, purple gradients.

### UI-S-02 `/pricing` (155)
- **Primary:** Choose a plan. **Skills:** `landing-page`. **Pressure:** 5. **Harness:** `/e2e/billing`.
- **States:** loading prices; price API error ("Prices didn't load. Try again." with a retry button); current plan.
- **Must not:** fake urgency, countdowns, hard-coded prices (`api.billingPlans` is the source). Test: `e2e/pricing.spec.ts` green.

### UI-S-03 `/privacy`, `/terms` (27 each)
- **Primary:** none (read). **Pressure:** 2 → cheap. Plain language, last-updated date, ≤ 70 characters per line.

### UI-S-04 `/login` (124)
- **Primary:** Sign in. **Skills:** `form-design`. **Pressure:** 7. **depends_on:** UI-F10.
- **States:** wrong credentials (does not say which field was wrong); locked account (what to do next); TOTP step; OAuth error; redirect after login.
- **A11y:** paste allowed in the password field; `autocomplete` set; WCAG 3.3.8 (no cognitive test).
- **Must not:** reveal whether an email exists.

### UI-S-05 `/signup` (78)
- **Primary:** Create account. **Skills:** `form-design`, `onboarding-ux`. **Pressure:** 5.
- **States:** inline validation after blur, not on each keystroke; email taken (neutral wording); success → verify email.

### UI-S-06 `/reset-password` (99)
- **Primary:** Send reset link. **Skills:** `form-design`. **Pressure:** 4 → cheap.
- **States:** sent (same message whether or not the email exists); token invalid or expired; new password set.

### UI-S-07 `/verify` (53)
- **Primary:** Continue. **Pressure:** 3 → cheap. **States:** missing token, invalid token, already verified, done.

### UI-S-08 `/connect` (537)
- **Primary:** Add connection. **Skills:** `form-design`, `onboarding-ux`. **Pressure:** 8.
- **States:** empty first run; probe in progress (stage text: reaching server, checking version, checking rights); probe failure with the cause (DNS, TLS, auth, unsupported major ≤ 15, 16 experimental); duplicate URL; success → overview.
- **Copy:** an API key is preferred over a password, and the screen says so. A secret field is write-only after save.
- **Must not:** echo the key or password back; accept `write_mode=production` (Job Autopilot refuses it).

## Connection operate (shell: `connections/[id]/layout.tsx` + `AppShell`; sidebar shows the active item)

### UI-S-10 `/connections/[id]` — overview (1225)
- **Split first:** UI-SP-OVERVIEW. **Primary:** Open the next build step. **Pressure:** 8.
- **States:** first run (nothing built yet: one action); connection unhealthy (last probe error and Re-check); stale schema fingerprint (Refresh schema).
- **Must not:** show vanity metrics.

### UI-S-11 `…/builder` (785)
- **Primary:** Add a field. **Harness:** `/e2e/builder`. **Skills:** `form-design`. **Pressure:** 7.
- **States:** no custom models; field name collision (suggest `x_` prefix); protected model refused (registry reason shown); offline-queued.

### UI-S-12 `…/designer` (1429)
- **Split first:** UI-SP-DESIGNER. **Primary:** Save the view. **Harness:** `/e2e/designer`, `/e2e/designer-ee`, `/e2e/designer-premium`. **Pressure:** 10 → Grok high effort.
- **States:** view XML invalid (line and reason); inherit conflict; preview stale.
- **Motion:** the inspector drawer only; the canvas does not animate layout per keystroke. Drag ghost uses transform.
- **A11y:** keyboard move of fields (`e2e/designer-keyboard.spec.ts` green).
- **Tests:** `designer-cmp3`, `designer-ee-panels`, `designer-premium`, `designer-vision` specs unchanged and green.

### UI-S-13 `…/menus` (409)
- **Primary:** Save the menu. **Harness:** `/e2e/menus`. **Pressure:** 6.
- **A11y:** tree pattern (arrow keys, `aria-expanded`). **States:** drag to an invalid parent (refused with a reason).

### UI-S-14 `…/website` (49)
- **Primary:** Publish. **Harness:** `/e2e/website`. **Pressure:** 4 → cheap.
- **States:** today the error is a bare string; replace it with what / why / next. Test: `e2e/website-editor.spec.ts`.

### UI-S-15 `…/automations` (696)
- **Primary:** Save the automation. **Harness:** `/e2e/automations`, `/e2e/automation-caps`, `/e2e/automation-gating`. **Skills:** `conversational-ux` (prompt box). **Pressure:** 8.
- **States:** gate callout (stays); `state=code` requested → Option A path (module → sandbox → promote), never live code; webhook requires the advanced confirmation.
- **Tests:** `automation-caps`, `automation-gating`, `automations-prod` specs.

### UI-S-16 `…/approvals` — Odoo approval process (320)
- **Primary:** Deploy a rule. **Pressure:** 6.
- **Copy:** label it "Odoo approval rules" so it is not confused with the `/approvals` plan inbox (UI-S-50).

### UI-S-17 `…/reports` (482)
- **Primary:** Save the report. **Pressure:** 6. **States:** QWeb render error (template line); preview loading.

### UI-S-18 `…/code-studio` (394)
- **Primary:** Validate. **Pressure:** 8. **Test:** `e2e/code-studio.spec.ts`.
- **Must not:** remove the Option A warning; offer Live Install of authored code before the authoring gate passes.

### UI-S-19 `…/access` (749)
- **Primary:** Save the right. **Harness:** `/e2e/access`. **Pressure:** 10 → Grok high effort. **depends_on:** O20-07 (Odoo 20 `ir.access` branch).
- **States:** Odoo 20 connection shows the `ir.access` model (one matrix, no separate record-rules tab); 17–19 show `ir.model.access` + `ir.rule`; R3 change → link to the plan card, no inline apply.
- **A11y:** the matrix is a real `table` with row and column headers.

### UI-S-20 `…/studio` — App Studio (1548)
- **Split first:** UI-SP-STUDIO. **Primary:** Generate. **Harness:** `/e2e/studio`, `/e2e/draft-studio`. **Skills:** `conversational-ux`, `agentic-ux-design-relationship-centric-interfaces`. **Pressure:** 11 → Grok high effort.
- **States:**
  - locked diagnosis card (host, inherit vs. new app, Option A vs. fields); Generate waits for the user to confirm it;
  - stage-accurate progress (T4-PROG);
  - an empty spec is capped at ReviewRequired, and the copy says so;
  - missing inherit host → offer to install the stock CE app;
  - gold or authored classify → no pack or stock chips.
- **Must not:** remove the honesty banners; show "Cert Gold" for an empty spec. Test: `e2e/studio-preview.spec.ts`.

### UI-S-21 `…/wizard` (1892)
- **Split first:** UI-SP-WIZARD. **Primary:** Generate the draft. **Pressure:** 10 → Grok high effort.
- **States:** clarify step asks one question at a time; scorecard (Completeness ≠ Cert ≠ Autopilot, labeled separately).
- **Tests:** `wizard-component`, `wizard-scaffold`, `wizard-scorecard` specs.

### UI-S-22 `…/job` — Job Autopilot (747)
- **Primary:** Run in sandbox. **Harness:** `/e2e/job`. **Pressure:** 9.
- **States:** recipe order (payments → inbound orders → messaging → hardware → statutory) as a stepper; smoke result per step; Promote shows a human confirmation step.
- **Must not:** offer Promote without that confirmation; offer production write mode.

### UI-S-23 `…/modulespec` (19)
- **Primary:** Validate. **Harness:** `/e2e/modulespec`. **Pressure:** 3 → cheap. Hidden from the sidebar; deep link from the build spine.

### UI-S-24 `…/projects` (19 + components)
- **Primary:** Apply the project. **Harness:** `/e2e/projects`. **Pressure:** 7.
- **Motion:** diff panes use `ListLayout` from UI-F09. **A11y:** additions and removals use +/− and text labels.

### UI-S-25 `…/expert` (60)
- **Primary:** Ask. **Harness:** `/e2e/expert`. **Skills:** `conversational-ux`. **Pressure:** 6.
- **Must not:** let the drawer and the page diverge (one component). Test: `e2e/shell-expert.spec.ts`, `expert-flows.spec.ts`.

### UI-S-26 `…/import` (593)
- **Primary:** Commit. **Skills:** `form-design`. **Pressure:** 8.
- **States:** dry-run before commit (counts: create, update, skip, error); column mapping errors per row; commit progress; partial failure with downloadable errors.

### UI-S-27 `…/id-generator` (428)
- **Primary:** Download the CSV. **Pressure:** 4 → cheap.

### UI-S-28 `…/ingest` (504)
- **Primary:** Commit. **Harness:** `/e2e/ingest`. **Pressure:** 7. **States:** dry-run; override (needs a reason). Test: `e2e/ingest.spec.ts`.

### UI-S-29 `…/operations` (100)
- **Primary:** Pick a tool. **Pressure:** 3 → cheap. Hub with no fake metrics.

### UI-S-30 `…/bulk-suite` (1312)
- **Split first:** UI-SP-BULK. **Primary:** Run the bulk action. **Pressure:** 9.
- **States:** the blast radius ("412 records on 3 models") appears before Run; destructive confirmation; per-row results through `BulkResultTable` (virtualized, UI-F11).

### UI-S-31 `…/power-ops` (409)
- **Primary:** Run the recipe. **Pressure:** 8. **States:** destructive confirmation with the advanced confirmation flag.

### UI-S-32 `…/cron-manager` (523)
- **Primary:** Save the cron. **Pressure:** 5. **States:** next-run preview in the connection's timezone.

### UI-S-33 `…/housekeeping` (538)
- **Primary:** Clean. **Pressure:** 7. **States:** destructive confirmation; snapshot taken first (snapshot id shown).

### UI-S-34 `…/reminders` (241)
- **Primary:** Create the reminder. **Pressure:** 4 → cheap.

### UI-S-35 `…/script-runner` (286)
- **Primary:** Run. **Pressure:** 7. **Test:** `e2e/script-runner.spec.ts`. **Must not:** remove the sandbox warning.

### UI-S-36 `…/config` (946)
- **Split first:** UI-SP-CONFIG (`ConfigCommandCenter`). **Primary:** Save the setting. **Pressure:** 7. **depends_on:** T5B cards for import or export controls.

### UI-S-37 `…/live-demo-copilot` (528)
- **Primary:** Start the session. **Pressure:** 6. **States:** consent before launch; session live; ended.

### UI-S-38 `…/journal` (356)
- **Primary:** Roll back. **Pressure:** 8.
- **States:** the empty state exists, so keep it; partial rollback ("dropped columns cannot be restored"); chain verify result once T5A-03 ships.

### UI-S-39 `/live-demo-copilot/overlay` (104)
- **Primary:** Advance. **Harness:** `/e2e/overlay`. **Pressure:** 4 → cheap. Presenter mode, not operate density. Test: `e2e/overlay-editor.spec.ts`.

### UI-S-40 `/connections` (9)
- Redirect only. No card unless it renders UI.

## Settings, admin, pipelines

### UI-S-41 `/settings` (347)
- **Primary:** Create an API key. **Pressure:** 7. **States:** the key is shown once with Copy, then hidden forever; revoke confirmation.

### UI-S-42 `/settings/billing` (154)
- **Primary:** Manage plan. **Harness:** `/e2e/billing`. **Pressure:** 4 → cheap. Real prices only.

### UI-S-43 `/settings/trust-safety` (43)
- **Primary:** none (read the gates). **Pressure:** 3 → cheap. Lists the real gate states from the API, not marketing claims.

### UI-S-44 `/admin` (210)
- **Primary:** Verify a user. **Pressure:** 7. Admin only (server-checked; a non-admin gets 404). Destructive actions need confirmation.

### UI-S-45 `/pipelines` (359)
- **Primary:** Promote. **Pressure:** 9.
- **Must not:** auto-promote; remove the phrase gate.

## New and seeded screens this phase

### UI-S-50 `/approvals` — plan-card inbox (98, seeded)
- **depends_on:** T6-04, T6-05, T8-P5-PAGE. **Primary:** Approve this fingerprint. **Pressure:** 12 → Grok high effort.
- **Plan card, all nine sections, in order:**
  1. Summary
  2. Risk class (R0–R4)
  3. Ops
  4. Diff
  5. Impact and blast radius
  6. Simulation result
  7. Rollback plan
  8. Verify plan
  9. Expiry
- **States:**
  - R3 shows two approver slots, and the second approver must be a different person;
  - a Client Approver sees one client only;
  - stale fingerprint → approval voided;
  - expired;
  - a missing or foreign id shows the "not found" copy (never "forbidden").
- **Motion:** list layout for the inbox; no stagger.
- **Vision:** add shots for R1, R3 (two slots), stale, and narrow R3 (the full diff is visible at 390 px).
- **Must not:** approve from a reaction or a Slack button for R ≥ 2.

### UI-S-51 `/command` — fleet command (34, seeded)
- **Primary:** Open a client. **Pressure:** 8. **States:** one skeleton per tile, so a slow track does not blank the page; live counts from T1–T5 endpoints; empty fleet.

### UI-S-52 `/bots` — roster (new)
- **depends_on:** T8-BOT-ROSTER. **Primary:** Open a bot. **Pressure:** 7.
- **States:** presence from the state machine only (idle, acknowledged, thinking, working, waiting_user, waiting_approval, blocked, applying, verifying, done); at the bot limit.
- **Must not:** use decorative avatars that imply emotion, or Grok/xAI/Cursor brand assets.

### UI-S-53 `/bots/rooms/[id]` — room (new)
- **depends_on:** T8-BOT-ROOMS. **Primary:** Send. **Skills:** `conversational-ux`. **Pressure:** 9.
- **States:** 2–6 participants; handoff cards; stall nudge; hop or fan-out cap reached.
- **Must not:** treat a reaction as an approval.

### UI-S-54 `/bots/[id]` — workbench (new)
- **depends_on:** T8-BOT-WORKBENCH. **Primary:** Take over. **Pressure:** 9. Shows plan, diff, and the Apply button only when the card is approved.

### UI-S-55 `/studio/dashboards` — Dashboard Studio (new)
- **depends_on:** T4-DASH. **Primary:** Save the dashboard. **Skills:** `data-visualization`. **Pressure:** 9.
- **Charts:** `recharts` only. Every figure carries its domain citation, and the protected-model refusal is visible.
- **Must not:** use pie charts.

### UI-S-56 `/bridge/contracts/new` (123, seeded)
- **depends_on:** BR cards. **Primary:** Validate tier I. **Pressure:** 8. **States:** two-way sync reveals the conflict-resolution choice; validation errors per field.

### UI-S-57 `/bridge/connections` (new)
- **Primary:** Verify. **Pressure:** 7. Secret fields are write-only.

### UI-S-58 `/onboarding` — first-run (new, optional)
- Only if OQ-ONB in `18` is answered. Otherwise UI-S-08 covers first run.

### UI-S-60 – UI-S-62 — harness hygiene
- **UI-S-60:** `/e2e/kit` and `/e2e/tokens` reflect the Base UI and Sonner primitives after UI-F04–F08.
- **UI-S-61:** every operate block above with a harness twin is listed in `e2e/a11y-primary.spec.ts` (UI-F12).
- **UI-S-62:** `e2e/vision-verify-sweep.spec.ts` covers every UI-S block.
- **Pressure:** 4 each → cheap.
