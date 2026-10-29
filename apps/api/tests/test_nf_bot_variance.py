"""BOT-VARIANCE-CONTROL behaviour tests against a fake, read-only Odoo."""

from __future__ import annotations

import math

import pytest

from app.bots.variance import analyse, load_metrics, split_shared
from app.bots.variance.variance import evaluate

WRITE = {"create", "write", "unlink", "copy"}


class Odoo:
    def __init__(self, models, rows, uoms=None, fail=(), shape="category"):
        self.models, self.rows, self.uoms, self.fail = models, rows, uoms or {}, set(fail)
        self.shape = shape
        self.calls = []

    def __call__(self, model, method, args, kw=None):
        self.calls.append((model, method))
        assert method not in WRITE and not method.startswith("action_")
        if (model, method) in self.fail:
            raise RuntimeError("boom")
        if method == "fields_get" and model == "uom.uom":
            return {
                "category": {"factor": 1, "category_id": 1},
                "relative": {"factor": 1, "relative_uom_id": 1},
            }.get(self.shape, {"name": 1})
        if method == "fields_get":
            if model not in self.models:
                raise RuntimeError("no model")
            return {f: {"type": "x"} for f in self.models[model]}
        if method == "search_read":
            co = (kw.get("context") or {}).get("force_company")
            rs = [dict(r) for r in self.rows.get(model, []) if co is None or r.get("_co") == co]
            return rs[: kw["limit"]] if "limit" in kw else rs
        if method == "read" and model == "uom.uom":
            assert set(kw["fields"]) == (
                {"factor", "category_id"}
                if self.shape == "category"
                else {"factor", "relative_uom_id"}
            )
            return [{"id": i, **self.uoms[i]} for i in args[0] if i in self.uoms]
        raise AssertionError(method)


MOVE_F = [
    "raw_material_production_id",
    "state",
    "quantity",
    "product_uom_qty",
    "product_uom",
    "product_id",
    "company_id",
    "date",
]
KG, G, L = 1, 2, 3
UOMS = {
    KG: {"factor": 1.0, "category_id": [1, "W"]},
    G: {"factor": 1000.0, "category_id": [1, "W"]},
    L: {"factor": 1.0, "category_id": [2, "V"]},
}


def mv(i, qty, exp, uom=KG, prod=7, comp=1, date="2026-01-05"):
    return {
        "id": i,
        "quantity": qty,
        "product_uom_qty": exp,
        "product_uom": [uom, "u"],
        "product_id": [prod, "P"],
        "company_id": [comp, "C"],
        "date": date,
        "raw_material_production_id": [1, "MO"],
        "state": "done",
    }


UOMS20 = {
    KG: {"factor": 1000.0, "relative_uom_id": [G, "g"]},
    G: {"factor": 1.0, "relative_uom_id": False},
    L: {"factor": 1.0, "relative_uom_id": False},
}


def run(rows, mid="component_consumption", models=None, shape="category", **kw):
    u = UOMS if shape == "category" else UOMS20
    mods = models if models is not None else {"stock.move": MOVE_F}
    odoo = Odoo(mods, {"stock.move": rows}, u, shape=shape)
    return analyse(odoo, [mid], **kw), odoo


def test_catalogue_is_data_driven_and_generic():
    cat = load_metrics()
    assert len(cat) >= 8
    for m in cat.values():
        assert {"model", "actual", "expected", "direction"} <= set(m)


def test_within_breach_warn_and_evidence():
    out, odoo = run(
        [mv(1, 10.1, 10), mv(2, 0, 0, prod=8), mv(3, 13, 10, prod=9), mv(4, 10.3, 10, prod=5)]
    )
    st = {r["group"]: r["status"] for r in out["rows"]}
    assert st == {
        "company=1|product_id=5": "warn",
        "company=1|product_id=7": "within",
        "company=1|product_id=8": "within",
        "company=1|product_id=9": "breach",
    }
    assert out["writes"] == 0 and not out["ok"]
    assert out["rows"][-1]["evidence"] == [3]
    assert all(m in ("fields_get", "search_read", "read") for _, m in odoo.calls)
    plan = out["plan"]
    assert plan and all(
        s["needs_approval"] and s["level"] in (2, 3) and s["writes"] == 0 for s in plan
    )


