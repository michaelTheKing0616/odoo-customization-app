# Premium World-Class Upgrade Spec — Odoo Customization App

**Audience:** Fabian + Claude (Sonnet) refinement before implementation  
**Author:** Odoo Customization App Bot Builder  
**Date:** 2026-09-16  
**Tip audited:** `premium-local-tip` @ `febdab7` (includes Co-Pilot `9e7ace5` + Studio/AI honesty `febdab7`)  
**Bar:** Linear / Figma properties / Intercom / Stripe Dashboard density — **not** cloning Odoo Enterprise Studio source  
**Clean-room:** public ORM/RPC + public Studio docs only. Never `web_studio` source.

---

## 0. How to use this document

1. Read §1 (executive distance-to-goal) and §2 (north star).  
2. Skim §3 inventory, then deep-read §4–§5 (strengths / gaps).  
3. Treat §6–§8 as the proposed program of work — **refine with Claude before any build**.  
4. §12 is a prompt pack for Claude.  
5. Do **not** start coding from this file until Fabian signs a refined v2.

---

## 1. Executive summary — how far are we?

### 1.1 One-line verdict

We have a **real, unusually honest, mid-to-high-premium Community Studio-class platform** with a coherent safety dialect and broad surface coverage — but we are **not yet** “the best, most seamless, easiest, truly elite Odoo no-code app anywhere.”

### 1.2 Distance score (honest)

| Dimension | Today (1–5) | World-class target | Gap |
|---|---:|---:|---|
| Capability breadth (Community Studio+ ops) | **4.2** | 4.8 | Narrow: polish + a few missing Studio-feel edges |
| Safety / honesty / promote discipline | **4.6** | 4.8 | Already a moat — protect it |
| Visual / interaction premium (Linear/Figma bar) | **3.2 → ~3.6*** | 4.7 | Largest gap |
| Journey seamlessness (one job, one path) | **3.0** | 4.7 | AI Studio product sprawl |
| Live reliability (RPC + sandbox + demos) | **3.4** | 4.6 | Live UAT thin; LLM quota fragility |
| Onboarding → first win in <10 min | **2.8** | 4.5 | Connect→value path still consultant-shaped |
| Production / multi-tenant SaaS readiness | **3.0** | 4.5 | Deploy plan exists; ops not productized |
| Differentiator delight (Expert, Co-Pilot, sandbox) | **3.8** | 4.8 | Strong seeds; need productization |

\*Chrome UAT (2026-09-14) averaged **~3.3/5**. Since then: Studio-like Designer shell, dark-mode contrast, Co-Pilot, Studio Repair honesty — estimated **~3.5–3.7** visual/interaction if re-scored, still far from 4.7.

### 1.3 Time-to-goal (realistic)

Assuming **one focused builder** (you + agents) without pausing for unrelated arcs:

| Milestone | Calendar | Outcome |
|---|---|---|
| **M1 — World-class chrome spine** | 4–8 weeks | Designer extracted; AI Studio IA collapsed; confirm hygiene complete; re-UAT ≥4.2 avg |
| **M2 — Seamless journeys** | +4–6 weeks | First-win onboarding; cross-links; live RPC UAT green on 18/19 |
| **M3 — Elite differentiators** | +4–8 weeks | Expert destination; Co-Pilot real-meeting pilot; production host |
| **M4 — “Best in class” claimable** | +2–3 months after M3 | External design polish pass, marketing site, paying beta |

**Bottom line:** ~**4–7 months** of disciplined premium work to honestly claim top-tier; **not** “two more PRs.” Capability is ahead of craft. Craft is the bottleneck.

### 1.4 What would make a competitor beat us tomorrow

1. Better **IA** (one AI builder path, not five overlapping tools).  
2. A **Figma-grade Designer** without a 5.9k orchestrator dump.  
3. Faster **time-to-first customization** on Odoo Online.  
4. Polished **marketing + onboarding** while we look “consultant toolbox.”

Our moat if we stay disciplined: **honesty + sandbox-before-promote + Community Studio-class via public ORM + Expert RAG + Live Demo Co-Pilot**.

