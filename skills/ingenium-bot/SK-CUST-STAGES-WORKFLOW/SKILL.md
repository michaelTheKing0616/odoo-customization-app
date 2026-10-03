---
id: SK-CUST-STAGES-WORKFLOW
family: C
risk_ceiling: R2
ops_allowed: [field.create, view.inherit.create, automation.create]
---
# SK-CUST-STAGES-WORKFLOW

## When to use / When NOT to use

Use when the request matches: Use stages or a selection state. Archive a used stage only with a migration.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Use stages or a selection state. Archive a used stage only with a migration. Inspect first. Stop when the grant or the policy refuses the op.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
