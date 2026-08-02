"""Unit tests for calendar / graph / pivot (and map stub) arch round-trips."""

import pytest

from odoo_client.view_arch import (
    AxisFieldNode,
    CalendarViewSpec,
    FieldNode,
    GraphViewSpec,
    MapViewSpec,
    PivotViewSpec,
    parse_arch,
    parse_calendar_arch,
    parse_graph_arch,
    parse_map_arch,
    parse_pivot_arch,
    render_arch,
    render_calendar_arch,
    render_graph_arch,
    render_inherit_replace_arch,
    render_map_arch,
    render_pivot_arch,
)


def test_calendar_render_parse_round_trip() -> None:
    spec = CalendarViewSpec(
        string="Events",
        date_start="x_start",
        date_stop="x_stop",
        color="x_partner_id",
        mode="month",
        fields=[
            FieldNode(name="x_name"),
            FieldNode(name="x_partner_id"),
        ],
    )
    arch = render_calendar_arch(spec)
    assert '<calendar string="Events"' in arch
    assert 'date_start="x_start"' in arch
    assert 'date_stop="x_stop"' in arch
    assert 'color="x_partner_id"' in arch
    assert 'mode="month"' in arch
    assert 'name="x_name"' in arch

    parsed = parse_calendar_arch(arch)
    assert parsed.string == "Events"
    assert parsed.date_start == "x_start"
    assert parsed.date_stop == "x_stop"
    assert parsed.color == "x_partner_id"
    assert parsed.mode == "month"
    assert [f.name for f in parsed.fields] == ["x_name", "x_partner_id"]

    again = parse_arch("calendar", render_arch("calendar", parsed.model_dump()))
    assert again["date_start"] == "x_start"
    assert again["date_stop"] == "x_stop"
    assert [f["name"] for f in again["fields"]] == ["x_name", "x_partner_id"]


def test_calendar_optional_attrs_omitted() -> None:
    arch = render_calendar_arch(
        CalendarViewSpec(string="Simple", date_start="date_begin", fields=[])
    )
    assert 'date_start="date_begin"' in arch
    assert "date_stop" not in arch
    assert "color=" not in arch
    assert "mode=" not in arch
    parsed = parse_calendar_arch(arch)
    assert parsed.date_stop is None
    assert parsed.color is None
    assert parsed.mode is None


def test_graph_bar_round_trip() -> None:
    spec = GraphViewSpec(
        string="Sales",
        type="bar",
        fields=[
            AxisFieldNode(name="x_partner_id", type="row"),
            AxisFieldNode(name="x_amount", type="measure"),
        ],
    )
    arch = render_graph_arch(spec)
    assert '<graph string="Sales" type="bar"' in arch or (
        'string="Sales"' in arch and 'type="bar"' in arch
    )
    assert 'name="x_partner_id"' in arch and 'type="row"' in arch
    assert 'name="x_amount"' in arch and 'type="measure"' in arch

    parsed = parse_graph_arch(arch)
    assert parsed.type == "bar"
    assert [(f.name, f.type) for f in parsed.fields] == [
        ("x_partner_id", "row"),
        ("x_amount", "measure"),
    ]
    dumped = parse_arch("graph", render_arch("graph", parsed.model_dump()))
    assert dumped["type"] == "bar"
    assert [f["type"] for f in dumped["fields"]] == ["row", "measure"]


def test_graph_line_and_pie() -> None:
    for gtype in ("line", "pie"):
        arch = render_arch(
            "graph",
            {
                "string": "Trend",
                "type": gtype,
                "fields": [{"name": "x_qty", "type": "measure"}],
            },
        )
        assert f'type="{gtype}"' in arch
        parsed = parse_arch("graph", arch)
        assert parsed["type"] == gtype


