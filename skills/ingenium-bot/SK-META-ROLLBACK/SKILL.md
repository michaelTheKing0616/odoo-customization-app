---
id: SK-META-ROLLBACK
family: A
risk_ceiling: R2
ops_allowed: [none]
---
# SK-META-ROLLBACK

## When to use / When NOT to use

Use when the request matches: Plan exact or soft rollback. Rollback is itself a change-set.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Plan exact or soft rollback. Rollback is itself a change-set. Inspect first. Stop when the grant or the policy refuses the op.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
