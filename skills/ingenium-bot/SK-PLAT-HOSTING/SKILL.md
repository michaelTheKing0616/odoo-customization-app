---
id: SK-PLAT-HOSTING
family: B
risk_ceiling: R2
ops_allowed: [config_record.upsert]
---
# SK-PLAT-HOSTING

## When to use / When NOT to use

Use when the request matches: Online, Odoo.sh, and on-prem differ by capability flags, not by guesswork.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Online, Odoo.sh, and on-prem differ by capability flags, not by guesswork. Inspect first. Stop when the grant or the policy refuses the op.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
