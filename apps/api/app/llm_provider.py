"""LLM provider abstraction — ollama | openai-compatible (vLLM / LM Studio / OpenAI)."""

from __future__ import annotations

import json
import threading
from abc import ABC, abstractmethod
from typing import Any
from urllib import error, request

from app.settings import settings

_JSON_MARKER = "---JSON---"
_MANUAL_COT_PREFIX = (
    "Think step by step in plain text first. After your reasoning, output ONLY valid JSON "
    f"after a line containing exactly: {_JSON_MARKER}\n\n"
)

# Stable pipeline step schemas (Ollama `format` when supported — pydantic repair remains backstop)
FORMAT_SCHEMA_ENTITIES: dict[str, Any] = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "purpose": {"type": "string"},
            "is_workflow": {"type": "boolean"},
            "loop_role": {"type": "string"},
        },
        "required": ["name"],
    },
}

FORMAT_SCHEMA_FIELDS: dict[str, Any] = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "ttype": {"type": "string"},
            "string": {"type": "string"},
            "required": {"type": "boolean"},
            "selection": {"type": "string"},
            "relation": {"type": "string"},
        },
        "required": ["name", "ttype"],
    },
}

FORMAT_SCHEMA_RELATIONSHIPS: dict[str, Any] = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "model": {"type": "string"},
            "field": {"type": "string"},
            "ttype": {"type": "string"},
            "relation": {"type": "string"},
            "string": {"type": "string"},
        },
        "required": ["model", "field"],
    },
}

FORMAT_SCHEMA_WORKFLOW: dict[str, Any] = {
    "type": "object",
    "properties": {
        "states": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "value": {"type": "string"},
                    "label": {"type": "string"},
                },
                "required": ["value"],
            },
        },
        "transitions": {
            "type": "array",
            "items": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 2,
                "maxItems": 2,
            },
        },
    },
    "required": ["states", "transitions"],
}

FORMAT_SCHEMA_AUTOMATIONS: dict[str, Any] = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "model": {"type": "string"},
            "trigger": {"type": "string"},
            "description": {"type": "string"},
            "filter_domain": {"type": "string"},
            "safe_actions": {"type": "array"},
        },
        "required": ["name", "model"],
    },
}

_caps_lock = threading.Lock()
_caps_cache: dict[str, dict[str, Any]] = {}


class LLMError(Exception):
    """Provider unreachable, timeout, or empty response."""

    def __init__(self, message: str, *, status_code: int = 503) -> None:
        super().__init__(message)
        self.status_code = status_code


def resolve_bulk_model() -> str:
    bulk = (settings.ai_model_bulk or "").strip()
    if bulk:
        return bulk
    mode = settings.ai_assist.strip().lower()
    if mode in {"openai", "openai-compatible", "openai_compatible", "vllm"}:
        return settings.openai_compatible_model or "gpt-4o-mini"
    return settings.ollama_model


def resolve_reasoning_model() -> str:
    reasoning = (settings.ai_model_reasoning or "").strip()
    if reasoning:
        return reasoning
    return resolve_bulk_model()


def resolve_thinking_enabled(*, reasoning: bool, model_supports_think: bool) -> bool:
    if not reasoning:
        return False
    mode = (settings.ai_thinking or "auto").strip().lower()
    if mode == "off":
        return False
    if mode == "on":
        return model_supports_think
    # auto — only when model advertises native thinking
    return model_supports_think


def strip_thinking_trace(text: str) -> str:
    """Discard CoT / thinking traces before JSON extraction."""
    if _JSON_MARKER in text:
        return text.split(_JSON_MARKER, 1)[1].strip()
    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        return stripped
    # Model returned prose then JSON without the marker — slice from first object/array.
    for i, ch in enumerate(stripped):
        if ch in "{[":
            return stripped[i:].strip()
    return stripped


def _http_json(
    url: str,
    payload: dict[str, Any] | None,
    *,
    method: str = "GET",
    timeout_s: float = 5.0,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers=hdrs, method=method)
    with request.urlopen(req, timeout=timeout_s) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    return raw if isinstance(raw, dict) else {}


