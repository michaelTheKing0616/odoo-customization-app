import pytest

from app.sample_company import CUSTOMERS, PRODUCTS, assert_disposable, seed, with_vat


def test_local_and_believable():
    assert all("Lagos" in c["city"] for c in CUSTOMERS)
    assert all(p["list_price"] > p["standard_price"] > 0 for p in PRODUCTS)
    assert with_vat(100000) == 107500.0


def test_never_seeds_a_real_database():
    with pytest.raises(ValueError):
        assert_disposable("aonb_prod")


def test_seed_counts():
    calls = []

    class C:
        def create(self, model, vals):
            calls.append(model)

    assert seed(C(), "ingenium_sample") == {"res.partner": len(CUSTOMERS), "product.template": len(PRODUCTS)}


def test_test_copy_flag_allows_and_gate_runs_first():
    order = []

    class C:
        def create(self, model, vals):
            order.append(("create", model))

    seed(C(), "client_copy", is_test_copy=True, before_create=lambda m: order.append(("gate", m)))
    assert order[:2] == [("gate", "res.partner"), ("gate", "product.template")]
    with pytest.raises(ValueError):
        seed(C(), "client_live", is_test_copy=None)
