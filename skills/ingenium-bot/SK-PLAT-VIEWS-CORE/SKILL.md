---
id: SK-PLAT-VIEWS-CORE
family: B
risk_ceiling: R2
ops_allowed: [view.inherit.create, field.create]
---
# SK-PLAT-VIEWS-CORE

## When to use / When NOT to use

Use when the request matches: Pick the view type the action actually uses.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Pick the view type the action actually uses. Inspect first. Stop when the grant or the policy refuses the op.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
