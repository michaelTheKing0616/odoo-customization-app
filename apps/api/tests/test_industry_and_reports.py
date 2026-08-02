"""Unit tests for industry seeds + config/menu/report routers (no live Odoo)."""

from __future__ import annotations

from app.industry_seeds import get_seed_pack, list_seed_packs, template_csv_for_model
from app.data_import import template_csv


def test_seed_packs_listed() -> None:
    packs = list_seed_packs()
    ids = {p["id"] for p in packs}
    assert "car_rental" in ids
    assert "library" in ids
    assert "partners" in ids


def test_car_rental_seed_has_vehicles() -> None:
    pack = get_seed_pack("car_rental")
    assert pack is not None
    models = {m["model"] for m in pack["models"]}
    assert "x_rent_vehicle" in models
    csv = next(m["csv"] for m in pack["models"] if m["model"] == "x_rent_vehicle")
    assert "Toyota" in csv
    assert "available" in csv


def test_template_csv_uses_industry_seeds() -> None:
    csv = template_csv("x_rent_vehicle")
    assert "ABC-101-LA" in csv or "Toyota" in csv
    assert template_csv_for_model("x_lib_book") is not None


def test_reports_default_qweb_has_t_name() -> None:
    from app.routers.reports import DEFAULT_QWEB

    arch = DEFAULT_QWEB.format(key="custom.report_demo")
    assert 't-name="custom.report_demo"' in arch
    assert "web.html_container" in arch