---

## 2. North star & non-goals

### 2.1 Goal (Fabian)

> Build the best, most seamless, easiest to use (intuitive), and **truly premium** in look, feel, and function Odoo no-code app anywhere.

### 2.2 Product principles (locks)

1. **Clean-room only** — public docs/ORM/RPC; never Enterprise Studio source.  
2. **Completeness ≠ Certification ≠ Autopilot** — three separate bars, always labeled.  
3. **Promote stays human** — never auto-promote modules to production.  
4. **Sandbox before promote** for Option A / Python / Autopilot.  
5. **Inherit-default** for view edits; overwrite needs confirm + snapshot.  
6. **Confirm phrase** `I understand the risks` for advanced/destructive writes.  
7. **Enterprise = warn-only** — same public-ORM caps as Community for that major.  
8. **WhatsApp permanently out of scope** for Live Demo Co-Pilot.  
9. Premium bar = **Linear / Figma / Intercom / Stripe**, not “feature complete.”

### 2.3 Constraints — three buckets (not a forever ban list)

> **Lesson:** Treating soft delivery choices as sacred “non-goals” can stall the product
> (e.g. an earlier ban on LLM authoring for custom Python — later reverted).  
> Use this framing in Claude v2 and all agent work.

#### Bucket A — Hard locks (irreversible harm if broken)

Do **not** reopen without an explicit founder decision + legal/safety review.

| Lock | Why |
|---|---|
| **Clean-room only** — no Enterprise `web_studio` / OEEL-lineage Studio source | IP / integrity |
| **Promote stays human** — never auto-promote modules to production | Trust moat; blast radius |
| **Sandbox before Option A / Python module install** | Fake speed otherwise |
| **WhatsApp permanently out of scope** for Live Demo Co-Pilot | Platform + consent reality |
| **No silent unrestricted live `state=code` as the default no-code path** | Default ≠ available; see Bucket B |
| **Never pretend ModuleSpec Completeness 10.0 = go-live / Certification / Autopilot** | Honesty dialect |

#### Bucket B — Default-off capabilities (powerful, gated — not banned)

These **may and should** exist when the rails are real. Do not document them as “we don’t do X.”

| Capability | Gate |
|---|---|
| **LLM authoring of custom Python / Option A** | Sandbox smoke + human Promote; never default live `state=code` |
| **View overwrite (mutate)** | Confirm phrase + snapshot; inherit remains default |
| **Access live pack / hot ACL matrix writes** | Confirm phrase + clear blast-radius copy |
| **Job Autopilot / Config Packet apply** | Sandbox / named target; refuse `write_mode=production` |
| **Destructive Power Ops / bulk** | Dry-run + confirm; recipe tags |

#### Bucket C — Phase deferrals (reopen when signal appears)

Not “never.” Track a reopen signal; promote into a phase when evidence shows up.

| Deferral | Reopen when… |
|---|---|
| **Deep property-field Studio parity** | Paying / pilot users blocked by property fields on real forms |
| **Full `ir.translation` UI** (CSV remains) | Localization-heavy buyers or multi-language go-lives |
| **Mobile / tablet premium** | Mobile demo or field-consultant usage becomes a sales gate |
| **Collaborative multiplayer editing / comments** | Multi-seat SaaS or shared-draft workflows demanded |
| **Pixel-clone Studio OWL in-Odoo editor** | Stay deferred forever as *clone*; still pursue **beat Studio feel** via live canvas + density (different path) |
| **Majors ≤15 or speculative 20+** | Explicit founder unlock + adapters + live evidence |
| **EE live Docker verification** | Enterprise image available; still warn-only / public-ORM caps |

**Claude v2 instruction:** Keep Bucket A terse and sacred. Rewrite any remaining “non-goals” language into B or C. Prefer “default-off + rails” over “forbidden feature.”

---

## 3. Current product inventory (tip @ febdab7)

### 3.1 Nav groups & surfaces

