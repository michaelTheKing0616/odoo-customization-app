from app.routers.introspection import FILL_MAX_FIELDS, field_fill_rates


class _C:
    def __init__(self, total, counts, bad=()):
        self.total, self.counts, self.bad, self.calls = total, counts, set(bad), []

    def execute_kw(self, model, method, args, kwargs=None):
        assert method == "search_count"  # read-only
        self.calls.append(args)
        dom = args[0]
        if not dom:
            return self.total
        f = dom[0][0]
        if f in self.bad:
            raise RuntimeError("not searchable")
        return self.counts[f]


def test_rates_and_unknowns():
    c = _C(200, {"email": 150, "phone": 0}, bad={"x_calc"})
    out = field_fill_rates(c, "res.partner", ["email", "phone", "x_calc", "email", "bad name"])
    assert out["total"] == 200
    assert out["fill"] == {"email": 0.75, "phone": 0.0, "x_calc": None}


def test_empty_model_and_cap():
    c = _C(0, {})
    out = field_fill_rates(c, "m", [f"f{i}" for i in range(60)])
    assert len(out["fill"]) == FILL_MAX_FIELDS
    assert set(out["fill"].values()) == {None}
    assert len(c.calls) == 1