def test_missing_model_or_field_is_cannot_measure():
    out, _ = run([mv(1, 1, 1)], models={})
    assert out["rows"][0]["status"] == "cannot-measure" and not out["ok"]
    out, _ = run([mv(1, 1, 1)], models={"stock.move": MOVE_F[:-3]})
    assert out["rows"][0]["status"] == "cannot-measure"
    assert "missing fields" in out["rows"][0]["reason"]


def test_read_failure_and_unknown_metric():
    odoo = Odoo({"stock.move": MOVE_F}, {}, fail={("stock.move", "search_read")})
    out = analyse(odoo, ["component_consumption", "nope"])
    assert {r["status"] for r in out["rows"]} == {"cannot-measure"}


def test_no_records_is_no_data_not_green():
    out, _ = run([])
    assert out["rows"][0]["status"] == "no-data" and not out["ok"]


def test_missing_tolerance_is_review_needed():
    out, _ = run([mv(1, 10, 10)], tolerances={"component_consumption": {}})
    r = out["rows"][0]
    assert r["status"] == "warn" and r["review_needed"]
    out, _ = run([mv(1, 10, 10)], tolerances={"component_consumption": {"pct": -1}})
    assert out["rows"][0]["status"] == "warn"


def test_asymmetric_tolerance():
    tol = {"over": {"pct": 1}, "under": {"pct": 50}}
    out, _ = run(
        [mv(1, 9, 10), mv(2, 10.15, 10, prod=8)], tolerances={"component_consumption": tol}
    )
    assert [r["status"] for r in out["rows"]] == ["within", "warn"]


def test_zero_expected_never_divides_or_greens():
    r = evaluate(0, 5, {"breach_factor": 2.0, "base": {"pct": 5}, "over": {}, "under": {}})
    assert r["delta_pct"] is None and r["status"] == "breach"
    assert evaluate(None, 5, None)["status"] == "no-data"


@pytest.mark.parametrize("bad", [math.nan, math.inf, 1e30, True, "10", None])
def test_bad_numbers_cannot_measure(bad):
    out, _ = run([mv(1, bad, 10)])
    assert out["rows"][0]["status"] == "cannot-measure"


def test_truncated_read_never_green():
    out, _ = run([mv(i, 10, 10) for i in range(1, 6)], limit=3)
    assert out["summary"]["truncated"] == ["component_consumption"]
    assert out["rows"][0]["status"] == "warn" and not out["ok"]


def test_multi_company_split_and_stable_order():
    rows = [mv(2, 10, 10, comp=2), mv(1, 10, 10, comp=1)]
    a, _ = run(rows)
    b, _ = run(list(reversed(rows)))
    assert [r["group"] for r in a["rows"]] == [r["group"] for r in b["rows"]]
    assert len(a["rows"]) == 2


@pytest.mark.parametrize(("shape", "total"), [("category", 2.0), ("relative", 2000.0)])
def test_uom_normalised_or_mismatch(shape, total):
    out, _ = run([mv(1, 1, 1, uom=KG), mv(2, 1000, 1000, uom=G)], shape=shape)
    r = out["rows"][0]
    assert r["status"] == "within" and r["actual"] == pytest.approx(total)
    out, _ = run([mv(1, 1, 1, uom=KG), mv(2, 1, 1, uom=L)], shape=shape)
    assert "unit mismatch" in out["rows"][0]["reason"]
    out, _ = run([mv(1, 1, 1, uom=99)], shape=shape)
    assert out["rows"][0]["status"] == "cannot-measure"


PO_F = [
    "state",
    "price_unit",
    "currency_id",
    "product_id",
    "company_id",
    "date_order",
    "product_uom",
]
UNIT, DOZ = 4, 5
UOMS[UNIT] = {"factor": 1.0, "category_id": [3, "U"]}
UOMS[DOZ] = {"factor": 1 / 12, "category_id": [3, "U"]}
UOMS20[UNIT] = {"factor": 1.0, "relative_uom_id": False}
UOMS20[DOZ] = {"factor": 12.0, "relative_uom_id": [UNIT, "Units"]}


def po(i, price, cur=1, uom=UNIT):
    return {
        "product_uom": [uom, "u"],
        "id": i,
        "state": "purchase",
        "price_unit": price,
        "currency_id": [cur, "X"],
        "product_id": [7, "P"],
        "company_id": [1, "C"],
    }