def test_pivot_round_trip() -> None:
    spec = PivotViewSpec(
        string="Analysis",
        fields=[
            AxisFieldNode(name="x_partner_id", type="row"),
            AxisFieldNode(name="x_date", type="col", interval="month"),
            AxisFieldNode(name="x_total", type="measure"),
        ],
    )
    arch = render_pivot_arch(spec)
    assert "<pivot" in arch
    assert 'string="Analysis"' in arch
    assert 'type="row"' in arch
    assert 'type="col"' in arch
    assert 'interval="month"' in arch
    assert 'type="measure"' in arch

    parsed = parse_pivot_arch(arch)
    assert parsed.string == "Analysis"
    assert [(f.name, f.type, f.interval) for f in parsed.fields] == [
        ("x_partner_id", "row", None),
        ("x_date", "col", "month"),
        ("x_total", "measure", None),
    ]
    again = parse_arch("pivot", render_arch("pivot", parsed.model_dump()))
    assert [f["name"] for f in again["fields"]] == [
        "x_partner_id",
        "x_date",
        "x_total",
    ]
    assert again["fields"][1]["interval"] == "month"


def test_map_stub_round_trip() -> None:
    spec = MapViewSpec(
        string="Partners",
        res_partner="partner_id",
        fields=[FieldNode(name="name"), FieldNode(name="city")],
    )
    arch = render_map_arch(spec)
    assert "<map" in arch
    assert 'res_partner="partner_id"' in arch
    parsed = parse_map_arch(arch)
    assert parsed.res_partner == "partner_id"
    assert [f.name for f in parsed.fields] == ["name", "city"]
    again = parse_arch("map", render_arch("map", parsed.model_dump()))
    assert again["res_partner"] == "partner_id"


def test_reporting_inherit_replace_exprs() -> None:
    for vt, tag in (
        ("calendar", "calendar"),
        ("graph", "graph"),
        ("pivot", "pivot"),
        ("map", "map"),
    ):
        if vt == "calendar":
            inner = render_calendar_arch(
                CalendarViewSpec(date_start="x_start", fields=[FieldNode(name="x_name")])
            )
        elif vt == "graph":
            inner = render_graph_arch(
                GraphViewSpec(fields=[AxisFieldNode(name="x_amount", type="measure")])
            )
        elif vt == "pivot":
            inner = render_pivot_arch(
                PivotViewSpec(fields=[AxisFieldNode(name="x_amount", type="measure")])
            )
        else:
            inner = render_map_arch(MapViewSpec(fields=[FieldNode(name="name")]))
        wrapped = render_inherit_replace_arch(vt, inner)
        assert f'expr="//{tag}"' in wrapped
        assert "position=\"replace\"" in wrapped


# --- Adversarial / strict contracts (checker battery) ---


def test_calendar_rejects_missing_date_start() -> None:
    with pytest.raises(ValueError, match="date_start"):
        parse_calendar_arch('<calendar string="X"/>')


def test_calendar_rejects_wrong_root_tag() -> None:
    with pytest.raises(ValueError, match="Expected <calendar>"):
        parse_calendar_arch('<form><field name="x"/></form>')


def test_graph_unknown_type_defaults_to_bar() -> None:
    """Non bar/line/pie type attrs must not crash — coerce to bar."""
    parsed = parse_graph_arch(
        '<graph string="Bad" type="scatter">'
        '<field name="x_amount" type="measure"/>'
        "</graph>"
    )
    assert parsed.type == "bar"
    assert [f.name for f in parsed.fields] == ["x_amount"]


def test_graph_rejects_wrong_root() -> None:
    with pytest.raises(ValueError, match="Expected <graph>"):
        parse_graph_arch('<pivot><field name="x" type="measure"/></pivot>')


def test_pivot_rejects_wrong_root() -> None:
    with pytest.raises(ValueError, match="Expected <pivot>"):
        parse_pivot_arch('<graph type="bar"><field name="x" type="measure"/></graph>')


def test_pivot_ignores_unknown_axis_type() -> None:
    parsed = parse_pivot_arch(
        '<pivot string="P">'
        '<field name="x_partner_id" type="row"/>'
        '<field name="x_bogus" type="diagonal"/>'
        '<field name="x_total" type="measure"/>'
        "</pivot>"
    )
    assert [(f.name, f.type) for f in parsed.fields] == [
        ("x_partner_id", "row"),
        ("x_bogus", None),
        ("x_total", "measure"),
    ]


