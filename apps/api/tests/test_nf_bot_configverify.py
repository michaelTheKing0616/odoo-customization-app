"""BOT-CONFIG-VERIFY: behaviour against a fake read-only Odoo, incl. every fail-closed path."""

from __future__ import annotations

import ast
import copy
from pathlib import Path

import pytest

from app.bots import configverify as cv

pytestmark = pytest.mark.no_app_db
M2O = lambda rel: {"type": "many2one", "relation": rel}  # noqa: E731
F = {"type": "float", "digits": [16, 2]}


class Fake:
    def __init__(self, companies: int = 1) -> None:
        self.calls: list[str] = []
        self.denied: set[str] = set()
        self.m = {
            "res.company": (
                {"name": {"type": "char"}},
                [{"id": i, "name": f"C{i}"} for i in range(1, companies + 1)],
            ),
            "ir.module.module": (
                {"name": {"type": "char"}, "state": {"type": "selection"}},
                [{"id": 1, "name": "stock", "state": "installed"}],
            ),
            "product.product": (
                {"name": {"type": "char"}},
                [{"id": 7, "name": "Part A"}, {"id": 8, "name": "Part B"}],
            ),
            "x.parent": (
                {
                    "name": {"type": "char"},
                    "qty": F,
                    "company_id": M2O("res.company"),
                    "active": {"type": "boolean"},
                },
                [{"id": 1, "name": "P1", "qty": 2.004, "company_id": 1, "active": True}],
            ),
            "x.line": (
                {
                    "parent_id": M2O("x.parent"),
                    "product_id": M2O("product.product"),
                    "qty": F,
                    "tag_ids": {"type": "many2many", "relation": "product.product"},
                },
                [{"id": 5, "parent_id": 1, "product_id": 7, "qty": 1.0, "tag_ids": [7, 8]}],
            ),
            "res.config.settings": ({"group_x": {"type": "boolean"}}, [{"id": 0, "group_x": True}]),
        }

    def dn(self, model, r):  # Odoo-like display names: "[CODE] Name", BoM "REF: Product"
        if model == "mrp.bom":
            return f"BOM{r['id']}: " + self.dn(
                "product.template", self._row("product.template", r["product_tmpl_id"])
            )
        if r.get("default_code"):
            return f"[{r['default_code']}] {r.get('name')}"
        return r.get("name") or r.get("title") or str(r["id"])

    def _row(self, model, i):
        return next(r for r in self.m[model][1] if r["id"] == i)

    def _name(self, model, i):
        row = next((r for r in self.m[model][1] if r["id"] == i), None)
        return [i, row.get("name", str(i))] if row else False

    def _fmt(self, model, r, fields):
        fg = self.m[model][0]
        out = {"id": r["id"], "display_name": self.dn(model, r)}
        for f in set(fields) - {"display_name"}:
            v = r.get(f)
            out[f] = (
                self._name(fg[f]["relation"], v)
                if fg.get(f, {}).get("type") == "many2one" and v
                else v
            )
        return out

    def _match(self, model, r, dom):
        hits = []
        for f, op, v in (x for x in dom if x != "|"):
            got = self.dn(model, r) if f == "display_name" else r.get(f)
            if isinstance(got, list):  # x2many contains
                hits.append(op == "in" and bool(set(got) & set(v)))
            elif op == "ilike":
                hits.append(isinstance(got, str) and v.lower() in got.lower())
            else:
                hits.append(got == v if op == "=" else got in v)
        return any(hits) if "|" in dom else all(hits)

    def __call__(self, model, method, args, kw=None):
        self.calls.append(f"{model}.{method}")
        if model in self.denied:
            raise PermissionError("AccessError")
        if model not in self.m:
            raise KeyError(f"model {model} not found")
        fg, rows = self.m[model]
        kw = kw or {}
        if method == "fields_get":
            return copy.deepcopy(fg)
        if method == "search_count":
            return len(rows)
        if method == "search_read":
            hit = [r for r in rows if self._match(model, r, args[0])][: kw.get("limit") or None]
            return [self._fmt(model, r, kw.get("fields", [])) for r in hit]
        if method == "read":
            return [self._fmt(model, r, kw["fields"]) for r in rows if r["id"] in args[0]]
        if method == "default_get":
            return {f: rows[0].get(f) for f in args[0]}
        raise AssertionError(method)


PARENT = {
    "kind": "record",
    "model": "x.parent",
    "key": {"name": "P1"},
    "expected": {"qty": 2.0},
    "relations": {},
    "verdict": "stock",
    "ref": "x.parent:name=P1",
}
LINE = {
    "kind": "record",
    "model": "x.line",
    "key": {"parent_id": "P1", "product_id": "Part A"},
    "expected": {"qty": 1.0},
    "relations": {"parent_id": "x.parent:name=P1"},
    "verdict": "stock",
    "ref": "x.line:parent_id=P1,product_id=Part A",
}


