# Vertical playbook index

Curated **vertical playbooks** power the Odoo Expert RAG layer. Each playbook describes
which **stock Odoo Community apps** to install, typical **custom `x_` models**, rollout phases,
and honest **Community vs Enterprise** limits.

## Available playbooks

| Vertical | File | Domain pack in app |
|----------|------|-------------------|
| School / Education | `school-education.md` | — (custom scaffold) |
| Retail / eCommerce | `retail-ecommerce.md` | — |
| Manufacturing | `manufacturing.md` | — |
| Nonprofit / NGO | `nonprofit-ngo.md` | — |
| Logistics / Warehouse | `logistics-delivery.md` | — |
| General Community stack | `general-community-stack.md` | — |
| Car rental | _(generated from pack)_ | `car_rental` |
| Hospital | _(generated from pack)_ | `hospital` |
| Clinic | _(generated from pack)_ | `clinic` |
| Law firm | _(generated from pack)_ | `law_firm` |
| Hotel | _(generated from pack)_ | `hotel` |
| Restaurant | _(generated from pack)_ | `restaurant` |
| Real estate | _(generated from pack)_ | `real_estate` |
| Subscription | _(generated from pack)_ | `subscription` |
| Project tracker | _(generated from pack)_ | `project_tracker` |
| Field service | _(generated from pack)_ | `field_service` |

## Ingest

After editing playbooks, re-index Expert:

```bash
uv run --directory apps/api python -m app.expert.ingest --version 19.0 --offline --skip-odoo-docs
```

Or full ingest (includes official Odoo docs):

```bash
uv run --directory apps/api python -m app.expert.ingest --version 19.0
```

Vertical chunks use source tag **`vertical`** and receive retrieval boost over generic docs.

## Authoring guidelines

- Target **Odoo Community 17–19** unless noted.
- List **`depends`** module technical names (not display labels only).
- Separate **stock apps** from **custom models**.
- Flag Enterprise-only features explicitly.
- Include keywords operators actually type (school, clinic, rental, etc.).