def test_calendar_inherit_unwrap_round_trip() -> None:
    inner = render_calendar_arch(
        CalendarViewSpec(
            string="Ev",
            date_start="x_start",
            date_stop="x_stop",
            fields=[FieldNode(name="x_name")],
        )
    )
    wrapped = render_inherit_replace_arch("calendar", inner)
    parsed = parse_calendar_arch(wrapped)
    assert parsed.date_start == "x_start"
    assert parsed.date_stop == "x_stop"
    assert [f.name for f in parsed.fields] == ["x_name"]


def test_graph_pivot_empty_fields_still_valid_xml() -> None:
    g = render_graph_arch(GraphViewSpec(string="Empty", type="pie", fields=[]))
    assert 'type="pie"' in g
    assert parse_graph_arch(g).fields == []
    p = render_pivot_arch(PivotViewSpec(string="Empty", fields=[]))
    assert "<pivot" in p
    assert parse_pivot_arch(p).fields == []


def test_axis_field_without_type_omits_attr() -> None:
    arch = render_pivot_arch(
        PivotViewSpec(fields=[AxisFieldNode(name="x_only")])
    )
    assert 'name="x_only"' in arch
    assert "type=" not in arch.split("x_only", 1)[1].split("/>", 1)[0]
    parsed = parse_pivot_arch(arch)
    assert parsed.fields[0].type is None


# --- Activity / Gantt / Cohort / form attrs / map Designer readiness ---


def test_activity_round_trip() -> None:
    from odoo_client.view_arch import (
        ActivityViewSpec,
        FieldNode,
        parse_activity_arch,
        render_activity_arch,
        render_arch,
        parse_arch,
    )

    spec = ActivityViewSpec(
        string="Tasks",
        fields=[FieldNode(name="name"), FieldNode(name="user_id")],
    )
    arch = render_activity_arch(spec)
    assert "<activity" in arch
    assert 't-name="activity-box"' in arch
    assert "<templates>" in arch
    assert 'name="name"' in arch
    parsed = parse_activity_arch(arch)
    assert parsed.string == "Tasks"
    assert [f.name for f in parsed.fields] == ["name", "user_id"]
    again = parse_arch("activity", render_arch("activity", parsed.model_dump()))
    assert again["fields"][0]["name"] == "name"


def test_activity_parses_legacy_flat_fields() -> None:
    from odoo_client.view_arch import parse_activity_arch

    parsed = parse_activity_arch(
        '<activity string="Old"><field name="x_name"/><field name="x_isbn"/></activity>'
    )
    assert [f.name for f in parsed.fields] == ["x_name", "x_isbn"]


def test_activity_rejects_wrong_root() -> None:
    from odoo_client.view_arch import parse_activity_arch

    with pytest.raises(ValueError, match="Expected <activity>"):
        parse_activity_arch('<form><field name="x"/></form>')


def test_gantt_round_trip() -> None:
    from odoo_client.view_arch import (
        FieldNode,
        GanttViewSpec,
        parse_gantt_arch,
        render_gantt_arch,
        parse_arch,
        render_arch,
    )

    spec = GanttViewSpec(
        string="Plan",
        date_start="date_start",
        date_stop="date_end",
        default_group_by="user_id",
        color="stage_id",
        fields=[FieldNode(name="name")],
    )
    arch = render_gantt_arch(spec)
    assert 'date_start="date_start"' in arch
    assert 'default_group_by="user_id"' in arch
    parsed = parse_gantt_arch(arch)
    assert parsed.date_stop == "date_end"
    assert parsed.color == "stage_id"
    again = parse_arch("gantt", render_arch("gantt", parsed.model_dump()))
    assert again["date_start"] == "date_start"


def test_gantt_requires_date_start() -> None:
    from odoo_client.view_arch import parse_gantt_arch

    with pytest.raises(ValueError, match="date_start"):
        parse_gantt_arch('<gantt string="X"/>')


def test_cohort_round_trip() -> None:
    from odoo_client.view_arch import (
        CohortViewSpec,
        parse_cohort_arch,
        render_cohort_arch,
        parse_arch,
        render_arch,
    )

    spec = CohortViewSpec(
        string="Retention",
        date_start="create_date",
        date_stop="date",
        interval="month",
        mode="churn",
        timeline="forward",
        measure="__count__",
    )
    arch = render_cohort_arch(spec)
    assert 'interval="month"' in arch
    assert 'mode="churn"' in arch
    parsed = parse_cohort_arch(arch)
    assert parsed.interval == "month"
    assert parsed.mode == "churn"
    again = parse_arch("cohort", render_arch("cohort", parsed.model_dump()))
    assert again["timeline"] == "forward"


