---
id: SK-CUST-SERVER-ACTION
family: C
risk_ceiling: R2
ops_allowed: [field.create, view.inherit.create, automation.create]
---
# SK-CUST-SERVER-ACTION

## When to use / When NOT to use

Use when the request matches: Prefer a non-code server action. Code is a last resort.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Prefer a non-code server action. Code is a last resort. Inspect first. Stop when the grant or the policy refuses the op.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
