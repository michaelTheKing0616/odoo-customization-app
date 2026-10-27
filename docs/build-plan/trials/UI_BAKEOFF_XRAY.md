# Sealed UI trial: Database X-ray report (Tope, 22 Oct)

Purpose: one blind comparison of two builders on the same screen, to decide who builds NF UI cards. It is not a card. No code from it is ever merged. Both entries are deleted after judging.

## Contestants

| Entry | Builder | Tree | Route (scratch) | Port | `distDir` |
|---|---|---|---|---|---|
| Grok | `grok-4.7-xhigh` (the Grok bot, building itself) | worktree `../Odoo_Customization_App-nf` | `apps/web/src/app/e2e/trial-xray-grok/` | 3110 | `.next-trial-grok` |
| Cursor | a fresh Cursor chat on the model Tope picks | main tree | `apps/web/src/app/e2e/trial-xray-cursor/` | 3120 | `.next-trial-cursor` |

Grok may start once SCAN-01 is parked (ready to merge, or waiting on SEC-GATE-SCOPE); its SCAN-01 lock stays. Each entry adds one lock row in the main tree's `docs/build-plan/STATE.md`: `L-TRIAL-GROK` or `L-TRIAL-CURSOR`, covering only its route folder and its contact-sheet folder.

## Identical inputs (nothing else)

- Brief: `docs/build-plan/new-features/UNDERSTAND.md` §XRAY sections 2 and 3, plus `new-features/00_BASELINE.md` B1 (states) and B2 (UI rules).
- Data: `docs/build-plan/trials/xray_fixture.json` from the main tree, copied unchanged into your route folder as `fixture.json` and imported from there. It is Example data, and the screen says "Example" (INV-15).
- Bar: `AGENTS.md` UI bar; `07_UI_EXCELLENCE_PROTOCOL.md` §4 (including the 4a iteration rounds); `docs/design/references/ingenium-ui/` (`MANIFEST.md`, `motion/MOTION_NOTES.md`) and `UI_REFERENCE_MAP.md` areas 09 and 16; `docs/brand/README.md`.
- Stack: existing studio tokens only (no raw hex), Base UI, Sonner, `motion/react`, existing components in `apps/web/src/components/`. No new dependency.
- Skills: either builder may load the Prime skills. Nobody else reviews either entry before judging, including UI DESIGN BOT PRIME and this planning session.

## What to build

The X-ray report for one connection:
- the summary strip of 4 numbers;
- the tabs Apps / Customisations / People / Integrations / Risks (a `Select` at 390 px);
- the composition bar;
- the partial-run notice ("8 of 9 areas read; Integrations skipped because …");
- Export and Run buttons (no-ops with a toast);
- ⌘K entries "Run X-ray" and "Export X-ray".

States, reachable with `?state=`: `ready` (default), `loading`, `empty`, `partial` (the fixture as given), `error` (Odoo unreachable), `denied` (the Odoo user lacks read rights).

## Rules

- Budget: class M per entry. Up to 6 look-compare-fix rounds (protocol §4 step 4a). A 7th round is a stop-and-report.
- Do not edit any file outside your route folder and your contact-sheet folder. Do not edit shared components; compose them.
- T0 before submitting: axe shows 0 serious or critical issues; contrast passes (dark text on light-ish backgrounds); the jargon guard passes; `prefers-reduced-motion` is honoured.
- Contact sheet: `docs/vision-verify/trial-xray/<grok|cursor>/sheet.png`. The `ready` state in light and dark at 1440×900 and 390×844, plus one row with `loading`, `empty`, `error` and `denied` at 1440 light. No builder name, model name or logo on the sheet.
- Report in 5 lines or fewer: rounds used, T0 results, and the reference patterns matched or deliberately changed.

## Judging (blind)

1. When both sheets exist, Tope asks the planning session to copy them to `docs/vision-verify/trial-xray/blind/sheet-1.png` and `sheet-2.png` in random order. The key goes in `trials/BLIND_KEY.md`, which Tope does not open until he has scored both.
2. Tope scores each sheet 1–5 on:
   - reference fidelity;
   - hierarchy and density (calm operate screen);
   - states;
   - dark mode;
   - 390 px;
   - copy;
   - overall "would I ship this".
   He then opens the routes live once each, for motion and keyboard.
3. Decision: the higher total wins. A tie, or a difference of less than 3 points, keeps the status quo (Cursor builds UI). The result is logged as a DEC in `09_DECISIONS_FOR_TOPE.md` and in `MEMORY.md`.
4. Cleanup: both route folders are deleted (Tope's yes), the lock rows are removed, and the contact sheets stay as evidence.

## Result (22 Oct)

Tope viewed both live routes before scoring, so the trial was not blind and the 3-point rule did not apply. He preferred the Grok entry (`blind/sheet-1.png`). Decision: DEC-075. Floor sheet: `docs/design/bar/xray-floor.png`; the Cursor entry is kept at `docs/design/bar/xray-cursor-entry.png` for its 390 px pattern.

Cleanup (22 Oct, Tope's yes): the Cursor route, its `.next-trial-cursor` build and its port 3120 server are removed, and so is lock row `L-TRIAL-CURSOR`. The Grok route stays uncommitted in the worktree as the starting point for XRAY-UI, under `L-TRIAL-GROK`. Both are removed when XRAY-UI ships. The sheets stay as evidence.
