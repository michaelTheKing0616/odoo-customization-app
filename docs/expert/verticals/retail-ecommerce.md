# Vertical playbook: Retail / eCommerce

Keywords: retail, ecommerce, online store, webshop, POS, product catalog, boutique, shop.

## Summary

Retail on Odoo Community typically combines **Website Sale** (`website_sale`), **Sales**,
**Inventory** (`stock`), **Accounting**, and optionally **Point of Sale** (`point_of_sale`)
for physical stores. Contacts hold customers; products hold SKUs, prices, and images.

## Stock apps (install order)

`base`, `web`, `contacts`, `mail`, `product`, `sale`, `account`, `stock`, `website`,
`website_sale`, `payment` (provider-dependent), `point_of_sale` (if brick-and-mortar).

## Custom models (when needed)

Often minimal — use `product.product` variants for SKUs. Custom `x_` models for store locations,
loyalty tiers, or gift cards if stock apps are insufficient. Prefer product attributes/variants first.

## Workflows

- **Online:** publish products on website, checkout creates sale orders, delivery pickings from stock.
- **POS:** sync products to POS config; session closes into accounting entries (verify on sandbox).
- **Returns:** use stock return pickings and credit notes — test accounting impact in observer mode first.

## Phase rollout

Phase 1: products + website catalog. Phase 2: payment acquirer + delivery methods. Phase 3: POS or multi-warehouse.

## Community limits

Marketplace connectors and advanced loyalty may be third-party or Enterprise — verify module list on instance.
