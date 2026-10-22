"""S12: fixes found exercising the real install path on Odoo 17-20."""

from __future__ import annotations

from types import SimpleNamespace

from app.dry_run_middleware import is_write_capable
from app.spec_apply_ui import UiApplyResult, _apply_component_inherit


class _Client:
    def __init__(self, fail_anchor: bool):
        self.fail_anchor = fail_anchor
        self.injected: list[str] = []
        self.created: list[str] = []

    def model_exists(self, model):
        return True

    def field_exists(self, model, name):
        return name.startswith("x_")

    def find_view(self, model, vtype, primary_only=False):
        return SimpleNamespace(id=7, type="form")

    def _find_view_by_exact_name(self, name):
        return None

    def create_inherit_view(self, **kw):
        if self.fail_anchor:
            raise RuntimeError("Element '<xpath expr=\"//page[@name='lead']\">' cannot be located in parent view")
        self.created.append(kw["name"])

    def inject_field_into_views(self, model, fname, strategy="inherit"):
        self.injected.append(fname)
        return [1]


SPEC = {"models": [{"model": "crm.lead", "mode": "inherit", "fields": [
            {"name": "x_decision_date", "ttype": "date"}]}],
        "views": [{"model": "crm.lead", "mode": "extension", "type": "form", "name": "ext",
                   "arch": '<xpath expr="//page[@name=\'lead\']" position="inside"><group>'
                           '<field name="x_decision_date"/><field name="x_source"/></group></xpath>'}]}


def test_missing_anchor_falls_back_to_generic_inject():
    c = _Client(fail_anchor=True)
    r = UiApplyResult()
    _apply_component_inherit(c, SPEC, r)
    assert c.injected == ["x_decision_date", "x_source"]
    assert not r.skipped and any("standard inject" in w for w in r.warnings)


def test_anchor_present_uses_the_extension_view():
    c = _Client(fail_anchor=False)
    r = UiApplyResult()
    _apply_component_inherit(c, SPEC, r)
    assert c.created and c.injected == []


def test_install_apps_is_a_gated_odoo_write():
    assert is_write_capable("POST", "/api/ai/sessions/abc/install-apps")
    assert is_write_capable("POST", "/api/ai/sessions/abc/apply")
