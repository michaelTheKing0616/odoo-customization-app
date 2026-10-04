"""T8-S10 validator fuzz.

Oversized params, depth past ``MAX_DEPTH``, and prototype-pollution keys are
already rejected by ``validate``. Those cases stay in
``tests/test_changeset_engine.py``. NaN and duplicate keys stay in
``tests/test_llm_gateway.py`` (``parse_tool_args``). This module runs those
functions. It does not reimplement the walker or the parser.

A payload deeper than ``MAX_DEPTH`` is rejected by ``validate`` and is not
applied. A Greek omicron (U+03BF) in a model name is folded with the protected
registry norm. A known-model lookalike passes grounding as that Latin model.
The snapshot fails if that fold disappears. A protected lookalike stays denied
and is not applied. An unknown name that does not fold to a known or protected
model stays rejected.

This module does not call Odoo.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from app.changeset.executor import _protocol, apply, get_journal, reset_journal
from app.changeset.protected_registry import _norm, detections, protected_case, protected_denial
from app.changeset.validate import MAX_DEPTH, validate
from app.worker_bot import WorkerBot

pytestmark = pytest.mark.no_app_db

_ENGINE_TESTS = Path(__file__).resolve().parents[1] / "test_changeset_engine.py"
_GATEWAY_TESTS = Path(__file__).resolve().parents[1] / "test_llm_gateway.py"
_ENGINE_FUNCTIONS = (
    "test_rt26_oversized_params_rejected",
    "test_rt27_deep_params_rejected_at_named_depth",
    "test_rt33_prototype_pollution_keys_rejected",
)
_GATEWAY_FUNCTION = "test_malformed_nan_and_duplicate_keys_are_rejected"

# Greek small letter omicron. ``validate`` folds it with the registry norm.
_OMICRON = "\u03bf"
_LATIN_MODEL = "x_order"
_LOOKALIKE_MODEL = "x_" + _OMICRON + "rder"
_PROTECTED_LATIN = "account.move"
_PROTECTED_LOOKALIKE = "acc" + _OMICRON + "unt.move"
_UNKNOWN_MODEL = "x_widget"
_UNKNOWN_LOOKALIKE = "x_w" + _OMICRON + "dget"

# Measured 2026-10-04 after the registry fold. Removing the fold fails this lock.
_OPEN_HOLES: dict[str, bool] = {
    "greek_omicron_model_folded": True,
}


def _load_module(path: Path, module_name: str) -> ModuleType:
    """Load one existing test module from its file.

    Inputs: the file path and a unique module name.
    Outputs: the loaded module.
    Side effects: executes that module's imports. Does not call Odoo.
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


def _mail_template() -> dict[str, Any]:
    """One staging-applicable mail template op.

    Inputs: none.
    Outputs: a ``mail_template.create`` op on ``res.partner``.
    Side effects: none.
    """
    return {
        "type": "mail_template.create",
        "params": {"name": "Worker test template", "model": "res.partner"},
    }


def _deeper_than_limit(op: dict[str, Any]) -> dict[str, Any]:
    """Return ``op`` with a params chain past ``MAX_DEPTH``.

    Inputs: one op whose ``params`` is a dict. The root params object is
    walk level 0, the same level ``validate`` uses.
    Outputs: a new op. The original is unchanged.
    Side effects: none. This builds input. ``validate`` decides rejection.
    """
    node: dict[str, Any] = {"leaf": True}
    for _ in range(MAX_DEPTH):
        node = {"child": node}
    params = dict(op["params"])
    params["child"] = node
    return {"type": op["type"], "params": params}


def _grounding_accepts(model: str) -> bool:
    """Whether ``validate`` accepts ``model`` as the known Latin name.

    Inputs: a model string. The known set is the Latin ``x_order``.
    Outputs: True when the grounding stage passes.
    Side effects: none. Does not call Odoo.
    """
    report = validate(
        [{"type": "field.create", "params": {"model": model, "name": "x_flag"}}],
        known_models={_LATIN_MODEL},
    )
    grounding = next(stage for stage in report["stages"] if stage["name"] == "grounding")
    return bool(grounding["passed"])


def _handle(bot: WorkerBot, changeset: list[dict[str, Any]]) -> dict[str, Any]:
    """Run one L3 staging handle.

    Inputs: the bot and the change-set.
    Outputs: the handle result.
    Side effects: may apply in memory when ``validate`` accepts an R0 or R1
    op. Does not call Odoo.
    """
    return bot.handle(
        changeset,
        environment="staging",
        requester_id="user-1",
        connection_id="conn-suite-10",
        known_models={"res.partner"},
        goal="validator fuzz",
    )


def test_existing_oversized_deep_polluted_and_nan_checks_exist() -> None:
    """The seed checks are on disk and callable.

    Inputs: none.
    Outputs: none.
    Side effects: loads the two existing test modules. Does not run the
    checks and does not call Odoo.
    """
    engine = _load_module(_ENGINE_TESTS, "ingenium_existing_changeset_engine")
    gateway = _load_module(_GATEWAY_TESTS, "ingenium_existing_llm_gateway")
    for name in _ENGINE_FUNCTIONS:
        assert callable(getattr(engine, name, None)), name
    assert callable(getattr(gateway, _GATEWAY_FUNCTION, None))


