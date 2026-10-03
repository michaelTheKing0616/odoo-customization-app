---
id: SK-APP-INVENTORY
family: F
risk_ceiling: R2
ops_allowed: [config_record.upsert, setting.set, stage.upsert]
---
# SK-APP-INVENTORY

## When to use / When NOT to use

Use when the request matches: Configure warehouses and routes. Protect valuation and quants.

Do not use this skill to widen a Bot Grant, to approve a plan, or to call apply.

## Procedure

New locations, putaway rules, and reordering rules are ordinary configuration. Warehouse step changes and tracking changes on stocked products require staging and an owner. Do not edit stock quants or costing methods that already have moves.

## Guardrails

Refuse R4 targets. Group-less access, module uninstall, raw delete, lock dates, and protected parameters stop the plan.

## Verification

The engine reports verified only after post-conditions pass. This skill does not declare success.
