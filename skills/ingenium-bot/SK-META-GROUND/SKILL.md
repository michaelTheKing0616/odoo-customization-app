---
id: SK-META-GROUND
family: A
risk_ceiling: R2
ops_allowed: [none]
---
# SK-META-GROUND

## When to use / When NOT to use

Use when the request matches: Resolve every identifier against live introspection.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Extract candidate models, fields, menus, and groups from the request. Call schema_search with the user's wording. Rank exact technical names above labels. If the top two scores are close, stop and ask. Record each hit as a fact with an evidence id. Reuse a standard field such as client_order_ref instead of creating a duplicate.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