def spec(*items):
    return {
        "spec_version": 1,
        "status": "designed",
        "odoo_major": 18,
        "items": [copy.deepcopy(i) for i in items],
    }


def st(out):
    return [i["status"] for i in out["items"]]


def test_all_match_with_float_rounding_and_link():
    out = cv.verify(spec(PARENT, LINE), Fake())
    assert st(out) == ["matches", "matches"] and out["status"] == "matches"
    assert out["summary"]["matches"] == 2 and out["items"][0]["company"] == "C1"


def test_differs_reports_expected_and_found():
    p = PARENT | {"expected": {"qty": 3.0}}
    out = cv.verify(spec(p), Fake())
    assert st(out) == ["differs"] and out["items"][0]["diffs"] == [
        {"field": "qty", "expected": 3.0, "found": 2.004}
    ]


def test_missing_record_and_missing_key_target():
    out = cv.verify(
        spec(
            PARENT | {"key": {"name": "nope"}},
            LINE | {"key": {"parent_id": "P1", "product_id": "Zed"}},
        ),
        Fake(),
    )
    assert st(out) == ["missing", "missing"]


def test_broken_link_turns_match_into_differs():
    out = cv.verify(spec(PARENT | {"expected": {"qty": 9.0}}, LINE), Fake())
    assert (
        st(out) == ["differs", "differs"]
        and "target differs" in out["items"][1]["diffs"][0]["reason"]
    )
    out = cv.verify(spec(LINE), Fake())  # link target not in the design
    assert st(out) == ["differs"]


def test_cycle_in_relations_terminates():
    a = PARENT | {"relations": {"company_id": "x.line:parent_id=P1,product_id=Part A"}}
    out = cv.verify(spec(a, LINE), Fake())
    assert set(st(out)) == {"differs"}


def test_m2o_and_x2m_compared_by_id_not_text():
    f = Fake()
    out = cv.verify(
        spec(PARENT, LINE | {"expected": {"tag_ids": ["Part A", "Part B"], "product_id": 7}}), f
    )
    assert st(out) == ["matches", "matches"]
    tags = {"tag_ids": ["product.product:name=Part A", "product.product:name=Part B"]}
    pa, pb = (
        {
            "kind": "record",
            "model": "product.product",
            "key": {"name": n},
            "expected": {},
            "ref": f"product.product:name={n}",
        }
        for n in ("Part A", "Part B")
    )
    assert (
        st(cv.verify(spec(PARENT, pa, pb, LINE | {"relations": LINE["relations"] | tags}), f))[3]
        == "matches"
    )
    assert (
        st(cv.verify(spec(PARENT, pa, LINE | {"relations": LINE["relations"] | tags}), f))[2]
        == "differs"
    )
    out = cv.verify(spec(PARENT, LINE | {"expected": {"tag_ids": ["Part A"]}}), f)
    assert st(out)[1] == "differs"


@pytest.mark.parametrize("deny", ["x.parent", "product.product"])
def test_access_error_is_cannot_read(deny):
    f = Fake()
    f.denied.add(deny)
    out = cv.verify(spec(PARENT, LINE), f)
    assert st(out)[1] == "cannot-read" and out["status"] != "matches"


def test_missing_model_field_and_module_not_installed():
    f = Fake()
    items = [
        PARENT | {"model": "x.absent", "ref": "a"},
        PARENT | {"expected": {"nofield": 1}, "ref": "b"},
        {
            "kind": "module",
            "model": "ir.module.module",
            "key": {"name": "mrp"},
            "expected": {"state": "installed"},
            "ref": "m",
        },
        {
            "kind": "module",
            "model": "ir.module.module",
            "key": {"name": "stock"},
            "expected": {"state": "installed"},
            "ref": "s",
        },
    ]
    assert st(cv.verify(spec(*items), f)) == ["cannot-read", "cannot-read", "missing", "matches"]


def test_partial_company_view_never_matches():
    out = cv.verify(spec(PARENT), Fake(companies=2), companies=[1])
    assert st(out) == ["cannot-read"] and out["company_view"] == "bot sees 1 of 2 companies"
    assert st(cv.verify(spec(PARENT), Fake(companies=2), companies=[1, 2])) == ["matches"]


