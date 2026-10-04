"""T8-S09. Point at the existing protected-registry tests. Do not copy them.

RT-10 through RT-16 stay in ``tests/test_protected_registry.py``. This module
checks those functions exist, then runs one fail-closed apply: a protected
model in a scaffold or a field op is denied and is not journaled.

GATE-P3-05 is not fully passed. A two-hop ``$ref`` and a Greek omicron
lookalike are denied here. Reopening either one fails
``test_nested_ref_and_greek_omicron_are_denied_and_not_applied``.
This module does not call Odoo.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from app.changeset.executor import _protocol, apply, get_journal, reset_journal
from app.changeset.protected_registry import detections, protected_case, protected_denial

pytestmark = pytest.mark.no_app_db

_REGISTRY_TESTS = Path(__file__).resolve().parents[1] / "test_protected_registry.py"
_RT_FUNCTIONS = (
    "test_rt10_scaffold_expansion_into_a_protected_model",
    "test_rt11_ref_to_a_protected_model",
    "test_rt12_widened_domain_and_extra_models",
    "test_rt13_setting_side_effects",
    "test_rt14_stored_compute_and_private_field",
    "test_rt15_server_action_tricks",
    "test_rt16_journal_sequence_alias_and_confusable",
)

# Greek small letter omicron. casefold leaves it as Greek; the fold map sends it to "o".
_GREEK_OMICRON = "\u03bf"


def _load_protected_registry_tests() -> ModuleType:
    """Load the existing RT-10–RT-16 module from its file.

    Inputs: none. The path is ``tests/test_protected_registry.py``.
    Outputs: the loaded module.
    Side effects: executes that module's imports. Does not call Odoo.
    Raises FileNotFoundError when the file is missing, or ImportError when
    Python cannot load it.
    """
    if not _REGISTRY_TESTS.is_file():
        raise FileNotFoundError(_REGISTRY_TESTS)
    spec = importlib.util.spec_from_file_location(
        "ingenium_existing_protected_registry",
        _REGISTRY_TESTS,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {_REGISTRY_TESTS}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_existing_rt10_through_rt16_functions_exist() -> None:
    """The named RT-10 through RT-16 tests are on disk and callable.

    Inputs: none.
    Outputs: none.
    Side effects: loads ``test_protected_registry.py``. Does not run those tests
    and does not call Odoo.
    """
    module = _load_protected_registry_tests()
    assert callable(module._assert_policy_denied)
    for name in _RT_FUNCTIONS:
        assert callable(getattr(module, name, None)), name


def test_protected_model_in_a_scaffold_or_field_op_is_denied_and_not_applied() -> None:
    """A protected model in a scaffold or a stored-compute field op is not applied.

    Inputs: one ``model.scaffold`` and one ``field.create`` whose model is
    ``account.move``. The denial helper comes from the existing registry tests.
    Outputs: none.
    Side effects: clears the in-memory journal. Does not call Odoo.
    """
    module = _load_protected_registry_tests()
    scaffold = {"type": "model.scaffold", "params": {"model": "account.move"}}
    field_op = {
        "type": "field.create",
        "params": {"model": "account.move", "name": "x_total", "compute": "1", "store": True},
    }
    error = _protocol().BridgeError
    try:
        for op, case in ((scaffold, "RT-10"), (field_op, "RT-14")):
            module._assert_policy_denied(op, case)
            reset_journal()
            with pytest.raises(error) as denied:
                apply([op], mode="T", port=None)
            assert denied.value.code == "protected_deny"
            assert get_journal() == []
            assert detections()[-1]["alert"] == "policy_denied"
            assert detections()[-1]["case"] == case
    finally:
        reset_journal()


def test_nested_ref_and_greek_omicron_are_denied_and_not_applied() -> None:
    """A two-hop ``$ref`` and a Greek omicron scaffold are denied and not applied.

    This is not a claim that GATE-P3-05 passed. A regression that leaves the
    outer field op unclassified, or that applies the omicron scaffold, fails.

    The outer ``relation`` ``$ref`` points at another ``$ref``, which points at
    ``account.move``. That outer field op is RT-11. A cycle, or a later hop
    that does not resolve, is denied the same way. The middle hop, checked on
    its own, stays RT-11. A two-hop chain that ends on ``sale.order`` stays open.

    Greek small letter omicron (U+03BF) in ``account.move`` folds to Latin o.
    A scaffold of that name is RT-10.

    Inputs: the two-hop document, a cycle, an unresolved later hop, a benign
    two-hop chain, and the omicron scaffold.
    Outputs: none.
    Side effects: clears the in-memory journal. Does not call Odoo.
    """
    two_hop = [
        {"type": "field.update", "params": {"model": "account.move", "name": "ref"}},
        {"type": "field.update", "params": {"alias": {"$ref": "#/0/params/model"}}},
        {
            "type": "field.create",
            "params": {
                "model": "x_ticket",
                "name": "x_move",
                "relation": {"$ref": "#/1/params/alias"},
            },
        },
    ]
    outer = two_hop[2]
    assert protected_case(outer, document=two_hop) == "RT-11"
    assert protected_denial(outer, document=two_hop) == "protected_deny"
    assert protected_case(two_hop[1], document=two_hop) == "RT-11"

    cycle = [
        {"type": "field.update", "params": {"alias": {"$ref": "#/1/params/alias"}}},
        {"type": "field.update", "params": {"alias": {"$ref": "#/0/params/alias"}}},
        {
            "type": "field.create",
            "params": {
                "model": "x_ticket",
                "name": "x_move",
                "relation": {"$ref": "#/1/params/alias"},
            },
        },
    ]
    assert protected_case(cycle[2], document=cycle) == "RT-11"
    assert protected_denial(cycle[2], document=cycle) == "protected_deny"

    dangling = [
        {"type": "field.update", "params": {"name": "ref"}},
        {"type": "field.update", "params": {"alias": {"$ref": "#/9/params/model"}}},
        {
            "type": "field.create",
            "params": {
                "model": "x_ticket",
                "name": "x_move",
                "relation": {"$ref": "#/1/params/alias"},
            },
        },
    ]
    assert protected_case(dangling[2], document=dangling) == "RT-11"
    assert protected_denial(dangling[2], document=dangling) == "protected_deny"

    benign = [
        {"type": "field.update", "params": {"model": "sale.order", "name": "client_order_ref"}},
        {"type": "field.update", "params": {"alias": {"$ref": "#/0/params/model"}}},
        {
            "type": "field.create",
            "params": {
                "model": "x_ticket",
                "name": "x_move",
                "relation": {"$ref": "#/1/params/alias"},
            },
        },
    ]
    assert protected_case(benign[2], document=benign) is None

    error = _protocol().BridgeError
    reset_journal()
    try:
        for document in (two_hop, cycle, dangling):
            reset_journal()
            with pytest.raises(error) as denied:
                apply(document, mode="T", port=None)
            assert denied.value.code == "protected_deny"
            assert get_journal() == []

        lookalike = {
            "type": "model.scaffold",
            "params": {"model": f"acc{_GREEK_OMICRON}unt.move"},
        }
        assert _GREEK_OMICRON in str(lookalike["params"]["model"])
        assert protected_case(lookalike) == "RT-10"
        assert protected_denial(lookalike) == "protected_deny"
        reset_journal()
        with pytest.raises(error) as denied_lookalike:
            apply([lookalike], mode="T", port=None)
        assert denied_lookalike.value.code == "protected_deny"
        assert get_journal() == []
        assert detections()[-1]["alert"] == "policy_denied"
        assert detections()[-1]["case"] == "RT-10"
    finally:
        reset_journal()
