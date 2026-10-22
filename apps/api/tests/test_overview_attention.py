"""Overview 'needs attention' rules over a fake metadata-only Odoo."""

from __future__ import annotations

from typing import Any

import pytest

from app.odoo_snapshot import clear_snapshot_cache, connection_overview, overview_attention

pytestmark = pytest.mark.no_app_db


def fake(major: int = 18, *, failing=(), overdue=(), pending=(), broken=(), custom=(), acl=(), acts=(),
         orphan=False, version: str | None = None):
    ver = version or f"{major}.0.1.0"
    cron_fields = {"cron_name": {"type": "char"}, "active": {"type": "boolean"}, "nextcall": {"type": "datetime"}}
    if major >= 18:
        cron_fields["failure_count"] = {"type": "integer"}
    ids = {m: i + 100 for i, m in enumerate(custom)}

    def call(model: str, method: str, args: list, kwargs: dict) -> Any:
        dom = args[0] if args else []
        if method == "fields_get":
            return {"ir.cron": cron_fields, "base.automation": {"name": {"type": "char"}, "model_id": {"type": "many2one"},
                                                                 "active": {"type": "boolean"}}}.get(model, {"name": {"type": "char"}})
        if model == "ir.module.module":
            if dom and dom[0][0] == "state" and dom[0][1] == "in":
                return [{"name": n, "state": s} for n, s in pending]
            if dom and dom[0] == ["state", "=", "uninstallable"]:
                return [{"name": n} for n in broken]
            return [{"name": "base", "latest_version": ver}, {"name": "base_automation", "latest_version": ver}]
        if model == "ir.model" and method == "search_read" and dom and dom[0][0] == "model":
            return [{"id": ids[m], "model": m} for m in custom]
        if model == "ir.model":
            return [{"model": m, "name": m} for m in ("res.partner", "ir.cron", "base.automation", *custom)]
        if model == "ir.cron":
            if dom and dom[0][0] == "failure_count":
                assert major >= 18, "failure_count read on a version without it"
                return [{"cron_name": n, "failure_count": 3} for n in failing]
            if dom and dom[0] == ["active", "=", True]:
                return [
                    {"cron_name": n, "nextcall": "2020-01-01 00:00:00"} if isinstance(n, str)
                    else {"cron_name": n[0], "nextcall": n[1], "interval_number": n[2], "interval_type": n[3]}
                    for n in overdue
                ]
            return []
        if model in {"ir.model.access", "ir.access"}:
            assert (model == "ir.access") == (major >= 20)
            return [{"model_id": [ids[m], m]} for m in acl]
        if model == "ir.actions.act_window":
            return [{"res_model": m} for m in acts]
        if model == "base.automation":
            return [{"name": "Dangling", "model_id": False}] if orphan else []
        return []

    return call


def _attention(call, key: str, limits=None) -> list[dict[str, Any]]:
    clear_snapshot_cache(key)
    connection_overview(call, key)
    return overview_attention(call, key, limits)


def test_all_clear_is_empty() -> None:
    assert _attention(fake(18), "clear") == []


def test_failing_and_overdue_crons_rank_first() -> None:
    items = _attention(fake(18, failing=["Mail queue"], overdue=["Nightly"], pending=[("crm", "to upgrade")]), "crons")
    assert [i["key"] for i in items] == ["failing_crons", "overdue_crons", "pending_modules"]
    assert items[0]["severity"] == "critical" and items[0]["names"] == ["Mail queue"]
    assert items[0]["drill"] == {"section": "automations"}


def test_failure_count_is_probed_not_assumed_on_17() -> None:
    items = _attention(fake(17, overdue=["Nightly"]), "v17")
    assert [i["key"] for i in items] == ["overdue_crons"]


def test_broken_and_pending_modules() -> None:
    items = _attention(fake(18, broken=["old_addon"], pending=[("sale", "to install")]), "mods")
    assert [(i["key"], i["severity"]) for i in items] == [("broken_modules", "critical"), ("pending_modules", "notice")]
    assert items[1]["names"] == ["sale (to install)"]


def test_orphan_automation_is_critical() -> None:
    assert _attention(fake(18, orphan=True), "orph")[0]["key"] == "orphan_automations"


