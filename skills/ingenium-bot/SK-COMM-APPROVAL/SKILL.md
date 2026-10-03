---
id: SK-COMM-APPROVAL
family: I
risk_ceiling: R2
ops_allowed: [none]
---
# SK-COMM-APPROVAL

## When to use / When NOT to use

Use when the request matches: Lead with what changes, who is affected, the risk, and how to undo it.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Lead with what changes, who is affected, the risk, and how to undo it. Inspect first. Stop when the grant or the policy refuses the op.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
