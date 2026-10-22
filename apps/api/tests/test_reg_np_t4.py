"""REG-NP-T4: one positive and one negative pin for each acceptance criterion."""

from __future__ import annotations

import ast
import dataclasses
import json
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.ai_schema_client import FakeSchemaClient
from app.ai_structural_zip_gate import structural_zip_gate
from app.db import get_db
from app.db_models import AuditChainEntry, IdempotencyKey
from app.grounding.tools import ToolTarget, accept_tool_target, offer_tool_targets
from app.llm_gateway.gateway import Gateway
from app.llm_gateway.providers import (
    QWEN_GATEWAY_PROVIDER,
    ProviderReplayAdapter,
    default_active_providers,
    require_provider,
)
from app.llm_gateway.registry import TIER_C_CAPS, load_registry, lookup, model_ids_in_source
from app.llm_gateway.types import LLMError
from app.llm_provider import GeminiProvider, OllamaProvider, _ollama_local_model
from app.offline.flush import recorded_flush_effects, reset_flush_effects
from app.progress.stage_bus import StageBus
from app.progress.stage_registry import (
    BULK_STAGES,
    DASHBOARD_STAGES,
    EXPERT_STAGES,
    GENERATION_STAGES,
    KNOWN_STAGES,
    generation_stage_for_step,
)
from app.routers.offline import router as offline_router
from app.snapshots import CONFIRM_PHRASE
from app.triggers.runner import (
    ProtectedModelBlocked,
    approve,
    community_trigger,
    fire,
    plan_card,
    reset_trigger_gate,
)
from app.wireframe import sketch_to_module_spec
from app.wireframe import __all__ as wireframe_all
from module_generator import (
    CONFIRM_PHRASE as RECOMPILE_PHRASE,
    MODULE_EDITED_IN_ODOO,
    SPEC_EDITED_OUTSIDE,
    FieldSpec,
    ModelSpec,
    ModuleSpec,
    RecompileRefused,
    ViewSpec,
    artifact_ispec,
    artifact_module_files,
    ispec_to_module_spec,
    library_fines_python_module_spec,
    library_module_spec,
    module_spec_to_ispec,
    recompile_module,
    render_module_files,
    render_xpath_field_inject,
    resolve_named_widget,
    sync_module,
)
from module_generator.ispec import IspecError

pytestmark = pytest.mark.no_app_db

_API = Path(__file__).resolve().parents[1]
_APP = _API / "app"
_WEB = _API.parent / "web" / "src"
_WIREFRAME = _APP / "wireframe"
_GROUNDING = _APP / "grounding"
_SKETCHES = Path(__file__).resolve().parent / "fixtures" / "wireframe"
_RATE_PATH = _WEB / "testing" / "browserAgent" / "false_positive_rate.json"

_SURFACE_FILES = (
    _WEB / "app" / "connections" / "[id]" / "studio" / "page.tsx",
    _WEB / "app" / "connections" / "[id]" / "bulk-suite" / "page.tsx",
    _WEB / "components" / "expert",
    _WEB / "app" / "studio" / "dashboards" / "page.tsx",
)
_STAGE_PROGRESS = _WEB / "components" / "progress" / "StageProgress.tsx"
_EMITTERS = (
    (_APP / "ai_draft_jobs.py", "stage_emit(job_id, generation_stage_for_step(step), detail=label)"),
    (_APP / "expert" / "ask.py", 'stage_emit(progress_run_id, "expert_classify"'),
    (_APP / "expert" / "ask.py", 'stage_emit(progress_run_id, "expert_retrieve"'),
    (_APP / "expert" / "ask.py", 'stage_emit(progress_run_id, "expert_ground"'),
    (_APP / "expert" / "ask.py", 'stage_emit(progress_run_id, "expert_answer"'),
    (_APP / "routers" / "bulk_suite.py", 'stage_emit(progress_run_id, "bulk_resolve"'),
    (_APP / "routers" / "bulk_suite.py", 'stage_emit(progress_run_id, "bulk_sample"'),
    (_APP / "routers" / "bulk_suite.py", 'stage_emit(progress_run_id, "bulk_execute"'),
    (_APP / "routers" / "bulk_suite.py", 'stage_emit(progress_run_id or result.run_id, "bulk_report"'),
    (_APP / "routers" / "dashboard_studio.py", 'stage_emit(run_id, "dash_plan"'),
    (_APP / "routers" / "dashboard_studio.py", 'stage_emit(run_id, "dash_query"'),
    (_APP / "routers" / "dashboard_studio.py", 'stage_emit(run_id, "dash_render"'),
    (_APP / "routers" / "dashboard_studio.py", 'stage_emit(run_id, "dash_save"'),
)
_PROGRESS_MOUNTS = (
    _WEB / "components" / "studio" / "StudioGenerationStates.tsx",
    _WEB / "components" / "expert" / "ExpertConversation.tsx",
    _WEB / "app" / "studio" / "dashboards" / "page.tsx",
    _WEB / "components" / "bulk" / "use-bulk-suite-runs.ts",
)

