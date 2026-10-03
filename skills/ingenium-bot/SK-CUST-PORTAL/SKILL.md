---
id: SK-CUST-PORTAL
family: C
risk_ceiling: R2
ops_allowed: [field.create, view.inherit.create, automation.create]
---
# SK-CUST-PORTAL

## When to use / When NOT to use

Use when the request matches: Test the portal user. Portal visibility is a record rule plus a view.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Test the portal user. Portal visibility is a record rule plus a view. Inspect first. Stop when the grant or the policy refuses the op.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
