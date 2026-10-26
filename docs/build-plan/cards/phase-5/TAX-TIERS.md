# TAX-TIERS — task tiers, composition rule, graded refusal, tier-scoped claim

Source: derived from `~/.ingenium_nf/agent_runs/debate/RESOLUTION.md` item 3 (no prior card file).
Code: `apps/api/app/bots/tiers.py`; tests: `apps/api/tests/test_nf_bot_tax_tiers.py`.

## Tiers (by catalogue task-id kind)
- **T1 data/settings:** `m s seq param g b wiz sa cron t r`, `mod:*:install|upgrade|uninstall`.
- **T2 metadata/automation:** `c` (customize-field/view, report, automation), `v`.
- **T3 module code:** `code`.
- Any other kind: unknown -> refused (fail closed).

## Composition rule (cross-tier tasks)
Tier = highest part tier. Grade = worst part grade. All or nothing: no partial run.
Order: T3, then T2, then T1 (structure before data). Missing module installs are never added
silently; they stay a `needs-step` refusal that names the install step.

## Graded refusal (mildest first)
`ok` < `needs-step` < `needs-edition` < `not-in-version` < `out-of-tier` < `unknown`.
Every refusal has a plain reason and, where one exists, "what you can do instead".
Checks: risk classifier (`task_floor`, model of task) + versioncaps `availability`.
Unknown installed modules, version or model -> `unknown`. Read-only; no RPC writes.

## Product claim (tier-scoped)
> Ingenium bots handle Odoo data and settings (T1) and Odoo metadata and automation
> (T2: fields, views, reports, automations) on Odoo 17 to 20, with checks before every
> change. Module code (T3) is not done by bots yet: they say so and tell you what you
> can do instead. When a task cannot be checked, nothing runs.

Claim text still to align (not edited by this card): `MEMORY.md:207` ("owns ANY Odoo
customization"), `docs/build-plan/cards/phase-5/BOT-GENERIC-WALKER.md:3` ("any Odoo task").

## Done
- Unit tests pass offline on Odoo 17 and 20 capability data. Ruff clean.
