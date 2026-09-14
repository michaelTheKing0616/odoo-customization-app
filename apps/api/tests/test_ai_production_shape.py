"""Search-view polish: uid is res.users, not hr.employee."""

from __future__ import annotations

from app.ai_production_shape import ensure_search_views, scrub_uid_my_records_filters


def test_my_records_uses_uid_only_for_res_users() -> None:
    draft = {
        "models": [
            {
                "model": "x_visitor_log",
                "description": "Visitor Log",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_employee_id",
                        "ttype": "many2one",
                        "relation": "hr.employee",
                    },
                    {"name": "x_time_in", "ttype": "datetime"},
                    {
                        "name": "x_user_id",
                        "ttype": "many2one",
                        "relation": "res.users",
                    },
                ],
            }
        ],
        "actions": [{"model": "x_visitor_log"}],
        "views": [],
    }
    ensure_search_views(draft)
    arch = next(
        str(v.get("arch") or "")
        for v in draft["views"]
        if v.get("type") == "search"
    )
    assert "my_x_employee_id" not in arch
    assert "my_x_user_id" in arch
    assert "uid" in arch


def test_scrub_drops_employee_eq_uid_my_records() -> None:
    draft = {
        "models": [
            {
                "model": "x_visitor_log",
                "fields": [
                    {
                        "name": "x_employee_id",
                        "ttype": "many2one",
                        "relation": "hr.employee",
                    }
                ],
            }
        ],
        "views": [
            {
                "name": "x_visitor_log.search",
                "model": "x_visitor_log",
                "type": "search",
                "arch": (
                    '<search string="Visitor Logs">'
                    '<filter string="This month" name="month_x_time_in" '
                    "domain=\"[('x_time_in','&gt;=', (context_today().replace(day=1)).strftime('%Y-%m-%d'))]\"/>"
                    '<filter string="My records" name="my_x_employee_id" '
                    "domain=\"[('x_employee_id','=', uid)]\"/>"
                    "</search>"
                ),
            }
        ],
    }
    notes = scrub_uid_my_records_filters(draft)
    arch = str(draft["views"][0]["arch"])
    assert "my_x_employee_id" not in arch
    assert "month_x_time_in" in arch
    assert notes