| Group | Surfaces | Role |
|---|---|---|
| **Overview** | Connection home | Health, CTAs into AI/Build |
| **Build** | Models & Fields, View Designer, Menus, Website, Automations, Approvals, Reports, Code Studio, Access | Metadata craft |
| **AI Studio** | App Studio, Draft Studio, Job Autopilot, ModuleSpec, Projects, Odoo Expert, **Live Demo Co-Pilot** | Brief → author → job → ship assist |
| **Data** | Import, ID Generator | Record / external id |
| **Operations** | Bulk Suite, Power Ops, Cron, Housekeeping, Reminders, Script Runner | Operate at scale |
| **Safety & History** | Snapshots & Journal, Config | Govern |

### 3.2 LOC reality (orchestrator weight)

| Surface | `page.tsx` LOC | Signal |
|---|---:|---|
| View Designer | **~5,900** | Still a dump despite shell extraction |
| Draft Studio (`wizard`) | ~1,878 | Consultant worksheet + stage rail |
| App Studio (`studio`) | ~1,383 | Best brief; still dense |
| Overview | ~1,259 | Overloaded home |
| Live Demo Co-Pilot | ~528 | New, focused |
| Models & Fields | ~781 | Premium list→composer |
| Access | ~733 | Multi-job column |
| Job Autopilot | ~747 | Safety strong |
| Automations | ~694 | Highest-confidence sibling |
| Menus | ~407 | Sibling-correct |
| ModuleSpec / Projects pages | ~19 each | Thin shells → component workbenches |

**Designer components extracted (good):** `DesignerStudioShell`, `DesignerLiveCanvas`, `DesignerToolsRail`, `OverlayEditor`, `XPathInheritPanel`, `DesignerFieldInspector`, history hook, etc. — but **orchestration remains monolithic**.

### 3.3 Evidence baseline

| Artifact | Finding |
|---|---|
| `docs/UAT-PREMIUM-WORLD-CLASS.md` (2026-09-14) | Chain avg **3.3/5**; Expert **4.1** best; Designer prod **2.4** worst |
| P0 remediation PR | Access apply-live confirm; Autopilot resume; Overview AI entry; Projects Apply gate; ModuleSpec→Projects |
| Post-UAT commits | Studio Designer shell; overlay inject fix; dark-mode contrast; Co-Pilot full stack; Studio tax_id + Repair honesty |
| Mastery backlog | Mostly **cleared**; EE live image still blocked |
| Production plan | VPS+Compose recommended; not yet “productized SaaS” |
| Live Demo Co-Pilot | Code-complete through pilot readiness; **real meeting pilot still open** |

---

## 4. What we do well — and how to make it elite

### 4.1 Safety dialect (moat) — score ~4.6

**Well:** Completeness ≠ Cert ≠ Autopilot; human Promote; sandbox refuse on production Autopilot; confirm phrases; inherit-default; version capability grey-outs; Enterprise warn-only; honesty banners.

**Make it elite:**
- One **Safety glossary** component reused everywhere (kill duplicated honesty stacks).  
- Single confirm primitive: **ConfirmDialogV2 only** (kill v1 / `window.confirm`).  
- “Blast radius” preview on every write (models touched, ACL rows, inherit vs overwrite).  
- Audit trail UX that a consultant can show a client in 30 seconds.

### 4.2 Odoo Expert (closest to Intercom) — ~4.1

**Well:** Copilot drawer, citations, grounded-or-decline posture, never apply/certify/auto-promote, explain-this without blank Error log, Playwright coverage.

**Make it elite:**
- First-class **destination** (not only `?expert=1` on Overview + FAB).  
- Context chips: current model/view/job/ModuleSpec draft auto-attached.  
- “Do this for me” → **handoff cards** into Designer/Automations/App Studio (still human-confirmed).  
- Latency & quota honesty (recent Gemini 429 → hung Ollama → ISE fix is the right direction — productize).

### 4.3 Automations & Models list→composer — ~3.7

**Well:** Premium interaction pattern; draft/unsaved/saved session language; Option A Python honesty; hide-in-view vs delete-column clarity; Designer cross-link.

