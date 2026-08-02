"""LLM provider abstraction — ollama | openai-compatible (vLLM / LM Studio / OpenAI)."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any
from urllib import error, request

from app.settings import settings


class LLMError(Exception):
    """Provider unreachable, timeout, or empty response."""

    def __init__(self, message: str, *, status_code: int = 503) -> None:
        super().__init__(message)
        self.status_code = status_code


class LLMProvider(ABC):
    """Single interface so swapping models does not touch the draft pipeline."""

    @abstractmethod
    def generate_json(
        self,
        prompt: str,
        *,
        system: str | None = None,
        timeout_s: float = 120.0,
    ) -> str:
        """Return raw JSON text (object or array). Prefer grammar/json mode."""

    @abstractmethod
    def reachable(self, *, timeout_s: float = 2.0) -> tuple[bool, str]:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


class OllamaProvider(LLMProvider):
    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model

    @property
    def name(self) -> str:
        return "ollama"

    def reachable(self, *, timeout_s: float = 2.0) -> tuple[bool, str]:
        url = f"{self.base_url}/api/tags"
        req = request.Request(url, method="GET")
        try:
            with request.urlopen(req, timeout=timeout_s) as resp:
                if 200 <= getattr(resp, "status", 200) < 300:
                    return True, f"reachable {self.base_url} model={self.model}"
                return False, f"HTTP {getattr(resp, 'status', '?')}"
        except error.URLError as exc:
            return False, f"unreachable: {exc.reason}"
        except Exception as exc:  # noqa: BLE001
            return False, f"unreachable: {exc}"

    def generate_json(
        self,
        prompt: str,
        *,
        system: str | None = None,
        timeout_s: float = 120.0,
    ) -> str:
        url = f"{self.base_url}/api/generate"
        full = f"{system}\n\n{prompt}" if system else prompt
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": full,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2, "num_predict": 4096},
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=timeout_s) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            raise LLMError(f"Ollama HTTP {exc.code}: {exc.reason}") from exc
        except error.URLError as exc:
            raise LLMError(f"Ollama unreachable: {exc.reason}") from exc
        except TimeoutError as exc:
            raise LLMError("Ollama request timed out") from exc

        text = raw.get("response") if isinstance(raw, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise LLMError("Ollama returned an empty response", status_code=502)
        return text


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI chat completions API shape — vLLM, LM Studio, OpenAI, Groq, etc."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.base_url = (
            base_url or settings.openai_compatible_base_url or ""
        ).rstrip("/")
        self.model = model or settings.openai_compatible_model or "gpt-4o-mini"
        self.api_key = api_key if api_key is not None else settings.openai_compatible_api_key

    @property
    def name(self) -> str:
        return "openai-compatible"

    def reachable(self, *, timeout_s: float = 2.0) -> tuple[bool, str]:
        if not self.base_url:
            return False, "OPENAI_COMPATIBLE_BASE_URL empty"
        # Many servers expose /models; fall back to base URL HEAD-ish GET
        url = f"{self.base_url}/models"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = request.Request(url, method="GET", headers=headers)
        try:
            with request.urlopen(req, timeout=timeout_s) as resp:
                if 200 <= getattr(resp, "status", 200) < 300:
                    return True, f"reachable {self.base_url} model={self.model}"
                return False, f"HTTP {getattr(resp, 'status', '?')}"
        except Exception as exc:  # noqa: BLE001
            return False, f"unreachable: {exc}"

    def generate_json(
        self,
        prompt: str,
        *,
        system: str | None = None,
        timeout_s: float = 120.0,
    ) -> str:
        if not self.base_url:
            raise LLMError("OPENAI_COMPATIBLE_BASE_URL is not set")
        url = f"{self.base_url}/chat/completions"
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=timeout_s) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            raise LLMError(
                f"OpenAI-compatible HTTP {exc.code}: {exc.reason}"
            ) from exc
        except error.URLError as exc:
            raise LLMError(f"OpenAI-compatible unreachable: {exc.reason}") from exc
        except TimeoutError as exc:
            raise LLMError("OpenAI-compatible request timed out") from exc

        try:
            text = raw["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("Malformed chat completion response", status_code=502) from exc
        if not isinstance(text, str) or not text.strip():
            raise LLMError("Empty chat completion content", status_code=502)
        return text


def get_llm_provider() -> LLMProvider | None:
    """Return active provider or None when AI_ASSIST=off."""
    mode = settings.ai_assist.strip().lower()
    if mode in {"", "off", "false", "0", "none"}:
        return None
    if mode == "ollama":
        return OllamaProvider()
    if mode in {"openai", "openai-compatible", "openai_compatible", "vllm"}:
        return OpenAICompatibleProvider()
    # Unknown mode — treat as off
    return None


def ai_provider_enabled() -> bool:
    return get_llm_provider() is not None
