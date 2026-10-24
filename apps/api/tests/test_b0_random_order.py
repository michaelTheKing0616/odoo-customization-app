"""B0-RANDOM-ORDER: the plugin is installed, and shuffle is opt-in."""

from __future__ import annotations

import importlib.metadata
import os
import shlex
from pathlib import Path

import pytest

pytestmark = pytest.mark.no_app_db

# apps/api/pyproject.toml dev group. Deleting this declaration drops the plugin.
_DEPENDENCY_LINE = '"pytest-randomly>=5.0.0"'
_PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _requests_randomly(argv: list[str]) -> bool:
    """True when this argv enables the plugin. `-p no:randomly` does not count."""
    for index, arg in enumerate(argv):
        if arg == "-p" and index + 1 < len(argv) and argv[index + 1] == "randomly":
            return True
        if arg in {"-prandomly", "-p=randomly"}:
            return True
    return False


def test_random_order_plugin_is_loaded(pytestconfig: pytest.Config) -> None:
    """Installed always. Active only with `-p randomly` or PYTEST_ADDOPTS='-p randomly'."""
    declaration = _PYPROJECT.read_text(encoding="utf-8")
    assert _DEPENDENCY_LINE in declaration

    matched = [
        entry
        for entry in importlib.metadata.entry_points(group="pytest11", name="randomly")
        if entry.value == "pytest_randomly"
        and entry.dist is not None
        and entry.dist.metadata["Name"] == "pytest-randomly"
    ]
    assert matched, "pytest-randomly entry point is absent"

    opted_in = _requests_randomly(list(pytestconfig.invocation_params.args)) or _requests_randomly(
        shlex.split(os.environ.get("PYTEST_ADDOPTS", ""))
    )
    plugin = pytestconfig.pluginmanager.get_plugin("randomly")
    if opted_in:
        assert plugin is not None
        assert pytestconfig.getoption("randomly_reorganize") is True
    else:
        assert plugin is None
