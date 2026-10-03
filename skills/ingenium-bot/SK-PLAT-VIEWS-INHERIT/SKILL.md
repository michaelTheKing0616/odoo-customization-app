---
id: SK-PLAT-VIEWS-INHERIT
family: B
risk_ceiling: R2
ops_allowed: [view.inherit.create, field.create]
---
# SK-PLAT-VIEWS-INHERIT

## When to use / When NOT to use

Use when the request matches: Inherit with a unique xpath against the combined arch.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Read the combined arch. Choose a stable name anchor. Test the xpath and require exactly one match. Default position is after. Never use replace. Name the view Ingenium: model type – purpose. Priority defaults to 99.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
