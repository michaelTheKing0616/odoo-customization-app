"""Walkthrough seed planner + fake RPC create (no live Odoo)."""

from __future__ import annotations

from typing import Any

from app.ai_walkthrough_seed import plan_walkthrough_models, seed_walkthrough, walkthrough_name


class _SeedFake:
    def __init__(self) -> None:
        self.models = {
            "x_studio",
            "x_artist",
            "x_engagement",
            "x_booking",
            "x_equipment",
            "x_equipment_line",
            "res.partner",
            "res.currency",
        }
        self.rows: dict[str, list[dict[str, Any]]] = {m: [] for m in self.models}
        self.rows["res.partner"] = [{"id": 7, "name": "Admin"}]
        self.rows["res.currency"] = [{"id": 1, "name": "USD"}]
        self._nid = 20
        self.creates: list[tuple[str, dict[str, Any]]] = []
        self.live_required: dict[str, list[dict[str, Any]]] = {}

    def model_exists(self, model: str) -> bool:
        return model in self.models

    def execute_kw(
        self, model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None
    ) -> Any:
        kwargs = kwargs or {}
        if method == "search":
            domain = args[0] if args else []
            name = None
            for term in domain:
                if isinstance(term, (list, tuple)) and len(term) >= 3 and term[0] == "x_name":
                    name = term[2]
            hits = [
                r["id"]
                for r in self.rows.get(model, [])
                if name is None or r.get("x_name") == name
            ]
            limit = kwargs.get("limit")
            return hits[:limit] if limit else hits
        if method == "search_read":
            domain = args[0] if args else []
            if model != "ir.model.fields":
                return []
            mid = None
            for term in domain:
                if isinstance(term, (list, tuple)) and len(term) >= 3 and term[0] == "model":
                    mid = term[2]
            return list(self.live_required.get(str(mid or ""), []))
        if method == "create":
            vals = args[0]
            self._nid += 1
            rid = self._nid
            row = {"id": rid, **vals}
            self.rows.setdefault(model, []).append(row)
            self.creates.append((model, vals))
            return rid
        return []


_SPEC = {
    "models": [
        {
            "model": "x_studio",
            "mode": "new",
            "fields": [{"name": "x_name", "ttype": "char", "required": True}],
        },
        {
            "model": "x_artist",
            "mode": "new",
            "fields": [
                {"name": "x_name", "ttype": "char", "required": True},
                {"name": "x_partner_id", "ttype": "many2one", "relation": "res.partner"},
            ],
        },
        {
            "model": "x_engagement",
            "mode": "new",
            "fields": [
                {"name": "x_name", "ttype": "char", "required": True},
                {"name": "x_studio_id", "ttype": "many2one", "relation": "x_studio"},
                {"name": "x_artist_id", "ttype": "many2one", "relation": "x_artist"},
            ],
        },
        {
            "model": "x_booking",
            "mode": "new",
            "fields": [
                {"name": "x_name", "ttype": "char", "required": True},
                {
                    "name": "x_engagement_id",
                    "ttype": "many2one",
                    "relation": "x_engagement",
                    "required": True,
                },
                {
                    "name": "x_status",
                    "ttype": "selection",
                    "selection": "[('draft','Draft'),('done','Done')]",
                    "default": "draft",
                },
            ],
        },
        {
            "model": "x_equipment",
            "mode": "new",
            "fields": [{"name": "x_name", "ttype": "char", "required": True}],
        },
        {
            "model": "x_equipment_line",
            "mode": "new",
            "fields": [
                {"name": "x_name", "ttype": "char", "required": True},
                {
                    "name": "x_equipment_id",
                    "ttype": "many2one",
                    "relation": "x_equipment",
                    "required": True,
                },
                {
                    "name": "x_booking_id",
                    "ttype": "many2one",
                    "relation": "x_booking",
                    "required": True,
                },
            ],
        },
    ]
}


def test_plan_walkthrough_headers_before_lines() -> None:
    order = plan_walkthrough_models(_SPEC)
    assert order.index("x_equipment") < order.index("x_equipment_line")
    assert order.index("x_booking") < order.index("x_equipment_line")
    assert order.index("x_engagement") < order.index("x_booking")


def test_seed_walkthrough_links_spine() -> None:
    client = _SeedFake()
    result = seed_walkthrough(client, _SPEC)
    assert result["ok"] is True
    created = result["created"]
    assert "x_engagement" in created
    assert "x_booking" in created
    assert "x_equipment_line" in created
    line_vals = next(v for m, v in client.creates if m == "x_equipment_line")
    assert line_vals["x_booking_id"] == created["x_booking"]
    assert line_vals["x_equipment_id"] == created["x_equipment"]
    booking_vals = next(v for m, v in client.creates if m == "x_booking")
    assert booking_vals["x_engagement_id"] == created["x_engagement"]
    assert booking_vals["x_status"] == "draft"
    eng_vals = next(v for m, v in client.creates if m == "x_engagement")
    assert eng_vals["x_studio_id"] == created["x_studio"]
    assert eng_vals["x_artist_id"] == created["x_artist"]
    assert result["open_model"] in {"x_engagement", "x_booking"}
    assert result["open_record_id"] == created[result["open_model"]]


def test_seed_walkthrough_is_idempotent_by_name() -> None:
    client = _SeedFake()
    first = seed_walkthrough(client, _SPEC)
    n = len(client.creates)
    second = seed_walkthrough(client, _SPEC)
    assert len(client.creates) == n
    assert second["created"]["x_booking"] == first["created"]["x_booking"]
    assert walkthrough_name("x_booking").startswith("Walkthrough")


def test_seed_fills_live_required_fields_absent_from_spec() -> None:
    client = _SeedFake()
    client.live_required = {
        "x_studio": [{"name": "x_rate_hour", "ttype": "float", "readonly": False}],
        "x_booking": [
            {
                "name": "x_session_type",
                "ttype": "selection",
                "selection": "[('recording','Recording'),('mixing','Mixing')]",
                "readonly": False,
            }
        ],
        "x_booking_line": [
            {
                "name": "x_booking_id",
                "ttype": "many2one",
                "relation": "x_booking",
                "readonly": False,
            }
        ],
    }
    spec = {
        "models": [
            *_SPEC["models"],
            {
                "model": "x_booking_line",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_booking_id",
                        "ttype": "many2one",
                        "relation": "x_booking",
                        "required": False,
                    },
                ],
            },
        ]
    }
    client.models.add("x_booking_line")
    result = seed_walkthrough(client, spec)
    studio_vals = next(v for m, v in client.creates if m == "x_studio")
    assert studio_vals["x_rate_hour"] == 1.0
    booking_vals = next(v for m, v in client.creates if m == "x_booking")
    assert booking_vals["x_session_type"] == "recording"
    line_vals = next(v for m, v in client.creates if m == "x_booking_line")
    assert line_vals["x_booking_id"] == result["created"]["x_booking"]


def test_seed_skips_child_when_parent_create_fails() -> None:
    class _Boom(_SeedFake):
        def execute_kw(
            self, model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None
        ) -> Any:
            if method == "create" and model == "x_booking":
                raise RuntimeError("missing session type")
            return super().execute_kw(model, method, args, kwargs)

    client = _Boom()
    result = seed_walkthrough(client, _SPEC)
    assert "x_booking" not in result["created"]
    assert "x_equipment_line" not in result["created"]
    assert any("x_booking create failed" in w for w in result["warnings"])
    assert any("skip x_equipment_line" in w for w in result["warnings"])
