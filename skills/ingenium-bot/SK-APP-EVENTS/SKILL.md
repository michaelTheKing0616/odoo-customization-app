---
id: SK-APP-EVENTS
family: F
risk_ceiling: R2
ops_allowed: [config_record.upsert, setting.set, stage.upsert]
---
# SK-APP-EVENTS

## When to use / When NOT to use

Use when the request matches: Configure tickets and questions. Mail schedulers are outbound.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Configure tickets and questions. Mail schedulers are outbound. Inspect first. Stop when the grant or the policy refuses the op.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
