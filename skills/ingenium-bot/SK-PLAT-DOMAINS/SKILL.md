---
id: SK-PLAT-DOMAINS
family: B
risk_ceiling: R2
ops_allowed: [config_record.upsert]
---
# SK-PLAT-DOMAINS

## When to use / When NOT to use

Use when the request matches: Validate every domain by parsing it and counting matches.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Translate the request into prefix-notation domain syntax. Validate the domain and review the count. Beware inequality on empty relational fields. Keep the domain minimal.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