@pytest.mark.parametrize("major", [18, 20])
def test_custom_models_missing_access_or_menu(major: int) -> None:
    items = _attention(fake(major, custom=["x_a", "x_b"], acl=["x_a"], acts=["x_b"]), f"cm{major}")
    by = {i["key"]: i for i in items}
    assert by["custom_no_access"]["names"] == ["x_b"] and by["custom_no_access"]["severity"] == "warning"
    assert by["custom_no_access"]["drill"] == {"section": "explorer", "model": "x_b", "tab": "rules"}
    assert by["custom_no_menu"]["names"] == ["x_a"] and by["custom_no_menu"]["drill"]["tab"] == "menus"


def test_plan_limits_and_version_support_rank_last() -> None:
    items = _attention(fake(18, version="22.0.1.0", broken=["x"]), "lim",
                       [{"key": "python_module_install", "label": "custom code modules"}])
    assert [i["key"] for i in items] == ["broken_modules", "plan_limits", "version_support"]
    assert items[1]["severity"] == "limit" and "custom code modules" in items[1]["detail"]
    assert items[2]["drill"] == {"section": "header"}


def test_router_only_flags_plan_limits_when_customising(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    import app.routers.connections as rc

    for custom, expect in (((), False), (("x_a",), True)):
        row = SimpleNamespace(id=f"pl{len(custom)}", url="https://acme.odoo.com", server_version="18.0")
        clear_snapshot_cache(row.id)
        call = fake(18, custom=list(custom), acl=list(custom), acts=list(custom))
        monkeypatch.setattr(rc, "get_scoped_connection_or_404", lambda db, cid, auth, row=row: row)
        monkeypatch.setattr(rc, "_snapshot_call", lambda r, db, call=call: call)
        out = rc.get_connection_snapshot("c", db=None, auth=None)
        assert any(i["key"] == "plan_limits" for i in out["attention"]) is expect


def test_overdue_threshold_is_max_of_a_day_and_twice_the_interval() -> None:
    import time as _t
    three_days_ago = _t.strftime("%Y-%m-%d %H:%M:%S", _t.gmtime(_t.time() - 3 * 86400))
    # Daily cron 3 days late -> overdue (> 2 days). Weekly cron 3 days late -> not overdue (< 14 days).
    f = fake(18, overdue=[("Daily", three_days_ago, 1, "days"), ("Weekly", three_days_ago, 1, "weeks")])
    items = _attention(f, "thresh")
    assert [i["names"] for i in items if i["key"] == "overdue_crons"] == [["Daily"]]


def test_plan_limit_wording_is_soft() -> None:
    items = _attention(fake(18), "soft", [{"key": "module_deploy", "label": "installing your own modules"}])
    item = next(i for i in items if i["key"] == "plan_limits")
    assert "estimate" in item["detail"] and "may" in item["title"]


def test_snapshot_refresh_clears_only_this_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    import app.routers.connections as rc
    from app.odoo_snapshot import _BASE_CACHE

    row = SimpleNamespace(id="conn-refresh", url="http://x", server_version="18.0")
    monkeypatch.setattr(rc, "get_scoped_connection_or_404", lambda db, cid, auth: row)
    monkeypatch.setattr(rc, "_snapshot_call", lambda r, db: fake(18))
    rc.get_connection_snapshot("x", db=None, auth=None)
    _BASE_CACHE["other-conn"] = {"sentinel": True}
    assert "conn-refresh" in _BASE_CACHE
    calls: list[str] = []
    monkeypatch.setattr("app.odoo_snapshot.clear_snapshot_cache", lambda key=None: calls.append(key))
    rc.get_connection_snapshot("x", db=None, auth=None, refresh=True)
    rc.get_connection_snapshot_model("x", "res.partner", db=None, auth=None, refresh=True)
    assert calls == ["conn-refresh", "conn-refresh"] and "other-conn" in _BASE_CACHE
    _BASE_CACHE.pop("other-conn", None)


def test_model_detail_exposes_custom_field_ids_for_editing() -> None:
    from app.odoo_snapshot import model_detail

    base_call = fake(18, custom=["x_job"])

    def call(model, method, args, kwargs):
        if model == "ir.model.fields" and method == "search_read":
            return [{"id": 41, "name": "x_name", "help": "Job title"}]
        return base_call(model, method, args, kwargs)

    clear_snapshot_cache("ids")
    connection_overview(call, "ids")
    d = model_detail(call, "ids", "res.partner")
    byname = {f["name"]: f for f in d["fields"]}
    assert all(f["id"] is None and f["custom"] is False for n, f in byname.items() if not n.startswith("x_"))
