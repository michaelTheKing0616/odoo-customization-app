"""Vertex AI route for the Gemini provider (fakes only, no network)."""
import io
import json
from urllib import error

import pytest

from app import llm_provider as lp
from app.ai_conversation.app_design import _fallback_reason
from app.settings import settings


class _Resp(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def vertex(monkeypatch):
    monkeypatch.setattr(settings, "gemini_backend", "vertex")
    monkeypatch.setattr(settings, "vertex_project", "")
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    seen = {}

    def fake(req, timeout=0):
        seen["url"], seen["body"], seen["hdr"] = req.full_url, json.loads(req.data), dict(req.headers)
        if seen.get("fail"):
            raise error.HTTPError(req.full_url, seen["fail"][0], "x", {}, io.BytesIO(seen["fail"][1].encode()))
        return _Resp(json.dumps({"candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}]}).encode())

    monkeypatch.setattr(lp.request, "urlopen", fake)
    return seen


def test_express_key_uses_global_generate_content(vertex):
    p = lp.GeminiProvider(api_key="k" * 53, model="gemini-3.6-flash")
    assert p.generate_json("hi", format_schema={"type": "object"}) == '{"ok": true}'
    assert vertex["url"].startswith("https://aiplatform.googleapis.com/v1/publishers/google/models/gemini-3.")
    assert vertex["url"].endswith(":generateContent")
    cfg = vertex["body"]["generationConfig"]
    assert cfg["maxOutputTokens"] == 32768 and cfg["responseMimeType"] == "application/json"
    assert cfg["thinkingConfig"] == {"thinkingLevel": "LOW"}
    assert "interactions" not in vertex["url"]


def test_service_account_uses_project_location(vertex, monkeypatch):
    monkeypatch.setattr(settings, "vertex_project", "proj-1")
    monkeypatch.setattr(settings, "vertex_location", "us-central1")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/sa.json")
    monkeypatch.setattr(lp, "_vertex_access_token", lambda: "tok")
    lp.GeminiProvider(api_key="", model="gemini-3.6-flash").generate_json("hi")  # no key -> bearer
    assert vertex["url"].startswith(
        "https://us-central1-aiplatform.googleapis.com/v1/projects/proj-1/locations/us-central1/publishers/google/models/")
    assert vertex["hdr"].get("Authorization") == "Bearer tok"


def test_project_key_uses_project_path_with_header(vertex, monkeypatch):
    monkeypatch.setattr(settings, "vertex_project", "139730550278")
    monkeypatch.setattr(settings, "vertex_location", "global")
    lp.GeminiProvider(api_key="k" * 53, model="gemini-3.8-flash").generate_json("hi")
    assert vertex["url"] == ("https://aiplatform.googleapis.com/v1/projects/139730550278/locations/global"
                             "/publishers/google/models/gemini-3.8-flash:generateContent")
    assert vertex["hdr"].get("X-goog-api-key") == "k" * 53 and "key=" not in vertex["url"]


@pytest.mark.parametrize("code,body,plain", [
    (403, "Agent Platform API has not been used in project 1 before or it is disabled", "isn't switched on"),
    (403, "This API method requires billing to be enabled", "Billing isn't turned on"),
])
def test_vertex_errors_are_plain(vertex, code, body, plain):
    vertex["fail"] = (code, json.dumps({"error": {"code": code, "message": body}}))
    with pytest.raises(lp.LLMError) as e:
        lp.GeminiProvider(api_key="k", model="gemini-3.6-flash").generate_json("hi")
    assert plain in str(e.value)
    assert plain.split()[0] in _fallback_reason({"status": "failed", "error": str(e.value)})


def test_studio_is_default(monkeypatch):
    monkeypatch.setattr(settings, "gemini_backend", "studio")
    assert not lp.GeminiProvider(api_key="k").is_vertex
