# BOT-LOCKOUT-SIM: simulate access before any lockout-class change

Phase 5 (Bots). Sources: taxonomy DECISIONS.md (L1/L2/L3 tiers, per-button risk), the
catalogue R8 floors (`res.groups`, `res.groups.privilege`, `res.users`, `res.users.deletion`)
via `rules.MODEL_FLOOR` / `SECURITY_FIELDS` / `SENSITIVE_MODELS`, gate R8 branch
(`GateCtx.admins_after`, `removes_bot_access`), debate RESOLUTION.md.

## Spec
Before a Bot applies a change that can lock people out, `app/bots/lockout.simulate(rpc,
changes, bot_uid=)` reads the live access model through `diff.ReadOnly` (users incl.
inactive, groups + implied closure, `ir.model.access`, `ir.rule`, allowed companies,
menu/action groups, OAuth/API-key owners), applies the plan in memory and compares.

Scope: `needs_simulation` = risk layer floors the change at R8, or the model has a handler.
Every R8-floored model is in `HANDLERS` or `NOT_LOCKOUT` (with a reason); drift-tested.
Covers groups/roles, archive/deactivate, login/password/2FA, OAuth/LDAP/passkey, record
rules, access rights, company/allowed companies, signup/reset params, mail server, implied
groups, menu/action groups, admin users, API keys.

Refuse (RF-R8 `lockout-simulation`) when: no active internal user other than the Bot keeps
Settings (`base.group_system`, implied closure) with a working login path (active, login
unchanged, allowed company, OAuth provider on); the Bot's own user is touched or its groups,
ACL perms, companies or API key shrink; a new implied-group cycle; deleting users, groups,
companies or menus/actions (archive instead); any unknown field/command, unreadable record or
Odoo 19/20 `all_group_ids` disagreeing with the computed closure.
Otherwise always L3 (R8) with a plain-language impact list (who loses/gains what: sign-in,
Settings, internal access, portal->internal, groups, per-model ACL perms, menus, record-rule
visibility) plus counts and reasons; blanket auth changes (mail server, signup/reset params,
OAuth, LDAP) are named. Revertibility via `before_image.field_ops`/`reverse_op`: not
revertible (e.g. password) -> `revertible=False` and a reason on the card.
`gate_facts()` feeds `GateCtx`. Writes never happen here (guard/before-image only).

Versions: 17/18 `groups_id`, `res.groups.users`, reified `in_group_N`/`sel_groups_A_B`;
19/20 `group_ids`, `user_ids`, `all_group_ids`, `res.groups.privilege` (display only).

Also: `guard.KillSwitch.open_job` refuses reusing a live job whose level < need (RF-R3).

## Results
- Files: `app/bots/lockout.py` (new), `app/bots/guard.py` (open_job level check),
  `tests/test_nf_bot_lockout_sim.py` (27), `tests/test_nf_bot_lockout_sim_live.py` (4 x 17/20).
- Permanent adversarial: last admin (groups/archive/login/group-members/in_group/sel_groups/
  OAuth), Bot-only admin, circular implied, portal->internal, company-only user, Bot demoted
  (direct, via group members, via implied, via API key, via ACL), 17/20 field names,
  20 effective-group cross-check, fail-closed set, read-only proof, weaker live job.

- Runs: own + kill_audit, risk, risk_adversarial, clone, snapshot, diff_blast suites:
  2272 passed, 20 skipped, forward and reverse file order; live 8/8 on Odoo 17 + 20
  (`~/.ingenium_nf/nfwt/BOT-LOCKOUT-SIM_live.txt`); ruff clean.

## Gaps
- Record-rule domains are not evaluated: rule changes list every user in the rule's groups
  (all users for global rules) as "may see different records".
- Menu parent chains and action-level group inheritance are not walked (own groups only).
- Password/OAuth-only logins cannot be read; users touched by a login change or a disabled
  provider are counted as without a working login (fail closed).
- Odoo 20 has no `ir.model.access`/`ir.rule`: one `ir.access` (operation letters r/u/c/d +
  domain). Rows are read as grants; domain rows count as record rules (not evaluated).
- Not yet wired into a Bot apply path / approval card UI (next card).

## Review round 1 (BLOCK: 2 HIGH, 1 MEDIUM, lows) - fixed
- HIGH 1 (`res.users.role` on 19/20 slipped through): every written field on res.users,
  res.groups, ir.model.access, ir.access and ir.rule must be simulated (`HANDLED_FIELDS`) or
  on `FIELD_ALLOWLIST` (each entry has a reason) AND be plain in live fields_get (not
  readonly, not computed/related except res.users' own delegated partner fields, not linked
  to a security model); `field_verdict` says why otherwise. `role` and `auth_method` are refused.
  Live drift test on 17 and 20: no writable field passes without review; `role` exists and
  is refused on 20, absent on 17 (19 confirmed from source only, no 19 sandbox).
- HIGH 2 (only the final state was checked): the plan is simulated step by step in the given
  (= apply) order; admin, working-login and Bot-access invariants are checked after every
  prefix ("step k: ..."). Any step touching the Bot is refused: its user, its membership in a
  group's member list (either way), removing implied groups it relies on, access rows/rules
  that apply to it (its groups or global), its company, OAuth provider or API keys.
  Incremental closure keeps 3000 steps fast (probe l08).
- MEDIUM 3: cycles are compared as canonical SCC sets over ALL groups; any new cycle refuses
  even when others exist (existing ones are listed as a reason).
- LOWs: created users/groups/rows get distinct negative ids; created/changed access rows show
  "can now ..." gains with permission flags.
- Runs: reviewer probes 13/13; unit 36 (forward, reverse test order); live 12/12 on 17 + 20;
  on a temp copy of origin 5000f2b0 + these files: own + kill_audit, risk, risk_adversarial,
  clone, snapshot, diff_blast, approval_tiers, role_privileges + live = 2358 passed, 6 skipped,
  forward and reverse file order; ruff clean.
- Further gaps (follow-ups): record-rule / ir.access domains not evaluated; menu parent
  chains not walked; any edit to rows that apply to the Bot (incl. internal-user ACLs and
  global rules) is refused, a deliberately strict choice; 19 not run live.

## Proposed tracking lines
- PROGRESS: `BOT-LOCKOUT-SIM | done (nf2, uncommitted) | lockout.py + guard open_job level | 36 unit + 12 live, review round 1 fixed`
- STATE_NF: `lockout simulation available: lockout.simulate -> Refusal | LockoutSim(L3, impacts, gate_facts)`

## Note (BOT-V20-ACCESS review, 2026-10-26)
- `simulate` now refuses a plan if, after any step, the Bot GAINS anything: effective groups,
  ACL permissions, record rules that apply to it (any change), or companies. This covers every route (member list, implied
  chain, access rows, rules, company, user/role fields). Before this, only losses were refused. Unit test:
  `test_bot_self_widening_refused_by_every_route` (17/19/20).
- The live file reads `LOCKOUT_LIVE_URL` / `LOCKOUT_LIVE_DB` (defaults are the nf2 values `http://127.0.0.1:182{v}`,
  `ingenium_nf2_lock_{v}`) and skips without ODOO_LIVE. It was run on the NF sandboxes with
  `LOCKOUT_LIVE_URL='http://127.0.0.1:181{v}' LOCKOUT_LIVE_DB='ingenium_nf_bv_{v}'`: green.
