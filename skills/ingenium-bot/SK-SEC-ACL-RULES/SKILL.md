---
id: SK-SEC-ACL-RULES
family: E
risk_ceiling: R2
ops_allowed: [access.*, rule.*, group.create]
---
# SK-SEC-ACL-RULES

## When to use / When NOT to use

Use when the request matches: Design the smallest access row and record rule. Show the matrix.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Access lists are additive. A group-less access row is forbidden. Global record rules are ANDed and group rules are ORed. Snapshot effective access for a member, a non-member, and an admin. Show the before and after matrix. Refuse a rule that locks out the operator.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
