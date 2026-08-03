"""EE view arch golden fixtures (TIER-6)."""

from __future__ import annotations

import pytest

from odoo_client.view_arch import (
    CohortViewSpec,
    GanttViewSpec,
    GridViewSpec,
    MapViewSpec,
    parse_arch,
    render_arch,
)


@pytest.mark.parametrize("major", [17, 18, 19])
def test_gantt_golden_per_major(major: int) -> None:
    spec = GanttViewSpec(
        string="Plan",
        date_start="date_start",
        date_stop="date_end",
        default_scale="week",
        dependency_field="depend_on_id",
        allow_drag_drop=True,
        progress="progress",
    )
    arch = render_arch("gantt", {**spec.model_dump(), "major": major})
    assert 'default_scale="week"' in arch
    assert 'dependency_field="depend_on_id"' in arch
    assert 'allow_drag_drop="1"' in arch
    again = parse_arch("gantt", arch)
    assert again["default_scale"] == "week"


def test_map_routing_and_order() -> None:
    spec = MapViewSpec(
        res_partner="partner_id",
        routing=True,
        default_order="name asc",
    )
    arch = render_arch("map", spec.model_dump())
    assert 'routing="1"' in arch
    assert 'default_order="name asc"' in arch
    parsed = parse_arch("map", arch)
    assert parsed["routing"] is True


def test_grid_adjustment() -> None:
    spec = GridViewSpec(
        row_field="user_id",
        col_field="date",
        measure="amount",
        adjustment="increment",
    )
    arch = render_arch("grid", spec.model_dump())
    assert 'adjustment="increment"' in arch
    parsed = parse_arch("grid", arch)
    assert parsed["adjustment"] == "increment"


def test_cohort_golden() -> None:
    spec = CohortViewSpec(
        date_start="create_date",
        interval="month",
        mode="retention",
        measure="__count__",
    )
    arch = render_arch("cohort", spec.model_dump())
    assert 'interval="month"' in arch
    parsed = parse_arch("cohort", arch)
    assert parsed["mode"] == "retention"
