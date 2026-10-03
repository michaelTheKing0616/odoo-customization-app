---
id: SK-META-ENV
family: A
risk_ceiling: R2
ops_allowed: [none]
---
# SK-META-ENV

## When to use / When NOT to use

Use when the request matches: Promote by replaying the same change-set. Drift blocks replay.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Promote by replaying the same change-set. Drift blocks replay. Inspect first. Stop when the grant or the policy refuses the op.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
