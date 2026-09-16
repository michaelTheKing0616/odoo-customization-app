"""Config recipes catalog routes (no live Odoo required for catalogs)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_recipes_catalog_shape():
    res = client.get("/api/connections/any/config/recipes")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    ids = {row["id"] for row in data}
    assert {"day1", "numbering", "apps-pack", "import-seeds", "bulk-recipes"}.issubset(ids)
    for row in data:
        assert {"id", "phase", "title", "blurb", "clicks"} <= set(row)


def test_numbering_catalog_shape():
    res = client.get("/api/connections/any/config/recipes/numbering/catalog")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert any(row.get("key") == "sale" for row in data)


def test_apps_packs_catalog_shape():
    res = client.get("/api/connections/any/config/recipes/apps-packs")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert any(row.get("id") == "sales_desk" for row in data)
