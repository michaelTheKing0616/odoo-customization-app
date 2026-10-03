---
id: SK-APP-DISCUSS-MAIL
family: F
risk_ceiling: R2
ops_allowed: [config_record.upsert, setting.set, stage.upsert]
---
# SK-APP-DISCUSS-MAIL

## When to use / When NOT to use

Use when the request matches: Configure channels and aliases. Outgoing servers are protected.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Configure channels and aliases. Outgoing servers are protected. Inspect first. Stop when the grant or the policy refuses the op.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
