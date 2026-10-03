---
id: SK-CUST-AUTOMATION-DESIGN
family: C
risk_ceiling: R2
ops_allowed: [field.create, view.inherit.create, automation.create]
---
# SK-CUST-AUTOMATION-DESIGN

## When to use / When NOT to use

Use when the request matches: Design a loop-safe automation and dry-fire it.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Pick the trigger and the fields that should fire it. Validate pre and post filters by count. Prefer an internal activity over outbound mail. Guard loops by setting a flag the filter excludes. Estimate volume. Dry-fire on a synthetic record.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
