# UI-REF-STUDY: reference class + 2 references per screen + logged comparison

ID: UI-REF-STUDY
Title: reference class + 2 references per screen + logged comparison
Status: done
Phase: 1
Priority: P0
Type: ui-spec
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: UI-5.1;UIREF-PACK;UIREF-GAPS
Depends on: none (phase order applies)
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L2 separate session · Score: 4 (C0 U1 F2 K1 V0 I0)
Context pack:
- docs/build-plan/REFERENCE_NOTES.md
- docs/build-plan/UI_REFERENCE_MAP.md
- docs/build-plan/FACTS.md
File allow-list:
- docs/design/specs/ui_ref_study.md (new)
- docs/build-plan/REFERENCE_NOTES.md
Goal: Write the logged comparison inside the two allow-list files. Do not score routes. Route scores are UI-AUDIT-ALL (UIX-00). Do not fold them into this card or into F1-RESPONSIVE.
Steps:
1. Load the Prime skills (taste, motion, ux-copy, accessibility). Read `UI_REFERENCE_MAP.md` and the pack under `docs/design/references/ingenium-ui/` (MANIFEST, MOTION_NOTES, area notes, `_contact/`). Those paths are read-only.
2. Fill `docs/build-plan/REFERENCE_NOTES.md`. One entry per product in the "Entries to write" list, ≤ 8 lines, in the shape already at the top of that file. Anything not in the pack is `[Inferred]`. Do not copy vendor logos, colours, copy, or layouts.
3. Write only `docs/design/specs/ui_ref_study.md` (≤ 120 lines). Write each `07_UI_EXCELLENCE_PROTOCOL.md` §4 step-1 section once, for the study method: job and primary action; references; every §3 state with copy; motion spec; keyboard map; a11y; responsive 390/768/1024/1440/1920; density; dark parity. Each area's two references stay on its map row. The logged comparison is the notes file. Say that route scores are UI-AUDIT-ALL.
4. Do not edit `apps/web`. The jargon test does not read markdown. The spec and the notes must contain none of the banned strings named in the Test plan. Run that vitest and `python3 scripts/plan_lint.py all`.
5. This card adds no screens and no contact sheets. Do not edit `UI-AUDIT-ALL`, `F1-RESPONSIVE`, or `UI_REFERENCE_MAP.md`.
6. STOP-AND-ASK: a needed write is outside the allow-list; a pack file is missing and the note would be an invention rather than `[Inferred]`; a live check would need a non-`ingenium_` DB, a forbidden port, a git write, or a new dependency.
Acceptance criteria:
- AC1: reference class + 2 references per screen + logged comparison (source: ledger UI-5.1, §5.1; §5.14). The two references for a screen are the pair on its `UI_REFERENCE_MAP.md` area row. The comparison is the notes entry.
- AC2: UI reference pack at docs/design/references/ingenium-ui: per-screen 3-5 adopted patterns; side-by-side before done; avoid spinner-only loads (source: ledger UIREF-PACK, user brief 21 Oct). Record the patterns in the notes. Do not produce the side-by-side sheets here.
- AC3: gaps: Attio no in-app; n8n in-app is only a signup gate; no clips for Raycast Figma Webflow Make Stripe-vendor Attio Fathom Warp; old Things 2017 + Granola 2024 clips (source: ledger UIREF-GAPS, MANIFEST + MOTION_NOTES)
- AC4: Spec contains every 07 §4 step-1 section, written once, ≤ 120 lines, and names `UI_REFERENCE_MAP.md` as the source of each area's two references. Copy passes the jargon check in the Test plan. Route scores are not in this file.
Test plan:
- `python3 scripts/plan_lint.py all` → 0 new errors
- `rg -c '^## ' docs/design/specs/ui_ref_study.md` ≥ 8
- `rg -n -F -e 'Mutations blocked' -e 'grounded fields only' -e 'unsafe gate family' -e 'TRUST-9' -e 'sha256 required' -e 'title="Philosophy"' -e 'XML-RPC' -e 'JSON-RPC' docs/design/specs/ui_ref_study.md docs/build-plan/REFERENCE_NOTES.md` → no hits
- `cd apps/web && pnpm vitest run src/lib/jargon-guard.test.ts` → pass
Common mistakes: scoring routes in these two files; a per-area spec outside the allow-list; raw hex; copying a vendor layout; marking an unobserved pattern as seen.
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only).
Definition of Done: Every AC has evidence; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
Not this card: UIX-00, the every-route score, is UI-AUDIT-ALL. F1-RESPONSIVE stays the 390 scroll pin. Tope, 24 Oct.
2026-10-25 closed. Spec 65 lines, headings 9. Jargon vitest 1 passed. plan_lint errors=48, none from these files. UI-5.1 is [Done, code]. UIREF-PACK stays On-disk. UIREF-GAPS stays Verified. Reviewer APPROVE.
