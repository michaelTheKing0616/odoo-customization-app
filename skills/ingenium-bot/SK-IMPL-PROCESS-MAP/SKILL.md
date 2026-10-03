---
id: SK-IMPL-PROCESS-MAP
family: G
risk_ceiling: R2
ops_allowed: [none]
---
# SK-IMPL-PROCESS-MAP

## When to use / When NOT to use

Use when the request matches: Map the business step to the Odoo flow it will use.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Map the business step to the Odoo flow it will use. Inspect first. Stop when the grant or the policy refuses the op.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
