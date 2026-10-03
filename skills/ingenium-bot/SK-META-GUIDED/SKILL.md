---
id: SK-META-GUIDED
family: A
risk_ceiling: R2
ops_allowed: [none]
---
# SK-META-GUIDED

## When to use / When NOT to use

Use when the request matches: Give a click-path when the engine cannot apply the change.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

When the API or the bridge cannot do the work, write a numbered click-path and say that nothing was changed. Do not invent menu names. Flag version-specific steps.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
