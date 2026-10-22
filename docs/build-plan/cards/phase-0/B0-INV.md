# B0-INV: docs/handoff/WORKTREE_STATE.md groups uncommitted changes by feature + commit plan (no com

ID: B0-INV
Title: docs/handoff/WORKTREE_STATE.md groups uncommitted changes by feature + commit plan (no com
Status: done
Phase: 0
Priority: P0
Type: docs
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: XS (caps in budget.json). Stop at 80%.
Ledger IDs: P0-9-AC1;P0-9-AC2;P0-9-AC3;P0-9-AC4;VD-REG-CLASSIC;DOC-WORKTREE;DISC-TMP;DISC-ROOTPATCH
Depends on: none (phase order applies)
Routing: Worker: L1 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L1 separate session · Score: 1 (C0 U0 F0 K0 V0 I1)
Context pack:
- `sed -n '508p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- `sed -n '509p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- `sed -n '510p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- `sed -n '511p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- `sed -n '261p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- docs/build-plan/FACTS.md
File allow-list:
- docs/handoff/WORKTREE_STATE.md (new)
Goal: Update the named documents so `B0-INV`'s ACs are true; no product code.
Steps:
1. Read the context pack. Make only the documentation change the ACs ask for, in plain words (glossary).
2. Check every path and command you cite exists: `ls <path>` / `rg -n <symbol>` → found.
3. Run `python3 scripts/plan_lint.py all` if a plan file changed → 0 new errors.
4. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong.
Acceptance criteria:
- AC1: a written inventory (`docs/handoff/WORKTREE_STATE.md`) groups the uncommitted changes by feature with a proposed commit plan. You commit nothing without Tope's yes. (source: INGENIUM_MASTER_HANDOVER.md L508)
- AC2: leftover dev servers and stray processes are listed with their purpose; you stop only ones you started. (source: INGENIUM_MASTER_HANDOVER.md L509)
- AC3: `/tmp` backups referenced by PROGRESS (`/tmp/designer_classic.bak`, `/tmp/fp_*.bak`, `/tmp/no_school_casual.gold.bak`, eval outputs) are listed; anything worth keeping is proposed for a durable location under `docs/` or `apps/api/evals/v2/` (needs Tope). (source: INGENIUM_MASTER_HANDOVER.md L510)
- AC4: root-level patch and APPLY scripts are listed with whether their content is already in the tree. (source: INGENIUM_MASTER_HANDOVER.md L511)
- AC5: Known bugs. Dark-mode paper contrast (fixed G9; keep the test). Margins overlay for the PDF proof deferred because the PDF viewer's page offset is unknown (touch 131). `/designer/classic` now redirects to `/designer` (backup at `/tmp/designer_classic.bak` on the Mac; that file may not survive a reboot). (source: INGENIUM_MASTER_HANDOVER.md L261)
- AC6: docs/handoff/WORKTREE_STATE.md (source: ledger DOC-WORKTREE, §4 P0-9 AC1)
- AC7: /tmp backups worth keeping (source: ledger DISC-TMP, §4 P0-9 AC3)
- AC8: root .patch + APPLY_*.sh (source: ledger DISC-ROOTPATCH, §4 P0-9 AC4)
Symbols:
- New file `docs/handoff/WORKTREE_STATE.md`.
- `/tmp` names in AC3: `designer_classic.bak`, `fp_*.bak`, `no_school_casual.gold.bak`.
- Root `APPLY_*.sh` (9): `APPLY_ANY_CUSTOMIZATION_P0_ON_MAC.sh`, `APPLY_ATLAS_ELITE_P4_ON_MAC.sh`, `APPLY_BUILD_SPINE_P2_ON_MAC.sh`, `APPLY_CONTINUOUS_INVENT_P3_ON_MAC.sh`, `APPLY_FX_RATE_JOB1_ON_MAC.sh`, `APPLY_HINT_CHROME_FLASH_TOGGLE_ON_MAC.sh`, `APPLY_INVENT_FAMILIES_ARC3_ON_MAC.sh`, `APPLY_MARKUP_WHT_JOB2_ON_MAC.sh`, `APPLY_REPORT_LAYOUT_SCRUB_JOB3_ON_MAC.sh`.
- Root `*.patch` (13): `0001-feat-ingenium-any-customization-p0.patch`, `0001-feat-ingenium-atlas-elite-p4.patch`, `0001-feat-ingenium-build-spine-p2.patch`, `0001-feat-ingenium-continuous-invent-p3.patch`, `0001-feat-ingenium-first-try-generate-repair.patch`, `0001-feat-ingenium-fx-rate-job1.patch`, `0001-feat-ingenium-generate-spray-grammar.patch`, `0001-feat-ingenium-install-grammar-o2m-preview.patch`, `0001-feat-ingenium-invent-families-arc3.patch`, `0001-feat-ingenium-markup-wht-job2.patch`, `0001-feat-ingenium-prefer-host-fullapp-noun.patch`, `0001-feat-ingenium-report-layout-scrub-job3.patch`, `0001-feat-ingenium-state-title-identity-spray.patch`.
Worked example:
- One group in the file: a feature heading, the paths in that feature, one proposed commit message, and the line `commit: no`. `ls docs/handoff/WORKTREE_STATE.md` finds the file. Each root script and patch above appears once, marked `in tree` or `not in tree`.
Decision:
| item | action |
| a process this session started | list its purpose, then stop it |
| any other process, including servers already on 3002, 8001, 8069-8073, 5433, 5436, or 11434 | list its purpose, leave it running |
| a `/tmp` backup worth keeping | name a path under `docs/` or `apps/api/evals/v2/`; leave the file in `/tmp` until Tope says yes |
Test plan:
- `python3 scripts/plan_lint.py all` → 0 new errors
- `ls`/`rg` each cited path → found
Common mistakes: citing a path that does not exist; restating the handover instead of citing its line; upgrading a label without evidence.
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
