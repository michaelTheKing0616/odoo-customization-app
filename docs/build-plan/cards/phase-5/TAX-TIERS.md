# TAX-TIERS — task tiers, composition rule, graded refusal, tier-scoped claim

Source: derived from `~/.ingenium_nf/agent_runs/debate/RESOLUTION.md` item 3 (no prior card file).
Code: `apps/api/app/bots/tiers.py`; tests: `apps/api/tests/test_nf_bot_tax_tiers.py`.

## Tiers (by catalogue task-id kind)
- **T1 data/settings:** `m s seq param g b wiz sa cron t r`, `mod:*:install|upgrade|uninstall`.
- **T2 metadata/automation:** `c` (customize-field/view, report, automation), `v`.
- **T3 module code:** `code`.
- Any other kind: unknown -> refused (fail closed).

## Capability registry
A tier runs only when every capability it requires is present in `_CAPABILITIES` (code
constants, read-only mapping; never set by task text or caller input). T1 `data-settings`,
T2 `metadata-automation` (present); T3 `module-authoring` + `module-test-gate` (absent today,
so T3 grades `not-built-yet`; flips when both real modules land).

## Composition rule (cross-tier tasks)
Tier = highest part tier. Grade = worst part grade (unrecognised grades count as unknown).
All or nothing: no partial run. Order: T3, then T2, then T1 (structure before data). Missing
module installs are never added silently; they stay a `needs-step` refusal naming the step.

## Graded refusal (mildest first)
`ok` < `approval-required` (uninstall: deletes data, owner approval + backup) < `needs-step`
< `needs-edition` < `not-in-version` < `not-built-yet` < `unknown`.
Every refusal has a plain reason and, where one exists, "what you can do instead".
Model is read from the id (m/b/wiz/sa via the classifier; c/v/t parsed here); ids with no
model (r, cron) are `unknown`. Checks: classifier `task_floor` + versioncaps `availability`,
each guarded. Non-collection installed-module lists, faults or unknown verdicts -> `unknown`.
Read-only; no RPC writes.

## Product claim (tier-scoped)
> Ingenium bots can check and plan Odoo data and settings tasks (T1) and metadata and
> automation tasks (T2: fields, views, reports, automations) on Odoo 17 to 20. A task runs
> only when its app and model are confirmed for your Odoo version, and uninstalling an app
> always needs your approval and a backup. Module code (T3) is coming but not yet available:
> bots say so and tell you what you can do instead. When a task cannot be checked, nothing runs.

Claim text still to align (not edited by this card): `MEMORY.md:207` ("owns ANY Odoo
customization"), `docs/build-plan/cards/phase-5/BOT-GENERIC-WALKER.md:3` ("any Odoo task").

## Done
- Unit tests pass offline on Odoo 17 and 20 capability data. Ruff clean.
