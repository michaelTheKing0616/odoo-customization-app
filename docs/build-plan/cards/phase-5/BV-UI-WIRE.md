# BV-UI-WIRE: Mount the evidence viewer in Bots, fed by the verify-runs API

ID: BV-UI-WIRE
Title: Mount the evidence viewer in Bots, fed by the verify-runs API
Status: in progress
Phase: 5
Priority: P1
Type: build
Owner: ui
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: NF-EPIC-BV;NF-BV-UI-WIRE
Depends on: BV-UI (134020d9), BV-04 (masked artifacts), BV-STORE (artifact route). D-BV-WIRE-1 = (a) (2026-10-24, NF owner).
Routing: Worker: L2 · full UI trial process · Tester + Reviewer separate sessions
Context pack:
- docs/build-plan/new-features/BOT_VERIFY.md §6
- docs/design/UI_DIRECTION.md (Evidence viewer (BV-UI))
- apps/web/src/components/bots/EvidenceViewer.tsx
- apps/web/src/lib/api/botVerify.ts
- apps/api/app/routers/bot_verify.py
- docs/build-plan/cards/phase-4/UI-BOTS-BUILD.md (owner of connections/[id]/operations)
File allow-list:
- apps/web/src/components/bots/VerifyRunPanel.tsx (new; container: fetch, loading/error/retry, artifact URL)
- apps/web/src/components/bots/VerifyRunPanel.test.tsx (new)
- apps/web/src/components/bots/EvidenceViewer.tsx (one-line fix only: "Change 1" chip whitespace-nowrap at 390 px)
- apps/web/src/components/bots/EvidenceViewer.test.tsx (one test for the above)
- apps/web/src/app/connections/[id]/operations/verify/[runId]/page.tsx (new; thin route rendering VerifyRunPanel; D-BV-WIRE-1 = (a), UI-BOTS-BUILD files untouched)
- docs/design/UI_DIRECTION.md (BV-UI-WIRE line under Evidence viewer only)
Not on allow-list: apps/web/src/components/ui/**, the app shell (L-F1-HYDRATE), apps/web/src/lib/api/botVerify.ts (reuse as is), package.json, pnpm-lock.yaml.
Goal: A user opening a verify run in the Bots area sees the BV-UI viewer with the real run and its masked screenshots, a calm loading state, and a plain-language error with Retry.
Steps:
1. Read BOT_VERIFY.md §6 and the UI_DIRECTION Evidence viewer section. Build only what the ACs name.
2. Write the tests first; they must fail before the code and pass after.
3. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts the epic doc; a check would need a non-`ingenium_` DB, a forbidden port (3002, 8001, 8002, 8012, 5433, 5436, 8069–8073, 11434, 54329), a git write, an outbound call to a third party, or a new dependency; an Odoo claim proves false on any of 17–20. Also stop if the mount point would edit a file owned by UI-BOTS-BUILD or L-F1-HYDRATE.
Acceptance criteria:
- AC1 VerifyRunPanel calls botVerifyApi.getVerifyRun(connectionId, runId) once on mount and once per Retry; passes run + artifactUrl=botVerifyApi.verifyArtifactUrl to EvidenceViewer.
- AC2 loading: EvidenceViewer loading=true until settle (calm skeleton kept). Error: error=true, errorCopy plain language ("We couldn't load this check. Your Odoo data is unchanged." style; no status codes, stack, ids or banned words), onRetry refetches. 403 -> denied state with group; 404 -> empty state, no existence leak in copy.
- AC3 screenshots are the masked BV-04 artifacts served by the existing artifact route; no raw blob paths, no client-side unmasking; images load via same-origin URLs only.
- AC4 "Change 1" chip stays on one line at 390 px (no wrap, no x-scroll).
- AC5 full UI trial: light/dark × 1440/390, states ready/loading/error/denied/empty, axe 0 (wcag2a/aa/21aa/22aa), 44 px targets, reduced motion; real masked artifacts from one live BV-04 run on an ingenium_* clone (or recorded fixtures of them).
Test plan: vitest VerifyRunPanel.test.tsx (fetch mocked: ok, slow, 500, 403, 404, retry) + EvidenceViewer.test.tsx; tsc --noEmit; eslint on touched files; trial shots.
Focused set: src/components/bots/
Combined set: vitest src/components/bots src/lib/api, both orders.
Trial scope (NF-owner call 2026-10-24, option a): x-scroll is asserted only within the panel/main region, with the shell sidebar hidden at 390 px; shell sidebar overflow on phones is out of scope (separate shell card). Console errors count only those from the panel's own code: shell 401s are ignored, and the verify-run fixtures' expected 403/404/500 (denied/empty/error) are allowed; JS errors and any other verify-run failure count.
Gate: tests ×2 green; typecheck 0; trial r-final axe 0, no x-scroll.
Evidence to log: PROGRESS line; trial dir; UI_DIRECTION line.
Rollback: delete the new files; revert the one-line chip fix.
Definition of Done: ACs pass; independent Reviewer APPROVE; merged; lock released.