def run_po(rows, std, shape="category", fields=PO_F):
    u = UOMS if shape == "category" else UOMS20
    odoo = Odoo({"purchase.order.line": fields}, {"purchase.order.line": rows}, u, shape=shape)
    return analyse(odoo, ["purchase_price"], standards={"purchase_price": std})["rows"][0]


def test_currency_mismatch_flagged():
    assert (
        "currency" in run_po([po(1, 10), po(2, 10, cur=2)], {"value": 10, "currency": 1})["reason"]
    )
    assert "standard has no currency" in run_po([po(1, 10)], 10)["reason"]
    assert run_po([po(1, 10)], {"value": 10, "currency": 1})["status"] == "within"
    assert (
        run_po([po(1, 12)], {"by": {"product_id=7": {"value": 10, "currency": 1}}})["status"]
        == "breach"
    )
    assert run_po([po(1, 10)], None)["status"] == "no-data"
    assert run_po([po(1, 10)], {"value": "ten", "currency": 1})["status"] == "cannot-measure"


def test_recirculation_counted_once():
    rows = [mv(1, 10, 10), mv(2, 50, 0)]
    out, _ = run(rows, recirculated={"component_consumption": [2]})
    r = out["rows"][0]
    assert r["status"] == "within" and r["recirculated_excluded"] == 1


BP_F = ["production_id", "state", "quantity", "byproduct_id", "company_id", "date"]


def bp(i, q, by):
    return {
        "id": i,
        "production_id": [1, "MO"],
        "state": "done",
        "quantity": q,
        "byproduct_id": [3, "B"] if by else False,
        "company_id": [1, "C"],
    }


BPM = {
    "by_product_share": {
        "model": "stock.move",
        "direction": "both",
        "domain": [["state", "=", "done"]],
        "actual": {"field": "quantity", "ratio_filter": {"field": "byproduct_id"}},
        "expected": {"design": {"kind": "byproduct", "field": "cost_share"}, "scale": 0.01},
        "group_by": ["production_id"],
        "tolerance": {"abs": 0.02},
    }
}


def test_ratio_metric_from_design_spec():
    spec = {
        "spec_version": 1,
        "status": "ok",
        "odoo_major": 17,
        "items": [
            {
                "kind": "byproduct",
                "model": "mrp.bom.byproduct",
                "key": {},
                "expected": {"cost_share": 10},
                "relations": {},
                "ref": "s1",
            }
        ],
    }
    odoo = Odoo({"stock.move": BP_F}, {"stock.move": [bp(1, 90, False), bp(2, 10, True)]})
    r = analyse(odoo, ["by_product_share"], design=spec, metrics=BPM)["rows"][0]
    assert r["status"] == "within" and r["expected"] == pytest.approx(0.1)
    spec["items"].append({**spec["items"][0], "expected": {"cost_share": 20}, "ref": "s2"})
    r = analyse(odoo, ["by_product_share"], design=spec, metrics=BPM)["rows"][0]
    assert "ambiguous" in r["reason"]
    r = analyse(odoo, ["by_product_share"], design={"spec_version": 9}, metrics=BPM)["rows"][0]
    assert r["status"] == "cannot-measure"


def test_shared_input_split():
    out = split_shared(
        100, {"a": {"weight": 3, "expected": 75}, "b": {"weight": 1, "expected": 20}}, {"pct": 5}
    )
    assert [o["status"] for o in out] == ["within", "breach"]
    assert {o["status"] for o in split_shared(100, {"a": {"weight": 0}})} == {"cannot-measure"}
    assert {o["status"] for o in split_shared(True, {"a": {"weight": 1}})} == {"cannot-measure"}


def test_period_and_rolling():
    rows = [
        mv(1, 10, 10, date="2026-01-03"),
        mv(2, 12, 10, date="2026-02-03"),
        mv(3, 9, 10, date="2026-03-03"),
    ]
    out, _ = run(rows, period="month", rolling=3)
    assert len(out["rows"]) == 3
    last = out["rows"][-1]["rolling"]
    assert last["window"] == 3 and last["expected"] == 30 and last["actual"] == 31
    out, _ = run(
        rows,
        period="month",
        models={"stock.move": MOVE_F},
        metrics={
            "component_consumption": {**load_metrics()["component_consumption"], "date_field": None}
        },
    )
    assert out["rows"][0]["status"] == "cannot-measure"


# ---------------------------------------------------------------- review round 1


