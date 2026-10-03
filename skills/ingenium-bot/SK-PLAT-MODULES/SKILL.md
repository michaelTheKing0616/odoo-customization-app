---
id: SK-PLAT-MODULES
family: B
risk_ceiling: R2
ops_allowed: [config_record.upsert]
---
# SK-PLAT-MODULES

## When to use / When NOT to use

Use when the request matches: Install on staging first. Uninstall is refused.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Install on staging first. Uninstall is refused. Inspect first. Stop when the grant or the policy refuses the op.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
