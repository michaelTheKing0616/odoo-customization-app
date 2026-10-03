"""Registry coverage for Odoo 20 GA major."""

from __future__ import annotations

import pytest

from odoo_client.compat.capabilities import UnsupportedOdooMajorError
from odoo_client.compat.registry import for_major, ga_majors, parse_major


def test_ga_majors_includes_17_through_20_not_16() -> None:
    ga = ga_majors()
    assert 17 in ga
    assert 18 in ga
    assert 19 in ga
    assert 20 in ga
    assert 16 not in ga


def test_for_major_15_raises() -> None:
    with pytest.raises(UnsupportedOdooMajorError):
        for_major(15)


def test_for_major_20_is_ga() -> None:
    caps = for_major(20)
    assert caps.major == 20
    assert caps.ga is True


def test_for_major_16_not_ga() -> None:
    assert for_major(16).ga is False


def test_parse_major_20_variants() -> None:
    assert parse_major("20.0") == 20
    assert parse_major("20.0+e") == 20
