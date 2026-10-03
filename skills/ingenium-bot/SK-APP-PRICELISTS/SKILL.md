---
id: SK-APP-PRICELISTS
family: F
risk_ceiling: R2
ops_allowed: [config_record.upsert, setting.set, stage.upsert]
---
# SK-APP-PRICELISTS

## When to use / When NOT to use

Use when the request matches: Add price rules and probe the computed price.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Add price rules and probe the computed price. Inspect first. Stop when the grant or the policy refuses the op.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