def test_cohort_requires_date_start() -> None:
    from odoo_client.view_arch import parse_cohort_arch

    with pytest.raises(ValueError, match="date_start"):
        parse_cohort_arch('<cohort string="X"/>')


def test_notebook_page_fields_wrapped_in_group_for_labels() -> None:
    """Odoo omits labels for bare fields under <page>; wrap in <group>."""
    from odoo_client.view_arch import (
        FieldNode,
        FormViewSpec,
        NotebookNode,
        PageNode,
        parse_form_arch,
        render_form_arch,
    )

    arch = render_form_arch(
        FormViewSpec(
            string="Book",
            children=[
                NotebookNode(
                    pages=[
                        PageNode(
                            string="Catalog",
                            children=[
                                FieldNode(name="x_author_id", string="Author"),
                                FieldNode(name="x_copies", string="Copies"),
                            ],
                        )
                    ]
                )
            ],
        )
    )
    page_body = arch.split('<page string="Catalog">', 1)[1].split("</page>", 1)[0]
    assert "<group>" in page_body
    assert 'string="Author"' in page_body
    parsed = parse_form_arch(arch)
    nb = next(c for c in parsed.children if getattr(c, "kind", None) == "notebook")
    assert [f.name for f in nb.pages[0].children] == ["x_author_id", "x_copies"]
    assert nb.pages[0].children[0].string == "Author"


def test_form_can_create_edit_delete_duplicate_round_trip() -> None:
    from odoo_client.view_arch import FormViewSpec, parse_form_arch, render_form_arch

    spec = FormViewSpec(
        string="Locked",
        create=False,
        edit=True,
        delete=False,
        duplicate=False,
        children=[],
    )
    arch = render_form_arch(spec)
    assert 'create="0"' in arch
    assert 'edit="1"' in arch
    assert 'delete="0"' in arch
    assert 'duplicate="0"' in arch
    parsed = parse_form_arch(arch)
    assert parsed.create is False
    assert parsed.edit is True
    assert parsed.delete is False
    assert parsed.duplicate is False


def test_list_multi_edit_and_default_order() -> None:
    from odoo_client.view_arch import (
        FieldNode,
        ListViewSpec,
        parse_list_arch,
        render_list_arch,
    )

    spec = ListViewSpec(
        string="Rows",
        multi_edit=True,
        default_order="name asc",
        create=False,
        columns=[FieldNode(name="name")],
    )
    arch = render_list_arch(spec)
    assert 'multi_edit="1"' in arch
    assert 'default_order="name asc"' in arch
    parsed = parse_list_arch(arch)
    assert parsed.multi_edit is True
    assert parsed.default_order == "name asc"
    assert parsed.create is False


def test_map_inherit_replace_expr() -> None:
    from odoo_client.view_arch import (
        MapViewSpec,
        render_inherit_replace_arch,
        render_map_arch,
        parse_map_arch,
    )

    inner = render_map_arch(MapViewSpec(string="Partners", res_partner="partner_id"))
    wrapped = render_inherit_replace_arch("map", inner)
    assert 'expr="//map"' in wrapped
    parsed = parse_map_arch(wrapped)
    assert parsed.res_partner == "partner_id"


def test_activity_gantt_cohort_inherit_exprs() -> None:
    from odoo_client.view_arch import (
        ActivityViewSpec,
        CohortViewSpec,
        GanttViewSpec,
        render_activity_arch,
        render_cohort_arch,
        render_gantt_arch,
        render_inherit_replace_arch,
    )

    assert 'expr="//activity"' in render_inherit_replace_arch(
        "activity", render_activity_arch(ActivityViewSpec())
    )
    assert 'expr="//gantt"' in render_inherit_replace_arch(
        "gantt",
        render_gantt_arch(GanttViewSpec(date_start="date_start")),
    )
    assert 'expr="//cohort"' in render_inherit_replace_arch(
        "cohort",
        render_cohort_arch(CohortViewSpec(date_start="create_date")),
    )
