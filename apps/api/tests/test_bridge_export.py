import io
import zipfile

from app.bridge.export import build_zip, check_files

V = {"n": 2, "hash": "abc", "money": False, "defn": {"connector": "shopify", "entity": "orders", "odoo_model": "sale.order", "direction": "in",
                                                      "mapping": [{"remote": "total", "odoo": "amount_total", "transform": "to_float"}]}}


def test_service_and_module_zip_parse():
    for kind in ("service", "module"):
        data, errs = build_zip("Shop Orders", V, kind)
        assert errs == []
        names = zipfile.ZipFile(io.BytesIO(data)).namelist()
        assert "HANDBOOK.md" in names
    z = zipfile.ZipFile(io.BytesIO(build_zip("Shop Orders", V, "service")[0]))
    src = z.read("app.py").decode()
    ns = {}
    exec(compile(src.split("ODOO_URL, ODOO_DB")[0].split("from fastapi")[1].split("\n", 1)[1], "m", "exec"), ns)
    assert ns["map_record"]({"total": "12.5"}) == {"amount_total": 12.5}
    assert "module" and "ingenium_bridge_shop_orders/__manifest__.py" in zipfile.ZipFile(io.BytesIO(build_zip("Shop Orders", V, "module")[0])).namelist()


def test_secret_check():
    assert check_files({"a.py": "K='sk_live_abcdefgh'"})