_APPLY_NAMES = frozenset(
    {
        "apply_module_spec",
        "apply_module_spec_ui",
        "apply_session_route",
        "apply_project_spec",
        "apply_project",
        "apply_queued_flush",
    }
)
_FORBIDDEN_IMPORT_ROOTS = frozenset(
    {"llm_gateway", "llm_provider", "changeset", "agent_runtime"}
)
_FORBIDDEN_RAG = ("ai_rag2", "ai_rag_v2", "compiler_rag")

MUTATION_BODY = {
    "kind": "mutation",
    "method": "POST",
    "path": "/api/connections/c1/fields",
    "body": {"name": "x_note"},
}
PROMOTE_BODY = {
    "kind": "promote",
    "method": "POST",
    "path": "/api/connections/c1/modules/promote",
    "body": {"validation_id": "val-1"},
}

_BROWSER_MODULE = "x_ticket_browser"
_BROWSER_DEFECT = "view_arch_unparseable"
_BROWSER_PY = (
    "from odoo import fields, models\n\n"
    "class Ticket(models.Model):\n"
    "    _name = 'x_ticket'\n"
    "    _description = 'Ticket'\n"
    "    name = fields.Char(required=True)\n"
)
_BROWSER_ACL = (
    "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink\n"
    "access_x_ticket,x_ticket,model_x_ticket,base.group_user,1,1,1,1\n"
)
_BROWSER_MANIFEST = "{'name': 'Tickets', 'version': '1.0'}\n"
_CLEAN_ARCH = (
    "<?xml version='1.0' encoding='utf-8'?>\n"
    "<odoo>\n"
    '  <record id="view_x_ticket_form" model="ir.ui.view">\n'
    '    <field name="name">x.ticket.form</field>\n'
    '    <field name="model">x_ticket</field>\n'
    '    <field name="arch" type="xml">\n'
    '      <form string="Ticket">\n'
    "        <sheet><group><field name=\"name\"/></group></sheet>\n"
    "      </form>\n"
    "    </field>\n"
    "  </record>\n"
    "</odoo>\n"
)
_DIRTY_ARCH = (
    "<?xml version='1.0' encoding='utf-8'?>\n"
    "<odoo>\n"
    '  <record id="view_x_ticket_form" model="ir.ui.view">\n'
    '    <field name="name">x.ticket.form</field>\n'
    '    <field name="model">x_ticket</field>\n'
    '    <field name="arch" type="xml">\n'
    '      <form string="Ticket">\n'
    "        <sheet><group><field name=\"name\">\n"
    "      </form>\n"
    "    </field>\n"
    "  </record>\n"
    "</odoo>\n"
)

