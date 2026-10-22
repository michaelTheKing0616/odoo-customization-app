"""Pin isolated sandbox stacks, assert_isolated, and the docker block (L192 / REG-SANDBOX)."""

from __future__ import annotations

import dataclasses
import os
import subprocess
import sys
from pathlib import Path

import pytest

import app.sandbox as sb

pytestmark = pytest.mark.no_app_db

_MAJORS = (17, 18, 19, 20)


@pytest.mark.parametrize("major", _MAJORS)
def test_isolated_sandbox_stack_passes_guard(major):
    stack = sb.sandbox_stack_for_major(major)
    assert stack.project == f"ingenium_sandbox_v{major}"
    assert stack.odoo_container.startswith("ingenium_sandbox_")
    assert stack.db_container.startswith("ingenium_sandbox_")
    assert stack.port and stack.port not in sb.DEV_PORTS
    assert stack.compose.name == "docker-compose.ingenium-sandbox.yml"
    assert sb.assert_isolated(stack) is None


def test_each_major_has_its_own_port():
    ports = [sb.sandbox_stack_for_major(major).port for major in _MAJORS]
    assert len(set(ports)) == len(_MAJORS)


@pytest.mark.parametrize(
    "bad",
    [
        {"project": "odoo20-custom-dev"},
        {"odoo_container": "odoo20"},
        {"port": 8073},
        {"compose": sb.REPO_ROOT / "docker" / "docker-compose.odoo20.yml"},
        {"addons": sb.SANDBOX_ADDONS},
    ],
)
def test_assert_isolated_refuses_dev_targets(bad):
    stack = dataclasses.replace(sb.sandbox_stack_for_major(20), **bad)
    with pytest.raises(sb.SandboxGuardError):
        sb.assert_isolated(stack)


def test_real_docker_is_blocked_when_live_infra_unset():
    assert os.environ.get("INGENIUM_LIVE_INFRA") != "1"
    with pytest.raises(RuntimeError, match="real docker is blocked"):
        subprocess.run(["docker", "ps"])


@pytest.mark.skipif(
    os.environ.get("INGENIUM_LIVE_INFRA") != "1",
    reason="run under INGENIUM_LIVE_INFRA=1",
)
def test_docker_not_blocked_when_live_infra():
    try:
        subprocess.run(["docker", "ps"], capture_output=True, timeout=10)
    except subprocess.TimeoutExpired:
        return
    except FileNotFoundError:
        return
    except RuntimeError as exc:
        raise AssertionError("docker block fixture raised") from exc


def test_docker_block_fixture_does_not_raise_when_live_infra():
    env = os.environ.copy()
    env["INGENIUM_LIVE_INFRA"] = "1"
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_reg_sandbox.py::test_docker_not_blocked_when_live_infra",
            "-p",
            "no:cacheprovider",
            "--tb=short",
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    output = proc.stdout + "\n" + proc.stderr
    assert proc.returncode == 0, output
    assert "1 passed" in proc.stdout
    assert "skipped" not in proc.stdout
