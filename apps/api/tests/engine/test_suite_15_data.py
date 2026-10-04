"""T8-S15. Data-op safety on the in-process path.

Samples are already capped at 20, rows are already capped, and writes are
already batched by ``test_sample_is_at_most_20_cap_is_1000_and_batches_are_200``
in ``tests/test_data_ops.py``. ``data.delete`` is already refused before the
port by ``test_delete_without_two_approvers_and_allow_list_does_not_reach_the_port``.
``module.uninstall`` and ``data.delete`` are already R4, and uninstall is
already refused before the port, by ``test_module_uninstall_and_data_delete_are_r4``
and ``test_module_uninstall_is_r4_and_refuses_before_any_port_call``. This
module calls those functions. It does not copy a second implementation.

A ``data.delete`` does not reach the port. A sample over the cap is refused.

No live rows were deleted. This module does not probe Odoo.
"""

from __future__ import annotations

import importlib.util
import re
import socket
from pathlib import Path
from types import ModuleType

import pytest

from app.changeset.data_ops import DELETE_DENIED, SAMPLE_LIMIT, SAMPLE_OVER_LIMIT, delete_port_reason
from app.changeset.dispatch import DispatchError, dispatch_op

pytestmark = pytest.mark.no_app_db

_TESTS = Path(__file__).resolve().parents[1]
_DATA_OPS = _TESTS / "test_data_ops.py"
_SETTING_OPS = _TESTS / "test_setting_ops.py"
_ENGINE = _TESTS / "test_changeset_engine.py"

_SAMPLE_CAP_BATCH = "test_sample_is_at_most_20_cap_is_1000_and_batches_are_200"
_DELETE_BEFORE_PORT = "test_delete_without_two_approvers_and_allow_list_does_not_reach_the_port"
_UNINSTALL_BEFORE_PORT = "test_module_uninstall_is_r4_and_refuses_before_any_port_call"
_R4_CATALOG = "test_module_uninstall_and_data_delete_are_r4"


@pytest.fixture(autouse=True)
def _no_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def _refuse_socket(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("data suite opened a socket")

    monkeypatch.setattr(socket, "socket", _refuse_socket)


def _load_module(path: Path, module_name: str) -> ModuleType:
    """Load one existing test module from its file.

    Inputs: the file path and a unique module name.
    Outputs: the loaded module.
    Side effects: executes that module's imports. Does not call Odoo and
    does not delete a row.
    Raises FileNotFoundError when the file is missing, or ImportError when
    Python cannot load it.
    """
    if not path.is_file():
        raise FileNotFoundError(path)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _call(module: ModuleType, name: str) -> None:
    """Call one existing test function by name.

    Inputs: the loaded module and the function name.
    Outputs: none.
    Side effects: runs that function. Does not copy its body.
    Raises AssertionError when the name is missing or not callable.
    """
    function = getattr(module, name, None)
    assert callable(function), name
    function()


def test_existing_caps_batches_and_r4_refusals() -> None:
    """Call the tests that already cap samples, cap rows, batch writes, and refuse R4.

    Inputs: none.
    Outputs: none.
    Side effects: loads ``test_data_ops.py``, ``test_setting_ops.py``, and
    ``test_changeset_engine.py``, then calls the four named functions.
    Does not copy those checks, does not probe Odoo, and does not delete a live row.
    """
    data_ops = _load_module(_DATA_OPS, "ingenium_existing_data_ops")
    setting_ops = _load_module(_SETTING_OPS, "ingenium_existing_setting_ops")
    engine = _load_module(_ENGINE, "ingenium_existing_changeset_engine")
    _call(data_ops, _SAMPLE_CAP_BATCH)
    _call(data_ops, _DELETE_BEFORE_PORT)
    _call(setting_ops, _UNINSTALL_BEFORE_PORT)
    _call(engine, _R4_CATALOG)


def test_data_delete_does_not_reach_the_port_and_an_over_cap_sample_is_refused() -> None:
    """A delete stays off the port, and a sample past the cap is refused.

    Inputs: a bare ``data.delete`` and a ``data.update_batch`` whose sample
    is one row past ``SAMPLE_LIMIT``. The port is the in-memory recorder from
    ``tests/test_data_ops.py``.
    Outputs: none.
    Side effects: calls ``delete_port_reason`` and ``dispatch_op``. Does not
    copy the cap or the delete gate. Does not probe Odoo. No live rows were deleted.
    """
    data_ops = _load_module(_DATA_OPS, "ingenium_existing_data_ops_port")
    port = data_ops._Port()
    delete = {"type": "data.delete", "params": {"model": "res.partner"}}
    assert delete_port_reason(delete) == DELETE_DENIED
    with pytest.raises(DispatchError, match=re.escape(DELETE_DENIED)):
        dispatch_op(port, delete)
    assert port.calls == []

    over_sample = {
        "model": "res.partner",
        "domain": [["id", "=", 1]],
        "values": {"name": "Ada"},
        "sample": [{}] * (SAMPLE_LIMIT + 1),
    }
    update = {"type": "data.update_batch", "params": over_sample}
    with pytest.raises(DispatchError, match=re.escape(SAMPLE_OVER_LIMIT)):
        dispatch_op(port, update)
    assert port.calls == []
