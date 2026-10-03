---
id: SK-DATA-EXPORT
family: D
risk_ceiling: R2
ops_allowed: [data.update_batch, data.import_upsert, data.archive_batch]
---
# SK-DATA-EXPORT

## When to use / When NOT to use

Use when the request matches: Export an allowlist of fields. Audit the download.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Export an allowlist of fields. Audit the download. Inspect first. Stop when the grant or the policy refuses the op.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
