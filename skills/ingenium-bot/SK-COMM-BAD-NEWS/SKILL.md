---
id: SK-COMM-BAD-NEWS
family: I
risk_ceiling: R2
ops_allowed: [none]
---
# SK-COMM-BAD-NEWS

## When to use / When NOT to use

Use when the request matches: Say what failed, what the database state is now, and the next options.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Say what failed, what the database state is now, and the next options. Inspect first. Stop when the grant or the policy refuses the op.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
