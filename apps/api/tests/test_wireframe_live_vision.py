"""Live photograph vision. Fake transport / fake provider. No sockets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.ai_apply_readiness import prepare_spec_for_live_apply
from app.llm_gateway.providers import DEFAULT_VISION_PROVIDER, FRONTIER_PROVIDER
from app.llm_provider import AnthropicProvider, GeminiProvider
from app.settings import settings
from app.wireframe.review import WireframeReviewRequired
from app.wireframe_live import clarify_uploaded_sketch, read_uploaded_photo, vision_status

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "wireframe"
_PHOTO = json.loads((_FIXTURES / "visitor_log_photo.json").read_text(encoding="utf-8"))
_UNLABELED = json.loads((_FIXTURES / "unlabeled_region.json").read_text(encoding="utf-8"))

pytestmark = pytest.mark.no_app_db


class _FakeVision:
    def __init__(self, name: str, payload: dict[str, Any]) -> None:
        self.name = name
        self.payload = payload
        self.calls = 0
        self.last: dict[str, Any] = {}

    def generate_json(self, prompt: str, **kwargs: Any) -> str:
        self.calls += 1
        self.last = {"prompt": prompt, **kwargs}
        return json.dumps(self.payload)


class _Resp:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = json.dumps(data).encode("utf-8")
        self.status = 200

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):  # noqa: ANN002
        return False


@pytest.fixture(autouse=True)
def _vision_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # noqa: ANN001
    # Own AI cache per test: the shared client caches by image hash, and must not reuse the real cache.
    monkeypatch.setenv("INGENIUM_AI_CACHE_PATH", str(tmp_path / "ai_cache.sqlite"))
    monkeypatch.setattr(settings, "gemini_backend", "studio")
    monkeypatch.setattr(settings, "ai_vision_provider", "")
    monkeypatch.setattr(settings, "gemini_api_key", "gem-test")
    monkeypatch.setattr(settings, "google_api_key", None)
    monkeypatch.setattr(settings, "anthropic_api_key", None)


def test_missing_gemini_key_does_not_invent_or_fall_through_to_claude(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "google_api_key", "")
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-present")
    claude = _FakeVision("anthropic", _PHOTO)
    monkeypatch.setattr("app.wireframe_live.AnthropicProvider", lambda **_k: claude)
    monkeypatch.setattr("app.llm_provider.AnthropicProvider", lambda **_k: claude)
    status = vision_status()
    assert status["connected"] is False
    assert status["provider"] == DEFAULT_VISION_PROVIDER
    assert "gemini" in status["message"].lower()
    outcome = read_uploaded_photo(b"fake-bytes", "image/jpeg")
    assert outcome["status"] == "not_connected"
    assert outcome["spec"] is None
    assert outcome["sketch"] is None
    assert outcome["apply_ready"] is False
    assert claude.calls == 0


def test_fake_gemini_photo_runs_stage_h_and_does_not_apply() -> None:
    fake = _FakeVision("gemini", _PHOTO)
    outcome = read_uploaded_photo(b"fake-bytes", "image/jpeg", provider=fake)
    assert fake.calls == 1
    assert fake.last.get("image_bytes") == b"fake-bytes"
    assert fake.last.get("mime_type") == "image/jpeg"
    assert outcome["status"] == "review"
    assert outcome["apply_ready"] is False
    assert outcome["spec"]["_wireframe"]["stage_h"] is True
    assert outcome["form_preview"]["model"] == "x_visitor_log"


def test_low_confidence_region_still_clarifies() -> None:
    fake = _FakeVision("gemini", _UNLABELED)
    outcome = read_uploaded_photo(b"fake-bytes", "image/png", provider=fake)
    assert outcome["status"] == "clarify"
    assert outcome["spec"] is None
    assert outcome["apply_ready"] is False
    clarified = clarify_uploaded_sketch(
        outcome["sketch"],
        merge_key="wireframe_region",
        answer_id="date",
        answer_text="Visit date",
    )
    assert clarified["status"] == "review"
    assert clarified["spec"]["_wireframe"]["stage_h"] is True


def test_unsigned_wireframe_spec_still_refused() -> None:
    fake = _FakeVision("gemini", _PHOTO)
    outcome = read_uploaded_photo(b"fake-bytes", "image/jpeg", provider=fake)
    unsigned = dict(outcome["spec"])
    unsigned["_wireframe"] = {**unsigned["_wireframe"], "stage_h": False}
    with pytest.raises(WireframeReviewRequired):
        prepare_spec_for_live_apply(unsigned)


def test_frontier_setting_selects_anthropic_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gemini = _FakeVision("gemini", _PHOTO)
    claude = _FakeVision("anthropic", _PHOTO)
    monkeypatch.setattr(settings, "ai_vision_provider", FRONTIER_PROVIDER)
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-test")
    monkeypatch.setattr("app.wireframe_live.GeminiProvider", lambda **_k: gemini)
    monkeypatch.setattr("app.wireframe_live.AnthropicProvider", lambda **_k: claude)
    from app.wireframe_live import get_vision_llm_provider

    from app.ai_client.shared_client import unwrap

    provider = get_vision_llm_provider()
    assert unwrap(provider) is claude  # served through the shared AI client
    outcome = read_uploaded_photo(b"frontier-bytes", "image/jpeg")
    assert claude.calls == 1
    assert gemini.calls == 0
    assert outcome["provider"] == FRONTIER_PROVIDER


def test_gemini_generate_json_adds_inline_image(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def _urlopen(req, timeout=120.0):  # noqa: ANN001, ARG002
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return _Resp({"candidates": [{"content": {"parts": [{"text": '{"ok":true}'}]}}]})

    # Ingenium runs Gemini on Vertex (generateContent payload with inline image).
    monkeypatch.setattr(settings, "gemini_backend", "vertex")
    monkeypatch.setattr(settings, "vertex_project", "ingenium-test")
    monkeypatch.setattr("app.llm_provider._vertex_access_token", lambda: "tok")
    monkeypatch.setattr("app.llm_provider.request.urlopen", _urlopen)
    out = GeminiProvider(api_key="gem-test").generate_json(
        "read",
        image_bytes=b"abc",
        mime_type="image/png",
    )
    assert out == '{"ok":true}'
    parts = captured["payload"]["contents"][0]["parts"]
    assert parts[0]["text"] == "read"
    assert parts[1]["inlineData"]["mimeType"] == "image/png"
    assert parts[1]["inlineData"]["data"]


def test_anthropic_generate_json_adds_image_block(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def _urlopen(req, timeout=120.0):  # noqa: ANN001, ARG002
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return _Resp({"content": [{"type": "text", "text": '{"ok":true}'}]})

    monkeypatch.setattr("app.llm_provider.request.urlopen", _urlopen)
    out = AnthropicProvider(api_key="sk-ant-test").generate_json(
        "read",
        image_bytes=b"abc",
        mime_type="image/jpeg",
    )
    assert out == '{"ok":true}'
    content = captured["payload"]["messages"][0]["content"]
    assert content[0]["type"] == "image"
    assert content[0]["source"]["media_type"] == "image/jpeg"
    assert content[1]["type"] == "text"


def test_vertex_backend_counts_as_connected_without_studio_key(monkeypatch: pytest.MonkeyPatch) -> None:
    gemini = _FakeVision("gemini", _PHOTO)
    monkeypatch.setattr(settings, "ai_vision_provider", None)
    monkeypatch.setattr(settings, "gemini_api_key", None)
    monkeypatch.setattr(settings, "google_api_key", None)
    monkeypatch.setattr(settings, "gemini_backend", "vertex")
    monkeypatch.setattr(settings, "vertex_project", "ingenium-test")
    monkeypatch.setattr("app.wireframe_live.GeminiProvider", lambda **_k: gemini)
    from app.ai_client.shared_client import unwrap
    from app.wireframe_live import get_vision_llm_provider

    provider = get_vision_llm_provider()
    assert unwrap(provider) is gemini  # Vertex Gemini, behind the shared AI client
    outcome = read_uploaded_photo(b"vertex-bytes", "image/jpeg")
    assert gemini.calls == 1
    assert outcome["status"] != "not_connected"
