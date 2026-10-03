---
id: SK-CUST-DASHBOARD-LITE
family: C
risk_ceiling: R2
ops_allowed: [field.create, view.inherit.create, automation.create]
---
# SK-CUST-DASHBOARD-LITE

## When to use / When NOT to use

Use when the request matches: Save a filter and a pivot action. Do not invent a SQL view.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Save a filter and a pivot action. Do not invent a SQL view. Inspect first. Stop when the grant or the policy refuses the op.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