_TOOL_SCHEMA = {
    "type": "object",
    "properties": {"model": {"type": "string"}},
    "required": ["model"],
    "additionalProperties": False,
}
_TOOL_REQUEST = {
    "model_id": "configured",
    "max_output_tokens": 32,
    "messages": [{"role": "user", "content": "plan one model"}],
    "tools": [{"name": "describe_model", "description": "look", "input_schema": _TOOL_SCHEMA}],
}
_TOOL_ARGS = {"model": "sale.order"}


def _texts_under(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(item for item in path.rglob("*") if item.suffix in {".ts", ".tsx"})


def _fingerprint(root: Path) -> list[tuple[str, bytes]]:
    rows: list[tuple[str, bytes]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        rows.append((path.relative_to(root).as_posix(), path.read_bytes()))
    return rows


def _call_names(fn: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            names.add(func.id)
        elif isinstance(func, ast.Attribute):
            names.add(func.attr)
    return names


def _imports(tree: ast.AST) -> list[str]:
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            for alias in node.names:
                found.append(f"{base}.{alias.name}" if base else alias.name)
            if base:
                found.append(base)
    return found


def _top_function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"missing function {name}")


def _function(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"missing function {name}")


def _calls_executor_apply(fn: ast.AST) -> bool:
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        value = node.func.value
        if node.func.attr == "apply" and isinstance(value, ast.Name) and value.id == "executor":
            return True
    return False


@contextmanager
def _flush_client(tmp_path: Path) -> Iterator[TestClient]:
    reset_flush_effects()
    engine = create_engine(
        f"sqlite:///{tmp_path}/offline_flush.db",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    IdempotencyKey.__table__.create(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    app = FastAPI()
    app.include_router(offline_router, prefix="/api")

    def _db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        reset_flush_effects()


def _audit_session() -> Session:
    engine = create_engine("sqlite://")
    AuditChainEntry.__table__.create(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _sale_trigger(*, record_id: int | None = 42):
    return community_trigger(
        name="Note on create",
        target_model="sale.order",
        trigger="on_create",
        changeset=[
            {"type": "field.create", "params": {"model": "sale.order", "name": "x_fire_note"}}
        ],
        record_id=record_id,
    )


def _fire(db: Session, trigger, *, person: str = "user-1"):
    return fire(
        trigger,
        person=person,
        connection_id="conn-reg-np-t4",
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


def _browser_files(arch: str) -> dict[str, str]:
    return {
        f"{_BROWSER_MODULE}/__manifest__.py": _BROWSER_MANIFEST,
        f"{_BROWSER_MODULE}/models/ticket.py": _BROWSER_PY,
        f"{_BROWSER_MODULE}/security/ir.model.access.csv": _BROWSER_ACL,
        f"{_BROWSER_MODULE}/views/ticket_views.xml": arch,
    }


def _recompile_confirm() -> dict[str, object]:
    return {"confirm_advanced": True, "confirm_phrase": RECOMPILE_PHRASE}


def _spec(display_name: str = "Alpha Name") -> ModuleSpec:
    return ModuleSpec(technical_name="demo_min", display_name=display_name)


def _sale_client() -> FakeSchemaClient:
    return FakeSchemaClient(
        models={"sale.order"},
        fields={
            "sale.order": {
                "partner_id": {"type": "many2one", "ttype": "many2one", "relation": "res.partner"},
                "name": {"type": "char", "ttype": "char"},
            }
        },
        methods={"sale.order": {"action_confirm"}},
    )


def _complete(provider: str, payload: dict[str, Any], *, allow_frontier: bool = False):
    adapter = ProviderReplayAdapter(provider, [payload], allow_frontier=allow_frontier)
    return Gateway(adapter, sleep=lambda _ms: None).complete(
        _TOOL_REQUEST, {"describe_model": _TOOL_SCHEMA}
    )


def test_ac1_four_surfaces_emit_named_stages() -> None:
    expected = [
        *GENERATION_STAGES,
        *EXPERT_STAGES,
        *BULK_STAGES,
        *DASHBOARD_STAGES,
        "tool_call_limit",
    ]
    assert set(expected) <= KNOWN_STAGES
    for step, name in enumerate(GENERATION_STAGES):
        assert generation_stage_for_step(step) == name

    bus = StageBus()
    seen: list[str] = []
    bus.subscribe("run-1", lambda event: seen.append(event["stage"]))
    for stage in expected:
        bus.emit("run-1", stage, detail="closed until asked")
    assert seen == expected
    assert bus.events[-1]["detail"] == "closed until asked"
    assert all(event["run_id"] == "run-1" for event in bus.events)

    for path, snippet in _EMITTERS:
        text = path.read_text(encoding="utf-8")
        assert snippet in text, f"{path.name} no longer emits {snippet}"

    for path in _SURFACE_FILES:
        assert path.exists(), path
        for file in _texts_under(path):
            assert "animate-spin" not in file.read_text(encoding="utf-8"), file

    progress = _STAGE_PROGRESS.read_text(encoding="utf-8")
    assert "const [detailsOpen, setDetailsOpen] = useState(false);" in progress
    assert "Show details" in progress
    assert "{detailsOpen ? (" in progress
    assert "Continue or stop?" in progress
    assert "It will not continue until you choose." in progress
    effect_at = progress.index("useEffect(() =>")
    effect_body = progress[effect_at:progress.index("}, [latest?.stage]);", effect_at)]
    assert "onContinue" not in effect_body
    assert "setToolLimitOpen(true)" in effect_body
    assert progress.count("onContinue?.()") == 1
    assert progress.index("onContinue?.()") > effect_at
    for mount in _PROGRESS_MOUNTS[:3]:
        assert "StageProgress" in mount.read_text(encoding="utf-8"), mount
    bulk_run = _PROGRESS_MOUNTS[3].read_text(encoding="utf-8")
    assert "progress_run_id" in bulk_run
    assert 'beginProgressRun("bulk")' in bulk_run


def test_ac1_unknown_stage_name_is_rejected() -> None:
    bus = StageBus()
    with pytest.raises(ValueError, match="unknown stage"):
        bus.emit("run-1", "not_a_registered_stage")
    assert bus.events == []
    with pytest.raises(ValueError, match="stage must name the work"):
        bus.emit("run-1", "spinner")
    assert bus.events == []


def test_ac2_same_idempotency_key_records_one_effect(tmp_path: Path) -> None:
    headers = {"Idempotency-Key": "01JREGNPT4ACK00000000001"}
    with _flush_client(tmp_path) as client:
        first = client.post("/api/offline/flush", json=MUTATION_BODY, headers=headers)
        second = client.post("/api/offline/flush", json=MUTATION_BODY, headers=headers)
        assert first.status_code == 200
        assert second.status_code == 200
        body = first.json()
        assert second.json() == body
        assert body["applied"] is True
        assert body["effect_seq"] == 1
        assert recorded_flush_effects() == [
            {"kind": "mutation", "method": "POST", "path": "/api/connections/c1/fields"}
        ]


def test_ac2_promote_without_phrase_records_zero_effects(tmp_path: Path) -> None:
    headers = {"Idempotency-Key": "01JREGNPT4PROM0000000001"}
    with _flush_client(tmp_path) as client:
        refused = client.post("/api/offline/flush", json=PROMOTE_BODY, headers=headers)
        assert refused.status_code == 403
        detail = refused.json()["detail"]
        assert detail["requires_confirmation"] is True
        assert detail["confirm_phrase"] == CONFIRM_PHRASE == "I understand the risks"
        assert recorded_flush_effects() == []

        confirmed = client.post(
            "/api/offline/flush",
            json={
                **PROMOTE_BODY,
                "confirm_advanced": True,
                "confirm_phrase": CONFIRM_PHRASE,
            },
            headers=headers,
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["applied"] is True
        assert confirmed.json()["kind"] == "promote"
        assert confirmed.json()["effect_seq"] == 1
        assert len(recorded_flush_effects()) == 1


def test_ac3_ispec_round_trip_keeps_module_spec() -> None:
    fenced = dataclasses.replace(library_module_spec(), display_name="```")
    cases = (
        ("library", library_module_spec()),
        ("library-fines", library_fines_python_module_spec()),
        ("fenced-name", fenced),
    )
    for name, spec in cases:
        blob = module_spec_to_ispec(spec)
        assert blob.startswith("# ISPEC module_spec 1\n"), name
        again = ispec_to_module_spec(blob)
        assert type(again) is ModuleSpec
        assert again.__class__.__module__ == "module_generator"
        assert again == spec, name
        assert module_spec_to_ispec(again) == blob

    source = Path(ispec_to_module_spec.__code__.co_filename)
    assert source.name == "ispec.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    class_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    assert "ModuleSpec" not in class_names
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for deco in node.decorator_list:
            name = deco.id if isinstance(deco, ast.Name) else ""
            assert name != "dataclass"


def test_ac3_dropped_or_unknown_field_is_refused() -> None:
    minimal = ModuleSpec(technical_name="demo_min", display_name="Demo Min")
    dropped = [
        line
        for line in module_spec_to_ispec(minimal).splitlines()
        if not line.startswith("author:")
    ]
    with pytest.raises(IspecError, match="missing module.author"):
        ispec_to_module_spec("\n".join(dropped) + "\n")

    unknown = module_spec_to_ispec(minimal).replace("## module\n", "## module\nextra: 1\n", 1)
    with pytest.raises(IspecError, match="unknown field"):
        ispec_to_module_spec(unknown)

    with pytest.raises(TypeError, match="ModuleSpec"):
        module_spec_to_ispec(ModelSpec(model="x_a", description="A"))  # type: ignore[arg-type]


def test_ac4_recompile_keeps_previous_and_drift_blocks_sync(tmp_path: Path) -> None:
    store = tmp_path / "store"
    original = _spec("Alpha Name")
    first = recompile_module(original, store=store, provider="provider_a", **_recompile_confirm())
    previous = _fingerprint(store / first.version_path)
    second = recompile_module(
        _spec("Beta Name"), store=store, provider="provider_a", **_recompile_confirm()
    )
    assert first.version_path != second.version_path
    assert second.diff.previous_version_path == first.version_path
    assert _fingerprint(store / first.version_path) == previous
    kept = (store / first.version_path / "ispec.md").read_text(encoding="utf-8")
    assert "Alpha Name" in kept
    assert "Beta Name" not in kept
    assert (store / second.version_path / "ispec.md").is_file()

    other = recompile_module(original, store=store, provider="provider_b", **_recompile_confirm())
    assert other.version_path != first.version_path
    assert other.provider == "provider_b"
    assert first.provider == "provider_a"
    assert _fingerprint(store / first.version_path) == previous
    first_record = (store / first.version_path / "artifact.json").read_bytes()
    other_record = (store / other.version_path / "artifact.json").read_bytes()
    assert first_record != other_record
    assert b"provider_b" in other_record

    before_sync = _fingerprint(store)
    outside = ispec_to_module_spec(artifact_ispec(store, first.version_path))
    outside.display_name = "Edited outside"
    spec_drift = sync_module(
        store=store,
        version_path=first.version_path,
        outside_ispec=module_spec_to_ispec(outside),
        odoo_module_files=artifact_module_files(store, first.version_path),
        **_recompile_confirm(),
    )
    assert spec_drift.blocked is True
    assert spec_drift.report
    assert {item.source for item in spec_drift.report} == {SPEC_EDITED_OUTSIDE}
    assert _fingerprint(store) == before_sync

    observed = artifact_module_files(store, first.version_path)
    manifest = next(path for path in observed if path.endswith("__manifest__.py"))
    observed[manifest] += "\n# fixture: module edited in Odoo\n"
    module_drift = sync_module(
        store=store,
        version_path=first.version_path,
        outside_ispec=artifact_ispec(store, first.version_path),
        odoo_module_files=observed,
        **_recompile_confirm(),
    )
    assert module_drift.blocked is True
    assert {item.source for item in module_drift.report} == {MODULE_EDITED_IN_ODOO}
    assert any(item.path == manifest for item in module_drift.report)
    assert _fingerprint(store) == before_sync


def test_ac4_identical_spec_into_existing_version_is_refused(tmp_path: Path) -> None:
    store = tmp_path / "store"
    first = recompile_module(_spec(), store=store, provider="provider_a", **_recompile_confirm())
    before = _fingerprint(store)
    with pytest.raises(RecompileRefused, match="existing version path"):
        recompile_module(_spec(), store=store, provider="provider_a", **_recompile_confirm())
    assert _fingerprint(store) == before
    assert (store / first.version_path).is_dir()


def test_ac5_stage_f_records_a_defect_python_checks_miss() -> None:
    gate = structural_zip_gate(files=_browser_files(_DIRTY_ARCH))
    assert "browser_agent" in gate
    assert gate["browser_agent"]["ran"] is True
    assert gate["ok"] is False
    assert not any("syntax" in finding for finding in gate["findings"])
    assert not any("ir.model.access" in finding for finding in gate["findings"])
    assert not any("view_field_undefined" in finding for finding in gate["findings"])
    assert any(_BROWSER_DEFECT in finding for finding in gate["findings"])
    caught = gate["browser_agent"]["caught"]
    assert caught, gate["browser_agent"]
    assert caught[0]["module"] == _BROWSER_MODULE
    assert caught[0]["defect"] == _BROWSER_DEFECT
    if shutil.which("node"):
        assert gate["browser_agent"]["invoked_web_agent"] is True
        web_caught = gate["browser_agent"].get("web_agent_caught") or []
        assert any(row.get("defect") == _BROWSER_DEFECT for row in web_caught), web_caught


def test_ac5_clean_fixture_is_not_that_defect() -> None:
    gate = structural_zip_gate(files=_browser_files(_CLEAN_ARCH))
    assert gate["browser_agent"]["ran"] is True
    assert gate["ok"] is True, gate["findings"]
    report = gate["browser_agent"]
    assert report["views_checked"] >= 1
    assert report["caught"] == []
    assert not any(_BROWSER_DEFECT in finding for finding in gate["findings"])
    false_positives = len(report["findings"])
    rate = false_positives / report["views_checked"]
    assert rate == report["false_positive_rate"] == 0.0
    measured = {
        "fixture": "x_ticket_browser clean form",
        "module": report["module"],
        "views_checked": report["views_checked"],
        "false_positives": false_positives,
        "false_positive_rate": rate,
        "measured_from": "clean fixture via structural_zip_gate",
        "defect_class_not_raised": _BROWSER_DEFECT,
    }
    assert json.loads(_RATE_PATH.read_text(encoding="utf-8")) == measured


def test_ac6_sketch_becomes_spec_through_the_public_path() -> None:
    assert "sketch_to_module_spec" in wireframe_all
    assert "regions_to_draft" not in wireframe_all
    outcome = sketch_to_module_spec(_SKETCHES / "visitor_log_photo.json")
    assert outcome["status"] == "review"
    assert outcome["clarification"] is None
    assert outcome["apply_ready"] is False
    spec = outcome["spec"]
    assert spec["technical_name"] == "visitor_log"
    assert spec["_wireframe"]["source"] == "sketch"
    assert spec["_wireframe"]["stage_h"] is True
    assert any(row["model"] == "x_visitor_log" for row in spec["models"])

    producers: list[str] = []
    for path in sorted(_WIREFRAME.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for fn in tree.body:
            if not isinstance(fn, ast.FunctionDef):
                continue
            calls = _call_names(fn)
            if "regions_to_draft" in calls and (
                "attach_stage_h" in calls or "residual_form_preview" in calls
            ):
                producers.append(fn.name)
    assert producers == ["sketch_to_module_spec"]
    review = ast.parse((_WIREFRAME / "review.py").read_text(encoding="utf-8"))
    sole = _top_function(review, "sketch_to_module_spec")
    assert "attach_stage_h" in _call_names(sole)


def test_ac6_wireframe_does_not_import_or_apply() -> None:
    outcome = sketch_to_module_spec(_SKETCHES / "unlabeled_region.json")
    assert outcome["status"] == "clarify"
    assert outcome["spec"] is None
    assert outcome["apply_ready"] is False
    assert outcome["clarification"]["id"] == "wireframe_unlabeled"

    for path in sorted(_WIREFRAME.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for module in _imports(tree):
            hit = _FORBIDDEN_IMPORT_ROOTS.intersection(module.split("."))
            assert not hit, f"{path.name} imports {module}"
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef):
                hits = _call_names(fn) & _APPLY_NAMES
                assert hits == set(), f"{path.name}:{fn.name} calls {sorted(hits)}"


def test_ac7_gateway_switches_provider_above_the_binding() -> None:
    openai_payload = {
        "status": "completed",
        "output": [
            {
                "type": "function_call",
                "call_id": "fc_swap",
                "name": "describe_model",
                "arguments": json.dumps(_TOOL_ARGS),
            }
        ],
    }
    gemini_payload = {
        "candidates": [
            {
                "finishReason": "STOP",
                "content": {
                    "parts": [
                        {"functionCall": {"name": "describe_model", "args": dict(_TOOL_ARGS)}}
                    ]
                },
            }
        ]
    }
    openai_response = _complete("openai", openai_payload)
    gemini_response = _complete("gemini", gemini_payload)
    assert openai_response.stop_reason == gemini_response.stop_reason == "tool_calls"
    assert openai_response.tool_calls[0].args == gemini_response.tool_calls[0].args == _TOOL_ARGS
    assert GeminiProvider().name == "gemini"
    assert OllamaProvider().name == "ollama"
    assert _ollama_local_model("gemini-2.5-flash") == "qwen3:8b"
    assert QWEN_GATEWAY_PROVIDER == "openai"
    assert "gemini" in default_active_providers()
    assert "openai" in default_active_providers()
    provider_source = (_APP / "llm_provider.py").read_text(encoding="utf-8")
    assert "llm_gateway" not in provider_source
    assert "litellm" not in provider_source.lower()


def test_ac7_local_tier_s_and_unknown_model_are_refused() -> None:
    with pytest.raises(ValueError, match="tier must be A, B, C, or unset"):
        load_registry([{"provider": "local", "model_id": "x", "tier": "S"}])

    records = load_registry([{"provider": "openai", "model_id": "known", "tier": "B"}])
    found = lookup(records, "openai", "missing-model")
    assert found.record is None
    assert found.tier is None
    assert found.caps == TIER_C_CAPS
    assert found.caps.read_only is True
    assert found.caps.can_submit_changeset is False

    assert "anthropic" not in default_active_providers()
    with pytest.raises(LLMError) as caught:
        require_provider("anthropic")
    assert caught.value.kind == "invalid_request"

    registry_path = _APP / "llm_gateway" / "registry.py"
    ids = model_ids_in_source(registry_path.read_text(encoding="utf-8"))
    leaks: list[str] = []
    for path in sorted(_APP.rglob("*.py")):
        if "__pycache__" in path.parts or path.resolve() == registry_path.resolve():
            continue
        text = path.read_text(encoding="utf-8")
        for model_id in ids:
            if model_id in text:
                leaks.append(f"{path}:{model_id}")
    assert leaks == []


def test_ac8_existing_trigger_stays_pending() -> None:
    reset_trigger_gate()
    db = _audit_session()
    try:
        trigger = _sale_trigger(record_id=42)
        assert trigger.host_model == "base.automation"
        opened = _fire(db, trigger)
        card = plan_card(opened.plan_hash)
        assert opened.status == "pending"
        assert opened.approval_id is None
        assert card["approvals"] == []
        assert card["status"] == "pending"
    finally:
        db.close()
        reset_trigger_gate()


def test_ac8_second_firing_and_protected_models_stay_gated() -> None:
    reset_trigger_gate()
    db = _audit_session()
    try:
        trigger = _sale_trigger(record_id=42)
        first = _fire(db, trigger)
        second = _fire(db, trigger)
        assert first.plan_hash != second.plan_hash
        approve(first.plan_hash, person="user-1")
        assert plan_card(first.plan_hash)["status"] == "approved"
        assert plan_card(second.plan_hash)["status"] == "pending"
        assert plan_card(second.plan_hash)["approvals"] == []

        runner_tree = ast.parse(Path(fire.__code__.co_filename).read_text(encoding="utf-8"))
        assert _calls_executor_apply(_function(runner_tree, "fire")) is False

        for model in ("account.move", "hr.payslip"):
            blocked = community_trigger(
                name="Protected write",
                target_model=model,
                trigger="on_write",
                changeset=[
                    {"type": "field.create", "params": {"model": model, "name": "x_blocked"}}
                ],
            )
            before = len(_notes(db))
            with pytest.raises(ProtectedModelBlocked):
                fire(
                    blocked,
                    person="user-1",
                    connection_id="conn-reg-np-t4",
                    environment="staging",
                    requester_id="user-1",
                    known_models={model},
                    db=db,
                    trigger_exists=True,
                )
            assert len(_notes(db)) == before
    finally:
        db.close()
        reset_trigger_gate()


def test_ac9_known_tool_and_named_widget_use_existing_index() -> None:
    client = _sale_client()
    unknown = ToolTarget(kind="model", model="x.unknown.nowhere")
    offered = offer_tool_targets(
        client,
        [
            ToolTarget(kind="model", model="sale.order"),
            unknown,
        ],
    )
    assert offered == (ToolTarget(kind="model", model="sale.order"),)

    rag_tree = ast.parse((_GROUNDING / "rag.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(rag_tree):
        if isinstance(node, ast.ImportFrom) and node.module == "app.ai_rag":
            imported.update(alias.name for alias in node.names)
    assert "_cache_dir" in imported
    assert "retrieve_with_rag" in imported

    arch = render_xpath_field_inject("x_priority", "form", widget="priority")
    assert 'widget="priority"' in arch
    files = render_module_files(
        ModuleSpec(
            technical_name="demo_named_widget",
            display_name="Named Widget",
            models=[
                ModelSpec(
                    model="sale.order",
                    description="Sales Order",
                    mode="inherit",
                    inherit="sale.order",
                    fields=[FieldSpec(name="x_priority", ttype="selection", string="Priority")],
                )
            ],
            views=[
                ViewSpec(
                    name="sale.order.form.priority",
                    model="sale.order",
                    type="form",
                    arch=arch,
                    inherit_xml_id="sale.view_order_form",
                    mode="extension",
                )
            ],
        )
    )
    views_xml = files["demo_named_widget/views/views.xml"]
    assert 'name="x_priority"' in views_xml
    assert 'widget="priority"' in views_xml
    assert 'widget="char"' not in views_xml


def test_ac9_unknown_model_and_second_rag_root_are_refused() -> None:
    client = _sale_client()
    unknown = ToolTarget(kind="model", model="x.unknown.nowhere")
    assert accept_tool_target(client, unknown) is False
    offered = offer_tool_targets(
        client,
        [
            ToolTarget(kind="model", model="sale.order"),
            unknown,
        ],
    )
    assert unknown not in offered
    assert offered == (ToolTarget(kind="model", model="sale.order"),)

    for path in _GROUNDING.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in _FORBIDDEN_RAG:
            assert token not in text, f"{path.name} introduced {token}"

    assert resolve_named_widget("monetary", standin="char") == "monetary"
    assert resolve_named_widget("priority", standin="text") == "priority"
    standin_arch = render_xpath_field_inject(
        "x_amount", "form", widget="monetary", standin="char"
    )
    assert 'widget="monetary"' in standin_arch
    assert 'widget="char"' not in standin_arch
