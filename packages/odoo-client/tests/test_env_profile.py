"""EnvProfile from an in-memory payload. No socket is opened."""

from __future__ import annotations

import socket

import pytest

from odoo_client.env_profile import (
    HEALTH_VALUES,
    EnvProfile,
    EnvProfileError,
    MajorRefusedError,
)


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "version": "19.0",
        "edition": "community",
        "deployment": "self_hosted",
        "api": "json2",
        "bridge_posture": "P2",
        "installed_apps": ["sale", "account"],
        "studio": False,
        "multi_company": False,
        "languages": ["en_US"],
        "capabilities": {"inherit_views": "yes", "server_action_code": "unknown"},
        "staging": False,
    }
    payload.update(overrides)
    return payload


def test_from_payload_maps_every_profile_field() -> None:
    profile = EnvProfile.from_payload(
        _payload(
            version="19.0+e",
            edition="enterprise",
            deployment="odoo_sh",
            api="json-2",
            bridge_posture="P1",
            installed_apps=["sale", "web_studio"],
            studio=True,
            multi_company=True,
            languages=["en_US", "fr_FR"],
            staging=True,
        )
    )
    assert profile.version == "19.0+e"
    assert profile.major == 19
    assert profile.edition == "enterprise"
    assert profile.deployment == "odoo_sh"
    assert profile.api == "json2"
    assert profile.bridge_posture == "P1"
    assert profile.installed_apps == ("sale", "web_studio")
    assert profile.studio is True
    assert profile.multi_company is True
    assert profile.languages == ("en_US", "fr_FR")
    assert profile.staging is True
    assert profile.health == "ok"
    assert profile.health in HEALTH_VALUES
    assert profile.mode == "operate"
    assert len(profile.fingerprint) == 64


def test_from_payload_keeps_unknown_capability_as_no() -> None:
    profile = EnvProfile.from_payload(_payload())
    assert profile.allows("inherit_views") is True
    assert profile.allows("server_action_code") is False
    assert profile.allows("missing") is False
    for value in ("Yes", "YES", "true", " yes", "no", "unknown"):
        built = EnvProfile.from_payload(_payload(capabilities={"inherit_views": value}))
        assert built.allows("inherit_views") is False


def test_api_unavailable_is_guided_mode_only() -> None:
    profile = EnvProfile.from_payload(_payload(api="unavailable"))
    assert profile.health == "api_unavailable"
    assert profile.guided_only is True
    assert profile.mode == "guided"
    assert profile.read_only_qa is False
    assert profile.allows_apply() is False

    flagged = EnvProfile.from_payload(_payload(api="json2", api_available=False))
    assert flagged.health == "api_unavailable"
    assert flagged.guided_only is True
    assert flagged.api == "unavailable"


def test_auth_failed_blocks_without_guided_mode() -> None:
    profile = EnvProfile.from_payload(_payload(auth_failed=True))
    assert profile.health == "auth_failed"
    assert profile.mode == "blocked"
    assert profile.guided_only is False
    assert profile.allows_apply() is False


def test_degraded_health_stays_on_a_supported_major() -> None:
    profile = EnvProfile.from_payload(_payload(health="degraded"))
    assert profile.health == "degraded"
    assert profile.mode == "operate"
    assert profile.guided_only is False
    assert profile.read_only_qa is False


def test_unsupported_major_is_read_only_qa() -> None:
    profile = EnvProfile.from_payload(_payload(major=21, version="21.0"))
    assert profile.major == 21
    assert profile.health == "version_unsupported"
    assert profile.read_only_qa is True
    assert profile.mode == "read_only_qa"
    assert profile.guided_only is False
    assert profile.allows_apply() is False
    assert profile.allows("inherit_views") is True


def test_api_unavailable_wins_over_an_unsupported_major() -> None:
    profile = EnvProfile.from_payload(_payload(major=21, version="21.0", api="unavailable"))
    assert profile.health == "api_unavailable"
    assert profile.guided_only is True
    assert profile.read_only_qa is False


def test_majors_at_or_below_15_are_refused() -> None:
    for major in (0, 14, 15):
        with pytest.raises(MajorRefusedError):
            EnvProfile(major=major)
        with pytest.raises(MajorRefusedError):
            EnvProfile.from_payload(_payload(major=major, version=f"{major}.0"))
    with pytest.raises(MajorRefusedError):
        EnvProfile.from_payload({"version": "15.0", "api": "xmlrpc"})
    with pytest.raises(MajorRefusedError):
        EnvProfile.from_payload(_payload(major=15, api="unavailable"))


def test_experimental_major_16_is_not_refused() -> None:
    profile = EnvProfile.from_payload(_payload(major=16, version="16.0", api="xmlrpc"))
    assert profile.major == 16
    assert profile.health == "ok"
    assert profile.mode == "operate"
    assert profile.read_only_qa is False


def test_bridge_posture_defaults_to_transport_only() -> None:
    profile = EnvProfile.from_payload(_payload(bridge_posture="nope"))
    assert profile.bridge_posture == "P2"
    installed = EnvProfile.from_payload(
        _payload(bridge_posture=None, installed_apps=["sale", "ingenium_bridge"])
    )
    assert installed.bridge_posture == "P1"


def test_saas_version_parses_without_a_socket() -> None:
    profile = EnvProfile.from_payload({"server_version": "saas~19.4+e", "api": "jsonrpc"})
    assert profile.major == 19
    assert profile.version == "saas~19.4+e"
    assert profile.edition == "enterprise"
    assert profile.deployment == "online"
    assert profile.health == "ok"


def test_url_sets_deployment_without_a_socket() -> None:
    profile = EnvProfile.from_payload(_payload(deployment=None, url="https://acme.odoo.com/odoo"))
    assert profile.deployment == "online"
    assert profile.major == 19


def test_fingerprint_is_stable_and_changes_when_apps_change() -> None:
    left = EnvProfile.from_payload(_payload(capabilities={"b": "no", "a": "yes"}))
    right = EnvProfile.from_payload(_payload(capabilities={"a": "yes", "b": "no"}))
    changed = EnvProfile.from_payload(_payload(installed_apps=["sale", "crm"]))
    assert left.fingerprint == right.fingerprint
    assert left == right
    assert left.fingerprint != changed.fingerprint


def test_from_payload_does_not_open_a_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("socket opened")

    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    profile = EnvProfile.from_payload(
        _payload(url="https://acme.odoo.com", deployment="online")
    )
    assert profile.major == 19
    assert profile.health == "ok"


def test_missing_version_is_rejected() -> None:
    with pytest.raises(EnvProfileError):
        EnvProfile.from_payload({"api": "json2"})
