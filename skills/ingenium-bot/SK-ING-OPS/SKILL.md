---
id: SK-ING-OPS
family: H
risk_ceiling: R2
ops_allowed: [config_record.upsert]
---
# SK-ING-OPS

## When to use / When NOT to use

Use when the request matches: Report cost, incidents, and kill-switch state for operators.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Report cost, incidents, and kill-switch state for operators. Inspect first. Stop when the grant or the policy refuses the op.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