def test_not_designed_and_bad_input():
    nd = PARENT | {"verdict": "needs-custom", "ref": "n1"}
    bad = [
        PARENT | {"expected": {"qty": float("nan")}, "ref": "n2"},
        PARENT | {"key": "x", "ref": "n3"},
        PARENT | {"expected": {"qty": "y" * 5000}, "ref": "n4"},
        PARENT | {"kind": "weird", "ref": "n5"},
    ]
    out = cv.verify(spec(nd, *bad, PARENT, PARENT), Fake())
    assert st(out) == ["not designed"] * 5 + ["matches", "not designed"]  # last: duplicate ref
    for s in (
        None,
        {},
        [],
        {"spec_version": 1, "items": []},
        {"spec_version": 2, "items": [PARENT]},
        "x",
    ):
        assert cv.verify(s, Fake())["status"] == "not enough input"


def test_setting_and_duplicates_and_archived():
    f = Fake()
    s = {
        "kind": "setting",
        "model": "res.config.settings",
        "key": {},
        "expected": {"group_x": True},
        "ref": "s",
    }
    assert st(cv.verify(spec(s), f)) == ["matches"]
    f.m["x.parent"][1].append({"id": 2, "name": "P1", "qty": 2.0, "company_id": 1})
    assert st(cv.verify(spec(PARENT), f)) == ["differs"]
    f.m["x.parent"][1][:] = [{"id": 1, "name": "P1", "qty": 2.0, "company_id": 1, "active": False}]
    assert st(cv.verify(spec(PARENT), f)) == ["differs"]


def test_item_limit_reports_truncated(monkeypatch):
    monkeypatch.setattr(cv, "MAX_ITEMS", 1)
    out = cv.verify(spec(PARENT, PARENT | {"ref": "z"}), Fake())
    assert out["truncated"] and st(out) == ["matches", "cannot-read"] and out["status"] != "matches"


def test_only_read_methods_reach_odoo():
    f = Fake()
    cv.verify(spec(PARENT, LINE), f)
    assert {c.split(".")[-1] for c in f.calls} <= cv.READ_METHODS
    with pytest.raises(cv.ReadOnlyViolation):
        cv.read_only(f)("res.partner", "unlink", [[1]], None)
    src = (Path(cv.__file__)).read_text()
    names = {n.value for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Constant)}
    assert not names & {"write", "create", "unlink", "execute_kw", "button_immediate_install"}


# ---------------------------------------------------------------- review round 1


def test_same_name_archived_duplicate_is_never_matches():
    f = Fake()
    f.m["product.product"][0]["active"] = {"type": "boolean"}
    f.m["product.product"][1][:] = [
        {"id": 1, "name": "Raw R1", "active": True},
        {"id": 2, "name": "Raw R1", "active": False},
    ]
    f.m["x.line"][1][0]["product_id"] = 2
    line = LINE | {"key": {"parent_id": "P1"}, "expected": {"product_id": "Raw R1"}}
    out = cv.verify(spec(PARENT, line), f)
    assert st(out) == ["matches", "cannot-read"] and "ambiguous" in out["items"][1]["reason"]
    keyed = LINE | {"key": {"parent_id": "P1", "product_id": "Raw R1"}}
    assert st(cv.verify(spec(PARENT, keyed), f))[1] == "cannot-read"
    f.m["product.product"][1].pop(0)  # only the archived one is left
    assert st(cv.verify(spec(PARENT, line), f))[1] == "differs"
    assert st(cv.verify(spec(PARENT, keyed), f))[1] == "differs"


def test_setting_on_partial_company_view_is_cannot_read():
    s = {
        "kind": "setting",
        "model": "res.config.settings",
        "key": {},
        "expected": {"group_x": True},
    }
    assert st(cv.verify(spec(s), Fake(companies=2), companies=[1])) == ["cannot-read"]


def test_missing_reason_mentions_access_rules():
    out = cv.verify(spec(PARENT | {"key": {"name": "nope"}}), Fake())
    assert out["items"][0]["status"] == "missing" and "access rules" in out["items"][0]["reason"]


def test_name_cap_hit_is_cannot_read_not_missing():
    f = Fake()
    rows = [{"id": 100 + i, "name": f"Part A{i}"} for i in range(cv.BATCH)]
    f.m["product.product"][1][:] = rows + [{"id": 7, "name": "Part A"}]
    out = cv.verify(spec(PARENT, LINE), f)
    assert st(out)[1] == "cannot-read" and "truncated" in out["items"][1]["reason"]


