# Odoo Customization App — World-Class Build Spec v2
### (Build-Ready — verified against tip `febdab7` on 2026-09-16)

**Supersedes:** `PREMIUM-WORLD-CLASS-UPGRADE-SPEC.md` (v1) and the Claude-refined draft pastedin chat (same day)  
**Human sign-off:** **Tope** (not “Fabian” — same person/project; Claude name mix-up resolved)  
**Audience:** Build agent + Tope  
**Tip verified:** `premium-local-tip` @ `febdab7`  
**Status:** Build-ready **after** §0 process gates. Measured claims below were checked on disk — not assumed from prose.

**Bar:** Apple / Stitch / Linear / Figma / Intercom / Stripe quiet density — not Odoo Enterprise Studio clone.  
**Clean-room:** Public ORM/RPC + public Studio docs only. Never `web_studio` source.

**Visual system locks (Tope, 2026-09-16):** Not a designer — “look like the best no-code apps (Stitch, Apple).” Locked as:
- **Inter-only** product type (no second type family in app chrome)
- **Keep current accent** token (one accent; no Linear-blue rebrand mid-craft)
- **Compact density default**
- **Draft Studio → merge into App Studio in M1** (nav demote alone is insufficient; aligns §3 IA)

Companion: `docs/VISUAL-SYSTEM-UPGRADE-PROPOSAL.md` (UI DESIGN BOT PRIME) — adopt keepers under hard-reject (never worse than tip).

---

## 0. How the build agent should use this document

1. **§2 is law.** Every task in §10 must be checked against §2 before execution. If a task cannot be completed without violating a Bucket A lock, **stop and escalate to Tope** — do not reinterpret, workaround, or soften.
2. **§3–§5 are resolved design decisions.** Do not re-litigate IA or Designer architecture mid-build unless a stop-ship risk appears — then flag in PR and wait.
3. **§9 defines “done” numerically.** Demo alone does not complete a phase.
4. **§10 is the backlog.** Within a phase, work top→bottom. Phase order follows §4 (6-week demo window).
5. **Every PR touching Bucket A or B must state in the PR description which bucket it touches and why it stays compliant.**
6. Report against §9 artifacts (screenshots, test reports, LOC counts), not vibes.
7. **HARD PROCESS (added after Claude review):** After each week’s §9 checklist passes, **stop and wait for Tope’s explicit sign-off** before starting the next week. Escalation-on-Bucket-A-violation alone is not enough for unsupervised multi-week execution.

---

## 0A. Verification log (measured on tip — 2026-09-16)

| Claim | Source in Claude draft | Measured on tip | Verdict |
|---|---|---|---|
| Tip hash `febdab7` | Assumed | `git rev-parse` → `febdab7` on `premium-local-tip` | **Confirmed** |
| Designer `page.tsx` ~5,900 LOC | ~5,900 / UAT said 5,739 | `wc -l` → **5900** | **Confirmed** (grew slightly since UAT) |
| Designer leftover hex | UAT mauve open | `grep` hex in designer page → **0** | **Improved since UAT**; extract still needed |
| Chrome UAT avg ~3.3; Designer 2.4; Expert 4.1 | v1 UAT doc | Present in `docs/UAT-PREMIUM-WORLD-CLASS.md` | **Confirmed as historical UAT** (not re-run) |
| AI Studio many doors | 5 doors | `nav.ts` **7** `group: "ai"` entries (App, Draft, Job, ModuleSpec, Projects, Expert, Live Demo Co-Pilot) | **Confirmed; worse than “5”** — Co-Pilot + Expert also in AI group |
| ConfirmDialog v1 remnants | Sweep needed | **7** product imports of `@/components/ConfirmDialog` (wizard, designer, connect, approvals, invoicing, property fields, scanner) + e2e harness; **2** `window.confirm` in Expert | **Confirmed Week-1 work real** |
| Financial / accounting logic guard | Claude asked if missing | **`protected_modules.py` + `protected_enforcement.py` + `strip_protected_module_effects`**: Tier-1 includes `accounting_core` (`account*`), payments, payroll, etc. — **never generate business logic** on those models; link-only OK | **Exists — promote to Bucket A7** |
| Attendee for Co-Pilot | Locked capture layer | GitHub `attendee-labs/attendee`: ~730★, **pushed 2026-09-16**, not archived, **Elastic License 2.0 (ELv2)** | **Active, but ELv2 restricts offering Attendee itself as multi-tenant hosted SaaS** — self-host / BYO OK; productize carefully |

### Attendee license diligence (required reading before Co-Pilot “platform-hosted” claims)

Upstream LICENSE is **Elastic License 2.0**: you may use/modify, but **may not provide the software to third parties as a hosted or managed service** that gives users access to a substantial set of Attendee’s features.  

