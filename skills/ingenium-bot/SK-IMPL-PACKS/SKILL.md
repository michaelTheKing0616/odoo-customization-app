---
id: SK-IMPL-PACKS
family: G
risk_ceiling: R2
ops_allowed: [none]
---
# SK-IMPL-PACKS

## When to use / When NOT to use

Use when the request matches: Apply a versioned starter pack as reviewed ops, not as a silent import.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

Apply a versioned starter pack as reviewed ops, not as a silent import. Inspect first. Stop when the grant or the policy refuses the op.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
