---
id: SK-META-DECOMPOSE
family: A
risk_ceiling: R2
ops_allowed: [none]
---
# SK-META-DECOMPOSE

## When to use / When NOT to use

Use when the request matches: Order schema, then UI, then logic, then security, then data, in packages of at most fifteen ops.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Order schema, then UI, then logic, then security, then data, in packages of at most fifteen ops. Inspect first. Stop when the grant or the policy refuses the op.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
