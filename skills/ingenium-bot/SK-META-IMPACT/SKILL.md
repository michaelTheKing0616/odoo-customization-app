---
id: SK-META-IMPACT
family: A
risk_ceiling: R2
ops_allowed: [none]
---
# SK-META-IMPACT

## When to use / When NOT to use

Use when the request matches: List dependents before changing or removing anything.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Call find_usages for every touched target. Classify dependents as breaks, changes behavior, or informational. A breaking dependent must be fixed in the plan or the plan stops. Do not hide dependents to keep the plan small.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
