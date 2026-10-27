# 07 UI excellence protocol

Tope's bar (21 Oct): **the absolute best design on every screen.** The current UI is rated "really, really poor"; every route is rebuilt to its area's bar (`UI_REFERENCE_MAP.md`). A screen is not done while it is a plain form with a generic spinner, has a missing state, or uses copy that does not say what will happen (AGENTS.md UI bar).

Inputs every UI card uses, and nothing else:

| Input | Path |
|---|---|
| Area → references → cards; all 78 routes assigned | `docs/build-plan/UI_REFERENCE_MAP.md` |
| Reference pack (images, in-app captures, clips) | `docs/design/references/ingenium-ui/` (`MANIFEST.md`, `motion/MOTION_NOTES.md`, `_contact/*.jpg`) |
| Distilled notes (≤ 8 lines per reference) | `docs/build-plan/REFERENCE_NOTES.md` (card UI-REF-STUDY) |
| Brand kit (logo, mark, usage) | `docs/brand/` (`README.md` first) |
| Tokens, components | `apps/web/src/app/globals.css`, `apps/web/src/components/ui/`, `apps/web/src/components/shell/` |
| Plain words | handover Appendix C glossary; `apps/web/src/lib/terms.ts`; jargon guard `apps/web/src/lib/jargon-guard.test.ts` |
| Prime skills (load before editing a screen) | user store `skills/prime/`: `taste`, `motion`, `ux-copy`, `accessibility` (+ `ui-craft-dense-dashboard` for operate screens) |

## §1 Experience principles (every decision derives from these)

1. **Calm confidence.** Neutral surfaces, colour only for meaning, type hierarchy over boxes, generous space. No glow, glass or emoji in chrome.
2. **One job per screen**, one obvious primary action. Pick → Choose → Check → Run → Review.
3. **Instant and certain.** Every action answers in < 100 ms (optimistic state or a final-layout skeleton). No layout jump.
4. **Trust made visible.** Before and after every write, show what will change, how reversible it is, who approved it and what the money guard blocked.
5. **Keyboard-first, mouse-friendly.** Cmd-K reaches everything; shortcuts are shown where they apply.
6. **Bots are colleagues.** Visible steps, honest confidence, provenance ("Drafted by Expert, checked by code"), steerable while working, always inside a stated permission grant.
7. **Forgiveness.** Undo and History everywhere; reversibility shown up front.
8. **Delight earned by craft.** Physical motion on direct manipulation, success sized to stakes, empty states that teach, errors that fix. Never guilt, fake urgency, streaks or invented numbers (INV-15).
9. **Plain words.** Odoo's own names for Odoo things; the glossary is law (INV-04).
10. **Beautiful in dark and light, at 390 and 1440 px**, with WCAG 2.2 AA, reduced motion and screen readers treated as part of the beauty.

Duolingo-style pacing is allowed **only** in first-run and checklists (tiny steps, visible progress, first success < 5 min). No streaks, XP, guilt or mascots in working screens.

## §2 Reference map

