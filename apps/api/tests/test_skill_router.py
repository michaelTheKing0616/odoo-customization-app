"""Skill router: at most three skills, no executable package, grant only narrows."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agent_runtime.runtime import AgentRuntime
from app.bots.grant import BotGrant
from app.skills.catalog import all_skills
from app.skills.router import (
    MAX_LOADED_SKILLS,
    MAX_SKILL_TOKENS,
    match_skill_ids,
    route_skills,
    skill_token_count,
)

pytestmark = pytest.mark.no_app_db


def _package(skill_id: str):
    return next(skill for skill in all_skills() if skill.skill_id == skill_id)


def _write_skill(root: Path, skill_id: str, body: str | None = None) -> Path:
    folder = root / skill_id
    folder.mkdir(parents=True)
    text = body if body is not None else _package(skill_id).markdown()
    (folder / "SKILL.md").write_text(text, encoding="utf-8")
    return folder


def test_router_drops_the_fourth_catalog_match() -> None:
    matched = match_skill_ids("configure")
    assert len(matched) >= 4
    caller = BotGrant(
        "studio",
        frozenset({"config_record.upsert", "setting.set", "stage.upsert", "module.install"}),
        "R2",
    )
    result = route_skills("configure", caller)
    assert result.skill_ids == matched[:MAX_LOADED_SKILLS]
    assert len(result.skill_ids) == 3
    assert result.dropped[0] == matched[3]
    assert matched[3] not in result.skill_ids
    catalog_ids = {skill.skill_id for skill in all_skills()}
    assert set(result.skill_ids).issubset(catalog_ids)
    assert set(result.dropped).issubset(catalog_ids)
    assert result.grant.ops_allowed <= caller.ops_allowed
    assert "module.install" not in result.grant.ops_allowed


def test_router_refuses_executable_skill_and_does_not_load(tmp_path: Path) -> None:
    caller = BotGrant("studio", frozenset({"field.create", "module.install"}), "R2")
    clean = route_skills("relational", caller)
    assert clean.skill_ids == ("SK-PLAT-FIELDS",)

    fenced = tmp_path / "fenced"
    poisoned = _package("SK-PLAT-FIELDS").markdown() + "\n```python\nprint(1)\n```\n"
    _write_skill(fenced, "SK-PLAT-FIELDS", poisoned)
    refused_fence = route_skills("relational", caller, packages_root=fenced)
    assert refused_fence.skill_ids == ()
    assert refused_fence.refused == ("SK-PLAT-FIELDS",)
    assert refused_fence.grant == caller

    tilde = tmp_path / "tilde"
    tilde_body = _package("SK-PLAT-FIELDS").markdown() + "\n~~~python\nprint(1)\n~~~\n"
    _write_skill(tilde, "SK-PLAT-FIELDS", tilde_body)
    refused_tilde = route_skills("relational", caller, packages_root=tilde)
    assert refused_tilde.skill_ids == ()
    assert refused_tilde.refused == ("SK-PLAT-FIELDS",)

    foreign = tmp_path / "foreign"
    _write_skill(foreign, "SK-PLAT-FIELDS")
    (foreign / "SK-PLAT-FIELDS" / "run.py").write_text("print(1)\n", encoding="utf-8")
    refused_file = route_skills("relational", caller, packages_root=foreign)
    assert refused_file.skill_ids == ()
    assert refused_file.refused == ("SK-PLAT-FIELDS",)
    assert refused_file.grant == caller

    notes = tmp_path / "notes"
    _write_skill(notes, "SK-PLAT-FIELDS")
    (notes / "SK-PLAT-FIELDS" / "notes.md").write_text("A markdown note.\n", encoding="utf-8")
    loaded = route_skills("relational", caller, packages_root=notes)
    assert loaded.skill_ids == ("SK-PLAT-FIELDS",)
    assert loaded.refused == ()


def test_router_grant_is_the_intersection_and_not_a_superset() -> None:
    caller = BotGrant("studio", frozenset({"field.create", "module.install"}), "R3")
    result = route_skills("relational", caller)
    skill_ops = frozenset(_package("SK-PLAT-FIELDS").ops_allowed)
    assert result.skill_ids == ("SK-PLAT-FIELDS",)
    assert result.grant.ops_allowed == frozenset({"field.create"})
    assert result.grant.ops_allowed <= caller.ops_allowed
    assert result.grant.ops_allowed < caller.ops_allowed
    assert skill_ops - caller.ops_allowed
    assert result.grant.ops_allowed.isdisjoint(skill_ops - caller.ops_allowed)
    assert "view.inherit.create" not in result.grant.ops_allowed
    assert "automation.create" not in result.grant.ops_allowed
    assert "module.install" not in result.grant.ops_allowed
    assert result.grant.risk_ceiling == caller.risk_ceiling
    assert result.grant.autonomy_cap == caller.autonomy_cap
    assert result.grant.bot_id == caller.bot_id
    assert result.grant.apps_allowed == caller.apps_allowed


def test_router_refuses_skill_markdown_over_the_token_cap(tmp_path: Path) -> None:
    caller = BotGrant("studio", frozenset({"field.create"}), "R2")
    base = _package("SK-PLAT-FIELDS").markdown()
    extra = "word " * 2000
    text = base + "\n" + extra
    assert skill_token_count(text) > MAX_SKILL_TOKENS
    assert "```" not in extra
    root = tmp_path / "long"
    _write_skill(root, "SK-PLAT-FIELDS", text)
    result = route_skills("relational", caller, packages_root=root)
    assert result.skill_ids == ()
    assert result.refused == ("SK-PLAT-FIELDS",)
    assert result.grant == caller


def test_skill_load_uses_the_router_and_does_not_widen() -> None:
    """The discover tool loads through the router and cannot add an op.

    Inputs: a caller grant that includes field.create and module.install.
    Outputs: none.
    Side effects: none. Does not call a model.
    """
    caller = BotGrant("studio", frozenset({"field.create", "module.install"}), "R3")
    runtime = AgentRuntime(grant=caller)
    state = runtime.start()
    runtime.complete_phase(state, "DISCOVER")
    body = json.loads(
        runtime.call_tool(state, "skill_load", {"phrase": "relational"})["untrusted_data"]
    )
    assert len(body["loaded"]) <= MAX_LOADED_SKILLS
    assert body["loaded"]
    assert set(body["ops"]) <= {"field.create"}
    assert "module.install" not in body["ops"]
