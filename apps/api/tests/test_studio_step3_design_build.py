"""Step 3: the locked App design drives Generate, the preview data and Apply.

Fake LLM + fake Odoo only. Customer Health brief fixture.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")

from app.ai_conversation.grounding import StudioGrounding, reset_grounding, set_grounding  # noqa: E402
from app.ai_conversation.intent_llm import reset_intent_llm_override, set_intent_llm_override  # noqa: E402
from test_studio_step2a_app_design import BRIEF, GOOD_DESIGN, GROUNDING, _FakeProvider  # noqa: E402

pytestmark = pytest.mark.no_app_db

TITLE = "Customer Health & Retention Intelligence"
SH = StudioGrounding(
    edition="enterprise", hosting="odoo_sh", server_version="18.0+e",
    apps_installed=("CRM", "Sales", "Invoicing", "Project"), apps_missing=("Helpdesk",),
)


def _locked(monkeypatch: pytest.MonkeyPatch, provider: _FakeProvider, grounding: StudioGrounding = GROUNDING,
            prompt: str = BRIEF) -> dict[str, Any]:
    import app.llm_provider as lp
    from app.ai_conversation.understand import build_understanding, clear_enrich_cache

    clear_enrich_cache()
    monkeypatch.setattr(lp, "get_llm_provider_for_tier", lambda tier: provider)
    g, i = set_grounding(grounding), set_intent_llm_override(True)
    try:
        return build_understanding(prompt).to_dict()
    finally:
        reset_intent_llm_override(i)
        reset_grounding(g)


def _generate(monkeypatch: pytest.MonkeyPatch, locked: dict[str, Any], prompt: str = BRIEF) -> dict[str, Any]:
    import app.ai_draft_jobs as jobs

    monkeypatch.setattr(jobs, "_default_progress", lambda job_id: (lambda *a, **k: None))
    kwargs = jobs.build_draft_job_kwargs(
        prompt=prompt, connection_id=None, available_models=None, installed_modules=None,
        stock_catalog=None, locked_understanding=locked,
    )
    return jobs.run_draft_job_body(job_id="t-step3", db_factory=None, client=None, **kwargs)


class FakeOdoo:
    """Records every write; search/read over an in-memory store (idempotency)."""

    server_version = "18.0"

    def __init__(self) -> None:
        self.models: set[str] = {"res.partner", "res.users", "res.company", "res.currency", "res.groups", "ir.ui.menu", "ir.ui.view",
                                 "ir.model.access", "ir.actions.act_window", "crm.lead", "sale.order",
                                 "account.move", "project.project"}
        self.fields: dict[str, set[str]] = {"res.groups": {"implied_ids"}, "ir.ui.menu": {"group_ids"},
                                            "res.users": {"group_ids"}}
        self.db: dict[str, list[dict[str, Any]]] = {}
        self.log: list[tuple[str, ...]] = []
        self._id = 0

    def model_exists(self, model: str) -> bool:
        return model in self.models

    def field_exists(self, model: str, name: str) -> bool:
        return name in self.fields.get(model, set()) or (model in self.models and name in {"name", "id"})

    def create_model(self, request: Any, *, with_defaults: bool = True) -> Any:
        self.models.add(request.model)
        self.fields.setdefault(request.model, set()).add("x_name")
        self.log.append(("model", request.model))
        return request

    def create_field(self, request: Any) -> Any:
        ttype = getattr(request.ttype, "value", str(request.ttype))
        if request.relation and request.relation not in self.models:
            raise ValueError(f"unknown relation {request.relation}")
        if ttype == "one2many" and request.relation_field not in self.fields.get(request.relation, set()):
            raise ValueError("inverse missing")
        self.fields.setdefault(request.model, set()).add(request.name)
        self.log.append(("field", request.model, request.name, ttype))
        return request

    def create_access_right(self, request: Any) -> int:
        self.log.append(("create", "ir.model.access", request.model))
        return self._create("ir.model.access", {"model": request.model, "group_id": request.group_id, "name": request.name})

    def create_record_rule(self, request: Any) -> int:
        return self._create("ir.rule", {"model": request.model})

    def resolve_xml_id(self, xml_id: str) -> int:
        raise LookupError(xml_id)

    def _create(self, model: str, vals: dict[str, Any]) -> int:
        self._id += 1
        self.db.setdefault(model, []).append({"id": self._id, **vals})
        return self._id

    def _match(self, row: dict[str, Any], domain: list[Any]) -> bool:
        for cond in domain or []:
            if not isinstance(cond, (list, tuple)) or len(cond) != 3:
                continue
            key, op, val = cond
            key = {"model_id.model": "model"}.get(key, key)
            have = row.get(key)
            if isinstance(have, (list, tuple)) and have and isinstance(have[0], int):
                have = have[0]
            if op == "=" and have != val and not (val is False and have in (None, False)):
                return False
            if op == "in" and have not in val:
                return False
        return True

    def execute_kw(self, model: str, method: str, args: list[Any] | None = None, kwargs: dict[str, Any] | None = None) -> Any:
        args, kwargs = args or [], kwargs or {}
        rows = self.db.setdefault(model, [])
        if method == "create":
            vals = args[0] if args else {}
            if isinstance(vals, list):
                return [self.execute_kw(model, "create", [v]) for v in vals]
            self.log.append(("create", model, str(vals.get("name") or vals.get("model") or "")))
            return self._create(model, dict(vals))
        if method in {"search", "search_read", "search_count"}:
            found = [r for r in rows if self._match(r, args[0] if args else [])]
            if kwargs.get("limit"):
                found = found[: kwargs["limit"]]
            if method == "search_count":
                return len(found)
            return found if method == "search_read" else [r["id"] for r in found]
        if method == "read":
            ids = set(args[0]) if args else set()
            return [r for r in rows if r["id"] in ids]
        if method == "write":
            self.log.append(("write", model, str(args[1] if len(args) > 1 else "")))
            for r in rows:
                if r["id"] in set(args[0]):
                    r.update(args[1])
            return True
        return []

    def create_view(self, request: Any) -> int:
        self.log.append(("create", "ir.ui.view", f"{request.model}.{request.type}"))
        return self._create("ir.ui.view", {"model": request.model, "type": str(request.type), "name": request.name})

    def find_view(self, model: str, vtype: str, primary_only: bool = False) -> Any:
        from types import SimpleNamespace

        row = next((r for r in self.db.get("ir.ui.view", []) if r["model"] == model and r["type"] == vtype), None)
        return SimpleNamespace(id=row["id"]) if row else None

    def create_window_action(self, name: str = "", model: str = "", **kw: Any) -> int:
        self.log.append(("create", "create_window_action", name))
        return self._create("ir.actions.act_window", {"name": name, "res_model": model})

    def create_menu(self, name: str = "", parent_id: int | None = None, **kw: Any) -> int:
        self.log.append(("create", "ir.ui.menu", name))
        return self._create("ir.ui.menu", {"name": name, "parent_id": parent_id or False, **kw})

    def __getattr__(self, name: str) -> Any:  # other create_* helpers record; the rest no-op
        if name.startswith("__"):
            raise AttributeError(name)
        if name.startswith("create_"):
            def _create_any(*a: Any, **k: Any) -> int:
                self.log.append(("create", name, str(k.get("name") or "")))
                return self._create(name, dict(k))
            return _create_any
        return lambda *a, **k: None


def test_generate_builds_full_app_from_good_design(monkeypatch: pytest.MonkeyPatch) -> None:
    locked = _locked(monkeypatch, _FakeProvider(GOOD_DESIGN))
    out = _generate(monkeypatch, locked)
    draft = out["draft"]
    assert draft["_pipeline"] == "app_design" and draft["grain"] == "full_app"
    new = [m for m in draft["models"] if m.get("mode") == "new"]
    assert len(new) == 11
    ext = [m for m in draft["models"] if m.get("stock_extension")]
    assert [m["model"] for m in ext] == ["res.partner"]
    assert {f["name"] for f in ext[0]["fields"]} >= {"x_health_score", "x_health_status", "x_risk_ids"}
    risk_link = next(f for f in ext[0]["fields"] if f["name"] == "x_risk_ids")
    assert risk_link["relation_field"] == "x_partner_id"  # inverse on x_customer_risk
    score = next(m for m in new if m["model"] == "x_health_score")
    status = next(f for f in score["fields"] if f["name"] == "x_health_status")
    assert "('at_risk', 'At Risk')" in status["selection"]
    hist = next(f for f in score["fields"] if f["name"] == "x_history_ids")
    assert hist["relation"] == "x_health_score_history" and hist["relation_field"] == "x_health_score_id"
    renewal = next(m for m in new if m["model"] == "x_renewal")
    assert "x_ticket_id" not in {f["name"] for f in renewal["fields"]}  # Helpdesk deferred
    assert [d["module"] for d in draft["_deferred_integrations"]] == ["helpdesk"]
    assert "helpdesk" not in draft["depends"] and {"crm", "sale", "project"} <= set(draft["depends"])
    groups = {g["name"]: g for g in draft["groups"]}
    assert set(groups) == {"CS User", "CS Manager", "Sales Manager", "Admin"}
    assert groups["CS Manager"]["implied"] == [groups["CS User"]["id"]]
    acl_models = {r["model"] for r in draft["access_rules"]}
    assert acl_models == {m["model"] for m in new}
    leaf = [m for m in draft["menus"] if m.get("action_xml_id")]
    assert len(leaf) == 11 and any(m["name"] == "Configuration" for m in draft["menus"])
    assert {(v["model"], v["type"]) for v in draft["views"]} >= {("x_customer_risk", "kanban"), ("x_health_score", "form")}
    plan = draft["_architecture_plan"]
    assert plan["surface_budget"]["new_models"] == 11 and len(plan["new_x_models"]) == 11
    # host=res.partner must not turn the app into a Prefer / inherit job
    from app.spec_apply_ui import inherit_host_model_from_spec

    assert inherit_host_model_from_spec(draft) is None
    assert draft["_generation_engine"]["capability"] == "residual_app"
    assert locked["host_model"] == "res.partner" and locked["inherit_existing"] is False
    # clipping keeps every design model
    from app.ai_document_shape import clip_llm_models_to_plan

    clip_llm_models_to_plan(draft, {"new_x_models": ["x_health_score"], "surface_budget": {"new_models": 1}})
    assert len([m for m in draft["models"] if m.get("mode") == "new"]) == 11


def test_generate_outline_fallback_builds_eight_models(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.llm_provider import LLMError

    locked = _locked(monkeypatch, _FakeProvider(fail=LLMError("Gemini request timed out")))
    assert locked["app_design"]["source"] == "outline"
    draft = _generate(monkeypatch, locked)["draft"]
    new = [m for m in draft["models"] if m.get("mode") == "new"]
    assert len(new) == 12
    assert [m["model"] for m in draft["models"] if m.get("stock_extension")] == ["res.partner"]
    assert {g["name"] for g in draft["groups"]} == {
        "Customer Success User", "Customer Success Manager", "Sales Manager", "Administrator"}
    assert len([m for m in draft["menus"] if m.get("action_xml_id")]) == 12


def test_apply_order_and_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai_apply_readiness import prepare_spec_for_live_apply
    from app.spec_apply_ui import apply_module_spec_ui

    draft = _generate(monkeypatch, _locked(monkeypatch, _FakeProvider(GOOD_DESIGN)))["draft"]
    spec, _notes = prepare_spec_for_live_apply(draft)
    client = FakeOdoo()
    result = apply_module_spec_ui(client, spec)
    log = client.log
    made = [e[1] for e in log if e[0] == "model"]
    assert len(made) == 11, result.warnings
    idx = lambda pred: [i for i, e in enumerate(log) if pred(e)]  # noqa: E731
    last_model = max(idx(lambda e: e[0] == "model"))
    rel = idx(lambda e: e[0] == "field" and e[3] in {"many2one", "one2many", "many2many"})
    assert rel and min(rel) > last_model
    o2m = idx(lambda e: e[0] == "field" and e[3] == "one2many")
    m2o = idx(lambda e: e[0] == "field" and e[3] == "many2one")
    assert min(o2m) > max(m2o)
    assert ("field", "res.partner", "x_health_score", "float") in log
    groups = idx(lambda e: e[:2] == ("create", "res.groups"))
    acl = idx(lambda e: e[:2] == ("create", "ir.model.access"))
    assert len(groups) == 4 and acl and max(groups) < min(acl)
    assert any(e[:2] == ("write", "res.groups") and "implied_ids" in e[2] for e in log)
    menus = idx(lambda e: e[:2] == ("create", "ir.ui.menu"))
    assert menus and min(menus) > last_model, result.warnings
    assert not [w for w in result.warnings if "Failed" in w], result.warnings
    # idempotent second run: nothing new is created
    before = len([e for e in log if e[0] in {"model", "field"} or e[0] == "create"])
    n_first = len(client.log)
    apply_module_spec_ui(client, spec)
    after = len([e for e in client.log if e[0] in {"model", "field"} or e[0] == "create"])
    assert after == before, sorted({e for e in client.log[n_first:] if e[0] != 'write'})


def test_python_pieces_batch_into_one_option_a_module(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai_generation_engine import is_option_a_authored_draft

    online = _generate(monkeypatch, _locked(monkeypatch, _FakeProvider(GOOD_DESIGN)))
    batch = online["draft"]["_option_a_batch"]
    assert batch["online_blocked"] is True and batch["status"] == "blocked_online"
    assert "cannot install on Odoo Online" in " ".join(online["warnings"])
    assert not online["draft"].get("custom_code_blocks")  # no Python in the live spec
    assert batch["promote"] == {"mode": "single_button", "label": "Promote", "config_required": False}
    # Scheduled jobs are Online scheduled actions now; only module-level Python is batched.
    assert len(batch["pieces"]) >= 2 and all(p["delivery_lane"] == "module_sh_or_self" for p in batch["pieces"])

    sh = _generate(monkeypatch, _locked(monkeypatch, _FakeProvider(GOOD_DESIGN), grounding=SH))
    sh_batch = sh["draft"]["_option_a_batch"]
    assert sh_batch["online_blocked"] is False and sh_batch["status"] == "ready_to_author"
    companion = sh_batch["draft"]
    assert is_option_a_authored_draft(companion)
    assert "Computed health score" in companion["_user_prompt"] and "x_health_rule" in companion["_user_prompt"]

    from app.ai_option_a_author import author_option_a_module

    seen: list[str] = []

    def fake_blocks(text: str, draft: dict[str, Any]) -> list[dict[str, Any]]:
        seen.append(text)
        return []

    author_option_a_module(companion, generate_blocks=fake_blocks)
    assert seen and "Rules engine evaluation" in seen[0]  # the lane received every piece


def test_short_and_prefer_briefs_do_not_route_to_design(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai_design_compile import design_applies

    for prompt in ("Add a Priority field on sales orders.",
                   "Prefer extend the Sales order form: add a Priority selection (Low/High)."):
        provider = _FakeProvider(GOOD_DESIGN)
        locked = _locked(monkeypatch, provider, prompt=prompt)
        assert locked["app_design"] is None and not design_applies(locked.get("app_design"))
        assert not [c for c in provider.calls if c["system"].startswith("You design")]


def test_option_a_batch_route_single_child_session(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    import app.ai_option_a_author as author
    from app.ai_conversation.refine import artifact_hash
    from app.ai_conversation.session_store import create_session, get_session, update_session
    from app.ai_generation_engine import is_option_a_authored_draft
    from app.db import SessionLocal, init_db
    from app.main import app

    authored: list[str] = []
    monkeypatch.setattr(author, "author_option_a_module",
                        lambda draft, prompt=None, **k: authored.append(prompt or "") or draft)
    sh_draft = _generate(monkeypatch, _locked(monkeypatch, _FakeProvider(GOOD_DESIGN), grounding=SH))["draft"]
    online_draft = _generate(monkeypatch, _locked(monkeypatch, _FakeProvider(GOOD_DESIGN)))["draft"]
    init_db()
    db = SessionLocal()
    try:
        ids = []
        for art in (sh_draft, online_draft):
            row = create_session(db, connection_id=None, feature="ai_studio", prompt=BRIEF, status="review")
            update_session(db, row, artifact=art, artifact_hash=artifact_hash(art))
            ids.append(row.id)
    finally:
        db.close()
    with TestClient(app) as client:
        first = client.post(f"/api/ai/sessions/{ids[0]}/option-a-batch")
        again = client.post(f"/api/ai/sessions/{ids[0]}/option-a-batch")
        blocked = client.post(f"/api/ai/sessions/{ids[1]}/option-a-batch")
    assert first.status_code == 200, first.text
    assert again.json()["session_id"] == first.json()["session_id"] and len(authored) == 1
    assert first.json()["promote"]["mode"] == "single_button"
    assert blocked.status_code == 409 and "Online" in blocked.text
    db = SessionLocal()
    try:
        import json as _json

        child = get_session(db, first.json()["session_id"])
        assert is_option_a_authored_draft(_json.loads(child.artifact_json))
    finally:
        db.close()


def test_edited_design_is_accepted_and_revalidated(monkeypatch: pytest.MonkeyPatch) -> None:
    import copy

    from app.ai_conversation.understand import Understanding, apply_understanding_edits

    locked = _locked(monkeypatch, _FakeProvider(GOOD_DESIGN))
    design = copy.deepcopy(locked["app_design"])
    design["app_name"] = "Health Hub"
    design["new_models"] = [m for m in design["new_models"] if m["name"] != "x_expansion_recommendation"]
    risk = next(m for m in design["new_models"] if m["name"] == "x_customer_risk")
    risk["label"] = "Account Risk"
    dropped = next(f["name"] for f in risk["fields"] if f["name"] != "x_name" and f.get("ttype") != "many2one")
    risk["fields"] = [f for f in risk["fields"] if f["name"] != dropped]
    design["integrations_off"] = ["helpdesk"]
    edited = apply_understanding_edits(Understanding.from_dict(locked), {"app_design": design}).to_dict()
    out = edited["app_design"]
    names = [m["name"] for m in out["new_models"]]
    assert len(names) == 10 and "x_expansion_recommendation" not in names
    risk2 = next(m for m in out["new_models"] if m["name"] == "x_customer_risk")
    assert risk2["label"] == "Account Risk" and dropped not in {f["name"] for f in risk2["fields"]}
    assert out["app_name"] == "Health Hub" and out["source"] == locked["app_design"]["source"]
    assert "helpdesk" not in {i["module"] for i in out["integrations"]}
    assert all(r["target"] != "x_expansion_recommendation" for r in out["relations"])
    # python lane labels survive without live grounding (Online stays blocked)
    assert all(p.get("online_blocked") for p in out["python_needed"])
    draft = _generate(monkeypatch, edited)["draft"]
    assert len([m for m in draft["models"] if m.get("mode") == "new"]) == 10
    assert draft["display_name"] == "Health Hub"
    # no base design -> an edited design is ignored (no invent through the edit path)
    bare = Understanding.from_dict({**locked, "app_design": None})
    assert apply_understanding_edits(bare, {"app_design": design}).app_design is None