**Make it elite:**
- Production Playwright on Builder live route.  
- Completeness triad named on Automations (consistency).  
- Composer properties density to Figma-inspector level (spacing, sticky sections, keyboard).  
- Delete confirms via ConfirmDialogV2 everywhere.

### 4.4 Projects board — ~3.4 → high potential

**Well:** Only Linear-shaped board; stage language; Review-gated Apply (post-P0).

**Make it elite:**
- Confirm phrase on rollback / destructive history.  
- Diff UX worthy of GitHub PR review (file/model filters already sentence-case — push further).  
- Project as **home object** for AI Studio work (App Studio / ModuleSpec / Job attach here by default).

### 4.5 Capability & multi-version honesty — ~4.0

**Well:** Caps matrix 16–19; GA 17–19; adapters; grey-out banners; matching-major sandbox story; Power Ops recipe tags.

**Make it elite:**
- Connection “capabilities postcard” on Overview (human readable, not engineer dump).  
- One-click “why is this locked?” with upgrade/export paths.  
- EE live image still missing — keep honest; don’t fake Enterprise Studio features.

### 4.6 Sandbox → module → promote pipeline — ~4.0 (unique)

**Well:** Option A path; ephemeral sandbox; zip per major; Autopilot production refuse.

**Make it elite:**
- Progress UX that feels like Vercel deploy (stages, logs, retry, artifacts).  
- Config Packet never defaults apply-target to self silently.  
- Gold certification narrative without Accounting-shaped CTAs when gold is POS/etc.

### 4.7 Live Demo Co-Pilot (new differentiator) — code ~3.8 / proven ~2.5

**Well:** Consent, Attendee ops, Stage 1/2, private overlay, presenter ignore-list, docs/PILOT.md, 15 tests.

**Make it elite:**
- First **real Zoom/Meet pilot** with Attendee + Deepgram.  
- Latency SLO + presenter speaker allowlist tuning.  
- Overlay visual polish to Intercom-sidebar grade.  
- Tie answers to Expert citations one-tap.

### 4.8 Design token kit & dark mode — ~3.5

**Well:** Tokenized surfaces (`text-ink`, `bg-surface`, …); recent dark-mode contrast pass; vision-verify sweeps.

**Make it elite:**
- Formal **design system doc** (type scale, density, motion, elevation).  
- Ban raw hex in product pages (Designer page now 0 hex — keep that gate).  
- Motion: 150–200ms transitions; list→composer shared element feel.  
- Empty/loading/error states kit-complete on every surface.

---

## 5. What we don’t do well (or at all)

### 5.1 Craft / IA failures (P0–P1)

| Gap | Severity | Reality on tip |
|---|---|---|
| Designer still ~5.9k orchestrator | **P0** | Shell exists; extract incomplete |
| AI Studio product sprawl (App vs Draft vs Job vs ModuleSpec vs Projects) | **P0** | Operators confused which door to open |
| First-win onboarding <10 min | **P0** | Connect flow ≠ guided first customization |
| Cross-link coherence incomplete | **P1** | UAT matrix still sparse from Designer/Job |
| ConfirmDialog v1 still on Draft Promote | **P1** | Python install path |
| Access matrix live CRUD confirm depth | **P1** | Apply-live fixed; matrix toggles still hot |
| Expert not a destination | **P1** | Overview query + FAB dual launchers |
| Stage rails don’t collapse later panels | **P2** | Display-only rails |
| `/e2e/designer` legacy purple harness | **P2** | Confuses visual QA |

### 5.2 Missing or thin product capabilities

| Area | Status | Notes |
|---|---|---|
| In-Odoo OWL editor feel | Intentional external app | Mitigate with unbeatable live iframe + Open-in-Odoo |
| Property fields deep Studio | Out of scope / thin | Document; don’t half-claim |
| Full translation UI | Refused | CSV only |
| Collaborative multiplayer editing | Absent | Future SaaS |
| Commenting / review on drafts | Thin | Projects could own this |
| Mobile / tablet premium | Absent | Desktop-first OK short-term; say so |
| Marketplace / template gallery UX | Partial | Draft templates exist; not “App Store” grade |
| Billing / plans as product | Partial | UpgradeSheet + router exist; not Stripe-Dashboard-grade |
| Public marketing site = product quality | Weak | README/docs ≠ conversion |
| Real-meeting Co-Pilot proof | Open | Blocks “demo magic” claim |
| EE live verification | Blocked on image | Keep grey-out honesty |

