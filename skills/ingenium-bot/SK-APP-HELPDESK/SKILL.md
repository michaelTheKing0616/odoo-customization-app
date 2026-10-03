---
id: SK-APP-HELPDESK
family: F
risk_ceiling: R2
ops_allowed: [config_record.upsert, setting.set, stage.upsert]
---
# SK-APP-HELPDESK

## When to use / When NOT to use

Use when the request matches: Configure teams, stages, and SLAs. Test assignment on a synthetic ticket.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Configure teams, stages, and SLAs. Test assignment on a synthetic ticket. Inspect first. Stop when the grant or the policy refuses the op.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
