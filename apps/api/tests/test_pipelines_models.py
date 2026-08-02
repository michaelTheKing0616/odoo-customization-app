"""Pipeline model + hop gate unit tests (no Docker)."""

from __future__ import annotations

from app.db_models import EnvPipeline, PipelineHop


def test_pipeline_models_importable() -> None:
    assert EnvPipeline.__tablename__ == "env_pipelines"
    assert PipelineHop.__tablename__ == "pipeline_hops"
