"""RPC transport package — XML-RPC (≤18) and External JSON-2 (19+)."""

from odoo_client.transport.execute_kw_map import execute_kw_to_json2_body
from odoo_client.transport.json2 import Json2Transport, Json2TransportError

__all__ = [
    "Json2Transport",
    "Json2TransportError",
    "execute_kw_to_json2_body",
]
