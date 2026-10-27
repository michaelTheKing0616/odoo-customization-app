# DOC-SPECS-INTAKE: copy SPEC.md + IDEA.md from box into docs/specs/

ID: DOC-SPECS-INTAKE
Title: copy SPEC.md + IDEA.md from box into docs/specs/
Status: done
Phase: 0
Priority: P0
Type: docs
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: XS (caps in budget.json). Stop at 80%.
Ledger IDs: DOC-SPEC-SPEC;DOC-SPEC-CSS;DOC-SPEC-BRS;DOC-SPEC-AS;DOC-SPEC-GAP;DOC-SPEC-BRAND
Depends on: none (phase order applies)
Routing: Worker: L1 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L1 separate session · Score: 1 (C0 U0 F0 K0 V1 I0)
Context pack:
- `sed -n '27,30p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- `sed -n '622,624p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- docs/
- docs/build-plan/FACTS.md
File allow-list:
- docs/
Goal: Update the named documents so `DOC-SPECS-INTAKE`'s ACs are true; no product code.
Steps:
1. Read the context pack. Make only the documentation change the ACs ask for, in plain words (glossary). Decision 2026-10-23: handover §0.2 box paths `/workspace/ingenium_builders/` and `/home/box/design-repo` are not on this machine. The named copies are already in `docs/specs/` and are non-empty, and the AC5/AC6 absence files are absent. Prove that with `ls`. Do not fetch, rewrite, or empty those files. Do not edit `docs/build-plan/`, `apps/api/evals/v2/PROGRESS.md`, or anything outside `docs/specs/` and `docs/brand/`. `apps/web/public/brand/` is `ls` only. If a named copy is missing or empty, STOP.
2. Check every path and command you cite exists: `ls <path>` / `rg -n <symbol>` → found.
3. Run `python3 scripts/plan_lint.py all` if a plan file changed → 0 new errors.
4. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong.
Acceptance criteria:
- AC1: copy SPEC.md + IDEA.md from box into docs/specs/ (source: ledger DOC-SPEC-SPEC, §0.2; App. D)
- AC2: copy CONFIG_SUITE_SPEC.md + ODOO_CONFIG_CATALOG.md (source: ledger DOC-SPEC-CSS, §0.2)
- AC3: copy BRIDGE_RUNNER_SPEC.md (source: ledger DOC-SPEC-BRS, §0.2)
- AC4: copy APP_STUDIO_HANDOFF.md + APP_STUDIO_FIX_PLAN.md (blocks App Studio Pack) (source: ledger DOC-SPEC-AS, §0.2; §13.3 prompt)
- AC5: GAP_AUDIT copied 21 Oct; builders PROGRESS.md + stage3/contrast.md still box-only (source: ledger DOC-SPEC-GAP, §0.2)
- AC6: brand SVGs present (docs/brand, public/brand); BRAND_GUIDE.md + brand tokens.css + DESIGN_SYSTEM_PLAYBOOK.md still box-only (source: ledger DOC-SPEC-BRAND, §5.2; §0.2)
Symbols: `docs/specs/SPEC.md`, `docs/specs/IDEA.md`, `docs/specs/CONFIG_SUITE_SPEC.md`, `docs/specs/ODOO_CONFIG_CATALOG.md`, `docs/specs/BRIDGE_RUNNER_SPEC.md`, `docs/specs/APP_STUDIO_HANDOFF.md`, `docs/specs/APP_STUDIO_FIX_PLAN.md`, `docs/specs/GAP_AUDIT.md`, `docs/brand/ingenium-logo.svg`, `apps/web/public/brand/ingenium-logo.svg`.
Worked example:
- Example AC1: `docs/specs/SPEC.md` and `docs/specs/IDEA.md` exist and are non-empty.
- Example AC2: `docs/specs/CONFIG_SUITE_SPEC.md` and `docs/specs/ODOO_CONFIG_CATALOG.md` exist and are non-empty.
- Example AC3: `docs/specs/BRIDGE_RUNNER_SPEC.md` exists and is non-empty.
- Example AC4: `docs/specs/APP_STUDIO_HANDOFF.md` and `docs/specs/APP_STUDIO_FIX_PLAN.md` exist and are non-empty.
- Example AC5: `docs/specs/GAP_AUDIT.md` exists and is non-empty. `docs/specs/PROGRESS.md` and `docs/specs/stage3/contrast.md` do not exist. Other `PROGRESS.md` files in the repo are not the builders log.
- Example AC6: `docs/brand/ingenium-logo.svg` and `apps/web/public/brand/ingenium-logo.svg` exist. `docs/brand/BRAND_GUIDE.md`, `docs/brand/tokens.css`, and `DESIGN_SYSTEM_PLAYBOOK.md` do not exist. `apps/web/src/styles/**/tokens.css` is the app token file, not the box brand file. `apps/web/public/brand/` is outside the allow-list; confirm with `ls` only.
Test plan:
- `python3 scripts/plan_lint.py all` → 0 new errors
- `ls`/`rg` each cited path → found
Common mistakes: citing a path that does not exist; restating the handover instead of citing its line; upgrading a label without evidence.
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