### 5.3 Reliability / ops gaps

- LLM quota / fallback still a founder pain (STATE 2026-09-16).  
- Live RPC UAT not continuously proven on every premium surface.  
- Production host not the default daily environment.  
- SSE fan-out for Co-Pilot is process-local (scale story incomplete).

### 5.4 Test confidence skew

Honesty copy is over-tested vs page orchestrators. Strong Playwright: Automations, Draft, Expert. Weak: App Studio live route, Builder live route, Access, Menus, Job, ModuleSpec/Projects browser journeys.

---

## 6. Program of work — phased upgrade (proposed)

> Refine sequencing with Claude. Do not execute until v2 signed.

### Phase A — Foundation of craft (3–5 weeks) — “looks elite”

**A0. Design system freeze (UI DESIGN BOT PRIME §8A)** — type/density/elevation/motion tokens + hex lint + hard-reject checklist. **Do this before or in lockstep with A1** so extract doesn’t re-bake one-off chrome.

**A1. Extract View Designer**  
- Split `designer/page.tsx` into route + hooks + feature panels (<400 LOC page).  
- Single canvas path (kill dual-canvas leftovers).  
- Overlay always available in Live Odoo mode (already patched inject — verify UAT).  
- Density pass: properties panel = Figma inspector (accordion per §8A #4).

**A2. Kit hygiene**  
- ConfirmDialogV2 everywhere; ban ConfirmDialog v1 / `window.confirm`.  
- Empty/loading/error/forbidden kit mandatory checklist (§8A #8).  
- Shared list→composer kit starting from Automations pattern (§8A #7).

**A3. Confirm hygiene sweep**  
- Draft Promote → ConfirmDialogV2.  
- Access matrix destructive toggles confirm.  
- Projects rollback / delete confirm phrase.  
- Expert `window.confirm` → kit dialog.

**Exit:** Re-run chrome UAT; Designer ≥4.0; chain avg ≥4.0.

### Phase B — Journey seamlessness (3–5 weeks) — “feels inevitable”

**B1. AI Studio IA collapse**  
Recommended product model (debate with Claude):

| Operator intent | Primary door | Secondary |
|---|---|---|
| “Describe what people should do” | **App Studio** (hero) | — |
| “Edit IR / ModuleSpec deeply” | ModuleSpec | via App Studio handoff |
| “Run implementation job” | Job Autopilot | from App/ModuleSpec |
| “Track drafts / apply / review” | **Projects** (home object) | — |
| Draft Studio | **Deprecate as hero**; keep as power workshop or merge stages into App Studio | |

**B2. First-win onboarding**  
- Post-connect checklist: pick model → add field → see in Designer live canvas → Open in Odoo.  
- Timebox demo script to 8 minutes with screenshots.

**B3. Cross-link graph**  
- Complete UAT cross-link matrix; Designer↔Builder↔Menus↔Access↔Expert↔Projects.

**Exit:** Untrained operator completes first customization without docs; AI door confusion ≤1 primary CTA.

### Phase C — Differentiators (4–6 weeks) — “nothing else has this”

**C1. Expert destination + handoff cards**  
**C2. Live Demo Co-Pilot real-meeting pilot + latency SLO**  
**C3. Sandbox deploy UX (Vercel-like)**  
**C4. Projects as system of record for AI work**

**Exit:** Investor demo script uses Expert + Co-Pilot + sandbox without apology.

### Phase D — Production & growth (ongoing)

**D1. Production host per `docs/PRODUCTION-PLAN.md`**  
**D2. Billing UX polish (if monetizing)**  
**D3. Marketing site matching product craft**  
**D4. Continuous live major-matrix + premium Playwright on live routes**

---

## 7. Surface-by-surface upgrade cards

### 7.1 View Designer — highest craft leverage

| Now | Target |
|---|---|
| Studio shell + tools rail + live canvas; 5.9k page | Extracted modules; Figma-grade props; seamless DnD; zero dual-canvas |
| Overlay click-to-select works when proxy injects | Always-on selection HUD; structure picker elite |
| XPath inherit advanced | Same power, progressive disclosure |

**Acceptance:** Chrome UAT ≥4.5; page.tsx <500 LOC; Playwright on `/connections/{id}/designer` with live Odoo optional flag.

### 7.2 App Studio

| Now | Target |
|---|---|
| Best brief in product | **The** AI entry; gold CTAs model-aware; Review not banner pile |
| ~1.4k page | Extracted stages; collapse completed stages |

### 7.3 Draft Studio

| Now | Target |
|---|---|
| Honesty excellent; layout worksheet | Merge into App Studio power mode **or** radical simplify to ModuleSpec workshop |
| Promote ConfirmDialog v1 | V2 + snapshotNote |

### 7.4 Job Autopilot

| Now | Target |
|---|---|
| Production refuse; resume fixed | Config Packet never silent-self; deploy-like progress; leave/return bulletproof |

### 7.5 ModuleSpec / Projects

| Now | Target |
|---|---|
| Workbenches + board | Projects = hub; ModuleSpec always linked; rollback confirms |

### 7.6 Automations / Builder / Menus / Access

| Now | Target |
|---|---|
| High mid-premium siblings | Shared list→composer kit; Access safety complete; Playwright |

### 7.7 Odoo Expert

| Now | Target |
|---|---|
| Best surface (4.1) | Destination route; handoffs; quota UX; single launcher |

### 7.8 Live Demo Co-Pilot

| Now | Target |
|---|---|
| Pilot-ready code | Real meeting proof; latency; overlay polish; optional allowlist sophistication |

### 7.9 Operate / Data / Govern

| Now | Target |
|---|---|
| Broad coverage; older UIX partial | Same premium dialect as Build/AI; empty states; danger confirms |

### 7.10 Shell / Overview / Connect

| Now | Target |
|---|---|
| Functional AppShell | Overview as mission control (health, next action, capabilities postcard) |
| Connect works | First-win wizard after connect |

---

## 8. Premium look/feel definition (acceptance language)

A surface is **truly premium** only if all are true:

1. **Visual:** token-only color; consistent type scale; ≤2 primary accents; dark mode WCAG-ish contrast.  
2. **Density:** Stripe/Linear — information dense without clutter; progressive disclosure.  
3. **Interaction:** list→composer or staged journey; keyboard paths; optimistic where safe.  
4. **States:** empty / loading / error / forbidden / success designed (not accidental).  
5. **Safety:** honest copy; confirm on blast radius; no fake “done.”  
6. **Continuity:** obvious next step to the adjacent surface.  
7. **Motion:** subtle, purposeful (150–200ms), no carnival.  
8. **Test:** Vitest for logic + Playwright chrome; live RPC for write paths on GA majors.

---

## 8A. Visual system upgrade (UI DESIGN BOT PRIME — folded 2026-09-16)

**Full proposal:** [`docs/VISUAL-SYSTEM-UPGRADE-PROPOSAL.md`](./VISUAL-SYSTEM-UPGRADE-PROPOSAL.md)  
**Status:** Design-only. Fold into Claude Sonnet v2. **Do not implement** until Fabian accepts keepers.  
**Hard reject:** anything that looks worse than tip; no gradients; no `#714B67`; no raw hex; no cluttered “premium” chrome; never soften honesty/safety copy.

### North star
Quiet density — **more signal per pixel, less chrome per decision**. Linear / Figma / Intercom / Stripe.

### Adopt into Phase A (before/with Designer extract)

| # | Recommendation | Acceptance sketch |
|---|---|---|
| 1 | **Freeze type + density tokens** (Inter-only product chrome; 13/20 body; 11 meta; list row 36px; inspector 280–320; 4/8/12/16 rhythm) | No one-off text sizes across 5 spot-check surfaces |
| 2 | **Flat elevation** — border + token shadows only | Reject glass/gradients on product chrome |
| 3 | **Motion 150–200ms** — opacity + ≤4px travel; reduced-motion = instant | No carnival springs |
| 4 | **Designer props (P0)** — Figma accordion (Selection open; Layout/Attributes/Inherit collapsed); single canvas; XPath progressive | ≥12 attrs above fold @1440×900; Designer visual UAT ≥4.5 |
| 5 | **AI Studio chrome** — App Studio sole hero CTA; Projects hub; Job/ModuleSpec secondary; Draft demoted; collapse completed stages; one Review panel | ≤1 primary AI CTA; untrained user names the door in ≤3s |
| 6 | **Overview mission-control** — health + next action + human capabilities postcard + recent Projects | No raw caps JSON as hero |
| 7 | **Shared list→composer kit** — Automations-grade session chips + sticky footer + ConfirmDialogV2 | Same kit across Automations/Builder/Menus/Access |
| 8 | **Empty/loading/error/forbidden kit** — structure-preserving skeletons; Expert link on RPC faults | Never fake “done” while sandbox-pending |

### Visual priority order (from design bot)
1. Design-system freeze + hex lint  
2. Designer inspector density  
3. AI Studio IA hierarchy  
4. Overview mission-control  
5. Shared list→composer + states sweep  
6. Co-Pilot overlay polish **only after** real meeting pilot (don’t pretty-lie)

### Open questions — need Fabian (+ Claude)

1. Inter-only product type vs keep a second type family?  
2. One accent — keep current token or cooler Linear-blue?  
3. Draft Studio: nav demote only, or merge into App Studio in M1?  
4. Compact density default, or opt-in?  
5. Share tip screenshots (Designer props, App Studio, Overview) as before baselines?

### PR review checklist (paste)
- [ ] Side-by-side looks better or equal to tip  
- [ ] No `#714B67` / decorative gradient / random hex  
- [ ] Safety copy not softened  
- [ ] Motion ≤200ms; reduced-motion OK  
- [ ] Token-only colors  
- [ ] No extra chrome that hides next action  

---

## 9. Journey maps (target)

### 9.1 Consultant first win (8 minutes)

Connect → Overview checklist → Models & Fields add `x_*` → Designer live canvas see field → Open in Odoo → Snapshot.

### 9.2 AI-assisted residual app

App Studio brief → diagnosis lock → Option A / ModuleSpec → sandbox → **human** Promote → Projects history.

### 9.3 Live client demo

Co-Pilot consent → Attendee join → overlay on display 2 → share meeting window only → client asks Odoo Q → private bullets → leave/purge.

### 9.4 Break-glass Expert

Fault banner → Expert diagnose → citation → handoff card to Designer/Automations → human apply.

---

## 10. Architecture & ops notes (for Claude)

| Layer | Today | Upgrade need |
|---|---|---|
| Web | Next.js ~3002 | Route-level code split; Designer extract |
| API | FastAPI ~8001 | Stable error envelopes (ISE hygiene ongoing) |
| App DB | Postgres + Alembic | Keep `DB_MIGRATIONS=auto` for deploy |
| Odoo | XML-RPC public ORM | Live UAT automation |
| Expert RAG | Optional extra | Production ingest required for quality |
| LLM | Gemini/Ollama/etc. | Quota fail-fast + honest UI (partially done) |
| Co-Pilot | Attendee self-host | k8s one-bot-per-pod; real Zoom SDK |
| Deploy | Compose deploy file | Execute PRODUCTION-PLAN Option A |

---

## 11. Competitive positioning (honest)

| Competitor class | They win on | We win on |
|---|---|---|
| Odoo Enterprise Studio | In-app OWL, brand trust | Community affordability; sandbox; honesty; Expert; Co-Pilot |
| Generic no-code (Retool etc.) | Polish, onboarding | Odoo-native metadata depth |
| Studio community clones | Familiarity | Legal clean-room; multi-version caps; promote discipline |
| Services-only consultancies | Delivery | Productized reuse + demos |

**Claim we can make after M1–C:**  
“Studio-class customization for Odoo Community — safer to promote, smarter to ask, and premium enough to demo without apology.”

**Claim we cannot make today:**  
“The most seamless / easiest / most beautiful Odoo no-code app anywhere.”

---

## 12. Prompt pack — refine with Claude (Sonnet)

Paste this file and ask Claude:

1. **Challenge the distance scores** — where am I too optimistic or too harsh?  
2. **Propose a sharper AI Studio IA** — merge vs rename vs progressive disclosure; kill sacred cows.  
3. **Reorder Phase A–D** for maximum investor-demo impact in 6 weeks.  
4. **Write Designer extraction architecture** (modules, hooks, state ownership) without prescribing line edits.  
5. **Define a 20-item Definition of Done** for “world-class v1” ship.  
6. **Identify 5 delight features** that aren’t more admin screens.  
7. **Risk register** — what breaks if we extract Designer aggressively?  
8. **Produce v2 of this spec** with acceptance tests per phase.

9. **Respect §2.3 three buckets** — do not reintroduce forever-bans for Bucket B/C items.  
10. **UI DESIGN BOT PRIME** will run a visual-system pass on v2; incorporate only proposals that **strictly improve** density/contrast/hierarchy vs today’s tip (reject decorative regressions).

Constraints to remind Claude: Bucket A hard locks (clean-room; Promote human; Completeness≠Cert≠Autopilot; WhatsApp out; no default live state=code); Bucket B = gated power (LLM Python OK behind sandbox+promote); Bucket C = deferrals reopen on signal; Community 17–19 GA.

---

## 13. Immediate next actions (after Claude v2 — not now)

1. Fabian answers §8A open questions (type, accent, Draft fate, density default) + optional tip screenshots.  
2. Fabian + Claude produce **SPEC v2** locking IA + adopting/rejecting §8A keepers (hard-reject regressions).  
3. Only then start Phase A on `premium-local-tip` (A0 design freeze → A1 Designer extract).  
4. Re-UAT with screenshots into `docs/uat-premium/`.  
5. Real Co-Pilot meeting pilot in parallel (ops track) — overlay polish after proof.

---

## 14. Appendix — evidence snapshot

### 14.1 UAT scorecard (2026-09-14)

Designer 2.4 · Automations 3.7 · Builder 3.7 · Menus/Access 2.9 · App Studio 3.4 · Draft 3.1 · Job 3.3 · ModuleSpec 3.3 · Projects 3.4 · Expert 4.1 · **Avg 3.3**

### 14.2 Tip commits (selected)

- `2554e0a` Studio-like View Designer shell  
- `6865184` Dark-mode contrast  
- `9e7ace5` Live Demo Co-Pilot  
- `febdab7` Studio tax_id + Repair-with-AI honesty  

### 14.3 Key doc paths

- `docs/UAT-PREMIUM-WORLD-CLASS.md`  
- `docs/STUDIO_PARITY_BY_MAJOR.md`  
- `docs/PRODUCTION-PLAN.md`  
- `docs/OPERATOR-FEATURE-DEMO-GUIDE.md`  
- `docs/live-demo-copilot/PILOT.md`  
- `skills/studio-parity.md`  

### 14.4 Open operator proofs still required

- [ ] Live RPC UAT on write paths (create model, inherit save, automation, Autopilot refuse)  
- [ ] Real Attendee Zoom/Meet Co-Pilot pilot  
- [ ] Designer extract + re-score ≥4.0  
- [ ] Production host smoke (`launch_smoke.sh` on public URL)

---

## 15. Closing judgment

**Capability-wise**, you are surprisingly close to “Studio-class for Community.”  
**Craft- and journey-wise**, you are mid-premium with elite pockets (Expert, safety dialect, Automations/Builder patterns, Co-Pilot seed).  

The path to “best / seamless / easiest / truly premium” is **not more surfaces** — it is **extraction, IA collapse, first-win onboarding, live proof, and obsessive density**. Protect the honesty moat; spend the next quarters on craft and inevitability.

*End of SPEC v1 — refine before build.*
