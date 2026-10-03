---
id: SK-PLAT-VIEWS-MODIFIERS
family: B
risk_ceiling: R2
ops_allowed: [view.inherit.create, field.create]
---
# SK-PLAT-VIEWS-MODIFIERS

## When to use / When NOT to use

Use when the request matches: Use the version's modifier dialect and keep expression fields in the view.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Write modifiers in the target version's dialect. Every field used in an expression must exist in the view. Modifiers are not security. Pair them with access rules when the rule must hold.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