@pytest.mark.parametrize("shape", ["category", "relative"])
def test_price_normalised_per_unit_across_units(shape):
    r = run_po([po(1, 10), po(2, 120, uom=DOZ)], {"value": 10, "currency": 1}, shape)
    assert "standard has no unit" in r["reason"]
    std = {"value": 10, "currency": 1, "uom": UNIT}
    r = run_po([po(1, 10), po(2, 120, uom=DOZ)], std, shape)
    assert r["status"] == "within" and r["actual"] == pytest.approx(10.0)
    r = run_po([po(1, 120, uom=DOZ)], {"value": 120, "currency": 1, "uom": DOZ}, shape)
    assert r["status"] == "within"
    r = run_po([po(1, 10), po(2, 10, uom=DOZ)], std, shape)  # raw average would be 10
    assert r["status"] == "warn" and r["actual"] == pytest.approx(65 / 12)


def test_price_unit_field_candidates_and_missing():
    rows = [{**po(1, 10), "product_uom_id": [UNIT, "u"]}]
    f20 = [f for f in PO_F if f != "product_uom"] + ["product_uom_id"]
    assert run_po(rows, {"value": 10, "currency": 1}, fields=f20)["status"] == "within"
    r = run_po(rows, {"value": 10, "currency": 1}, fields=PO_F[:-1])
    assert "no unit field" in r["reason"]


def test_unknown_uom_shape_or_cycle_fails_closed():
    out, _ = run([mv(1, 1, 1, uom=KG), mv(2, 1, 1, uom=G)], shape="none")
    assert out["rows"][0]["status"] == "cannot-measure"
    cyc = {
        KG: {"factor": 2.0, "relative_uom_id": [G, "g"]},
        G: {"factor": 1.0, "relative_uom_id": [KG, "kg"]},
    }
    odoo = Odoo(
        {"stock.move": MOVE_F},
        {"stock.move": [mv(1, 1, 1, uom=KG), mv(2, 1, 1, uom=G)]},
        cyc,
        shape="relative",
    )
    assert analyse(odoo, ["component_consumption"])["rows"][0]["status"] == "cannot-measure"


def test_by_product_share_not_shipped():
    assert "by_product_share" not in load_metrics()


PP_F = ["standard_price", "company_id"]


def test_standard_cost_read_per_company_context():
    rows = [
        {"id": 5, "standard_price": 10.0, "company_id": False, "_co": 1},
        {"id": 5, "standard_price": 30.0, "company_id": False, "_co": 2},
    ]
    odoo = Odoo(
        {"product.product": PP_F},
        {
            "product.product": rows,
            "res.company": [{"id": 1, "currency_id": [1, "A"]}, {"id": 2, "currency_id": [2, "B"]}],
        },
    )
    std = {
        "by": {
            "company=1|id=5": {"value": 10, "currency": 1},
            "company=2|id=5": {"value": 30, "currency": 2},
        }
    }
    out = analyse(odoo, ["standard_cost"], standards={"standard_cost": std})
    assert [(r["group"], r["status"]) for r in out["rows"]] == [
        ("company=1|id=5", "within"),
        ("company=2|id=5", "within"),
    ]
    out = analyse(odoo, ["standard_cost"], standards={"standard_cost": 10})
    assert {r["status"] for r in out["rows"]} == {"cannot-measure"}
    odoo.rows["res.company"] = []
    out = analyse(odoo, ["standard_cost"], standards={"standard_cost": std})
    assert out["rows"][0]["status"] == "cannot-measure"


def test_favourable_side_never_unbounded_green():
    r = evaluate(10, 1e9, None, "under")
    assert r["status"] == "warn" and r["review_needed"]
    tol = {"breach_factor": 2.0, "base": {"pct": 5}, "over": {}, "under": {}}
    assert evaluate(10, 20, tol, "under")["status"] == "warn"
    assert evaluate(10, 10.2, tol, "under")["status"] == "within"
    assert evaluate(10, 20, tol, "over")["status"] == "breach"


def test_rolling_breach_counts_in_summary_ok_and_plan():
    rows = [mv(1, 11.9, 10, date="2026-01-03"), mv(2, 11.9, 10, date="2026-02-03")]
    out, _ = run(
        rows,
        period="month",
        rolling=2,
        tolerances={"component_consumption": {"abs": 2, "breach_factor": 1.5}},
    )
    assert [r["status"] for r in out["rows"]] == ["within", "within"]
    assert out["summary"]["rolling"]["breach"] == 1 and not out["ok"] and out["plan"]


