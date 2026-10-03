---
id: SK-APP-ACCOUNTING-CONFIG
family: F
risk_ceiling: R2
ops_allowed: [config_record.upsert, setting.set, stage.upsert]
---
# SK-APP-ACCOUNTING-CONFIG

## When to use / When NOT to use

Use when the request matches: Draft additive accounting setup for an accountant to approve.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

The operator is an assistant to the accountant. Default to analysis and a draft. New payment terms and unused-range accounts can be proposed. Lock dates, posted entries, and used taxes are refused. Prefer the installed localisation over a parallel tax.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
