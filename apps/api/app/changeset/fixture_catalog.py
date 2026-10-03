"""Offline fixture catalog for engine tests.

Seeds, majors, and postures are definitions. Nothing here opens Odoo, starts
Docker, or writes a customer database. ``reset_local_standin`` clears an
in-memory mapping or a temp directory the caller provides. That stand-in is
not a live Odoo reset. Live fixtures on 17, 18, 19, and 20 are not brought
up by this module, so GATE-P0-03 is not fully passed.
"""

from __future__ import annotations

import re
import tempfile
import time
from collections.abc import MutableMapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final
from urllib.parse import urlparse

SEED_NAMES: Final[tuple[str, ...]] = (
    "demo",
    "minimal",
    "messy_client",
    "accounting_locked",
    "inventory_live",
    "hr_sensitive",
    "huge",
    "portal_public",
)
GA_MAJORS: Final[tuple[int, ...]] = (17, 18, 19, 20)
EXPERIMENTAL_MAJORS: Final[tuple[int, ...]] = (16,)
POSTURES: Final[tuple[str, ...]] = ("Bridge", "P2", "Online-simulated")

# Online-simulated is a posture label. It is not a connection to Odoo Online.
ONLINE_SIMULATED_CONNECTS_TO_ODOO_ONLINE: Final[bool] = False
LIVE_FIXTURES_UP: Final[bool] = False
LOCAL_STANDIN_RESET_BUDGET_SECONDS: Final[float] = 60.0

_MESSY_CLIENT_FIELD_COUNT: Final[int] = 150
_DB_PREFIX: Final[str] = "ingenium_fx_"
_MARKER_NAME: Final[str] = "standin_reset.txt"
_CUSTOMER_DB_NAMES: Final[frozenset[str]] = frozenset({"aonb"})
_BARE_HOSTS: Final[frozenset[str]] = frozenset({"localhost"})
_CUSTOMER_TOKEN: Final[re.Pattern[str]] = re.compile(r"(?:^|[^a-z0-9])aonb(?:[^a-z0-9]|$)")


