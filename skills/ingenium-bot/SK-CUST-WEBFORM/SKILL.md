---
id: SK-CUST-WEBFORM
family: C
risk_ceiling: R2
ops_allowed: [field.create, view.inherit.create, automation.create]
---
# SK-CUST-WEBFORM

## When to use / When NOT to use

Use when the request matches: Map a website form to a model and require a consent checkbox when personal data is collected.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Map a website form to a model and require a consent checkbox when personal data is collected. Inspect first. Stop when the grant or the policy refuses the op.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
