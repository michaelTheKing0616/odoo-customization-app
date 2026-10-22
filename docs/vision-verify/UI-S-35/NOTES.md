# UI-S-35 · Script Runner (Studio-bar visual leap)

Card: UI-S-35 `…/script-runner`. Pressure 7. Primary: **Run script** (teal).
Status: Studio-bar visual leap implemented and verified locally. **Not marked DONE.** Nothing committed.

Sources: Playbook + ingenium-v2; eyes on UI-S-12 + UI-S-20-premier. Shared `OperateStudioBar` / `operate-studio.css`.

## Design Read

Operate-mode sandboxed Python runner with Designer-class basalt studio chrome. No-dry-run honesty lives in the studio bar (not a twin stacked banner). Idle/empty guides use brief density inside the paper desk. Sandbox limits + editor workbench stay. Must not remove sandbox warning.

## Before → after craft

| Before | After |
|---|---|
| PageHeader + pill rail + honesty card + idle card | Basalt studio chrome + session bar honesty + connected rail |
| Twin banners | Honesty in bar only; idle/empty as `density="brief"` |
| Flat panels on gray | Dot-grid desk + cream paper |

## Tests

- Vitest: script-runner + operate-studio → **5 files, 11 passed**
- Playwright on shared `:3002`: **6 passed** (one flaky timeout retried green). No isolated mirror left by this agent.

## Files

- `OperateStudioBar` / `operate-studio.css` (shared)
- `script-runner-operate.css`, harness, live page chrome, `ScriptRunnerStateGuide` density, e2e spec
- `docs/vision-verify/UI-S-35/{before,after}-*`, NOTES

## Gaps

- Live page three-column workbench chrome is wrapped; some inner panel nesting indent is imperfect but balanced.
- Other agents' Next mirrors on non-3002 ports left alone (Stop YOUR mirrors only).
