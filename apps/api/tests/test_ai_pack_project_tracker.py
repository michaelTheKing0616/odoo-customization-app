"""Project tracker pack retrieval + merge tests."""

from __future__ import annotations

from app.ai_domain_pack_law_firm import scaffold_teaching_blob
from app.ai_domain_pack_project_tracker import project_tracker_pack
from app.ai_domain_packs import merge_domain_pack, retrieve_domain_pack_lexical


def test_project_tracker_pack_uses_canonical_names() -> None:
    pack = project_tracker_pack()
    ids = {m["model"] for m in pack["models"] if isinstance(m, dict)}
    assert "x_project" in ids
    assert "x_task" in ids
    assert "x_milestone" in ids
    assert "x_time_entry" in ids
    assert "x_team_member" in ids
    task = next(m for m in pack["models"] if m["model"] == "x_task")
    assignee = next(f for f in task["fields"] if f["name"] == "x_assignee_id")
    assert assignee["relation"] == "x_team_member"
    member = next(m for m in pack["models"] if m["model"] == "x_team_member")
    assert next(f for f in member["fields"] if f["name"] == "x_user_id")["relation"] == "res.users"


def test_retrieve_project_tracker_from_prompt() -> None:
    hit = retrieve_domain_pack_lexical(
        "Project management tracker with tasks, milestones, and time entry logging"
    )
    assert hit is not None
    pack_id, pack, score = hit
    assert pack_id == "project_tracker"
    assert score >= 0.99
    assert pack.get("domain_pack") == "project_tracker"


def test_project_tracker_teaching_blob_depth() -> None:
    blob = scaffold_teaching_blob(project_tracker_pack())
    assert "x_project" in blob
    assert "x_task" in blob
    assert "('specialty_a'" not in blob


def test_merge_deepens_thin_project_task() -> None:
    thin = {
        "models": [
            {
                "model": "x_task",
                "fields": [{"name": "x_name", "ttype": "char"}],
            }
        ]
    }
    merged, notes = merge_domain_pack(thin, project_tracker_pack())
    task = next(m for m in merged["models"] if m["model"] == "x_task")
    names = {f.get("name") for f in task["fields"]}
    assert "x_status" in names
    assert "x_project_id" in names
    assert any("domain pack added field" in n for n in notes)
