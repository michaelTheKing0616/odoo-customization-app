"""Offline fixture catalog. No live Odoo, no customer database."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.changeset.fixture_catalog import (
    FixtureRefused,
    load_fixture_catalog,
    local_database_name,
    require_major,
    reset_local_standin,
)

pytestmark = pytest.mark.no_app_db

_EIGHT_SEEDS = (
    "demo",
    "minimal",
    "messy_client",
    "accounting_locked",
    "inventory_live",
    "hr_sensitive",
    "huge",
    "portal_public",
)


def test_catalog_lists_the_eight_seed_names() -> None:
    catalog = load_fixture_catalog()
    assert tuple(seed.name for seed in catalog.seeds) == _EIGHT_SEEDS
    assert catalog.ga_majors == (17, 18, 19, 20)
    assert catalog.experimental_majors == (16,)
    assert catalog.postures == ("Bridge", "P2", "Online-simulated")
    assert catalog.online_simulated_is_odoo_online_connection is False
    assert catalog.live_fixtures_up is False
    assert require_major(16) == "experimental"
    assert require_major(19) == "ga"


def test_messy_client_declares_at_least_150_custom_field_names() -> None:
    catalog = load_fixture_catalog()
    messy = next(seed for seed in catalog.seeds if seed.name == "messy_client")
    assert len(messy.custom_field_names) >= 150
    assert len(set(messy.custom_field_names)) == len(messy.custom_field_names)
    assert messy.custom_fields_are_database_rows is False
    assert all(
        name.startswith("x_") and not name.startswith("x_studio_")
        for name in messy.custom_field_names
    )


def test_huge_is_nightly_only() -> None:
    catalog = load_fixture_catalog()
    huge = next(seed for seed in catalog.seeds if seed.name == "huge")
    assert huge.nightly_only is True
    others = [seed for seed in catalog.seeds if seed.name != "huge"]
    assert len(others) == 7
    assert all(seed.nightly_only is False for seed in others)


def test_major_15_is_refused() -> None:
    with pytest.raises(FixtureRefused, match="15"):
        require_major(15)
    standin: dict[str, object] = {"untouched": True}
    with pytest.raises(FixtureRefused, match="15"):
        reset_local_standin("ingenium_fx_15_demo", standin)
    assert standin == {"untouched": True}
    with pytest.raises(FixtureRefused, match="15"):
        local_database_name(major=15, seed="demo")


def test_customer_url_is_refused() -> None:
    standin: dict[str, object] = {"untouched": True}
    with pytest.raises(FixtureRefused, match="customer url"):
        reset_local_standin("https://aonb.odoo.com", standin)
    assert standin == {"untouched": True}
    with pytest.raises(FixtureRefused, match="customer database"):
        reset_local_standin("aonb", {})
    with pytest.raises(FixtureRefused, match="hostname"):
        reset_local_standin("aonb.odoo.com", {})


def test_standin_reset_finishes_under_60_seconds(tmp_path: Path) -> None:
    database_name = local_database_name(major=19, seed="minimal")
    memory: dict[str, object] = {"rows": [1, 2, 3]}
    started = time.perf_counter()
    memory_result = reset_local_standin(database_name, memory)
    elapsed = time.perf_counter() - started
    assert elapsed < 60
    assert memory_result.elapsed_seconds < 60
    assert memory_result.live_odoo is False
    assert memory_result.standin_kind == "memory"
    assert memory["database_name"] == database_name
    assert memory["live_odoo"] is False
    assert "rows" not in memory

    started_temp = time.perf_counter()
    temp_result = reset_local_standin(database_name, tmp_path)
    temp_elapsed = time.perf_counter() - started_temp
    assert temp_elapsed < 60
    assert temp_result.elapsed_seconds < 60
    assert temp_result.live_odoo is False
    assert temp_result.standin_kind == "temp"
    marker = (tmp_path / "standin_reset.txt").read_text(encoding="utf-8")
    assert "live_odoo=false" in marker
    assert "not a live Odoo reset" in marker
