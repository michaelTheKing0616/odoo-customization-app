# UI-S-18 · Code Studio (Studio-bar visual leap)

Status: Studio-bar visual leap on CodeStudioScreen (+ harness via real screen). **Not marked DONE.**

Ground-rule chips collapsed into bar honesty. CodeStudioHonesty Option A detail stays in paper as content (not a second banner). Gate rail unchanged.

Gaps: early authoring gate states still use ResultPanels inside paper; dense two-pane layout unchanged.


---

## Prior elevate notes (archive)

# UI-S-18 · Code Studio (Studio-bar visual leap)

Status: Studio-bar visual leap on CodeStudioScreen. **Not marked DONE.**

Ground-rule chips collapsed into bar honesty. CodeStudioHonesty Option A detail stays in paper as content.

Gaps: dense two-pane layout unchanged; early ResultPanels stay in paper.


---

## Prior elevate notes (archive)

# UI-S-18 Code Studio: vision notes

Card: UI-S-18 `…/code-studio`. Pressure 8. Primary: **Validate code** (teal, the only filled primary on the screen).
Status: elite pass implemented and verified locally. **Not marked DONE. Nothing committed.**

Sources loaded before the edits:
- `~/Desktop/prime-skills-pack/docs/DESIGN_SYSTEM_PLAYBOOK.md` (laws §0, colour §5, motion §6, error anatomy §15.4)
- `~/Desktop/ingenium-v2/final/BRAND_GUIDE.md` (basalt `#1A1C21`, limestone `#F3F4F6`, teal `--accent` stays the UI accent, cinnabar keystone only)
- Sibling passes: UI-S-13 Menus, UI-S-15 Automations, UI-S-22 Job Autopilot notes

## Design read
Operate-mode developer tool. Basalt chrome (editor bar, ground-rule chip, Option A band), one teal accent (Validate, selection, focus).
Green = passed, amber = changed or blocked rule, red = syntax error or failed run. Cinnabar never appears.
Validate is the authoring gate: nothing that runs the code (test run), installs it live (bind) or packages it (zip) is offered before the current code passes.

## Must-not checks
| Rule | How it holds |
|---|---|
| Do not remove the Option A warning | Kept and made louder: basalt band "Option A module · Never installs from here", the original copy (`code-studio-limit-option-a`: "does not install… does not promote"), plus three numbered steps ending "A person promotes it". Dark mode inverts the band to limestone so it stays the loudest surface. Tests assert all of it. |
| No Live Install of authored code before the authoring gate passes | `liveBindGate()` in `code-studio-gate.ts`: Bind live stays disabled until Validate passed on the exact code on screen, with no blocked rule, a cleared probe and no failed test on that code. Any edit voids the pass ("This code changed. Validate again."). `confirmBind` re-checks the gate. Unit, page and Playwright tests cover it. |

## Behaviour changes (all UI-side, no API change)
- Validate result is pinned to the code it judged. Editing shows the stale state and voids the pass (spec global "stale" rule).
- Test run now waits for Validate too (it executes on a real record).
- Option A zip waits for Validate; a syntax error blocks it, blocked server-action rules do not (they are shown).
- A refused probe opens on the Option A path (unless the user already picked a path).
- Cmd/Ctrl+Enter in the editor runs Validate (hint hidden on touch).
- `PythonLineEditor`: long lines scroll horizontally with the highlight and caret aligned (the old reserved 3rd column clipped code), sticky line numbers, diagnostics under the line, `onSubmit` / `showHeader` props. Script Runner still uses it unchanged (its 4 tests pass).

## States captured (`after-*`, desktop = real route in the app shell, mobile = `/e2e/code-studio` harness)
| State | What to verify |
|---|---|
| ready | Validate teal primary; rail at Validate; bind locked with "Validate this code first."; idle line explains the gate |
| validated | Gate pill "Validated"; rail Bind live = next; checklist ticks; bind enabled (secondary) |
| blocked | `import os` marked on line 1; amber "Blocked on the server-action path" with line numbers; bind locked |
| syntax | Red "Validation failed" with the line and "Fix line 2, then validate again." |
| stale | Edited after Validate: amber "This code changed. Validate again."; bind locked again |
| testfail | Test failed panel + snapshot id; rail Test run red; checklist "Last test run failed"; bind locked with reason |
| optiona | Option A path selected; zip unlocked after Validate; checklist ends with sandbox + human promote |
| gate | Probe refused: GatingCallout, Re-probe, Option A path preselected |
| error | Traceback hidden behind Show details; customer sentence; Retry |
| loading | Layout-matching skeleton |
| validated-dark, optiona-dark | Dark tokens; inverted Option A band |

`before-*` shots were taken from the same mocks before the pass (old mobile overflowX=99 was the app shell at 390 px).
Every `after-*` shot measured overflowX=0.

## Regenerate
```bash
# isolated dev server (do not share .next with the main dev server on :3002)
# copy apps/web/{src,public,next.config.ts,package.json,postcss.config.mjs,tsconfig.json,next-env.d.ts} to /private/tmp/s18web,
# symlink node_modules, then:
cd /private/tmp/s18web && PLAYWRIGHT_E2E_BUILD=1 NEXT_PUBLIC_E2E=1 node <next>/dist/bin/next dev -H 127.0.0.1 -p 3118
cd apps/web
NODE_PATH=$PWD/node_modules node ../../docs/vision-verify/UI-S-18/capture.cjs http://127.0.0.1:3118 ../../docs/vision-verify/UI-S-18 after
```

## Tests
```bash
cd apps/web
npx vitest run src/components/code-studio "src/app/connections/[id]/code-studio" "src/app/connections/[id]/script-runner"
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3118 npx playwright test e2e/code-studio.spec.ts
```

## Known gaps
- Offline-queued state for bind is not built (no queue exists for Code Studio writes).
- The app shell does not collapse at 390 px, so mobile shots use the shell-free harness. Shell is outside this card.
- The floating "Odoo Expert" button overlaps the right rail on desktop (global shell component).
- ErrorNotice keeps its generic "Request failed" title; the customer sentence carries the what. The why/next live in the shared component.
- The original e2e test (real connection) still skips without a live API; the new harness tests do not.
- The "Live server action" radio stays selectable when the probe is refused (bind shows as locked with the reason) rather than disabled.