class FixtureRefused(ValueError):
    """The target is outside the local fixture catalog."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True, slots=True)
class SeedDefinition:
    """One named seed. Custom field names are catalog definitions, not database rows."""

    name: str
    nightly_only: bool
    custom_field_names: tuple[str, ...]
    custom_fields_are_database_rows: bool = False


@dataclass(frozen=True, slots=True)
class FixtureCatalog:
    """Majors, seeds, and postures a test can load without a live Odoo."""

    seeds: tuple[SeedDefinition, ...]
    ga_majors: tuple[int, ...]
    experimental_majors: tuple[int, ...]
    postures: tuple[str, ...]
    online_simulated_is_odoo_online_connection: bool
    live_fixtures_up: bool


@dataclass(frozen=True, slots=True)
class StandInResetResult:
    """Timing for a stand-in reset. ``live_odoo`` is false: this is not Odoo."""

    database_name: str
    elapsed_seconds: float
    live_odoo: bool
    standin_kind: str


def _messy_client_field_names() -> tuple[str, ...]:
    return tuple(f"x_messy_{index:03d}" for index in range(1, _MESSY_CLIENT_FIELD_COUNT + 1))


def _build_seeds() -> tuple[SeedDefinition, ...]:
    messy_fields = _messy_client_field_names()
    seeds: list[SeedDefinition] = []
    for name in SEED_NAMES:
        if name == "messy_client":
            fields = messy_fields
        else:
            fields = ()
        seeds.append(
            SeedDefinition(
                name=name,
                nightly_only=name == "huge",
                custom_field_names=fields,
                custom_fields_are_database_rows=False,
            )
        )
    return tuple(seeds)


_SEEDS: Final[tuple[SeedDefinition, ...]] = _build_seeds()


def _catalog_database_names() -> frozenset[str]:
    names: set[str] = set()
    for major in (*GA_MAJORS, *EXPERIMENTAL_MAJORS):
        for seed in SEED_NAMES:
            names.add(f"{_DB_PREFIX}{major}_{seed}")
    return frozenset(names)


_CATALOG_DATABASE_NAMES: Final[frozenset[str]] = _catalog_database_names()


def load_fixture_catalog() -> FixtureCatalog:
    """Return the offline fixture catalog.

    Inputs: none.
    Outputs: seed definitions, GA majors 17–20, experimental 16, and postures.
    Side effects: none. Does not connect to Odoo or start Docker.
    """
    return FixtureCatalog(
        seeds=_SEEDS,
        ga_majors=GA_MAJORS,
        experimental_majors=EXPERIMENTAL_MAJORS,
        postures=POSTURES,
        online_simulated_is_odoo_online_connection=ONLINE_SIMULATED_CONNECTS_TO_ODOO_ONLINE,
        live_fixtures_up=LIVE_FIXTURES_UP,
    )


def require_major(major: int) -> str:
    """Classify a major for the fixture catalog.

    Inputs: major version integer.
    Outputs: ``ga`` for 17–20, ``experimental`` for 16.
    Side effects: none. Raises FixtureRefused for majors at or below 15.
    """
    if isinstance(major, bool) or not isinstance(major, int):
        raise FixtureRefused("major must be an integer")
    if major <= 15:
        raise FixtureRefused(f"major {major} is refused; majors at or below 15 are refused")
    if major in GA_MAJORS:
        return "ga"
    if major in EXPERIMENTAL_MAJORS:
        return "experimental"
    raise FixtureRefused(f"major {major} is not in the fixture catalog")


def local_database_name(*, major: int, seed: str) -> str:
    """Build a local catalog database name.

    Inputs: major and seed name.
    Outputs: ``ingenium_fx_{major}_{seed}``.
    Side effects: none. Raises FixtureRefused when the pair is not in the catalog.
    """
    require_major(major)
    if seed not in SEED_NAMES:
        raise FixtureRefused(f"seed {seed!r} is not in the fixture catalog")
    name = f"{_DB_PREFIX}{major}_{seed}"
    if name not in _CATALOG_DATABASE_NAMES:
        raise FixtureRefused("database name is not in the fixture catalog")
    return name


def _is_url(value: str) -> bool:
    lowered = value.lower()
    if "://" in lowered:
        return True
    return lowered.startswith(("http:", "https:", "postgres:", "postgresql:", "ftp:"))


def _looks_like_hostname(value: str) -> bool:
    if any(ch in value for ch in ".@:"):
        return True
    return value.lower() in _BARE_HOSTS


def _extract_host(value: str) -> str:
    raw = value.strip()
    if "://" in raw:
        parsed = urlparse(raw)
        return (parsed.hostname or "").lower().rstrip(".")
    if _looks_like_hostname(raw):
        host_part = raw.split("/", 1)[0]
        parsed = urlparse(f"//{host_part}")
        return (parsed.hostname or "").lower().rstrip(".")
    return ""


def _is_customer_host(host: str) -> bool:
    if not host:
        return False
    if host in _CUSTOMER_DB_NAMES or host.startswith("aonb."):
        return True
    if host == "odoo.com" or host.endswith(".odoo.com"):
        return True
    return host == "odoo.sh" or host.endswith(".odoo.sh")


def _is_customer_reference(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in _CUSTOMER_DB_NAMES:
        return True
    if _CUSTOMER_TOKEN.search(lowered):
        return True
    return _is_customer_host(_extract_host(lowered))


def _parse_catalog_database_name(name: str) -> tuple[int, str] | None:
    if not name.startswith(_DB_PREFIX):
        return None
    rest = name[len(_DB_PREFIX) :]
    major_text, separator, seed = rest.partition("_")
    if separator != "_" or not major_text.isdigit() or seed not in SEED_NAMES:
        return None
    return int(major_text), seed


def _refusal_reason(target: str) -> str | None:
    if not isinstance(target, str):
        return "database name is not in the fixture catalog"
    name = target.strip()
    if not name or any(ch.isspace() for ch in name):
        return "database name is not in the fixture catalog"
    lowered = name.lower()
    customer = _is_customer_reference(lowered)
    if _is_url(name) or "/" in name or "\\" in name:
        if customer:
            return "customer url is refused"
        return "url is refused"
    if _looks_like_hostname(name):
        if customer:
            return "customer hostname is refused"
        return "hostname is refused"
    if customer:
        return "customer database name is refused"
    parsed = _parse_catalog_database_name(name)
    if parsed is not None:
        major, _seed = parsed
        if major <= 15:
            return f"major {major} is refused; majors at or below 15 are refused"
        if name not in _CATALOG_DATABASE_NAMES:
            return "database name is not in the fixture catalog"
        return None
    if lowered.isdigit() and int(lowered) <= 15:
        return f"major {int(lowered)} is refused; majors at or below 15 are refused"
    return "database name is not in the fixture catalog"


def _marker_text(database_name: str) -> str:
    return (
        f"database_name={database_name}\n"
        "live_odoo=false\n"
        "standin_reset=true\n"
        "note=not a live Odoo reset\n"
    )


def _reset_memory(standin: MutableMapping[str, Any], database_name: str) -> None:
    standin.clear()
    standin["database_name"] = database_name
    standin["live_odoo"] = False
    standin["kind"] = "stand-in"


def _reset_temp_directory(path: Path, database_name: str) -> None:
    if path.is_symlink():
        raise FixtureRefused("temp stand-in symlink is refused")
    resolved = path.resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    if resolved == temp_root or temp_root not in resolved.parents:
        raise FixtureRefused("temp stand-in must live under the local temp directory")
    if resolved.exists() and not resolved.is_dir():
        raise FixtureRefused("temp stand-in must be a directory")
    resolved.mkdir(parents=True, exist_ok=True)
    children = list(resolved.iterdir())
    if any(child.is_dir() and not child.is_symlink() for child in children):
        raise FixtureRefused("temp stand-in contains a subdirectory")
    for child in children:
        if child.is_symlink() or child.is_file():
            child.unlink()
    (resolved / _MARKER_NAME).write_text(_marker_text(database_name), encoding="utf-8")


def _apply_standin_reset(
    standin: MutableMapping[str, Any] | Path,
    database_name: str,
) -> str:
    if isinstance(standin, MutableMapping):
        _reset_memory(standin, database_name)
        return "memory"
    if isinstance(standin, Path):
        _reset_temp_directory(standin, database_name)
        return "temp"
    raise FixtureRefused("stand-in must be an in-memory mapping or a temp path")


def reset_local_standin(
    database_name: str,
    standin: MutableMapping[str, Any] | Path,
) -> StandInResetResult:
    """Reset one catalog database name on a caller-provided stand-in.

    Inputs: a local catalog database name, and either a mutable mapping or a
    temp directory under the local temp root.
    Outputs: elapsed seconds and ``live_odoo=False``.
    Side effects: clears the mapping, or replaces top-level files in the temp
    directory with a stand-in marker. Does not open a network connection,
    start Docker, or reset a live Odoo database. Refuses a hostname, a URL,
    a customer database name, and any major at or below 15.
    """
    reason = _refusal_reason(database_name)
    if reason is not None:
        raise FixtureRefused(reason)
    started = time.perf_counter()
    kind = _apply_standin_reset(standin, database_name)
    elapsed = time.perf_counter() - started
    return StandInResetResult(
        database_name=database_name.strip(),
        elapsed_seconds=elapsed,
        live_odoo=False,
        standin_kind=kind,
    )
