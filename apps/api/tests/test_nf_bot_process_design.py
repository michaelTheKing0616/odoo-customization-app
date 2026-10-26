"""BOT-PROCESS-DESIGN: Odoo-native process design (offline; read-only by construction)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.bots.fitgap import fitgap as fg
from app.bots.fitgap import ingest
from app.bots.process_design import design as pd

FIX = Path(__file__).parent / "fixtures" / "process_design"
PACK = json.loads((FIX / "generic_pack.json").read_text())
F = {
    "mrp.workcenter": {"name", "costs_hour"},
    "mrp.bom": {"product_tmpl_id", "product_qty", "type"},
    "mrp.bom.line": {"bom_id", "product_id", "product_qty", "operation_id"},
    "mrp.bom.byproduct": {"bom_id", "product_id", "product_qty", "cost_share", "operation_id"},
    "mrp.routing.workcenter": {"bom_id", "name", "sequence", "workcenter_id", "time_cycle_manual"},
    "crm.stage": {"name", "sequence"},
    "product.pricelist": {"name"},
    "account.journal": {"name", "code", "type"},
    "base.automation": {"name", "trigger", "model_id"},
}
INV = pd.Inventory(
    17,
    frozenset({"base", "mrp", "crm", "account", "product", "base_automation"}),
    frozenset({"quality_control", "sale_management", "approvals"}),
    {k: frozenset(v) for k, v in F.items()},
)


def by(d, model, **key):
    return [
        i for i in d.items if i.model == model and all(i.key.get(k) == v for k, v in key.items())
    ]


def test_empty_input_is_not_enough():
    for desc in (None, {}, {"steps": []}, {"steps": [{"name": "no id"}]}):
        d = pd.design(desc, inventory=INV)
        assert d.status == "not enough input" and not d.items


def test_multi_step_maps_to_native_manufacturing():
    d = pd.design(PACK["multi_step"], inventory=INV)
    assert d.status == "designed"
    assert {i.key["product_tmpl_id"] for i in by(d, "mrp.bom")} == {
        "Intermediate I1",
        "Finished F1",
        "Packed P1",
    }
    ops = by(d, "mrp.routing.workcenter")
    assert [o.expected["sequence"] for o in ops] == [10, 20, 30]
    assert ops[0].relations["workcenter_id"] == "mrp.workcenter:name=Line A"
    assert all(i.verdict == "stock" for i in by(d, "mrp.bom") + ops)


def test_shared_inputs_utilities_and_work_centers():
    d = pd.design(PACK["multi_step"], inventory=INV)
    (la,) = by(d, "mrp.workcenter", name="Line A")
    assert la.step_ids == ["s1", "s3"] and la.expected["costs_hour"] == 15.0
    assert "Utility U1" in la.notes[0]
    a1 = by(d, "mrp.bom.line", product_id="Additive A1")
    assert len(a1) == 2 and all("shared input" in " ".join(i.notes) for i in a1)
    (ml,) = by(d, "mrp.bom.line", bom_id="Finished F1", product_id="Intermediate I1")
    assert any("multi-level" in n for n in ml.notes)


def test_shared_by_products_co_products_and_recirculation():
    d = pd.design(PACK["multi_step"], inventory=INV)
    s1 = by(d, "mrp.bom.byproduct", product_id="Side Output S1")
    assert {i.key["bom_id"] for i in s1} == {"Intermediate I1", "Finished F1"}
    (co,) = by(d, "mrp.bom.byproduct", product_id="Finished F2")
    assert co.role == "co_product" and co.expected["cost_share"] == 25
    (rec,) = by(d, "mrp.bom.byproduct", product_id="Recycled Stream")
    assert "recirculated" in rec.notes[0] and "s1" in rec.notes[0]
    assert not any("cycle" in r for r in d.review)  # by-product loop is legal


def test_main_product_cycle_refused():
    d = pd.design(PACK["cycle"], inventory=INV)
    assert any("BoM cycle" in r for r in d.review)
    assert all(i.verdict == "needs review" for i in by(d, "mrp.bom"))
    assert all(p["blocked"] for p in d.plan if p["ref"].startswith("mrp.bom:"))


def test_quality_points_grounded_install():
    d = pd.design(PACK["multi_step"], inventory=INV)
    (m,) = by(d, "quality.point", title="I1 moisture")
    assert m.expected["tolerance_min"] == 2 and m.expected["norm"] == 3
    assert m.verdict == "stock-install" and "quality_control" in m.reason
    (pf,) = by(d, "quality.point", title="F1 visual")
    assert pf.expected["test_type"] == "passfail"


def test_generic_business_flow_and_fail_closed():
    d = pd.design(PACK["services"], inventory=INV)
    assert by(d, "crm.stage", name="Qualify")[0].verdict == "stock"
    assert by(d, "sale.order.template")[0].verdict == "stock-install"
    (ap,) = by(d, "approval.category")
    assert ap.expected["approval_minimum"] == 2 and ap.verdict == "stock-install"
    assert by(d, "base.automation")[0].relations["model_id"] == "account.move"
    j = by(d, "account.journal")[0]
    assert j.verdict == "stock" and j.expected["type"] == "sale"
    assert j.key == {"code": "BILL"} and j.expected["name"] == "Bill"
    assert any("x (Ring the bell)" in r for r in d.review)  # unmapped step never dropped


def test_missing_field_and_unknown_model_fail_closed():
    inv = pd.Inventory(
        17, frozenset({"base", "mrp"}), frozenset(), {"mrp.workcenter": frozenset({"name"})}
    )
    d = pd.design(PACK["multi_step"], inventory=inv)
    wc = by(d, "mrp.workcenter", name="Line A")[0]
    assert wc.verdict == "needs-custom" and "costs_hour" in wc.reason
    bom = by(d, "mrp.bom")[0]
    assert bom.verdict == "needs review" and "not readable" in bom.reason
    q = by(d, "quality.point")[0]
    assert q.verdict == "needs-custom" and "Enterprise-only" in q.reason
    nd = pd.design(PACK["multi_step"])  # no inventory: nothing verified
    assert {i.verdict for i in nd.items} == {"needs review"}


def test_bad_values_go_to_review():
    desc = {
        "steps": [
            {
                "id": "a",
                "name": "A",
                "inputs": [{"product": "P", "qty": "lots"}],
                "outputs": [
                    {"product": "Q"},
                    {"product": "R", "role": "co_product"},
                    {"product": "Z", "role": "waste"},
                ],
                "checks": [{"name": "c", "type": "measure", "min": 5, "max": 1}],
                "loop_to": "nope",
            }
        ]
    }
    r = " | ".join(pd.design(desc, inventory=INV).review)
    for frag in (
        "not a finite number",
        "cost share",
        "'waste' unknown",
        "min <= max",
        "not a step",
    ):
        assert frag in r


def test_spec_contract_risk_and_plan_never_write():
    d = pd.design(PACK["multi_step"], inventory=INV)
    spec = d.to_spec()
    assert spec["spec_version"] == 1 and spec["odoo_major"] == 17
    for it in spec["items"]:
        assert {"kind", "model", "key", "expected", "relations", "verdict", "reason", "ref"} <= set(
            it
        )
        assert it["risk"] and it["reason"]
    assert d.to_dict()["writes"] == 0
    assert all(p["route"] == "bots-write-spine" and p["requires_approval"] for p in d.plan)
    assert by(d, "ir.module.module")[0].risk


def test_uses_fitgap_result():
    g = ingest.parse_text(
        "1. Move the deal to qualified in the sales pipeline\n2. Send a quotation to the customer"
    )
    env = fg.OdooEnv.from_modules(17, {"base", "crm", "sale", "sale_management"}, set())
    fit = fg.classify(g, env)
    desc = {"steps": [{"id": s.step_id, "name": s.text} for s in fit.steps if s.verdict]}
    d = pd.design(desc, fit=fit, inventory=INV)
    (st,) = by(d, "crm.stage")
    assert st.step_ids == ["t1"] and st.verdict == "stock"
    (qt,) = by(d, "sale.order.template")
    assert qt.step_ids == ["t2"] and not d.review


def test_fitgap_concept_not_fit_is_review():
    fit = {
        "steps": [
            {"step_id": "a", "concepts": [{"concept": "crm_pipeline", "status": "unavailable"}]}
        ]
    }
    d = pd.design({"steps": [{"id": "a", "name": "Qualify"}]}, fit=fit, inventory=INV)
    (st,) = by(d, "crm.stage")
    assert st.verdict == "needs review" and "unavailable" in st.reason


def test_every_step_yields_item_or_review():
    descs = [PACK[k] for k in ("multi_step", "cycle", "services")] + [
        {"steps": [{"id": "1", "concepts": ["quality_point"]}]},
        {"steps": [{"id": "2", "approval": {"min": "two"}}]},
        {"steps": [{"id": "3", "automation": {}}, {"id": "4", "concepts": []}]},
    ]
    for desc in descs:
        d = pd.design(desc, inventory=INV)
        for st in desc["steps"]:
            sid = st["id"]
            assert any(sid in i.step_ids for i in d.items) or any(
                r.startswith((f"step {sid}:", f"step {sid} (")) for r in d.review
            ), sid
    d = pd.design({"steps": [{"id": "1", "concepts": ["quality_point"]}]}, inventory=INV)
    assert any("manufacturing concept" in r for r in d.review)


def test_conflicting_shared_records_go_to_review():
    d = pd.design(
        {
            "steps": [
                {"id": "1", "work_center": "W", "utilities": [{"name": "u", "cost_per_hour": 5}]},
                {"id": "2", "work_center": "W", "utilities": [{"name": "v", "cost_per_hour": 50}]},
            ]
        },
        inventory=INV,
    )
    (wc,) = by(d, "mrp.workcenter")
    assert wc.verdict == "needs review" and any("5.0" in r and "50.0" in r for r in d.review)
    d = pd.design(
        {
            "steps": [
                {"id": "1", "outputs": [{"product": "A"}], "inputs": [{"product": "B", "qty": 1}]},
                {
                    "id": "2",
                    "outputs": [{"product": "A", "qty": 5}],
                    "inputs": [{"product": "B", "qty": 9}],
                },
            ]
        },
        inventory=INV,
    )
    assert all(i.verdict == "needs review" for i in by(d, "mrp.bom") + by(d, "mrp.bom.line"))
    assert sum("conflict" in r for r in d.review) == 2
    d = pd.design(
        {
            "steps": [
                {"id": "1", "outputs": [{"product": "A"}], "checks": [{"name": "C"}]},
                {"id": "2", "outputs": [{"product": "Z"}], "checks": [{"name": "C"}]},
            ]
        },
        inventory=INV,
    )
    assert {i.relations["product_ids"][0] for i in by(d, "quality.point")} == {"A", "Z"}


@pytest.mark.parametrize("bad", ["x", None, float("nan"), float("inf"), True, [1]])
def test_bad_numbers_never_crash(bad):
    steps = [
        {
            "id": "1",
            "outputs": [
                {"product": "A", "qty": bad},
                {"product": "B", "role": "co_product", "cost_share": bad},
            ],
            "inputs": [{"product": "C", "qty": bad}],
            "work_center": "W",
            "duration_min": bad,
            "utilities": [{"name": "u", "cost_per_hour": bad}],
            "checks": [{"type": "measure", "min": bad, "max": 2}],
        },
        {"id": "2", "approval": {"min": bad}},
    ]
    d = pd.design({"steps": steps}, inventory=INV)
    assert d.status == "designed" and len(d.review) >= 3
    assert not by(d, "approval.category")


@pytest.mark.parametrize("v", [0, -1, 1.5, 51])
def test_approval_min_range(v):
    d = pd.design({"steps": [{"id": "1", "approval": {"min": v}}]}, inventory=INV)
    assert not by(d, "approval.category") and d.review


def test_deep_chain_no_recursion_error():
    n = 2000
    steps = [
        {"id": str(k), "outputs": [{"product": f"P{k}"}], "inputs": [{"product": f"P{k + 1}"}]}
        for k in range(n)
    ]
    d = pd.design({"steps": steps})
    assert not any("cycle" in r for r in d.review)
    steps[-1]["inputs"] = [{"product": "P0"}]  # close the ring
    d = pd.design({"steps": steps})
    assert sum("BoM cycle" in r for r in d.review) == 1


def test_enterprise_only_flagged_by_edition():
    com = pd.Inventory(17, frozenset({"base", "mrp"}), frozenset(), {})
    d = pd.design(PACK["multi_step"], inventory=com)
    q = by(d, "quality.point")[0]
    assert q.verdict == "needs-custom" and "Enterprise-only" in q.reason and "Community" in q.reason
    d = pd.design({"steps": [{"id": "1", "concepts": ["helpdesk"]}]}, inventory=com)
    assert "Enterprise-only" in by(d, "helpdesk.stage")[0].reason


def test_templates_links_and_codes():
    d = pd.design(
        {
            "steps": [
                {
                    "id": "1",
                    "name": "Customer billing run",
                    "concepts": ["customer_invoice", "putaway", "tax_localisation"],
                }
            ]
        },
        inventory=INV,
    )
    (j,) = by(d, "account.journal")
    assert j.key == {"code": "CBR"} and j.expected["name"] == "Customer billing run"
    (pr,) = by(d, "stock.putaway.rule")
    assert (
        pr.relations["location_in_id"].startswith("stock.location:")
        and pr.verdict == "needs review"
    )
    assert by(d, "account.tax")[0].verdict == "needs review"
    tpl = json.loads(Path(pd.TEMPLATES).read_text())
    for c, ts in tpl.items():
        for t in ts if isinstance(ts, list) else []:
            for k, v in t["fields"].items():
                assert not (k.endswith(("_id", "_ids")) and isinstance(v, str)), (c, k)


def test_unclassified_risk_blocks_plan(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError

    monkeypatch.setattr(pd.classifier, "task_floor", boom)
    d = pd.design(PACK["services"], inventory=INV)
    assert d.plan and all(p["blocked"] for p in d.plan if p["risk"] == "unclassified")
    assert any(p["risk"] == "unclassified" for p in d.plan)


def test_read_inventory_read_only():
    calls = []

    def call(model, method, args, kw):
        calls.append((model, method))
        if model == "ir.module.module":
            return [
                {"name": "base", "state": "installed", "latest_version": "17.0.1.3"},
                {"name": "mrp", "state": "installed"},
            ]
        if model == "mrp.bom":
            return {"product_tmpl_id": {}, "product_qty": {}}
        raise RuntimeError("no such model")

    inv = pd.read_inventory(call, ["mrp.bom", "quality.point"])
    assert inv.major == 17 and set(inv.models) == {"mrp.bom"}
    assert {m for _, m in calls} <= {"search_read", "fields_get"}


@pytest.mark.parametrize("name", ["industry_optional.json"])
def test_optional_industry_pack(name):
    d = pd.design(json.loads((FIX / name).read_text()), inventory=INV)
    assert d.status == "designed" and not any("cycle" in r for r in d.review)
    assert len(by(d, "quality.point")) == 2


def test_no_client_wording_in_code():
    src = " ".join(
        p.read_text().casefold()
        for p in Path(pd.__file__).parent.iterdir()
        if p.suffix in (".py", ".json")
    )
    for w in ("zyn", "obukpa", "steam", "flour", "mill"):
        assert w not in src
