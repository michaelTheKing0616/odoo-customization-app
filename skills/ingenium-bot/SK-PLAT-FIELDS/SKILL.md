---
id: SK-PLAT-FIELDS
family: B
risk_ceiling: R2
ops_allowed: [field.create, view.inherit.create, automation.create]
---
# SK-PLAT-FIELDS

## When to use / When NOT to use

Use when the request matches: Create x_ fields with safe relational options.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Prefer a standard field. Name custom fields x_. Keep the identifier within 63 bytes. Monetary fields need a currency field. many2one on_delete is set null or restrict, never cascade. Do not change a field type in place.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
