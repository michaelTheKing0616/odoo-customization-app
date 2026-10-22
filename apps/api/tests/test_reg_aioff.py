"""Pin handover §2.7 / REG-AIOFF: AI_ASSIST off does not build the fast provider.

``_raw_provider_for_tier(tier="fast")`` with ``ai_assist="off"``:
  ``ai_llm_tier_fast="gemini"`` → None
  ``ai_llm_tier_fast="mock"`` → MockLLMProvider
"""

from __future__ import annotations

import pytest

from app.llm_provider import MockLLMProvider, _raw_provider_for_tier, resolve_provider_mode
from app.settings import Settings, settings

pytestmark = pytest.mark.no_app_db

# A configured key is what used to build Vertex while assist was off.
# Without it, the gemini branch returns None for a missing key, and deleting
# the off-guard (llm_provider.py, the `mode != "mock"` check) would stay green.
_DUMMY_GEMINI_KEY = "reg-aioff-dummy"


@pytest.mark.parametrize(
    ("ai_llm_tier_fast", "expected"),
    [
        pytest.param("gemini", None, id="gemini"),
        pytest.param("mock", MockLLMProvider, id="mock"),
    ],
)
def test_ac1_ai_assist_off_raw_provider_for_tier(
    monkeypatch: pytest.MonkeyPatch,
    ai_llm_tier_fast: str,
    expected: type[MockLLMProvider] | None,
) -> None:
    assert Settings.model_fields["ai_assist"].default == "off"
    assert Settings.model_fields["ai_llm_tier_fast"].default == "gemini"

    monkeypatch.setattr(settings, "ai_assist", "off")
    monkeypatch.setattr(settings, "ai_llm_tier_fast", ai_llm_tier_fast)
    monkeypatch.setattr(settings, "gemini_api_key", _DUMMY_GEMINI_KEY)
    monkeypatch.setattr(settings, "google_api_key", "")

    assert resolve_provider_mode() == "off"
    provider = _raw_provider_for_tier(tier="fast")
    if expected is None:
        assert provider is None
    else:
        assert isinstance(provider, expected)
