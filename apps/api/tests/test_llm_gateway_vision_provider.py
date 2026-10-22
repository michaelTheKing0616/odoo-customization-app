"""Vision provider port: Gemini default; Claude is one frontier setting."""

from __future__ import annotations

from app.llm_gateway.providers import (
    DEFAULT_VISION_PROVIDER,
    FRONTIER_PROVIDER,
    default_active_providers,
    vision_binding,
    vision_provider_name,
)


def _read_photo_binding(name: str | None = None):
    """Vision call site. Switching the name is the only change."""
    return vision_binding(name)


def test_default_vision_provider_is_gemini() -> None:
    assert DEFAULT_VISION_PROVIDER == "gemini"
    assert vision_provider_name() == DEFAULT_VISION_PROVIDER
    assert _read_photo_binding().name == "gemini"


def test_frontier_setting_selects_anthropic_and_nothing_else_changes() -> None:
    assert FRONTIER_PROVIDER == "anthropic"
    default_binding = _read_photo_binding()
    frontier_binding = _read_photo_binding(FRONTIER_PROVIDER)
    assert default_binding.name == "gemini"
    assert frontier_binding.name == FRONTIER_PROVIDER
    assert frontier_binding.name == "anthropic"
    assert FRONTIER_PROVIDER not in default_active_providers()
    assert "anthropic" not in default_active_providers()
