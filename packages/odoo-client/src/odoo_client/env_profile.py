"""Environment profile. An unknown capability is treated as unavailable.

``from_payload`` reads an in-memory mapping only. It does not open a socket.
Majors at or below 15 are refused. Any other unsupported major is read-only
Q&A. An unavailable external API is Guided Mode only.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from odoo_client.compat.registry import parse_major
from odoo_client.models import detect_hosting_kind

SUPPORTED_MAJORS = frozenset({16, 17, 18, 19, 20})
HEALTH_VALUES = frozenset(
    {"ok", "degraded", "auth_failed", "api_unavailable", "version_unsupported"}
)
BRIDGE_POSTURES = frozenset({"P1", "P2"})

_API_ALIASES = {
    "": "unknown",
    "unknown": "unknown",
    "json2": "json2",
    "json-2": "json2",
    "json_2": "json2",
    "external": "json2",
    "jsonrpc": "jsonrpc",
    "json-rpc": "jsonrpc",
    "json_rpc": "jsonrpc",
    "xmlrpc": "xmlrpc",
    "xml-rpc": "xmlrpc",
    "xml_rpc": "xmlrpc",
    "bridge": "bridge",
    "unavailable": "unavailable",
    "api_unavailable": "unavailable",
    "none": "unavailable",
}

_DEPLOYMENT_ALIASES = {
    "": "unknown",
    "unknown": "unknown",
    "online": "online",
    "odoo_online": "online",
    "saas": "online",
    "odoo_sh": "odoo_sh",
    "sh": "odoo_sh",
    "self_hosted": "self_hosted",
    "on_prem": "self_hosted",
    "on-prem": "self_hosted",
    "on_premise": "self_hosted",
    "on-premise": "self_hosted",
}

_BRIDGE_MODULES = frozenset({"ingenium_bridge"})


class MajorRefusedError(Exception):
    """Raised when the Odoo major is 15 or below."""


class EnvProfileError(Exception):
    """Raised when a payload cannot be turned into a profile."""


@dataclass(frozen=True, slots=True)
class EnvProfile:
    major: int
    capabilities: dict[str, str] = field(default_factory=dict)
    version: str = ""
    edition: str = "unknown"
    deployment: str = "unknown"
    api: str = "unknown"
    bridge_posture: str = "P2"
    installed_apps: tuple[str, ...] = ()
    studio: bool = False
    multi_company: bool = False
    languages: tuple[str, ...] = ()
    staging: bool = False
    health: str = ""
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.major, bool) or not isinstance(self.major, int):
            raise EnvProfileError("major must be an int")
        if self.major <= 15:
            raise MajorRefusedError(
                f"Odoo major {self.major} is refused. Majors at or below 15 are not supported."
            )

        capabilities = {
            str(key): value if isinstance(value, str) else str(value)
            for key, value in self.capabilities.items()
        }
        installed_apps = _name_tuple(self.installed_apps)
        languages = _name_tuple(self.languages)
        edition = _normalize_edition(self.edition)
        deployment = _normalize_deployment(self.deployment)
        api = _normalize_api(self.api)
        bridge_posture = self.bridge_posture if self.bridge_posture in BRIDGE_POSTURES else "P2"
        if api == "bridge":
            bridge_posture = "P1"
        health = _resolve_health(self.major, api, self.health)
        if health == "api_unavailable":
            api = "unavailable"
        fingerprint = _fingerprint(
            version=self.version,
            major=self.major,
            edition=edition,
            deployment=deployment,
            api=api,
            bridge_posture=bridge_posture,
            installed_apps=installed_apps,
            studio=bool(self.studio),
            multi_company=bool(self.multi_company),
            languages=languages,
            capabilities=capabilities,
            staging=bool(self.staging),
            health=health,
        )
        object.__setattr__(self, "capabilities", capabilities)
        object.__setattr__(self, "installed_apps", installed_apps)
        object.__setattr__(self, "languages", languages)
        object.__setattr__(self, "edition", edition)
        object.__setattr__(self, "deployment", deployment)
        object.__setattr__(self, "api", api)
        object.__setattr__(self, "bridge_posture", bridge_posture)
        object.__setattr__(self, "studio", bool(self.studio))
        object.__setattr__(self, "multi_company", bool(self.multi_company))
        object.__setattr__(self, "staging", bool(self.staging))
        object.__setattr__(self, "health", health)
        object.__setattr__(self, "fingerprint", fingerprint)

    def allows(self, name: str) -> bool:
        return self.capabilities.get(name) == "yes"

    @property
    def mode(self) -> str:
        if self.health == "api_unavailable":
            return "guided"
        if self.health == "version_unsupported":
            return "read_only_qa"
        if self.health == "auth_failed":
            return "blocked"
        return "operate"

    @property
    def guided_only(self) -> bool:
        return self.health == "api_unavailable"

    @property
    def read_only_qa(self) -> bool:
        return self.health == "version_unsupported"

    def allows_apply(self) -> bool:
        return self.health in {"ok", "degraded"}

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> EnvProfile:
        """Build a profile from an in-memory payload. Does not open a socket."""
        if isinstance(payload, (str, bytes)) or not isinstance(payload, Mapping):
            raise EnvProfileError("payload must be a mapping")

        version = _version_text(payload)
        major = _major_from_payload(payload, version)
        installed_apps = _name_tuple(payload.get("installed_apps", payload.get("modules")))
        languages = _name_tuple(payload.get("languages", payload.get("langs")))
        api = _api_from_payload(payload)
        capabilities = _capabilities_from_payload(payload.get("capabilities"))
        return cls(
            major=major,
            capabilities=capabilities,
            version=version or str(major),
            edition=_edition_from_payload(payload, version, installed_apps),
            deployment=_deployment_from_payload(payload, version),
            api=api,
            bridge_posture=_bridge_from_payload(payload, installed_apps, api),
            installed_apps=installed_apps,
            studio=_studio_from_payload(payload, installed_apps),
            multi_company=_multi_company_from_payload(payload),
            languages=languages,
            staging=_flag(payload.get("staging")),
            health=_health_signal(payload),
        )


def _resolve_health(major: int, api: str, health: str) -> str:
    """Apply posture rules. API loss and auth failure outrank version posture."""
    requested = health.strip().lower()
    if api == "unavailable" or requested == "api_unavailable":
        return "api_unavailable"
    if requested == "auth_failed":
        return "auth_failed"
    if major not in SUPPORTED_MAJORS:
        return "version_unsupported"
    if requested == "degraded":
        return "degraded"
    if requested in {"", "ok", "version_unsupported"}:
        return "ok"
    return "degraded"


def _major_from_payload(payload: Mapping[str, Any], version: str) -> int:
    if "major" in payload and payload["major"] not in (None, ""):
        return _coerce_major(payload["major"])
    if version:
        return parse_major(version)
    raise EnvProfileError("A version or major is required to build an environment profile.")


def _coerce_major(value: Any) -> int:
    if isinstance(value, bool) or value is None:
        raise EnvProfileError("major must be an int")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not value.is_integer():
            raise EnvProfileError("major must be a whole number")
        return int(value)
    if isinstance(value, str) and value.strip():
        return parse_major(value)
    raise EnvProfileError("major must be an int")


def _version_text(payload: Mapping[str, Any]) -> str:
    for key in ("server_version", "version"):
        raw = payload.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return ""


def _api_from_payload(payload: Mapping[str, Any]) -> str:
    if payload.get("api_available") is False or payload.get("external_api") is False:
        return "unavailable"
    raw = payload.get("api")
    if raw is None:
        return "unknown"
    if not isinstance(raw, str):
        return "unavailable"
    return _normalize_api(raw)


def _health_signal(payload: Mapping[str, Any]) -> str:
    health = ""
    raw = payload.get("health")
    if isinstance(raw, str):
        health = raw.strip().lower()
    if payload.get("auth_failed") is True or payload.get("auth") in {"failed", "auth_failed"}:
        health = "auth_failed"
    if payload.get("degraded") is True and health in {"", "ok"}:
        health = "degraded"
    return health


def _edition_from_payload(payload: Mapping[str, Any], version: str, apps: tuple[str, ...]) -> str:
    raw = payload.get("edition")
    if isinstance(raw, str) and raw.strip():
        return _normalize_edition(raw)
    lowered = version.lower()
    if "+e" in lowered:
        return "enterprise"
    if "web_studio" in apps:
        return "enterprise"
    if version:
        return "community"
    return "unknown"


def _deployment_from_payload(payload: Mapping[str, Any], version: str) -> str:
    for key in ("deployment", "hosting"):
        raw = payload.get(key)
        if isinstance(raw, str) and raw.strip():
            return _normalize_deployment(raw)
    url = payload.get("url")
    if isinstance(url, str) and url.strip():
        kind = detect_hosting_kind(url)
        if kind in {"online", "odoo_sh", "self_hosted"}:
            return kind
    if version.lower().startswith("saas"):
        return "online"
    return "unknown"


def _bridge_from_payload(payload: Mapping[str, Any], apps: tuple[str, ...], api: str) -> str:
    raw = payload.get("bridge_posture", payload.get("bridge"))
    if isinstance(raw, str) and raw.strip().upper() in BRIDGE_POSTURES:
        return raw.strip().upper()
    if api == "bridge" or payload.get("bridge_installed") is True or bool(_BRIDGE_MODULES & set(apps)):
        return "P1"
    return "P2"


def _studio_from_payload(payload: Mapping[str, Any], apps: tuple[str, ...]) -> bool:
    flag = payload.get("studio", payload.get("studio_installed"))
    return _flag(flag) or "web_studio" in apps


def _multi_company_from_payload(payload: Mapping[str, Any]) -> bool:
    if payload.get("multi_company") is True:
        return True
    companies = payload.get("companies")
    if isinstance(companies, (list, tuple, set, frozenset)) and len(companies) > 1:
        return True
    company_count = payload.get("company_count")
    if isinstance(company_count, int) and not isinstance(company_count, bool) and company_count > 1:
        return True
    return _flag(payload.get("multi_company"))


def _capabilities_from_payload(raw: Any) -> dict[str, str]:
    if raw is None:
        return {}
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Mapping):
        raise EnvProfileError("capabilities must be a mapping")
    copied: dict[str, str] = {}
    for key, value in raw.items():
        if isinstance(value, str):
            copied[str(key)] = value
        elif value is None:
            copied[str(key)] = "unknown"
        else:
            copied[str(key)] = str(value)
    return copied


def _flag(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str) and value.strip().lower() in {"1", "true", "yes"}:
        return True
    return False


def _normalize_edition(value: str) -> str:
    text = value.strip().lower()
    if text in {"community", "enterprise", "unknown"}:
        return text
    return "unknown"


def _normalize_deployment(value: str) -> str:
    return _DEPLOYMENT_ALIASES.get(value.strip().lower(), "unknown")


def _normalize_api(value: str) -> str:
    key = value.strip().lower()
    if key in _API_ALIASES:
        return _API_ALIASES[key]
    return "unavailable"


def _label(item: Mapping[str, Any]) -> str:
    for key in ("name", "code", "technical_name"):
        raw = item.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return ""


def _name_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        text = value.strip()
        return (text,) if text else ()
    if isinstance(value, Mapping):
        label = _label(value)
        return (label,) if label else ()
    if not isinstance(value, (list, tuple, set, frozenset)):
        return ()
    names: list[str] = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
            if text:
                names.append(text)
            continue
        if isinstance(item, Mapping):
            state = item.get("state")
            if isinstance(state, str) and state not in {"installed", ""}:
                continue
            label = _label(item)
            if label:
                names.append(label)
    ordered = tuple(dict.fromkeys(names))
    if isinstance(value, (set, frozenset)):
        return tuple(sorted(ordered))
    return ordered


def _fingerprint(
    *,
    version: str,
    major: int,
    edition: str,
    deployment: str,
    api: str,
    bridge_posture: str,
    installed_apps: tuple[str, ...],
    studio: bool,
    multi_company: bool,
    languages: tuple[str, ...],
    capabilities: dict[str, str],
    staging: bool,
    health: str,
) -> str:
    body = {
        "version": version,
        "major": major,
        "edition": edition,
        "deployment": deployment,
        "api": api,
        "bridge_posture": bridge_posture,
        "installed_apps": list(installed_apps),
        "studio": studio,
        "multi_company": multi_company,
        "languages": list(languages),
        "capabilities": {key: capabilities[key] for key in sorted(capabilities)},
        "staging": staging,
        "health": health,
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
