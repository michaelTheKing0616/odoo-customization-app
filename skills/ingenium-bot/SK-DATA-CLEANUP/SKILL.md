---
id: SK-DATA-CLEANUP
family: D
risk_ceiling: R2
ops_allowed: [data.update_batch, data.import_upsert, data.archive_batch]
---
# SK-DATA-CLEANUP

## When to use / When NOT to use

Use when the request matches: Normalize values in batches with a before-image.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Normalize values in batches with a before-image. Inspect first. Stop when the grant or the policy refuses the op.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
