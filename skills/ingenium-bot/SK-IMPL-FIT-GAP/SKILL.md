---
id: SK-IMPL-FIT-GAP
family: G
risk_ceiling: R2
ops_allowed: [none]
---
# SK-IMPL-FIT-GAP

## When to use / When NOT to use

Use when the request matches: Mark each requirement as standard, configuration, no-code, developer, or process change.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Mark each requirement as standard, configuration, no-code, developer, or process change. Inspect first. Stop when the grant or the policy refuses the op.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
