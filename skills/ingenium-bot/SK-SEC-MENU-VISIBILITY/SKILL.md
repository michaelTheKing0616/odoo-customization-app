---
id: SK-SEC-MENU-VISIBILITY
family: E
risk_ceiling: R2
ops_allowed: [access.*, rule.*, group.create]
---
# SK-SEC-MENU-VISIBILITY

## When to use / When NOT to use

Use when the request matches: Explain that hiding a menu is not hiding the data.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Explain that hiding a menu is not hiding the data. Inspect first. Stop when the grant or the policy refuses the op.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
