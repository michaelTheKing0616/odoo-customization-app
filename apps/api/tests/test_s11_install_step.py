"""S11: messaging channels by code, and the install step before the build."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai_conversation import install_step as ist
from app.ai_conversation.stock_routing import channel_route, route_service


def _snap(edition: str, installed=(), installable=(), major: int = 18):
    return SimpleNamespace(
        edition=edition, major=major,
        modules={m: f"{major}.0.1.0" for m in ("base", "mail", *installed)},
        installable={m: "uninstalled" for m in installable},
        index={"crm.lead": "Lead/Opportunity"} if "crm" in installed else {},
        selection_of=lambda *_a: [],
    )


def _item(kind: str, service: str) -> dict:
    return {"item": f"Send {service} messages", "service": service, "service_type": kind}


@pytest.mark.parametrize("major", [17, 18, 19, 20])
@pytest.mark.parametrize("edition", ["community", "enterprise"])
def test_sms_is_stock_on_both_editions(edition, major):
    r = channel_route(_item("sms", "Twilio SMS"), _snap(edition, installable=("sms",), major=major))
    assert r["route"] == "stock" and r["module"] == "sms"


@pytest.mark.parametrize("edition", ["community", "enterprise"])
def test_mail_is_stock_on_both_editions(edition):
    r = channel_route(_item("email", "Email"), _snap(edition))
    assert r["route"] == "stock" and r["module"] == "mail" and "uses" in r["label"]


def test_whatsapp_on_community_is_declined_with_plain_reason():
    r = route_service(_item("whatsapp", "WhatsApp"), _snap("community"))
    assert r["route"] == "decline"
    assert "Enterprise" in r["reason"] and "Community" in r["reason"]


def test_whatsapp_on_enterprise_is_stock():
    r = route_service(_item("whatsapp", "WhatsApp"), _snap("enterprise", installable=("whatsapp",)))
    assert r["route"] == "stock" and r["module"] == "whatsapp"


def test_unknown_type_falls_through_to_ladder():
    assert channel_route(_item("other", "Acme"), _snap("community")) is None


DESIGN = {"integrations": [
    {"app": "CRM", "module": "crm", "models": ["crm.lead"], "installed": False, "status": "available"},
    {"app": "Sales", "module": "sale", "models": ["sale.order"], "installed": True, "status": "available"},
]}


def test_install_step_lists_planned_missing_app_with_reason():
    step = ist.install_step(DESIGN, _snap("community", installable=("crm",)))
    assert step and [a["module"] for a in step["apps"]] == ["crm"]
    app = step["apps"][0]
    assert app["label"] == "CRM" and app["installable"] and "builds on CRM" in app["why"]
    assert step["can_install"] and step["install_label"] == "Install CRM"


def test_install_step_clears_after_install():
    assert ist.install_step(DESIGN, _snap("community", installed=("crm",))) is None


def test_install_step_not_installable_says_so():
    step = ist.install_step(DESIGN, _snap("community"))
    assert step and not step["can_install"] and "administrator" in step["message"]


def test_install_step_fails_closed_without_snapshot():
    assert ist.pending_apps(DESIGN, None)[0]["module"] == "crm"


def test_rental_label_from_domain_apps():
    d = {"integrations": [{"app": "sale_renting", "module": "sale_renting", "models": [],
                           "installed": False, "status": "available"}]}
    assert ist.install_step(d, _snap("enterprise", installable=("sale_renting",)))["apps"][0]["label"] == "Rental"


def test_install_gate_blocks_until_installed(monkeypatch):
    from fastapi import HTTPException

    from app.routers import ai_studio as r

    snaps = [_snap("community", installable=("crm",)), _snap("community", installed=("crm",))]
    monkeypatch.setattr(r, "_session_design", lambda _res: DESIGN)
    monkeypatch.setattr("app.odoo_service.get_connection_or_404", lambda _db, _cid: SimpleNamespace(id="c1"))
    monkeypatch.setattr(r, "snapshot_for_connection", lambda *_a, **_k: snaps[0])
    row = SimpleNamespace(connection_id="c1", prompt_original="x")
    with pytest.raises(HTTPException) as exc:
        r._install_gate(None, row, {})
    assert exc.value.status_code == 409
    assert exc.value.detail["install_step"]["apps"][0]["module"] == "crm"
    assert "can't build or apply" in exc.value.detail["message"]
    snaps.pop(0)
    r._install_gate(None, row, {})  # installed now: no raise


def test_install_gate_ignores_sessions_without_connection():
    from app.routers import ai_studio as r

    r._install_gate(None, SimpleNamespace(connection_id=None, prompt_original=""), {})


def test_install_apps_route_installs_planned_then_rechecks(monkeypatch):
    from app.routers import ai_studio as r

    calls = []
    state = {"snap": _snap("community", installable=("crm",))}
    row = SimpleNamespace(connection_id="c1", prompt_original="x", resolved_answers_json="{}")
    pend = {"kind": "diagnosis", "install_step": {"apps": [{"module": "crm"}]}}
    monkeypatch.setattr(r, "get_session", lambda _db, _sid: row)
    monkeypatch.setattr(r, "_session_design", lambda _res: DESIGN)
    monkeypatch.setattr("app.odoo_service.get_connection_or_404", lambda _db, _cid: SimpleNamespace(id="c1"))
    monkeypatch.setattr(r, "snapshot_for_connection", lambda *_a, **_k: state["snap"])
    monkeypatch.setattr(r, "_open_stock_app_port", lambda _c: object())
    monkeypatch.setattr(r, "append_turn", lambda *a, **k: None)
    monkeypatch.setattr(r, "clear_snapshot_cache", lambda *_a: None)
    monkeypatch.setattr(r, "session_to_dict", lambda _row: {"pending_clarification": pend})
    def fake_update(_db, _row, **f):
        if "pending_clarification" not in f:
            return None  # S12: resolved answers (design-refresh flag) are stored too
        pend.update(f["pending_clarification"])
        if "install_step" not in f["pending_clarification"]:
            pend.pop("install_step", None)

    monkeypatch.setattr(r, "update_session", fake_update)
    # S12: after an install the design is refreshed on the real models (covered in test_s12_followup).
    refreshed = []
    monkeypatch.setattr(r, "_refresh_design_after_install",
                        lambda *_a, **_k: refreshed.append(True) or "")
    monkeypatch.setattr(r, "_attach_diagnosis", lambda *_a, **_k: {"kind": "diagnosis"})
    monkeypatch.setattr(r, "assess_intent", lambda *_a, **_k: None)

    def fake_install(_port, module, label):
        calls.append(module)
        state["snap"] = _snap("community", installed=("crm",))
        return True, f"{label} is installed."

    monkeypatch.setattr("app.ai_conversation.install_step.install_planned_module", fake_install)
    out = r.install_apps_route("s1", db=None)
    assert calls == ["crm"]
    assert out["install_step"] is None and out["installed"] == ["CRM is installed."]
    assert refreshed == [True]


def test_field_pack_on_missing_host_gets_install_step():
    u = SimpleNamespace(host_model="crm.lead", inherit_existing=True)
    snap = _snap("community", installable=("crm",))
    step = ist.install_step({}, snap, ist.session_plans(u, None, snap))
    assert step and step["apps"][0]["module"] == "crm" and step["apps"][0]["models"] == ["crm.lead"]


def test_stock_check_install_is_planned_and_merged():
    dec = {"stock_checks": [{"choice": "stock", "install": "crm",
                             "use": {"module": "crm", "model": "crm.lead", "name": "CRM"}},
                            {"choice": "custom", "install": "event"}]}
    u = SimpleNamespace(host_model="crm.lead", inherit_existing=True)
    snap = _snap("community", installable=("crm", "event"))
    step = ist.install_step({}, snap, ist.session_plans(u, dec, snap))
    assert [a["module"] for a in step["apps"]] == ["crm"]


def test_present_host_needs_no_install():
    u = SimpleNamespace(host_model="crm.lead", inherit_existing=True)
    snap = _snap("community", installed=("crm",))
    assert ist.install_step({}, snap, ist.session_plans(u, None, snap)) is None
