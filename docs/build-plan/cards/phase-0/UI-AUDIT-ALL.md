# UI-AUDIT-ALL: whole-app UI is 'really really poor': score every route against its pack area; baseline co

ID: UI-AUDIT-ALL
Title: whole-app UI is 'really really poor': score every route against its pack area; baseline co
Status: done
Phase: 0
Priority: P0
Type: ui-spec
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: UIX-00;UIX-TOUCHES
Depends on: UI-REF-STUDY, B0-INV
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L2 separate session · Score: 4 (C0 U1 F2 K1 V0 I0)
Context pack:
- `sed -n '29,45p' docs/build-plan/UI_REFERENCE_MAP.md`
- `sed -n '36,47p' docs/build-plan/07_UI_EXCELLENCE_PROTOCOL.md`
- `sed -n '1,17p' docs/build-plan/REFERENCE_NOTES.md`
- `sed -n '8,9p' docs/build-plan/FACTS.md`
- `sed -n '17p' docs/build-plan/FACTS.md`
- docs/build-plan/FACTS.md
File allow-list:
- docs/design/specs/ui_audit_all.md (new)
- docs/design/specs/ui_audit/ (new; one file per map area for the score rows)
Goal: Write the route scores in `docs/design/specs/ui_audit_all.md` and, when a row would push that index over 120 lines, in `docs/design/specs/ui_audit/<NN-area>.md`. Do not edit `apps/web` or `DESIGN_TOUCHES.md`. Do not mark AC1 or AC2 done; STOP-AND-ASK. Later ui-build cards own the screens and the touches. Tope, 24 Oct: this is the widened home for UIX-00. It does not fit F1-RESPONSIVE.
Steps:
1. Load the Prime skills (taste, motion, ux-copy, accessibility). Read the route table in `docs/build-plan/UI_REFERENCE_MAP.md` (L29-45; 78 `page.tsx` routes outside `/e2e`) and each area folder `docs/design/references/ingenium-ui/<NN-area>/` (`01-shell-lists-history` through `19-docs`), plus `MANIFEST.md`, `motion/MOTION_NOTES.md`, and `_contact/`. Paste from `docs/build-plan/REFERENCE_NOTES.md` (skeleton until `UI-REF-STUDY`). There is no single area row. Each score row uses the two references on its own area row (L9–27).
2. Write `docs/design/specs/ui_audit_all.md` (≤ 120 lines) for the audit method, and put the score rows in `docs/design/specs/ui_audit/<NN-area>.md` so the index stays within 120 lines. Write each `07_UI_EXCELLENCE_PROTOCOL.md` §4 step-1 section once, for the audit method, not once per route: job and primary action; references; every §3 state with copy; motion spec (durations, easing, reduced motion); keyboard map; a11y; responsive 390/768/1024/1440/1920; density; dark parity. "Exactly two references" means each score row names the two references on that area's map row. It does not mean the whole file names only two references.
3. List the shared components (F1) the build composes; anything missing becomes a proposed F1 card, not a local component. Touches are read from `docs/specs/DESIGN_TOUCHES.md` (identical to `docs/DESIGN_TOUCHES.md`, 237 lines). Do not edit either file. One line per touch in the spec: already built (name the area card) or a proposed card id. Implementing the touch is not this card.
4. Copy deck passes the jargon guard. `apps/web/src/lib/jargon-guard.test.ts` walks `apps/web/src` `ts/tsx` only (`BANNED`, L6-15). It does not read markdown, and there is no spec fixture. Do not edit that test. The spec must contain none of those `BANNED` strings. Run `cd apps/web && pnpm vitest run src/lib/jargon-guard.test.ts` → pass.
5. This card adds no image files. It does not edit `apps/web` or either touches file. Baseline, after, and final contact sheets (one per screen) apply to ui-build cards, not to this spec. A missing sheet path forces score `below`. Do not mark `at` when the path is `missing`.
6. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong. STOP-AND-ASK before anyone marks AC1 done: the spec does not make "no screen ships below bar" true. The default is that later ui-build cards own the screens. STOP-AND-ASK before anyone marks AC2 done: implementing a touch is not this card. The index stays ≤ 120 lines. Score rows and touch lines that do not fit there go in the area file. Do not drop a row and do not drop a touch line. A path listed under two area bullets: STOP-AND-ASK. Missing input: which area owns the score row. Do not invent one.
Acceptance criteria:
- AC1: whole-app UI is 'really really poor': score every route against its pack area; baseline contact sheets; no screen ships below bar (source: ledger UIX-00, Tope 21 Oct)
- AC2: all 162 design touches implemented in full; built ones re-checked inside their area rebuild (source: ledger UIX-TOUCHES, Tope 21 Oct; DESIGN_TOUCHES)
- AC3: Spec contains every 07 §4 step-1 section, names exactly two references from its `UI_REFERENCE_MAP.md` row, ≤ 120 lines, copy passes the jargon guard
Worked example (one route; re-check the map before copying): `/connect` is area 06. Folder `docs/design/references/ingenium-ui/06-connect-onboarding/`. That area row names Stripe and Vercel. One score row: `| /connect | 06 | below | missing | UI-CONNECT-* | Stripe | Vercel |` (route, area, score, baseline sheet path or `missing`, owning card, then the two references on that area's map row). Do not mark `at` when the sheet path is `missing`. The two names sit on the row. The file may name every area's pair.
Decision table:

| Route class in `UI_REFERENCE_MAP.md` | Score row |
|---|---|
| named under one area bullet (L31-44) | that area number; the two references are the ones on the area row (L9-27) |
| bullet says retire, redirect, fold, or hide (DEC-024) | `redirect-only`: the redirect and the features it preserves |
| cross-cutting 02, 03, 16, 17, 18 (L45) | no route of its own; name the shared card |
| path listed under two area bullets | STOP-AND-ASK. Missing input: which area owns the score row. Do not invent one |
| sheet path `missing` | score `below`. Do not mark `at` |

Proof:

| AC in this file | Proof that belongs here | Not this card |
|---|---|---|
| AC1 | one score row per named route. A missing contact sheet forces score `below`. Do not mark `at` when the path is `missing` | "no screen ships below bar" is not made true by the spec. STOP-AND-ASK before anyone marks AC1 done. Default: later ui-build cards own the screens |
| AC2 | one line per touch: already built (name the area card) or a proposed card id | implementing the touch. STOP-AND-ASK before anyone marks AC2 done |
| AC3 | §4 sections written once, for the audit method. Each score row names the two references on that area's map row. File ≤ 120 lines. Jargon `rg` has no hits | sections repeated per route. The whole file naming only two references. Any image file |

§3 states to name under States, once: loading, empty, partial, error, offline, no permission, too much data, read-only, success. `rg -c '^## '` counts these headings: Job, References, States, Motion, Keyboard, Accessibility, Responsive, Density, Dark.
Reading:
1. Do not change the AC1, AC2, or AC3 lines. The index is `docs/design/specs/ui_audit_all.md` (≤ 120 lines). Score rows that do not fit there go in `docs/design/specs/ui_audit/<NN-area>.md`, one file per map area, one row per named route. Do not drop a row. It does not edit `apps/web` or `DESIGN_TOUCHES.md`.
2. AC1 in this file means one score row per named route. A missing contact sheet forces score `below`. Do not mark `at` when the path is `missing`. AC1's "no screen ships below bar" is not made true by the spec. STOP-AND-ASK before anyone marks AC1 done: the default is that later ui-build cards own the screens.
3. AC2 in this file means one line per touch: already built (name the area card) or a proposed card id. Implementing the touch is not this card. STOP-AND-ASK before marking AC2 done.
4. AC3's ≤ 120 lines stays. The §4 sections are written once, for the audit method, not once per route. "Exactly two references" means each score row names the two references on that area's map row. It does not mean the whole file names only two references.
5. This card adds no image files. Step 5's baseline/after/final contact sheets apply to ui-build cards, not to this spec.
Test plan:
- `python3 scripts/plan_lint.py all` → 0 new errors
- spec sections present: `rg -c '^## ' docs/design/specs/ui_audit_all.md` ≥ 8
- spec copy: `rg -n -F -e 'Mutations blocked' -e 'grounded fields only' -e 'unsafe gate family' -e 'TRUST-9' -e 'sha256 required' -e 'title="Philosophy"' -e 'XML-RPC' -e 'JSON-RPC' docs/design/specs/ui_audit_all.md` → no hits
Common mistakes: raw hex instead of tokens; a bare `next build` (overwrites dev `.next`; use own distDir); spinner instead of skeleton; copy that fails the jargon guard; light text on light-ish backgrounds.
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
2026-10-25 closed. 19 area files, 80 score rows, index 81 lines. Split kept: area 01 frame, area 04 content. UIX-00 stays Poor. UIX-TOUCHES stays Partial. AC1 and AC2 stay open. Reviewer APPROVE.
