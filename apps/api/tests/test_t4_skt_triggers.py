"""T4-SKT: a trigger firing is not pre-approved."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.changeset import executor
from app.db_models import AuditChainEntry
from app.triggers import runner
from app.triggers.runner import (
    ApprovalRequired,
    EnterpriseTriggerRefused,
    ProtectedModelBlocked,
    apply_firing,
    approval_id_for,
    approve,
    community_trigger,
    fire,
    plan_card,
    reset_trigger_gate,
)


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite://")
    AuditChainEntry.__table__.create(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _clear_firings() -> None:
    reset_trigger_gate()
    yield
    reset_trigger_gate()


def _sale_trigger(*, record_id: int | None = 42):
    return community_trigger(
        name="Note on create",
        target_model="sale.order",
        trigger="on_create",
        changeset=[
            {
                "type": "field.create",
                "params": {"model": "sale.order", "name": "x_fire_note"},
            }
        ],
        record_id=record_id,
    )


def _fire(db: Session, trigger, *, person: str = "user-1"):
    return fire(
        trigger,
        person=person,
        connection_id="conn-t4-skt",
        environment="staging",
        requester_id=person,
        known_models={"sale.order"},
        db=db,
        trigger_exists=trigger.record_id is not None,
    )


def _notes(db: Session) -> list[AuditChainEntry]:
    return (
        db.query(AuditChainEntry)
        .filter(AuditChainEntry.kind == "note")
        .order_by(AuditChainEntry.ts.asc(), AuditChainEntry.id.asc())
        .all()
    )


def test_existing_trigger_is_not_preapproved(db: Session) -> None:
    trigger = _sale_trigger(record_id=42)
    assert trigger.host_model == "base.automation"
    opened = _fire(db, trigger)
    card = plan_card(opened.plan_hash)
    assert opened.approval_id is None
    assert opened.status == "pending"
    assert card["status"] == "pending"
    assert card["approvals"] == []
    assert len(card["sections"]) == 9
    assert approval_id_for(opened.plan_hash) is None


def test_each_firing_opens_its_own_plan_card(db: Session) -> None:
    trigger = _sale_trigger()
    first = _fire(db, trigger)
    second = _fire(db, trigger)
    assert first.plan_hash != second.plan_hash
    assert plan_card(first.plan_hash)["status"] == "pending"
    assert plan_card(second.plan_hash)["status"] == "pending"
    first_approval = approve(first.plan_hash, person="user-1")
    assert plan_card(first.plan_hash)["status"] == "approved"
    assert plan_card(second.plan_hash)["status"] == "pending"
    assert approval_id_for(second.plan_hash) is None
    second_approval = approve(second.plan_hash, person="user-1")
    assert first_approval != second_approval
    assert approval_id_for(first.plan_hash) == first_approval
    assert approval_id_for(second.plan_hash) == second_approval


@pytest.mark.parametrize("model", ["account.move", "hr.payslip"])
def test_protected_models_are_blocked(db: Session, model: str) -> None:
    trigger = community_trigger(
        name="Protected write",
        target_model=model,
        trigger="on_write",
        changeset=[
            {"type": "field.create", "params": {"model": model, "name": "x_blocked"}}
        ],
    )
    with pytest.raises(ProtectedModelBlocked):
        fire(
            trigger,
            person="user-1",
            connection_id="conn-t4-skt",
            environment="staging",
            requester_id="user-1",
            known_models={model},
            db=db,
            trigger_exists=True,
        )
    assert _notes(db) == []


def test_community_trigger_does_not_need_enterprise(db: Session) -> None:
    trigger = community_trigger(
        name="Note on create",
        target_model="sale.order",
        trigger="on_create",
        changeset=[
            {
                "type": "field.create",
                "params": {"model": "sale.order", "name": "x_fire_note"},
            }
        ],
    )
    assert trigger.host_model == "base.automation"
    opened = _fire(db, trigger)
    assert opened.status == "pending"
    package = Path(runner.__file__).read_text(encoding="utf-8")
    assert "studio." not in package
    assert "web_studio" not in package
    with pytest.raises(EnterpriseTriggerRefused):
        community_trigger(
            name="Studio rule",
            target_model="sale.order",
            trigger="on_create",
            changeset=[
                {
                    "type": "field.create",
                    "params": {"model": "sale.order", "name": "x_fire_note"},
                }
            ],
            host_model="studio.approval.rule",
        )


def test_audit_note_names_trigger_person_and_plan_hash(db: Session) -> None:
    opened = _fire(db, _sale_trigger(), person="user-1")
    rows = _notes(db)
    assert len(rows) == 1
    row = rows[0]
    assert row.kind == "note"
    assert row.actor == "user-1"
    payload = json.loads(row.payload_json)
    assert payload == {
        "trigger": "Note on create",
        "person": "user-1",
        "plan_hash": opened.plan_hash,
    }


def test_two_firings_need_two_approvals(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def _spy(*_args, **_kwargs):
        calls.append("apply")
        return {"status": "not_used"}

    monkeypatch.setattr(executor, "apply", _spy)
    trigger = _sale_trigger()
    first = _fire(db, trigger)
    second = _fire(db, trigger)
    assert calls == []
    first_approval = approve(first.plan_hash, person="user-1")
    assert calls == []
    with pytest.raises(ApprovalRequired):
        apply_firing(second.plan_hash, approval_id=first_approval)
    with pytest.raises(ApprovalRequired):
        apply_firing(second.plan_hash, approval_id="")
    assert calls == []
    second_approval = approve(second.plan_hash, person="user-1")
    assert first_approval != second_approval
    apply_firing(second.plan_hash, approval_id=second_approval)
    assert calls == ["apply"]
    assert len(_notes(db)) == 2
    assert {json.loads(row.payload_json)["plan_hash"] for row in _notes(db)} == {
        first.plan_hash,
        second.plan_hash,
    }


def test_trigger_runner_does_not_apply_without_approval_id() -> None:
    source = Path(runner.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = [node for node in ast.walk(tree) if _is_executor_apply(node)]
    assert len(calls) == 1
    call = calls[0]
    owner = _enclosing_function(tree, call)
    assert owner is not None
    assert owner.name == "apply_firing"
    assert _raises_on_missing_approval_id(owner, call)
    fire_fn = _function(tree, "fire")
    assert fire_fn is not None
    assert not any(_is_executor_apply(node) for node in ast.walk(fire_fn))
    assert not _calls_name(fire_fn, "apply_firing")


def _is_executor_apply(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return False
    func = node.func
    return (
        func.attr == "apply"
        and isinstance(func.value, ast.Name)
        and func.value.id == "executor"
    )


def _function(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _enclosing_function(tree: ast.AST, call: ast.Call) -> ast.FunctionDef | None:
    found: ast.FunctionDef | None = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        end = getattr(node, "end_lineno", None)
        if end is None or call.lineno is None:
            continue
        if node.lineno <= call.lineno <= end:
            if found is None or node.lineno >= found.lineno:
                found = node
    return found


def _raises_on_missing_approval_id(fn: ast.FunctionDef, call: ast.Call) -> bool:
    arg_names = [arg.arg for arg in fn.args.args] + [arg.arg for arg in fn.args.kwonlyargs]
    if "approval_id" not in arg_names:
        return False
    for node in ast.walk(fn):
        if not isinstance(node, ast.If) or node.lineno >= call.lineno:
            continue
        if not _mentions(node.test, "approval_id"):
            continue
        for stmt in node.body:
            if any(isinstance(child, ast.Raise) for child in ast.walk(stmt)):
                return True
    return False


def _mentions(node: ast.AST, name: str) -> bool:
    return any(isinstance(child, ast.Name) and child.id == name for child in ast.walk(node))


def _calls_name(fn: ast.FunctionDef, name: str) -> bool:
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == name:
            return True
        if isinstance(func, ast.Attribute) and func.attr == name:
            return True
    return False