def test_link_fixpoint_propagates_through_three_steps():
    f = Fake()
    f.m["x.chain"] = (
        {"name": {"type": "char"}, "next_id": M2O("x.chain"), "qty": F},
        [
            {"id": i, "name": n, "next_id": i + 1 if i < 4 else False, "qty": 1.0}
            for i, n in enumerate("abcd", 1)
        ],
    )
    items = [
        {
            "kind": "record",
            "model": "x.chain",
            "key": {"name": n},
            "expected": {"qty": 1.0},
            "relations": {"next_id": f"x.chain:name={nx}"} if nx else {},
            "ref": f"x.chain:name={n}",
        }
        for n, nx in zip("abcd", ["b", "c", "d", None], strict=True)
    ]
    items[3]["expected"] = {"qty": 2.0}
    assert st(cv.verify(spec(*items), f)) == ["differs"] * 4


# real BOT-PROCESS-DESIGN output against an Odoo-like fake ('[CODE] Name', 'REF: Product')
PD_FIELDS = {
    "product.template": {
        "name": {"type": "char"},
        "default_code": {"type": "char"},
        "active": {"type": "boolean"},
    },
    "product.product": {
        "name": {"type": "char"},
        "default_code": {"type": "char"},
        "active": {"type": "boolean"},
        "product_tmpl_id": M2O("product.template"),
    },
    "mrp.bom": {
        "product_tmpl_id": M2O("product.template"),
        "product_qty": F,
        "type": {"type": "selection"},
        "active": {"type": "boolean"},
    },
    "mrp.workcenter": {"name": {"type": "char"}, "costs_hour": F},
    "mrp.routing.workcenter": {
        "bom_id": M2O("mrp.bom"),
        "name": {"type": "char"},
        "sequence": {"type": "integer"},
        "workcenter_id": M2O("mrp.workcenter"),
        "time_cycle_manual": F,
    },
    "mrp.bom.line": {
        "bom_id": M2O("mrp.bom"),
        "product_id": M2O("product.product"),
        "product_qty": F,
        "operation_id": M2O("mrp.routing.workcenter"),
    },
    "mrp.bom.byproduct": {
        "bom_id": M2O("mrp.bom"),
        "product_id": M2O("product.product"),
        "product_qty": F,
        "cost_share": F,
        "operation_id": M2O("mrp.routing.workcenter"),
    },
    "quality.point": {
        "title": {"type": "char"},
        "product_ids": {"type": "many2many", "relation": "product.product"},
        "operation_id": M2O("mrp.routing.workcenter"),
        "test_type": {"type": "selection"},
        "norm": F,
        "tolerance_min": F,
        "tolerance_max": F,
    },
}


def _pd_fake(sp):
    f = Fake()
    f.m["ir.module.module"][1].append({"id": 2, "name": "mrp", "state": "installed"})
    for m, fg in PD_FIELDS.items():
        f.m[m] = (fg, [])
    prod: dict[str, int] = {}

    def product(name):
        if name not in prod:
            n = len(prod) + 1
            f.m["product.template"][1].append(
                {"id": n, "name": name, "default_code": f"C{n}", "active": True}
            )
            f.m["product.product"][1].append(
                {
                    "id": n,
                    "name": name,
                    "default_code": f"C{n}",
                    "active": True,
                    "product_tmpl_id": n,
                }
            )
            prod[name] = n
        return prod[name]

    refs: dict[str, int] = {}
    for it in sp["items"]:
        if it["kind"] != "record":
            continue
        fg, rows = f.m[it["model"]]
        row = {"id": len(rows) + 1}
        for k, v in {**it["key"], **it["expected"], **it["relations"]}.items():
            rel = fg[k].get("relation")
            vs = v if isinstance(v, list) else [v]
            if rel in ("product.product", "product.template"):
                ids = [product(x) for x in vs]
            elif rel:
                ids = [
                    refs[x]
                    if x in refs
                    else next(
                        r["id"] for r in f.m[rel][1] if r.get("product_tmpl_id") == prod.get(x)
                    )
                    for x in vs
                ]
            else:
                row[k] = v
                continue
            row[k] = ids if fg[k]["type"] == "many2many" else ids[0]
        rows.append(row | ({"active": True} if "active" in fg else {}))
        refs[it["ref"]] = row["id"]
    return f


def test_real_process_design_output_matches():
    from app.bots.process_design import design as pd
    from tests.test_nf_bot_process_design import INV, PACK

    sp = pd.design(PACK["multi_step"], inventory=INV).to_spec()
    f = _pd_fake(sp)
    out = cv.verify(sp, f)
    assert out["summary"]["matches"] == len(sp["items"]) and out["status"] == "matches", [
        (i["ref"], i["status"], i.get("reason"), i["diffs"])
        for i in out["items"]
        if i["status"] != "matches"
    ]
    f.m["mrp.bom.line"][1][0]["product_qty"] = 99.0  # one broken line: it differs, nothing else
    out = cv.verify(sp, f)
    assert out["summary"]["differs"] == 1