def test_existing_checks_call_validate_and_the_args_parser() -> None:
    """Run the existing checks. Their bodies stay in those files.

    Inputs: none.
    Outputs: none.
    Side effects: runs the four seed functions. The three engine functions
    call ``validate``. The gateway function calls ``parse_tool_args``.
    Does not call Odoo.
    """
    engine = _load_module(_ENGINE_TESTS, "ingenium_existing_changeset_engine_run")
    gateway = _load_module(_GATEWAY_TESTS, "ingenium_existing_llm_gateway_run")
    for name in _ENGINE_FUNCTIONS:
        getattr(engine, name)()
    getattr(gateway, _GATEWAY_FUNCTION)()


def test_payload_deeper_than_max_depth_is_rejected_and_not_applied() -> None:
    """A params chain past ``MAX_DEPTH`` is rejected and is not applied.

    The same mail template without that chain applies on L3 staging. The
    deep chain fails ``validate``, and the bot does not journal it.

    Inputs: one flat ``mail_template.create`` and one copy nested past
    ``MAX_DEPTH``.
    Outputs: none.
    Side effects: clears the in-memory journal. Does not call Odoo.
    """
    clean = _mail_template()
    deep = _deeper_than_limit(clean)
    known = {"res.partner"}
    accepted = validate([clean], known_models=known)
    rejected = validate([deep], known_models=known)
    assert accepted["valid"] is True
    assert rejected["valid"] is False
    shape = next(stage for stage in rejected["stages"] if stage["name"] == "shape")
    assert shape["passed"] is False
    assert any(f"exceeds depth {MAX_DEPTH}" in error for error in shape["errors"])

    bot = WorkerBot("L3")
    reset_journal()
    try:
        applied = _handle(bot, [clean])
        assert applied["applied"] is True
        assert get_journal()
        reset_journal()
        refused = _handle(bot, [deep])
        assert refused["applied"] is False
        assert refused["ok"] is False
        assert refused["report"]["valid"] is False
        assert get_journal() == []
    finally:
        reset_journal()


def test_greek_omicron_model_fold_matches_the_measurement() -> None:
    """A known-model lookalike passes grounding as the Latin model.

    Measured 2026-10-04: ``validate`` accepts Latin ``x_order`` and accepts
    the same name with U+03BF in place of ``o``. The known set contains only
    the Latin name. Changing the snapshot without a matching measurement
    fails this test. Removing the fold fails it too.

    Inputs: the Latin model and the omicron lookalike.
    Outputs: none.
    Side effects: none. Does not call Odoo.
    """
    assert _LOOKALIKE_MODEL != _LATIN_MODEL
    assert _OMICRON in _LOOKALIKE_MODEL
    assert _norm(_LOOKALIKE_MODEL) == _LATIN_MODEL
    assert _grounding_accepts(_LATIN_MODEL) is True
    observed = {"greek_omicron_model_folded": _grounding_accepts(_LOOKALIKE_MODEL)}
    assert observed == _OPEN_HOLES, (
        "greek omicron model fold changed; update _OPEN_HOLES to the new measurement"
    )


def test_protected_omicron_lookalike_is_denied_and_not_applied() -> None:
    """``account.move`` spelled with U+03BF stays denied and is not applied.

    Inputs: one ``model.scaffold`` whose model is the protected lookalike.
    ``known_models`` includes the Latin protected name.
    Outputs: none.
    Side effects: clears the in-memory journal. ``protected_case``,
    ``protected_denial``, ``apply``, and ``validate`` run the real denial.
    Does not call Odoo.
    """
    lookalike = {"type": "model.scaffold", "params": {"model": _PROTECTED_LOOKALIKE}}
    assert _OMICRON in _PROTECTED_LOOKALIKE
    assert _PROTECTED_LOOKALIKE != _PROTECTED_LATIN
    assert _norm(_PROTECTED_LOOKALIKE) == _PROTECTED_LATIN
    assert protected_case(lookalike) == "RT-10"
    assert protected_denial(lookalike) == "protected_deny"

    error = _protocol().BridgeError
    reset_journal()
    try:
        with pytest.raises(error) as denied:
            apply([lookalike], mode="T", port=None)
        assert denied.value.code == "protected_deny"
        assert get_journal() == []
        assert detections()[-1]["alert"] == "policy_denied"
        assert detections()[-1]["case"] == "RT-10"
    finally:
        reset_journal()

    report = validate([lookalike], known_models={_PROTECTED_LATIN})
    assert report["valid"] is False
    static = next(stage for stage in report["stages"] if stage["name"] == "static")
    assert static["passed"] is False
    assert any("protected_deny" in item for item in static["errors"])


def test_unknown_model_that_does_not_fold_stays_rejected() -> None:
    """An unknown model that does not fold to a known or protected name is rejected.

    Inputs: Latin ``x_widget`` and the same name with U+03BF. The known set is
    Latin ``x_order``. Neither name is a protected model.
    Outputs: none.
    Side effects: none. Does not call Odoo.
    """
    assert _norm(_UNKNOWN_MODEL) == _UNKNOWN_MODEL
    assert _norm(_UNKNOWN_LOOKALIKE) == "x_wodget"
    assert _norm(_UNKNOWN_LOOKALIKE) not in {_LATIN_MODEL, _PROTECTED_LATIN}
    for model in (_UNKNOWN_MODEL, _UNKNOWN_LOOKALIKE):
        op = {"type": "field.create", "params": {"model": model, "name": "x_flag"}}
        assert protected_case(op) is None
        report = validate([op], known_models={_LATIN_MODEL})
        assert report["valid"] is False
        static = next(stage for stage in report["stages"] if stage["name"] == "static")
        grounding = next(stage for stage in report["stages"] if stage["name"] == "grounding")
        assert static["passed"] is True
        assert grounding["passed"] is False
        assert any("not in known_models" in item for item in grounding["errors"])
