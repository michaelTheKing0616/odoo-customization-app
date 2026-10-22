"""Pin community install dry_run as read-only (handover L177 / REG-DRYINSTALL)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.protected_modules import _normalize_odoo_version, load_vendored_community_modules
from app.routers.export_sandbox import install_community_module
from app.schemas import InstallCommunityModuleBody, InstallCommunityModuleOut

pytestmark = pytest.mark.no_app_db

_REFUSE = "{name!r} is not a known Community app — refuse non-CE install here"
_MISSING = "{name!r} isn't available on this database."


class _Caps:
    def __init__(self, major: int) -> None:
        self.major = major


class _Client:
    def __init__(self, major: int, rows: list[dict[str, str]] | None) -> None:
        self.capabilities = _Caps(major)
        self._rows = rows
        self.install_calls: list[str] = []
        self.reads: list[tuple[object, ...]] = []

    def execute_kw(
        self,
        model: str,
        method: str,
        args: list[object],
        kwargs: dict[str, object] | None = None,
    ) -> list[dict[str, str]]:
        self.reads.append((model, method, args, kwargs))
        return list(self._rows or [])

    def install_module_by_name(self, name: str) -> dict[str, str]:
        self.install_calls.append(name)
        return {"state": "installed"}


def _empty_vendored_list(_version: str) -> list[str]:
    return []


def _run(
    monkeypatch: pytest.MonkeyPatch,
    client: _Client,
    name: str,
    *,
    dry_run: bool | None = None,
) -> InstallCommunityModuleOut:
    monkeypatch.setattr(
        "app.routers.export_sandbox._client",
        lambda _connection_id, _db: client,
    )
    payload: dict[str, object] = {"module_name": name}
    if dry_run is not None:
        payload["dry_run"] = dry_run
    body = InstallCommunityModuleBody.model_validate(payload)
    return install_community_module("conn-reg-dryinstall", body, db=object())  # type: ignore[arg-type]


def _assert_read(client: _Client, name: str) -> None:
    assert client.reads == [
        (
            "ir.module.module",
            "search_read",
            [[["name", "=", name]]],
            {"fields": ["name", "state", "license"], "limit": 1},
        )
    ]


def _expect_http(
    monkeypatch: pytest.MonkeyPatch,
    client: _Client,
    name: str,
    *,
    dry_run: bool,
    status: int,
) -> None:
    with pytest.raises(HTTPException) as caught:
        _run(monkeypatch, client, name, dry_run=dry_run)
    assert caught.value.status_code == status
    expected = _REFUSE if status == 400 else _MISSING
    assert caught.value.detail == expected.format(name=name)
    _assert_read(client, name)
    assert client.install_calls == []


def _spy_loaded_versions(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    seen: list[str] = []
    real = load_vendored_community_modules

    def spy(version: str) -> list[str]:
        seen.append(version)
        return real(version)

    monkeypatch.setattr("app.protected_modules.load_vendored_community_modules", spy)
    return seen


@pytest.mark.parametrize("major", [17, 18, 19, 20])
def test_ac1_dry_run_reads_only_for_vendored_sale(
    major: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert "sale" in load_vendored_community_modules(f"{major}.0")
    seen = _spy_loaded_versions(monkeypatch)
    client = _Client(
        major,
        [{"name": "sale", "state": "uninstalled", "license": "LGPL-3"}],
    )
    out = _run(monkeypatch, client, "sale", dry_run=True)
    assert seen == [f"{major}.0"]
    assert out.ok is True
    assert out.module == "sale"
    assert out.module_state == "uninstalled"
    assert out.message == (
        "Would install sale (now uninstalled). Nothing was changed."
    )
    _assert_read(client, "sale")
    assert client.install_calls == []


def test_ac1_major_20_vendored_list_aliases_19_and_is_not_empty() -> None:
    assert _normalize_odoo_version("20.0") == "19.0"
    listed = load_vendored_community_modules("20.0")
    assert listed == load_vendored_community_modules("19.0")
    assert "sale" in listed


def test_ac1_empty_vendored_list_accepts_lgpl_and_reads_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    name = "custom_lgpl_app"
    assert name not in load_vendored_community_modules("19.0")
    monkeypatch.setattr(
        "app.protected_modules.load_vendored_community_modules",
        _empty_vendored_list,
    )
    client = _Client(
        19,
        [{"name": name, "state": "uninstalled", "license": "lgpl-3"}],
    )
    out = _run(monkeypatch, client, name, dry_run=True)
    assert out.ok is True
    assert out.module == name
    assert out.module_state == "uninstalled"
    assert out.message == (
        f"Would install {name} (now uninstalled). Nothing was changed."
    )
    _assert_read(client, name)
    assert client.install_calls == []


def test_ac1_empty_vendored_list_refuses_non_lgpl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    name = "custom_lgpl_app"
    monkeypatch.setattr(
        "app.protected_modules.load_vendored_community_modules",
        _empty_vendored_list,
    )
    client = _Client(
        19,
        [{"name": name, "state": "uninstalled", "license": "AGPL-3"}],
    )
    _expect_http(monkeypatch, client, name, dry_run=True, status=400)


def test_ac1_oeel_refused_even_when_vendored(monkeypatch: pytest.MonkeyPatch) -> None:
    assert "sale" in load_vendored_community_modules("19.0")
    client = _Client(
        19,
        [{"name": "sale", "state": "uninstalled", "license": "oeel-1"}],
    )
    _expect_http(monkeypatch, client, "sale", dry_run=True, status=400)


@pytest.mark.parametrize("name", ["l10n_generic_coa", "l10n_reg_dryinstall"])
def test_ac1_l10n_names_are_community_outside_the_vendored_list(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert name not in load_vendored_community_modules("19.0")
    client = _Client(19, [{"name": name, "state": "uninstalled", "license": "Other"}])
    out = _run(monkeypatch, client, name, dry_run=True)
    assert out.ok is True
    assert out.module == name
    assert out.module_state == "uninstalled"
    assert out.message == (
        f"Would install {name} (now uninstalled). Nothing was changed."
    )
    _assert_read(client, name)
    assert client.install_calls == []


@pytest.mark.parametrize("dry_run", [True, False])
def test_ac1_community_without_live_row_is_404(
    dry_run: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _Client(19, [])
    _expect_http(monkeypatch, client, "sale", dry_run=dry_run, status=404)


def test_ac1_unknown_name_refused_when_vendored_list_is_nonempty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    name = "not_a_community_app"
    assert name not in load_vendored_community_modules("19.0")
    client = _Client(
        19,
        [{"name": name, "state": "uninstalled", "license": "LGPL-3"}],
    )
    _expect_http(monkeypatch, client, name, dry_run=True, status=400)


def test_ac1_dry_run_defaults_false_and_installs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert InstallCommunityModuleBody(module_name="sale").dry_run is False
    client = _Client(
        19,
        [{"name": "sale", "state": "uninstalled", "license": "LGPL-3"}],
    )
    out = _run(monkeypatch, client, "sale")
    assert client.install_calls == ["sale"]
    _assert_read(client, "sale")
    assert out.ok is True
    assert out.module == "sale"
    assert out.module_state == "installed"
    assert out.message == "Module sale is installed"
