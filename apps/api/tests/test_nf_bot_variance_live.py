"""BOT-VARIANCE-CONTROL live, read-only: Odoo 17 (category UoM) and 20 (relative UoM).

Needs ODOO_LIVE=1 and the nf sandbox stacks (ports 18117 / 18120). Reads only.
"""

from __future__ import annotations

import pytest

from app.bots.variance import analyse
from app.bots.variance.variance import _Uom
from tests.test_nf_bot_sinkhole_live import LIVE, Json

pytestmark = [pytest.mark.no_app_db, pytest.mark.skipif(not LIVE, reason="live: ODOO_LIVE=1")]
WRITES = {"create", "write", "unlink", "copy"}


class ReadOnly:
    def __init__(self, o: Json) -> None:
        self.o = o

    def __call__(self, model, method, args, kw=None):
        assert method not in WRITES
        return self.o(model, method, args, kw)


@pytest.fixture(scope="module", params=[17, 20])
def odoo(request):
    return request.param, ReadOnly(Json(request.param))


def test_live_uom_shape_converts_kg_to_g(odoo) -> None:
    v, o = odoo
    ids = {
        r["name"]: r["id"]
        for r in o(
            "uom.uom", "search_read", [[["name", "in", ["kg", "g", "L"]]]], {"fields": ["name"]}
        )
    }
    u = _Uom(o)
    assert u.load(ids.values())
    assert u.shape == ("category" if v < 19 else "relative")
    assert u.cache[ids["kg"]][1] == u.cache[ids["g"]][1] != u.cache[ids["L"]][1]
    assert u.conv(1.0, ids["kg"]) == pytest.approx(1000 * u.conv(1.0, ids["g"]))


def test_live_unit_metrics_never_unit_blind(odoo) -> None:
    _, o = odoo
    out = analyse(o, ["component_consumption", "stock_count"], limit=200)
    assert out["writes"] == 0
    for r in out["rows"]:
        assert "no unit field" not in (r.get("reason") or "")
        assert r["status"] != "within" or not r["truncated"]
