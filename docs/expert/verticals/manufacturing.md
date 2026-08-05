# Vertical playbook: Manufacturing / MRP

Keywords: manufacturing, MRP, production order, bill of materials, BOM, work center, factory, assembly.

## Summary

Manufacturing uses **`mrp`** with **`stock`**, **`purchase`**, and **`product`**. BoMs define
components; manufacturing orders consume components and produce finished goods.

## Stock apps

`base`, `product`, `stock`, `purchase`, `mrp`, `account`, `sale` (make-to-order), `quality` (if available),
`maintenance` (equipment downtime optional).

## Custom models

Often extend with `x_work_instruction`, `x_quality_check` when quality app is not installed.
Prefer stock **Operations** types and **BoM** components before custom models.

## Workflows

Define products (storable/manufactured), BoMs, routes (MTS/MTO), work centers, then MO from sales or reorder rules.

## Safety

MO completion posts stock valuations — use sandbox and snapshots before bulk data fixes.
