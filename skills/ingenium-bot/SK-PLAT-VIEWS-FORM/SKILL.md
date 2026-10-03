---
id: SK-PLAT-VIEWS-FORM
family: B
risk_ceiling: R2
ops_allowed: [view.inherit.create, field.create]
---
# SK-PLAT-VIEWS-FORM

## When to use / When NOT to use

Use when the request matches: Place fields in the sheet using stable group and page names.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Place fields in the sheet using stable group and page names. Inspect first. Stop when the grant or the policy refuses the op.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
