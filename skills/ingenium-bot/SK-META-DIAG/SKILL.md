---
id: SK-META-DIAG
family: A
risk_ceiling: R2
ops_allowed: [none]
---
# SK-META-DIAG

## When to use / When NOT to use

Use when the request matches: Diagnose with read-only tools and evidence.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Restate who, what, where, and the expected versus actual result. Test the cheapest hypothesis with read-only tools. Separate confirmed cause, likely cause, and ruled-out cause. Do not change configuration during diagnosis.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