**Implication for our prod story:** “We run Attendee pods for every customer” can conflict with ELv2. Safer postures already in memory: **BYO Attendee for enterprise residency**, or ensure legal review before multi-tenant hosted Attendee. Capture layer choice stays Attendee for *our* bot join API pattern — hosting topology must stay license-clean.

---

## 1. Refined distance-to-goal scoring (v2)

(Claude’s recalibration adopted — verified that the *inputs* exist; scores themselves are judgment.)

| Dimension | v1 | v2 working | Note |
|---|---:|---:|---|
| Capability breadth | 4.2 | **3.8** | Usable buyer breadth |
| Safety / honesty | 4.6 | **4.6** | Moat — plus Tier-1 PCM confirmed on tip |
| Visual / interaction | 3.2–3.6* | **3.4** | Until Phase A exit UAT re-runs |
| Journey seamlessness | 3.0 | **3.0** | 7 AI-group nav items measured |
| Live reliability | 3.4 | **3.0** | Quota fragility still real (STATE 2026-09-16) |
| Onboarding &lt;10 min | 2.8 | **2.8** | |
| Prod SaaS readiness | 3.0 | **2.6** | Plan ≠ executed |
| Differentiator delight | 3.8 | **3.5** | Expert strong; Co-Pilot unproven live |

---

## 2. Non-negotiable constraints

### 2.1 Bucket A — Hard locks (STOP)

| # | Lock | Enforcement |
|---|---|---|
| A1 | Clean-room — no `web_studio` / OEEL-lineage source | Grep diffs |
| A2 | Promote stays human | Trace promote/apply_live/production writes to confirm UI |
| A3 | Sandbox before Option A / Python module install | |
| A4 | WhatsApp out for Co-Pilot forever | |
| A5 | No default live `state=code` path | |
| A6 | Completeness 10.0 ≠ go-live / Cert / Autopilot | |
| **A7** | **Protected Core Modules — never generate business logic on Tier-1 models** (`account.*`, payments, payroll, stock valuation, etc.). Link-only from custom models OK. Preserve `strip_protected_module_effects` / `protected_enforcement` through all refactors. | Diff review + existing unit tests must stay green |

### 2.2 Bucket B — Default-off, gated (build behind rails)

| Capability | Gate |
|---|---|
| LLM Python / Option A | Sandbox smoke + human Promote |
| View overwrite | Confirm phrase + snapshot; inherit default |
| Access live pack / hot ACL | Confirm + blast-radius preview |
| Job Autopilot / Config Packet | Non-prod / named target; refuse production write_mode |
| Destructive Power Ops / bulk | Dry-run + confirm + recipe tags |

Doc bug if you write “we don’t support X” for these — say “available behind [gate].”

### 2.3 Bucket C — Phase deferrals (reopen on signal)

Unchanged from Claude v2: property fields, full translation UI, mobile, multiplayer, Studio OWL *clone* (never as clone strategy), majors ≤15/20+, EE live image.

---

## 3. Information architecture v2 — AI Studio collapse

### 3.1 Routing table

| Intent | Primary | Others |
|---|---|---|
| Describe & build | **App Studio** (sole hero CTA) | |
| Track drafts/history | **Projects** (home object; auto-attach) | |
| Edit IR/spec | **ModuleSpec** workshop via handoff only | Not top-nav peer |
| Watch job | **Job Autopilot** execution view via App/Project | Not starting point |
| Old worksheet | **Draft Studio** merged into App Studio power mode; existing drafts migratable from Projects | No data delete |

### 3.2 Nav consequence

- AI Studio top-level: **App Studio + Projects** only (Expert + Live Demo Co-Pilot: decide breadcrumb — recommend Expert under Operate/Assist or keep as tertiary; Co-Pilot under AI as tertiary or Demo tools — **default for Week 2:** Expert as contextual drawer + dedicated route; Co-Pilot remains shipped but not a competing “start AI” CTA).
- Overview AI entry + FAB → same App Studio URL.
- Acceptance: first-time op reaches App Studio ≤1 click; ModuleSpec/Job only after Projects/App context.

### 3.3 Why Projects as home

Reuse the only Linear-shaped board already on tip.

### 3.4 Visual system (locked)

Quiet density Apple/Stitch/Linear: Inter-only, current accent, compact default, §8A of v1 upgrade spec + UI DESIGN BOT proposal keepers, hard-reject regressions.

---

## 4. Six-week sequencing