`UI_REFERENCE_MAP.md` is the map (Tope's 19 areas, which supersede master §9.2 where they differ). Each ui-spec card names **exactly two** references from its area row; a third needs a written reason. Study principles (layout rhythm, density, hierarchy, states, motion, copy). **Never** copy logos, colours, copy, pixel layouts or ship a vendor asset; Ingenium keeps its identity (keystone/arch mark from `docs/brand/`, studio tokens, Geist). Gaps: Attio and n8n have no in-app captures; Raycast has no clips (DEC-029). Use the official images in the area folder and label assumptions `[Inferred]`.

## §3 Foundation first (Phase 1, built once)

Tokens with paired `on-*` tokens (contrast enforced by data, Tope's rule: light-ish background → dark ink), a lint that bans raw hex/rgb, and shared components: states (loading, empty, partial, error, offline, no permission, too much data, read-only, success), virtualised tables, database switcher, Cmd-K, ConfirmDialog with target naming, ErrorNotice, Undo toast. Screens compose these; a screen card that re-implements one is sent back.

## §4 Per-screen process (`ui-spec` card precedes each `ui-build` card)

Every session on a UI card loads `.cursor/skills/ingenium-ui-excellence/SKILL.md` first (Tope, 22 Oct). Where the skill is stricter than this section, the skill wins.

1. **Spec** (L3 for P1-10 flagship screens, else L2) writes `docs/design/specs/<screen>.md`, ≤ 120 lines:
   - job of the screen and the one primary action;
   - the two references: paste only their `REFERENCE_NOTES.md` entries, plus 3–5 patterns adopted from `MANIFEST.md` / `MOTION_NOTES.md` for this area (layout, density, type scale, hover/focus, transitions) and what is deliberately different;
   - every state from §3 with its copy; copy deck in plain words;
   - motion spec: the "Borrow for Ingenium" rows for this screen, target durations (100–250 ms), ease-out on enter, skeleton rows instead of spinners for page changes, fixed sidebar while content changes, instant hover tint, reduced-motion fallback; easing is tuned by eye against the clip;
   - keyboard map; a11y notes; responsive plan (390/768/1024/1440/1920); density (Comfortable/Compact); dark parity.
2. **Build** (L2; L3 for canvas/editor engines) against the spec only.
3. **T0 checks before any model looks:** contrast + Tope's rule, axe, hydration, perf, jargon/term guard, reduced motion, CLS, visual diff.
4. **Screenshot checkpoints (contact sheet):** baseline, after, final. Light and dark at 1440×900 and 390×844, assembled into **one contact sheet per screen** in `docs/vision-verify/<screen>/`.
   4a. **Iteration rounds (ui-build only; Tope, 22 Oct):** between after and final, up to **6 look-compare-fix rounds** per screen. Each round: screenshot the screen (any of the four size/theme combinations), put it next to the reference, list the gaps, fix them. The Worker packet lists the rounds used and the gaps closed per round. Round screenshots stay out of the contact sheet and the repo (scratch folder, deleted on close). A 7th round is a stop-and-report.
5. **Side-by-side:** the Worker packet states which reference patterns were matched and what was done differently, and why.
   5a. **Floor (DEC-075):** the contact sheet is also put next to `docs/design/bar/xray-floor.png`. States, density and hierarchy, dark mode, 390 px and copy are each rated at, above or below the floor. Any "below" is CHANGES. Patterns come from `docs/design/UI_DIRECTION.md`.
6. **Reviewer** checks §6 against the contact sheet and spec.
7. **GATE-B:** Tope reviews the contact sheet before the card closes.

Screen order (P1-10): Connect, Home (agency view), App Studio, View Designer, Configuration Suite home, Approvals, History, Settings. Then sidebar + database switcher, Cmd-K, the full IA (Bridge and Wireframe in nav; retired pages redirect with a one-time toast).

Non-negotiable first fixes: P0-6 contrast (white on orange 2.80:1, teal chip 2.21:1), P0-7 hydration, P0-5/P0-8 pagination and virtualisation (16,014 junk connections), P0-4 distDir.

## §5 Surpass bars (in every UI card's ACs where relevant)

INP < 200 ms at 4× CPU slowdown · CLS < 0.05 · LCP < 2 s · zero serious/critical axe issues · first successful Check < 5 min · switcher discovery < 10 s (3 of 3 new users) · zero hydration warnings · 100% states preview coverage · both themes pass contrast · no horizontal scroll at 390 px outside tables and the canvas · motion < 300 ms, transform/opacity only, interruptible.

## §6 Reviewer UI checklist (handover L711, the DESIGN_SYSTEM_PLAYBOOK §11 items; the playbook itself is not in this repo, so this list is the source)

- [ ] 4 px grid; consistent radii; no orphan colours; tokens only (no raw hex).
- [ ] One primary action; the screen's job is obvious in 3 seconds.
- [ ] Every §3 state exists, is designed, and has real copy that says what will happen.
- [ ] Real data or labelled "Example" (INV-15); no invented numbers.
- [ ] Keyboard: every action reachable; focus visible; Cmd-K registered.
- [ ] Dark and light parity; 390 and 1440 both on the contact sheet.
- [ ] Motion matches the spec and is off under reduced motion.
- [ ] Brand used per `docs/brand/README.md`; no vendor asset, logo or copy.
- [ ] Side-by-side statement present in the Worker packet.
