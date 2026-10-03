---
id: SK-DATA-BULK-UPDATE
family: D
risk_ceiling: R2
ops_allowed: [data.update_batch, data.import_upsert, data.archive_batch]
---
# SK-DATA-BULK-UPDATE

## When to use / When NOT to use

Use when the request matches: Count, sample, enumerate triggers, then update under a cap.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Validate the domain, count the rows, and show a sample of at most twenty old-to-new diffs. List automations that will fire. Enforce the cap. Capture a before-image. Verify the count after apply.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