def test_undated_records_cannot_measure_under_period():
    out, _ = run([mv(1, 10, 10), mv(2, 10, 10, date=False)], period="month")
    r = [x for x in out["rows"] if x["group"] == "period=undated"][0]
    assert r["status"] == "cannot-measure" and r["evidence"] == [2] and not out["ok"]


@pytest.mark.parametrize("total,w", [(-5, 1), (100, -1), (100, math.nan), (math.nan, 1)])
def test_split_shared_rejects_bad_inputs(total, w):
    out = split_shared(total, {"a": {"weight": w}, "b": {"weight": 1}})
    assert {o["status"] for o in out} == {"cannot-measure"}


def test_caller_domain_validated():
    out, odoo = run([mv(1, 10, 10)], domains={"component_consumption": [["nope", "=", 1]]})
    assert "missing fields" in out["rows"][0]["reason"]
    assert ("stock.move", "search_read") not in odoo.calls
    out, _ = run([mv(1, 10, 10)], domains={"component_consumption": ["bad"]})
    assert out["rows"][0]["reason"] == "malformed domain"


@pytest.mark.parametrize(
    "kw",
    [
        {"limit": 0},
        {"limit": True},
        {"limit": "5"},
        {"limit": 10**9},
        {"period": "week"},
        {"rolling": 2},
        {"period": "month", "rolling": 0},
    ],
)
def test_bad_arguments_fail_closed(kw):
    out, odoo = run([mv(1, 10, 10)], **kw)
    assert out["rows"][0]["status"] == "cannot-measure" and not odoo.calls


# BOT-VERSION-CAPS runtime wiring: absent model/field -> catalogue verdict (read-only).
_CAPS_M = {"bom_qty": {"model": "mrp.bom", "actual": {"field": "product_qty"}}}


def test_caps_missing_model_says_needs_install():
    odoo = Odoo({}, {})
    out = analyse(odoo, metrics=_CAPS_M, version=17, installed_modules=["base"])
    (r,) = out["rows"]
    assert r["status"] == "cannot-measure" and not out["ok"]
    assert r["capability"]["status"] == "available-needs-install"
    assert r["capability"]["module"] == "mrp" and "needs install" in r["reason"]


def test_caps_reads_installed_list_when_not_given():
    odoo = Odoo({}, {"ir.module.module": [{"name": "base"}]})
    r = analyse(odoo, metrics=_CAPS_M, version=17)["rows"][0]
    assert r["capability"]["status"] == "available-needs-install"
    assert ("ir.module.module", "search_read") in odoo.calls


def test_caps_missing_field_not_in_version():
    from app.bots.versioncaps import caps as C

    f17, f20 = (set(C.load(v).models["res.partner"]["fields"]) for v in (17, 20))
    new = sorted(f20 - f17)[0]
    m = {"p": {"model": "res.partner", "actual": {"field": new}}}
    r = analyse(
        Odoo({"res.partner": ["name"]}, {}), metrics=m, version=17, installed_modules=["base"]
    )["rows"][0]
    assert r["status"] == "cannot-measure"
    assert r["capability"]["status"] == "not-in-this-version"
    assert new in r["reason"]


@pytest.mark.parametrize("version", [99, "x", None])
def test_caps_fail_closed_unknown_version(version):
    r = analyse(Odoo({}, {}), metrics=_CAPS_M, version=version, installed_modules=[])["rows"][0]
    assert r["status"] == "cannot-measure"
    if version is None:
        assert "capability" not in r
    else:
        assert r["capability"]["status"] == "unknown" and "nothing verified" in r["reason"]


def test_caps_missing_catalogue_fails_closed(monkeypatch):
    from app.bots.versioncaps import caps as C

    monkeypatch.setitem(C._OVERRIDE, 17, None)
    r = analyse(Odoo({}, {}), metrics=_CAPS_M, version=17, installed_modules=[])["rows"][0]
    assert r["status"] == "cannot-measure" and r["capability"]["status"] == "unknown"


def test_caps_present_model_unchanged():
    odoo = Odoo({"mrp.bom": ["product_qty"]}, {"mrp.bom": []})
    r = analyse(odoo, metrics=_CAPS_M, version=17, installed_modules=["mrp"])["rows"][0]
    assert "capability" not in r
