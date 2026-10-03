"""T8-CLI. Five commands on a two-op file. Fake port only. No LLM import."""

from __future__ import annotations

import ast
import json
import socket
import subprocess
from pathlib import Path

import pytest

from app.changeset.cli import COMMANDS, main

pytestmark = pytest.mark.no_app_db

_REPO = Path(__file__).resolve().parents[3]
_API = _REPO / "apps" / "api"
_PYTHON = _REPO / ".venv" / "bin" / "python"
_CLI = _API / "app" / "changeset" / "cli.py"
_FORBIDDEN = ("llm_gateway", "llm_provider", "openai", "anthropic")

_TWO_OPS = {
    "goal": "Add two fields on sales orders",
    "assumptions": ["sale.order is already installed."],
    "environment": "staging",
    "known_models": ["sale.order"],
    "requester_id": "operator",
    "connection_id": "fake",
    "approvals": [{"approver_id": "operator", "decision": "approve"}],
    "ops": [
        {
            "type": "field.create",
            "params": {"model": "sale.order", "name": "x_note", "ttype": "char"},
        },
        {
            "type": "field.create",
            "params": {"model": "sale.order", "name": "x_ref", "ttype": "char"},
        },
    ],
}


def _imported_modules(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_cli_module_does_not_import_an_llm_package() -> None:
    tree = ast.parse(_CLI.read_text(encoding="utf-8"), filename=str(_CLI))
    imported = _imported_modules(tree)
    hits = [name for name in imported if any(part in _FORBIDDEN for part in name.split("."))]
    assert hits == []
    assert imported


@pytest.fixture
def _no_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def _refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("changeset CLI opened a socket")

    monkeypatch.setattr(socket, "socket", _refuse)


def _write_file(tmp_path: Path) -> Path:
    path = tmp_path / "two_ops.json"
    path.write_text(json.dumps(_TWO_OPS), encoding="utf-8")
    return path


@pytest.mark.usefixtures("_no_socket")
def test_main_runs_two_op_changeset_on_fake_port(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write_file(tmp_path)
    payloads: dict[str, dict] = {}
    for command in COMMANDS:
        assert main([command, str(path)]) == 0
        payloads[command] = json.loads(capsys.readouterr().out)

    for command, payload in payloads.items():
        assert payload["ok"] is True
        assert payload["command"] == command
        assert payload["op_count"] == 2
        assert payload["port"] == "fake"
        assert payload["socket_opened"] is False
        assert payload["live_odoo"] is False

    plan = payloads["plan"]["result"]
    assert len(plan["changes"]) == 2
    assert plan["plan_hash"]
    assert payloads["plan"]["port_calls"] == 0

    report = payloads["validate"]["result"]
    assert report["valid"] is True
    assert len(report["stages"]) == 9
    assert payloads["validate"]["port_calls"] == 0

    simulated = payloads["simulate"]["result"]
    assert simulated["passed"] is True
    assert simulated["socket_opened"] is False
    assert simulated["live"] is False
    assert simulated["contacted_odoo"] is False
    assert payloads["simulate"]["port_calls"] == 0

    applied = payloads["apply"]
    assert applied["status"] == "VERIFIED"
    assert applied["port_calls"] == 2
    names = [row["values"]["name"] for row in applied["created"]]
    assert names == ["x_note", "x_ref"]
    assert {row["model"] for row in applied["created"]} == {"ir.model.fields"}

    rolled = payloads["rollback"]
    assert rolled["status"] == "ROLLED_BACK"
    assert rolled["snapshot_match"] is True
    assert rolled["port_calls"] == 2
    assert rolled["port_rows_after"] == 0
    assert rolled["replayed_on_fake_port"] is True


def test_module_entrypoint_runs_two_op_changeset(tmp_path: Path) -> None:
    path = _write_file(tmp_path)
    apply_payload: dict | None = None
    for command in COMMANDS:
        completed = subprocess.run(
            [str(_PYTHON), "-m", "app.changeset.cli", command, str(path)],
            cwd=_API,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert completed.returncode == 0, completed.stderr
        payload = json.loads(completed.stdout)
        assert payload["ok"] is True
        assert payload["command"] == command
        assert payload["op_count"] == 2
        assert payload["port"] == "fake"
        assert payload["live_odoo"] is False
        assert payload["socket_opened"] is False
        if command == "apply":
            apply_payload = payload
    assert apply_payload is not None
    assert apply_payload["status"] == "VERIFIED"
    assert apply_payload["port_calls"] == 2
