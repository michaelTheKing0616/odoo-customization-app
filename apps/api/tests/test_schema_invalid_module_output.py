"""PR-E: schema-invalid generated module output must be rejected in fast CI."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.no_app_db

from app import ai_ollama  # noqa: E402


def test_validate_draft_module_spec_rejects_schema_invalid_model_name() -> None:
    with pytest.raises(ValueError, match="x_"):
        ai_ollama.validate_draft_module_spec(
            {
                "technical_name": "ok_mod",
                "display_name": "Ok",
                "models": [{"model": "book", "fields": [{"name": "x_name"}]}],
            }
        )
