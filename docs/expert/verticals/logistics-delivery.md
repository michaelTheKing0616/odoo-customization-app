# Vertical playbook: Logistics / Delivery

Keywords: logistics, warehouse, delivery, shipping, courier, fulfillment, 3PL, supply chain.

## Summary

Logistics stacks **Inventory** with **Delivery** carriers, **Purchase**, **Sales**, and optional **Fleet**.

## Stock apps

`base`, `product`, `stock`, `delivery`, `purchase`, `sale`, `account`, `contacts`, `fleet` (own fleet).

## Custom models

`x_shipment`, `x_route_stop` for last-mile nuances; often stock pickings + packages suffice at v1.

## Workflows

Receipt → internal transfers → delivery order → carrier label (module-dependent). Multi-warehouse rules via routes and pull rules.

## Tips

Enable **Packages** and **Lots/Serials** only if SKUs require traceability — adds operational overhead.
