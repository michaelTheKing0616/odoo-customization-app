"""Validate-live dry-run checks (TIER-2)."""

from __future__ import annotations

from types import SimpleNamespace

from app.spec_validate_live import validate_module_spec_live


class _FakeView:
    def __init__(self, arch: str) -> None:
        self.id = 1
        self.arch = arch


class _FakeClient:
    def __init__(self) -> None:
        self.models = {"x_demo"}

    def model_exists(self, model: str) -> bool:
        return model in self.models

    def find_view(self, model: str, vtype: str, primary_only: bool = False):
        _ = primary_only
        if model == "x_demo" and vtype == "form":
            return _FakeView(
                '<form><sheet><field name="name"/></sheet></form>'
            )
        return None


def test_validate_live_passes_planned_model() -> None:
    spec = {
        "models": [{"model": "x_demo", "fields": [{"name": "x_status", "ttype": "char"}]}],
        "views": [],
    }
    result = validate_module_spec_live(_FakeClient(), spec)
    assert result.ok is True
    assert result.fail_count == 0


def test_validate_live_fails_missing_xpath_anchor() -> None:
    spec = {
        "models": [{"model": "x_demo", "fields": []}],
        "views": [
            {
                "model": "x_demo",
                "type": "form",
                "arch": '<xpath expr="//field[@name=\'missing\']" position="after"><field name="x_extra"/></xpath>',
            }
        ],
    }
    result = validate_module_spec_live(_FakeClient(), spec)
    assert result.ok is False
    assert any(i.status == "fail" and "xpath" in i.category for i in result.items)


def test_validate_live_passes_resolving_xpath() -> None:
    spec = {
        "models": [{"model": "x_demo", "fields": []}],
        "views": [
            {
                "model": "x_demo",
                "type": "form",
                "arch": '<xpath expr="//field[@name=\'name\']" position="after"><field name="x_extra"/></xpath>',
            }
        ],
    }
    result = validate_module_spec_live(_FakeClient(), spec)
    assert result.ok is True
    assert any(i.status == "pass" and i.category == "xpath" for i in result.items)
