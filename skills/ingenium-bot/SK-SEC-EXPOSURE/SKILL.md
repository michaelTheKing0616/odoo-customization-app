---
id: SK-SEC-EXPOSURE
family: E
risk_ceiling: R2
ops_allowed: [access.*, rule.*, group.create]
---
# SK-SEC-EXPOSURE

## When to use / When NOT to use

Use when the request matches: List what a portal or public user can reach. Read-only.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

List what a portal or public user can reach. Read-only. Inspect first. Stop when the grant or the policy refuses the op.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
