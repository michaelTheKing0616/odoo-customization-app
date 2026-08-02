# Odoo Client

Typed XML-RPC wrapper for **Odoo Community 19**.

## Usage

```python
from odoo_client import ConnectionConfig, OdooClient, CreateModelRequest

client = OdooClient(ConnectionConfig(
    url="http://127.0.0.1:8069",
    db="odoo_dev",
    username="admin",
    password="admin",
))
client.connect()
models = client.list_models(limit=20)
```

## Gate

Integration tests require local Docker Odoo 19 — see `skills/odoo-rpc-gate.md` and `docker/`.
