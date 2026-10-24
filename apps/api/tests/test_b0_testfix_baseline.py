"""Pin the P0-2-CL2 xfail on the version-branch baseline count.

Reads marks and `_VERSION_BRANCH_BASELINE` in tests/test_import_boundary.py only.
Does not walk the product tree. Does not xfail.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.no_app_db

_BOUNDARY_TEST = Path(__file__).resolve().parent / "test_import_boundary.py"
_COUNT = "test_real_app_tree_odoo_version_branch_count_matches_measured_baseline"
_PLANTED = "test_planted_odoo_version_branch_outside_compat_is_rejected"
_REASON = "P0-2-CL2: the app tree has 38 version branches and the constant stays 22"
_BASELINE = 22


def _load_boundary_tests() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "b0_testfix_baseline_boundary_target",
        _BOUNDARY_TEST,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {_BOUNDARY_TEST}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _xfail_marks(obj: object) -> list[object]:
    raw = getattr(obj, "pytestmark", [])
    if not isinstance(raw, list):
        raw = [raw]
    return [mark for mark in raw if getattr(mark, "name", None) == "xfail"]


_BOUNDARY = _load_boundary_tests()


def test_p0_2_cl2_xfail_is_pinned_on_version_branch_count_only() -> None:
    """Fails if the count xfail is dropped, loosened, or copied onto the planted probe.

    Product line: the xfail decorator on
    ``test_real_app_tree_odoo_version_branch_count_matches_measured_baseline``
    in ``tests/test_import_boundary.py``. ``_VERSION_BRANCH_BASELINE`` stays 22.
    """
    count_marks = _xfail_marks(getattr(_BOUNDARY, _COUNT))
    assert len(count_marks) == 1
    mark = count_marks[0]
    assert getattr(mark, "args", None) == ()
    assert getattr(mark, "kwargs", None) == {"strict": True, "reason": _REASON}
    assert _BOUNDARY._VERSION_BRANCH_BASELINE == _BASELINE
    assert _xfail_marks(getattr(_BOUNDARY, _PLANTED)) == []
    assert _xfail_marks(_BOUNDARY) == []
