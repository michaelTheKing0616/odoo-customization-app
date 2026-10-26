# BOT-V20-ACCESS — version-aware access changes for Bots

## Goal
Bots change access the same way on Odoo 17-20. Odoo 20 merges ir.model.access and ir.rule into
`ir.access` (operation letters c/r/u/d + domain) and is JSON-RPC/JSON2 only. 19/20 use
`group_ids`/`user_ids`/`all_group_ids`; 17/18 use `groups_id`/`users` (+ reified
in_group_N / sel_groups_*, never written here).

## Scope (app/bots/access.py)
- Typed ops: `UserGroups` (add/remove groups on a user), `GroupSpec` (create/modify a group,
  implied groups), `AccessRow` (create/modify an access right), `RecordRule` (create/modify a
  record rule). Per-version field maps (`VMAPS`, detected from live fields_get + ir.model).
- One normalised shape for reads, diff preview and before-image on every version.
- Every op: lockout.simulate (refusal = refused), risk floor from the existing classifier +
  reviewed append-only rule (core groups / global rules = L3, else >= L2), WriteGate only
  (writes: `WriteGate.run` + `before_image.RouteA`; creates: `WriteGate.call`), undo per op
  (simulated and gated too). No raw RPC writes, no new exemption.
- Live drift test: allowed fields vs fields_get on 17 and 20 (19 from source only).

## Results (2026-10-26 12:05 UTC+1, after the review fixes; nothing edited after the live run)
- Review MEDIUM fixed in `lockout.simulate`: after every step, any gain in the Bot's own access is refused
  (groups, ACL perms, applicable rules, companies, by any route). Live on 20, adding a probe group to the
  implied groups of group_system was refused with "widens the Bot's own access (groups)". On 17 the same request is refused earlier
  (adding an implied group to a group with members).
- LOWs: (2) undoing a group create refuses while any access row, record rule, menu or action names the group (also members/implied-by).
  (3) `base.group_no_one` is now a core group, and the core check follows the implied chain. (4) Odoo 20 group rows with a domain carry a
  plain "WARNING ... GIVES ... access" line. (6) the lockout live file is configured by env and skips cleanly.
- Ruff format + check clean on all 7 files. Unit: v20_access 45, lockout_sim 39.
- Live 17 + 20 (ODOO_LIVE=1, 18117/18120): v20_access_live 2/2 (drift ok, 5 applied + 5 undone, lockout
  and self-widening refused) and lockout_sim_live 8/8 on the NF DBs. Evidence: `~/.ingenium_nf/nfwt/BOT-V20-ACCESS_live.txt`.
- Both orders (v20_access + live, kill_audit, role_privileges, approval_tiers, lockout_sim + live, risk,
  risk_adversarial, risk_escalation): 2244 passed, 6 skipped, 0 failed/errors each. Sandboxes stopped.
- Earlier live finding: Odoo 20 makes every group imply `base.group_user_regular`. The layer previews it and refuses to remove it.

## Gaps (honest)
- 19 is from source only (no sandbox). 18 is assumed to match 17 (not run live).
- Global record rules are always refused (they bind the Bot). Any change to rules that apply to the Bot is refused, even one that narrows.
- 17/18: adding an implied group to a group with members is refused (it materialises and can't be undone).
- Undoing a group create skips lockout (lockout refuses group deletes); the reference checks above stand in for it. res.users.role
  is absent on both sandboxes and is not handled. Odoo 20: one group per row.

## Tracking line (proposal for STATE_NF; not edited)
`BOT-V20-ACCESS done (review fixes in): access.py version-aware access changes 17-18/19/20 via WriteGate, undo, L3; lockout.simulate refuses any Bot self-gain; unit + live 17/20 green.`

## Merge list
- apps/api/app/bots/access.py (new)
- apps/api/app/bots/risk/rules.py (appended only)
- apps/api/app/bots/lockout.py (minimal edit: `_sig`, `_bot_view`, gain check)
- apps/api/tests/test_nf_bot_v20_access.py (new)
- apps/api/tests/test_nf_bot_v20_access_live.py (new)
- apps/api/tests/test_nf_bot_lockout_sim.py (one test appended)
- apps/api/tests/test_nf_bot_lockout_sim_live.py (env-configurable target)
- docs/build-plan/cards/phase-5/BOT-V20-ACCESS.md (new), docs/build-plan/cards/phase-5/BOT-LOCKOUT-SIM.md (note appended)

Leave out (not mine): docs/vision-verify/trial-xray/, apps/web/.next-trial-*, apps/web/src/app/e2e/bv-ui-trial/,
apps/web/src/app/e2e/trial-xray-grok/.
