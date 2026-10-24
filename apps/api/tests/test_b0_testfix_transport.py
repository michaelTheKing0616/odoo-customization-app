"""Pin the P0-2-CL1 xfail on the suite XML-RPC scan.

Reads marks on tests/test_no_direct_xmlrpc.py only. Does not walk the product tree.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.no_app_db

_SCAN_TEST = Path(__file__).resolve().parent / "test_no_direct_xmlrpc.py"
_SUITE = "test_no_direct_xmlrpc_outside_legacy_adapter_and_sandbox"
_PLANTED = "test_direct_xmlrpc_scan_detects_planted_server_proxy_in_app_tree"
_REASON = "P0-2-CL1: code_runner/testing.py, bridge/export.py, routers/view_engine.py"


def _load_scan_tests() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "b0_testfix_transport_scan_target",
        _SCAN_TEST,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {_SCAN_TEST}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _xfail_marks(obj: object) -> list[object]:
    raw = getattr(obj, "pytestmark", [])
    if not isinstance(raw, list):
        raw = [raw]
    return [mark for mark in raw if getattr(mark, "name", None) == "xfail"]


_SCAN = _load_scan_tests()


def test_p0_2_cl1_xfail_is_pinned_on_suite_scan_only() -> None:
    """Fails if the suite-scan xfail is dropped, loosened, or copied onto the planted probe.

    Product line: the xfail decorator on
    ``test_no_direct_xmlrpc_outside_legacy_adapter_and_sandbox`` in
    ``tests/test_no_direct_xmlrpc.py``.
    """
    suite_marks = _xfail_marks(getattr(_SCAN, _SUITE))
    assert len(suite_marks) == 1
    mark = suite_marks[0]
    assert getattr(mark, "args", None) == ()
    assert getattr(mark, "kwargs", None) == {"strict": True, "reason": _REASON}
    assert _xfail_marks(getattr(_SCAN, _PLANTED)) == []
    assert _xfail_marks(_SCAN) == []
