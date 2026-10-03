---
id: SK-PLAT-SAFE-EVAL
family: B
risk_ceiling: R2
ops_allowed: [config_record.upsert]
---
# SK-PLAT-SAFE-EVAL

## When to use / When NOT to use

Use when the request matches: Lint server-action code and refuse sandbox escapes.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Use code only when a non-code server action cannot express the rule and the environment allows code. Reject imports, sudo, eval, exec, and commits. Test on a synthetic record inside a rollback.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