def probe_ollama_capabilities(
    *,
    base_url: str | None = None,
    model: str | None = None,
    timeout_s: float = 8.0,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Probe installed Ollama for think + JSON-schema format support (cached per base/model)."""
    base = (base_url or settings.ollama_base_url).rstrip("/")
    mdl = model or resolve_bulk_model()
    cache_key = f"{base}|{mdl}"
    with _caps_lock:
        if not force_refresh and cache_key in _caps_cache:
            return dict(_caps_cache[cache_key])

    result: dict[str, Any] = {
        "ollama_version": None,
        "model": mdl,
        "think_param": "think",
        "think_supported": False,
        "think_detail": "not probed",
        "schema_format_supported": False,
        "schema_format_detail": "not probed",
        "manual_cot_fallback": True,
    }
    try:
        ver = _http_json(f"{base}/api/version", None, timeout_s=2.0)
        result["ollama_version"] = ver.get("version")
    except Exception as exc:  # noqa: BLE001
        result["think_detail"] = f"version probe failed: {exc}"
        result["schema_format_detail"] = result["think_detail"]
        with _caps_lock:
            _caps_cache[cache_key] = dict(result)
        return result

    # Native thinking (Ollama 0.31+ — param name `think` on /api/generate)
    try:
        think_raw = _http_json(
            f"{base}/api/generate",
            {
                "model": mdl,
                "prompt": "What is 2+2? Answer briefly.",
                "stream": False,
                "think": True,
                "options": {"num_predict": 32},
            },
            method="POST",
            timeout_s=timeout_s,
        )
        if think_raw.get("error"):
            err = str(think_raw["error"])
            result["think_detail"] = err
            result["think_supported"] = False
        else:
            result["think_supported"] = True
            result["think_detail"] = "native think=true accepted"
            if think_raw.get("thinking"):
                result["think_detail"] += " (thinking field returned)"
    except Exception as exc:  # noqa: BLE001
        result["think_detail"] = f"think probe failed: {exc}"

    # JSON schema in `format` (not just literal "json")
    try:
        schema_raw = _http_json(
            f"{base}/api/generate",
            {
                "model": mdl,
                "prompt": 'Return {"name":"probe"} only.',
                "stream": False,
                "format": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
                "options": {"num_predict": 24},
            },
            method="POST",
            timeout_s=timeout_s,
        )
        if schema_raw.get("error"):
            result["schema_format_detail"] = str(schema_raw["error"])
        else:
            resp = schema_raw.get("response") or ""
            parsed = json.loads(resp) if isinstance(resp, str) and resp.strip() else {}
            if isinstance(parsed, dict) and "name" in parsed:
                result["schema_format_supported"] = True
                result["schema_format_detail"] = "object schema in format accepted"
            else:
                result["schema_format_detail"] = f"unexpected response: {resp!r:.120}"
    except Exception as exc:  # noqa: BLE001
        result["schema_format_detail"] = f"schema probe failed: {exc}"

    result["manual_cot_fallback"] = not result["think_supported"]
    with _caps_lock:
        _caps_cache[cache_key] = dict(result)
    return result


def llm_routing_status() -> dict[str, Any]:
    """Status blob for /api/ai/status — models, thinking mode, capability probes."""
    mode = settings.ai_assist.strip().lower()
    bulk = resolve_bulk_model()
    reasoning = resolve_reasoning_model()
    thinking_mode = (settings.ai_thinking or "auto").strip().lower()
    out: dict[str, Any] = {
        "ai_model_bulk": bulk,
        "ai_model_reasoning": reasoning,
        "ai_thinking": thinking_mode,
        "model_fallback": settings.ollama_model
        if mode == "ollama"
        else settings.openai_compatible_model,
    }
    if mode == "ollama":
        caps_bulk = probe_ollama_capabilities(model=bulk)
        caps_reason = (
            probe_ollama_capabilities(model=reasoning)
            if reasoning != bulk
            else caps_bulk
        )
        out["ollama_capabilities"] = {
            "bulk": caps_bulk,
            "reasoning": caps_reason,
        }
        out["schema_in_format_active"] = bool(caps_bulk.get("schema_format_supported"))
        out["thinking_native_supported"] = {
            "bulk_model": bool(caps_bulk.get("think_supported")),
            "reasoning_model": bool(caps_reason.get("think_supported")),
        }
    else:
        out["ollama_capabilities"] = None
        out["schema_in_format_active"] = False
        out["thinking_native_supported"] = {"bulk_model": False, "reasoning_model": False}
    return out


class LLMProvider(ABC):
    """Single interface so swapping models does not touch the draft pipeline."""

    @abstractmethod
    def generate_json(
        self,
        prompt: str,
        *,
        system: str | None = None,
        timeout_s: float = 120.0,
        reasoning: bool = False,
        temperature: float | None = None,
        format_schema: dict[str, Any] | None = None,
        model: str | None = None,
    ) -> str:
        """Return raw JSON text (object or array). Thinking traces are stripped."""

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
        self.model = model or resolve_bulk_model()

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
        reasoning: bool = False,
        temperature: float | None = None,
        format_schema: dict[str, Any] | None = None,
        model: str | None = None,
        num_predict: int | None = None,
    ) -> str:
        chosen = model or (resolve_reasoning_model() if reasoning else resolve_bulk_model())
        caps = probe_ollama_capabilities(base_url=self.base_url, model=chosen)
        use_think = resolve_thinking_enabled(
            reasoning=reasoning,
            model_supports_think=bool(caps.get("think_supported")),
        )
        # Native thinking + JSON schema often yields an empty `response` on Ollama.
        if format_schema and use_think:
            use_think = False
        user_prompt = prompt
        # Manual CoT + schema is similarly unreliable — rely on schema-only JSON.
        if reasoning and not use_think and not format_schema:
            user_prompt = _MANUAL_COT_PREFIX + prompt

        url = f"{self.base_url}/api/generate"
        full = f"{system}\n\n{user_prompt}" if system else user_prompt
        temp = 0.2 if temperature is None else temperature
        fmt: Any = "json"
        if format_schema and caps.get("schema_format_supported"):
            fmt = format_schema

        payload: dict[str, Any] = {
            "model": chosen,
            "prompt": full,
            "stream": False,
            "format": fmt,
            "options": {"temperature": temp, "num_predict": num_predict or 4096},
        }
        alive = (settings.ollama_keep_alive or "").strip()
        if alive:
            payload["keep_alive"] = alive
        if use_think:
            payload["think"] = True

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

        if isinstance(raw, dict) and raw.get("error"):
            raise LLMError(str(raw["error"]), status_code=502)

        text = raw.get("response") if isinstance(raw, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise LLMError("Ollama returned an empty response", status_code=502)
        # Native thinking lives in `thinking`; manual CoT uses ---JSON--- marker
        return strip_thinking_trace(text)


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
        reasoning: bool = False,
        temperature: float | None = None,
        format_schema: dict[str, Any] | None = None,
        model: str | None = None,
    ) -> str:
        if not self.base_url:
            raise LLMError("OPENAI_COMPATIBLE_BASE_URL is not set")
        chosen = model or (resolve_reasoning_model() if reasoning else resolve_bulk_model())
        user_content = prompt
        if reasoning:
            user_content = _MANUAL_COT_PREFIX + prompt

        url = f"{self.base_url}/chat/completions"
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user_content})
        temp = 0.2 if temperature is None else temperature
        payload: dict[str, Any] = {
            "model": chosen,
            "messages": messages,
            "temperature": temp,
            "response_format": {"type": "json_object"},
        }
        if reasoning:
            payload["reasoning_effort"] = "medium"
        if format_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "step_output",
                    "schema": format_schema,
                    "strict": False,
                },
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
        return strip_thinking_trace(text)


def generate_json_with_timeout_retry(
    provider: LLMProvider,
    prompt: str,
    *,
    system: str | None = None,
    timeout_s: float = 120.0,
    reasoning: bool = False,
    temperature: float | None = None,
    format_schema: dict[str, Any] | None = None,
    model: str | None = None,
) -> str:
    """Retry once with smaller ctx/model on timeout before callers fall back to seeds."""
    try:
        return provider.generate_json(
            prompt,
            system=system,
            timeout_s=timeout_s,
            reasoning=reasoning,
            temperature=temperature,
            format_schema=format_schema,
            model=model,
        )
    except LLMError as exc:
        msg = str(exc).lower()
        if "timed out" not in msg and "timeout" not in msg:
            raise
        retry_model = resolve_bulk_model()
        kwargs: dict[str, Any] = {
            "prompt": prompt,
            "system": system,
            "timeout_s": max(60.0, timeout_s * 0.75),
            "reasoning": False,
            "temperature": temperature,
            "format_schema": format_schema,
            "model": retry_model,
        }
        if isinstance(provider, OllamaProvider):
            kwargs["num_predict"] = 2048
        return provider.generate_json(**kwargs)


def get_llm_provider() -> LLMProvider | None:
    """Return active provider or None when AI_ASSIST=off."""
    mode = settings.ai_assist.strip().lower()
    if mode in {"", "off", "false", "0", "none"}:
        return None
    if mode == "ollama":
        return OllamaProvider()
    if mode in {"openai", "openai-compatible", "openai_compatible", "vllm"}:
        return OpenAICompatibleProvider()
    return None


def ai_provider_enabled() -> bool:
    return get_llm_provider() is not None
