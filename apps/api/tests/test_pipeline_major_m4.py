"""Pipeline matching-major resolution (mastery M4)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.routers.environments import _pipeline_sandbox_major


def test_pipeline_sandbox_major_prefers_staging_version() -> None:
    pipeline = SimpleNamespace(
        staging_connection_id="stg",
        prod_connection_id="prd",
        sandbox_connection_id=None,
    )
    db = MagicMock()
    with patch(
        "app.routers.environments.get_connection_or_404",
        return_value=SimpleNamespace(server_version="18.0-20260101"),
    ):
        assert _pipeline_sandbox_major(db, pipeline) == 18


def test_pipeline_sandbox_major_falls_back_prod_then_19() -> None:
    pipeline = SimpleNamespace(
        staging_connection_id="stg",
        prod_connection_id="prd",
        sandbox_connection_id=None,
    )
    db = MagicMock()

    def _get(_db, cid):
        if cid == "stg":
            return SimpleNamespace(server_version=None)
        return SimpleNamespace(server_version="17.0")

    with patch("app.routers.environments.get_connection_or_404", side_effect=_get):
        assert _pipeline_sandbox_major(db, pipeline) == 17


def test_pipeline_sandbox_major_default_19() -> None:
    pipeline = SimpleNamespace(
        staging_connection_id=None,
        prod_connection_id=None,
        sandbox_connection_id=None,
    )
    assert _pipeline_sandbox_major(MagicMock(), pipeline) == 19