| Week | Focus |
|---|---|
| **1** | Confirm hygiene (v1→V2, kill `window.confirm`) + LLM 429 fail-fast + blast-radius preview component |
| **2** | AI Studio IA collapse + Projects auto-attach |
| **3–4** | Designer strangler Phase 1 (Provider + Tools Rail + Field Inspector); flag `designer_v2_shell` |
| **5** | First-win onboarding ≤8 min recorded |
| **6** | Re-UAT ≥4.0 avg & Designer ≥4.0; Expert destination route; live RPC four paths |

**After each week:** Tope sign-off gate (§0.7).

Post-week-6: remaining Designer panels, cross-links, Co-Pilot real pilot (license-aware hosting), sandbox Vercel-style UX, PRODUCTION-PLAN, delight features.

---

## 5. View Designer extraction architecture

Target `page.tsx` **&lt;400 LOC** from **5900** measured.

Tree / reducer / strangler / progressive XPath — **as in Claude v2 §5**, adopted verbatim in substance:
- `DesignerProvider` + pure reducer = only cross-panel state
- Split selection vs history contexts if re-render lag
- One panel per PR, flag-gated, Playwright per panel
- Keep `useDesignerHistory` — wire, don’t rewrite
- Overlay injection snapshot both flag states every panel PR

---

## 6. Definition of Done — 20 items

Adopt Claude v2 §6 checklist in full, with these measured clarifications:
- DoD #1: start from **5900** LOC baseline (not 5739).
- DoD #3: includes Expert `window.confirm` (2 sites) + 7 ConfirmDialog v1 imports.
- DoD #4: after Week 2, AI *start* nav = 2; Expert/Co-Pilot must not reintroduce “five equal doors.”
- DoD #19: includes **A7** PCM/Tier-1 preservation.
- Add DoD #21: **Week sign-off from Tope recorded** after each of weeks 1–6.

---

## 7. Five delight features

As Claude v2 §7: locked explainer, sandbox deploy stages, one-tap Expert, capabilities postcard, GitHub-PR-style snapshot diff.

---

## 8. Risk register

As Claude v2 §8, plus:
| Risk | Mitigation |
|---|---|
| PCM/Tier-1 silently weakened during AI Studio or Designer refactors | A7 + existing PCM tests must run on every relevant PR |
| Attendee ELv2 vs “hosted for all tenants” | Legal/topology review before multi-tenant Attendee hosting; prefer BYO/enterprise residency |

---

## 9. Acceptance tests per phase

As Claude v2 §9, plus explicit **Tope sign-off** checkbox each week.

Week 1 grep must include `components/ConfirmDialog` imports (not only ConfirmDialogV1 string).

---

## 10. Build backlog

As Claude v2 §10 week tickets, with Week 1 expanded to the **measured** ConfirmDialog + window.confirm sites, and post-week-6 Co-Pilot item annotated **“Attendee ELv2 hosting review first.”**

---

## 11. Architecture & ops

As Claude v2 §11; Co-Pilot row: Attendee remains capture API; hosting must respect ELv2.

---

## 12. Glossary & sources

- Bucket A/B/C — §2  
- PCM / Tier-1 — `apps/api/app/protected_modules.py`, `protected_enforcement.py`, `ai_rules.strip_protected_module_effects`  
- Strangler — §5  
- Visual proposal — `docs/VISUAL-SYSTEM-UPGRADE-PROPOSAL.md`  
- v1 audit — `docs/PREMIUM-WORLD-CLASS-UPGRADE-SPEC.md`  
- UAT — `docs/UAT-PREMIUM-WORLD-CLASS.md`  

---

## 13. Claude review responses (squared)

| Claude concern | Resolution |
|---|---|
| “Fabian” vs you | **You are Tope.** Same project. Specs now say Tope. |
| Verify LOC / tip / UAT numbers | Done in §0A — 5900 LOC, febdab7, UAT file exists |
| Human checkpoint per week | §0 item 7 + DoD #21 |
| Financial/accounting guardrail | **Present** as PCM Tier-1; elevated to **A7** |
| Attendee diligence | Active repo; **ELv2** — hosting caution recorded |

---

## 14. Build readiness verdict

| Gate | Status |
|---|---|
| Spec quality (self-audit, checkable DoD, strangler) | Pass |
| Load-bearing numbers verified on tip | Pass |
| Naming / ownership | Pass (Tope) |
| PCM / accounting logic guard called out | Pass (A7) |
| Attendee license understood | Pass with **hosting caveat** |
| Visual direction locked without designer burden | Pass (Apple/Stitch quiet density) |
| Unsupervised 6-week run | **Not yet** — requires per-week Tope sign-off |

**Verdict:** Good enough to **start Week 1** when Tope says go — not good enough for fully unsupervised six-week execution.

---

*End of Build Spec v2 (verified). Stop-ship on any Bucket A breach including A7.*
