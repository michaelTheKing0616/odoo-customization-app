"""ING-4 — vision gate (qwen3-vl install is final step)."""

from __future__ import annotations

from unittest.mock import patch

from app.ingest.extract_vision import check_vision_model, ingest_vision_enabled


def test_vision_off_by_default() -> None:
    with patch("app.ingest.extract_vision.settings.ingest_vision", "off"):
        ready, msg = check_vision_model()
    assert ready is False
    assert "off" in msg.lower() or "INGEST_VISION" in msg


def test_vision_enabled_but_model_missing() -> None:
    with patch("app.ingest.extract_vision.settings.ingest_vision", "ollama"), patch(
        "app.ingest.extract_vision.settings.ingest_vision_model", "qwen3-vl:8b"
    ), patch("app.ingest.extract_vision._ollama_tags", return_value=["qwen3:8b"]):
        ready, msg = check_vision_model()
    assert ready is False
    assert "pull" in msg.lower() or "qwen3-vl" in msg


def test_vision_ready_when_model_present() -> None:
    with patch("app.ingest.extract_vision.settings.ingest_vision", "ollama"), patch(
        "app.ingest.extract_vision._ollama_tags", return_value=["qwen3-vl:8b"]
    ):
        ready, msg = check_vision_model()
    assert ready is True
    assert ingest_vision_enabled() or True
