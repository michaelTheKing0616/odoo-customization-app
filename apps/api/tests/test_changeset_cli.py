"""T8-CLI. Five commands on a two-op file. Fake port only. No LLM import."""

from __future__ import annotations

import ast
import json
import socket
import subprocess
from pathlib import Path

import pytest

from app.changeset.cli import COMMANDS, FakePort, load_changeset, main, run_command

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


_FIXTURE = _API / "tests" / "fixtures" / "changeset_cli_two_ops.json"
_LLM_MODULE_ROOTS = ("app.llm_gateway", "google", "anthropic", "openai", "litellm")


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(_PYTHON), "-m", "app.changeset.cli", *args],
        cwd=_API,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.mark.parametrize("command", COMMANDS)
def test_fixture_subcommand_exits_zero_with_result(command: str) -> None:
    completed = _run_cli(command, str(_FIXTURE))
    assert completed.returncode == 0, completed.stderr
    assert "Traceback" not in completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["command"] == command
    assert payload["op_count"] == 2
    assert payload["port"] == "fake"
    assert payload["live_odoo"] is False

    if command == "plan":
        assert len(payload["result"]["changes"]) == 2
        assert payload["result"]["plan_hash"]
    elif command == "validate":
        assert payload["result"]["valid"] is True
    elif command == "simulate":
        assert payload["result"]["passed"] is True
        assert payload["result"]["contacted_odoo"] is False
    elif command == "apply":
        assert payload["status"] == "VERIFIED"
        assert [row["model"] for row in payload["created"]] == ["ir.model.fields", "ir.ui.view"]
    else:
        assert payload["status"] == "ROLLED_BACK"
        assert payload["snapshot_match"] is True
        assert payload["port_rows_after"] == 0


def test_apply_then_rollback_returns_fake_port_to_start() -> None:
    loaded = load_changeset(_FIXTURE)
    port = FakePort()
    start = (list(port.created), list(port.writes))

    applied = run_command("apply", loaded, port)
    assert applied["ok"] is True
    assert [model for model, _values in port.created] == ["ir.model.fields", "ir.ui.view"]

    rolled = run_command("rollback", loaded, port)
    assert rolled["ok"] is True
    assert rolled["status"] == "ROLLED_BACK"
    assert (port.created, port.writes) == start


@pytest.mark.parametrize("body", [None, "{not json", '"just a string"', '{"ops": []}'])
def test_bad_file_exits_nonzero_with_one_line_error(tmp_path: Path, body: str | None) -> None:
    path = tmp_path / "bad.json"
    if body is not None:
        path.write_text(body, encoding="utf-8")
    completed = _run_cli("apply", str(path))
    assert completed.returncode == 1
    assert "Traceback" not in completed.stderr
    lines = completed.stderr.strip().splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("error: ")
    assert json.loads(completed.stdout)["ok"] is False


def test_cli_run_loads_no_llm_module() -> None:
    script = (
        "import json, sys\n"
        "from app.changeset.cli import COMMANDS, main\n"
        f"codes = [main([c, {str(_FIXTURE)!r}]) for c in COMMANDS]\n"
        "sys.stdout.flush()\n"
        "print('\\nMODULES=' + json.dumps({'codes': codes, 'modules': sorted(sys.modules)}))\n"
    )
    completed = subprocess.run(
        [str(_PYTHON), "-c", script],
        cwd=_API,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    marker = completed.stdout.rsplit("MODULES=", 1)[1]
    report = json.loads(marker)
    assert report["codes"] == [0, 0, 0, 0, 0]
    assert "app.changeset.executor" in report["modules"]
    leaked = [
        name
        for name in report["modules"]
        if any(name == root or name.startswith(root + ".") for root in _LLM_MODULE_ROOTS)
    ]
    assert leaked == []
