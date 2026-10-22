"""Touch 126: a sample company that feels local. Adebayo & Sons Furniture, a Lagos furniture maker.

Fictional but believable: naira prices, 7.5% Nigerian VAT, real Lagos areas and street patterns.
seed() only ever writes to a disposable database whose name starts with "ingenium_".
"""

from __future__ import annotations

from typing import Any

VAT_RATE = 7.5  # Nigeria VAT (Finance Act 2019)
COMPANY = {
    "name": "Adebayo & Sons Furniture Ltd",
    "street": "14 Oshodi-Apapa Expressway",
    "city": "Isolo, Lagos",
    "country_code": "NG",
    "currency": "NGN",
    "phone": "+234 803 555 0142",
    "vat": "RC 1234567",
}

CUSTOMERS = [
    {"name": "Chiamaka Okafor", "street": "22 Admiralty Way", "city": "Lekki Phase 1, Lagos", "email": "chiamaka.okafor@example.ng"},
    {"name": "Lagoon View Suites", "street": "5 Ozumba Mbadiwe Avenue", "city": "Victoria Island, Lagos", "email": "procurement@lagoonview.example.ng", "is_company": True},
    {"name": "Tunde Bakare", "street": "8 Allen Avenue", "city": "Ikeja, Lagos", "email": None},
    {"name": "Grace Primary School", "street": "31 Herbert Macaulay Way", "city": "Yaba, Lagos", "email": "bursar@graceschool.example.ng", "is_company": True},
    {"name": "Ngozi Eze", "street": "3 Bode Thomas Street", "city": "Surulere, Lagos", "email": "ngozi.eze@example.ng"},
]

PRODUCTS = [
    {"name": "Iroko dining table, 6-seater", "list_price": 485000, "standard_price": 290000},
    {"name": "Mahogany wardrobe, 3-door", "list_price": 620000, "standard_price": 380000},
    {"name": "Office chair, mesh back", "list_price": 78500, "standard_price": 41000},
    {"name": "School desk and bench, pair", "list_price": 36000, "standard_price": 19500},
    {"name": "3-seater sofa, ankara upholstery", "list_price": 395000, "standard_price": 228000},
    {"name": "Delivery within Lagos", "list_price": 15000, "standard_price": 9000, "type": "service"},
]


def with_vat(amount: float) -> float:
    return round(amount * (1 + VAT_RATE / 100), 2)


def assert_disposable(db_name: str, *, is_test_copy: bool | None = None) -> None:
    """Only disposable ingenium_* databases, or a connection explicitly marked as a test copy."""
    if not (db_name.startswith("ingenium_") or is_test_copy is True):
        raise ValueError("The sample company only loads into an ingenium_* database or a connection marked as a test copy.")


def seed(client: Any, db_name: str, *, is_test_copy: bool | None = None, before_create: Any = None) -> dict[str, int]:
    """Create the sample records through an Odoo client exposing create(model, vals). Disposable DBs only.
    before_create(model) runs the shared write gate for each model before anything is written."""
    assert_disposable(db_name, is_test_copy=is_test_copy)
    if before_create:
        for m in ("res.partner", "product.template"):
            before_create(m)
    made = {"res.partner": 0, "product.template": 0}
    for c in CUSTOMERS:
        client.create("res.partner", {k: v for k, v in c.items() if v is not None})
        made["res.partner"] += 1
    for p in PRODUCTS:
        client.create("product.template", {"type": "consu", **p})
        made["product.template"] += 1
    return made
