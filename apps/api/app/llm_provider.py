"""LLM provider abstraction — ollama | openai | claude | gemini | openai-compatible."""

from __future__ import annotations

import json
import re
import threading
import time
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

OPENAI_DEFAULT_BASE = "https://api.openai.com/v1"
ANTHROPIC_DEFAULT_BASE = "https://api.anthropic.com"
GEMINI_DEFAULT_BASE = "https://generativelanguage.googleapis.com/v1beta"
ANTHROPIC_VERSION = "2023-06-01"

_PROVIDER_ALIASES: dict[str, str] = {
    "openai": "openai",
    "claude": "anthropic",
    "anthropic": "anthropic",
    "gemini": "gemini",
    "google": "gemini",
    "openai-compatible": "openai-compatible",
    "openai_compatible": "openai-compatible",
    "vllm": "openai-compatible",
    "ollama": "ollama",
}

_PROVIDER_DEFAULT_MODELS: dict[str, tuple[str, str]] = {
    # (bulk, reasoning) — override with AI_MODEL_BULK / AI_MODEL_REASONING or provider MODEL env
    "openai": ("gpt-4.1", "gpt-4.1"),
    "anthropic": ("claude-sonnet-4-5", "claude-sonnet-4-5"),
    "gemini": ("gemini-2.5-flash", "gemini-2.5-flash"),
    "openai-compatible": ("gpt-4o-mini", "gpt-4o-mini"),
    "ollama": ("qwen3:8b", "qwen3:8b"),
}


class LLMError(Exception):
    """Provider unreachable, timeout, or empty response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 503,
        retry_after_s: float | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after_s = retry_after_s


def resolve_provider_mode() -> str:
    """Canonical provider id: off | ollama | openai | anthropic | gemini | openai-compatible."""
    raw = settings.ai_assist.strip().lower()
    if raw in {"", "off", "false", "0", "none"}:
        return "off"
    if raw == "auto":
        if (settings.anthropic_api_key or "").strip():
            return "anthropic"
        if (settings.openai_api_key or "").strip():
            return "openai"
        if settings.resolved_gemini_api_key():
            return "gemini"
        if (settings.openai_compatible_api_key or "").strip() and (
            settings.openai_compatible_base_url or ""
        ).strip():
            return "openai-compatible"
        return "off"
    return _PROVIDER_ALIASES.get(raw, "off")


def _supports_openai_reasoning_effort(name: str) -> bool:
    n = (name or "").strip().lower()
    return n.startswith(("o1", "o3", "o4", "gpt-5")) or "reasoning" in n


def _looks_like_ollama_model(name: str) -> bool:
    n = (name or "").strip().lower()
    if not n:
        return False
    if n.startswith(("gpt-", "o1", "o3", "o4", "chatgpt-", "claude-", "gemini-")):
        return False
    if ":" in n:
        return True
    return n.startswith(("qwen", "llama", "mistral", "phi", "gemma", "deepseek-r1"))


def _ollama_local_model(requested: str | None = None) -> str:
    """Tag Ollama actually serves. Never POST gemini-/gpt-/claude- bulk ids to /api/generate."""
    for name in (
        (requested or "").strip(),
        (settings.ollama_model or "").strip(),
        "qwen3:8b",
    ):
        if name and _looks_like_ollama_model(name):
            return name
    return "qwen3:8b"


_FAMILY_PREFIXES: dict[str, tuple[str, ...]] = {
    "openai": ("gpt-", "o1", "o3", "o4", "chatgpt-"),
    "anthropic": ("claude-",),
    "gemini": ("gemini-",),
}


def _chosen_cloud_model(
    instance_model: str,
    *,
    model: str | None,
    reasoning: bool,
    family: str,
) -> str:
    if model:
        return model
    chosen = resolve_reasoning_model() if reasoning else resolve_bulk_model()
    if _looks_like_ollama_model(chosen):
        return instance_model
    prefixes = _FAMILY_PREFIXES.get(family, ())
    if prefixes and not chosen.lower().startswith(prefixes):
        return instance_model
    return chosen


def _provider_default_model(mode: str, *, reasoning: bool) -> str:
    if mode == "openai":
        return (settings.openai_model or "").strip() or _PROVIDER_DEFAULT_MODELS["openai"][1 if reasoning else 0]
    if mode == "anthropic":
        return (settings.anthropic_model or "").strip() or _PROVIDER_DEFAULT_MODELS["anthropic"][1 if reasoning else 0]
    if mode == "gemini":
        return (settings.gemini_model or "").strip() or _PROVIDER_DEFAULT_MODELS["gemini"][1 if reasoning else 0]
    if mode == "openai-compatible":
        return (settings.openai_compatible_model or "").strip() or "gpt-4o-mini"
    if mode == "ollama":
        return (settings.ollama_model or "").strip() or "qwen3:8b"
    return "qwen3:8b"


def resolve_bulk_model() -> str:
    mode = resolve_provider_mode()
    bulk = (settings.ai_model_bulk or "").strip()
    default = _provider_default_model(mode, reasoning=False)
    if bulk and not (mode not in {"ollama", "off"} and _looks_like_ollama_model(bulk)):
        return bulk
    return default


def resolve_reasoning_model() -> str:
    mode = resolve_provider_mode()
    reasoning = (settings.ai_model_reasoning or "").strip()
    default = _provider_default_model(mode, reasoning=True)
    if reasoning and not (
        mode not in {"ollama", "off"} and _looks_like_ollama_model(reasoning)
    ):
        return reasoning
    bulk = resolve_bulk_model()
    if mode in {"ollama", "off"}:
        return bulk
    return default


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


def _http_error_detail(exc: error.HTTPError) -> str:
    extra = ""
    try:
        extra = exc.read().decode("utf-8")[:400]
    except Exception:  # noqa: BLE001
        extra = ""
    return extra or str(exc.reason)


_RETRY_AFTER_HEADER_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*$")
_RETRY_DELAY_RE = re.compile(
    r"retryDelay[\"']?\s*[:=]\s*[\"']?(\d+(?:\.\d+)?)\s*s",
    re.I,
)
_RETRY_IN_RE = re.compile(
    r"retry in (\d+(?:\.\d+)?)\s*(?:s|sec|seconds)?",
    re.I,
)


def _retry_after_seconds(exc: error.HTTPError, detail: str = "") -> float | None:
    headers = getattr(exc, "headers", None)
    raw = ""
    if headers is not None:
        raw = str(headers.get("Retry-After") or headers.get("retry-after") or "")
    match = _RETRY_AFTER_HEADER_RE.match(raw)
    if match:
        return float(match.group(1))
    blob = f"{raw} {detail}"
    found = _RETRY_DELAY_RE.search(blob) or _RETRY_IN_RE.search(blob)
    if found:
        return float(found.group(1))
    return None


def _raise_http_llm_error(label: str, exc: error.HTTPError) -> None:
    detail = _http_error_detail(exc)
    code = int(exc.code)
    upper = (detail or "").upper()
    if code == 429 or "RESOURCE_EXHAUSTED" in upper:
        code = 429
    raise LLMError(
        f"{label} HTTP {exc.code}: {detail}",
        status_code=code,
        retry_after_s=_retry_after_seconds(exc, detail),
    ) from exc


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
    mode = resolve_provider_mode()
    bulk = resolve_bulk_model()
    reasoning = resolve_reasoning_model()
    thinking_mode = (settings.ai_thinking or "auto").strip().lower()
    out: dict[str, Any] = {
        "ai_assist": settings.ai_assist,
        "provider": mode,
        "ai_model_bulk": bulk,
        "ai_model_reasoning": reasoning,
        "ai_thinking": thinking_mode,
        "model_fallback": _provider_default_model(mode, reasoning=False) if mode != "off" else None,
        "api_key_configured": _api_key_configured(mode),
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


def _api_key_configured(mode: str) -> bool:
    if mode == "openai":
        return bool((settings.openai_api_key or settings.openai_compatible_api_key or "").strip())
    if mode == "anthropic":
        return bool((settings.anthropic_api_key or "").strip())
    if mode == "gemini":
        return bool(settings.resolved_gemini_api_key())
    if mode == "openai-compatible":
        return bool((settings.openai_compatible_api_key or "").strip())
    if mode == "ollama":
        return True
    return False


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

    def generate_text(
        self,
        prompt: str,
        *,
        system: str | None = None,
        timeout_s: float = 120.0,
        temperature: float | None = None,
        model: str | None = None,
    ) -> str:
        """Plain-text generation for conversational clarify/refine (default: JSON path)."""
        return self.generate_json(
            prompt,
            system=system or "Reply in concise plain text.",
            timeout_s=timeout_s,
            temperature=temperature,
            model=model,
            format_schema=None,
            reasoning=False,
        )


class OllamaProvider(LLMProvider):
    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = _ollama_local_model(model)

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
        chosen = _ollama_local_model(
            model or (resolve_reasoning_model() if reasoning else resolve_bulk_model())
        )
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
            raise LLMError(
                f"Ollama HTTP {exc.code}: {exc.reason}",
                status_code=int(exc.code),
            ) from exc
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

    def generate_text(
        self,
        prompt: str,
        *,
        system: str | None = None,
        timeout_s: float = 120.0,
        temperature: float | None = None,
        model: str | None = None,
    ) -> str:
        chosen = _ollama_local_model(model or resolve_bulk_model())
        url = f"{self.base_url}/api/generate"
        full = f"{system}\n\n{prompt}" if system else prompt
        temp = 0.2 if temperature is None else temperature
        payload: dict[str, Any] = {
            "model": chosen,
            "prompt": full,
            "stream": False,
            "options": {"temperature": temp, "num_predict": 2048},
        }
        alive = (settings.ollama_keep_alive or "").strip()
        if alive:
            payload["keep_alive"] = alive
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=timeout_s) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        text = raw.get("response") if isinstance(raw, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise LLMError("Ollama returned an empty response", status_code=502)
        return strip_thinking_trace(text)


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI chat completions API shape — OpenAI, vLLM, LM Studio, Groq, xAI."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        provider_name: str = "openai-compatible",
    ) -> None:
        self.base_url = (
            base_url or settings.openai_compatible_base_url or ""
        ).rstrip("/")
        self.model = model or settings.openai_compatible_model or "gpt-4o-mini"
        self.api_key = api_key if api_key is not None else settings.openai_compatible_api_key
        self._provider_name = provider_name

    @property
    def name(self) -> str:
        return self._provider_name

    def reachable(self, *, timeout_s: float = 2.0) -> tuple[bool, str]:
        if not self.base_url:
            return False, (
                "OPENAI_API_KEY empty"
                if self._provider_name == "openai"
                else "OPENAI_COMPATIBLE_BASE_URL empty"
            )
        if self._provider_name == "openai" and not (self.api_key or "").strip():
            return False, "OPENAI_API_KEY empty"
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
            raise LLMError(
                "OPENAI_API_KEY is not set"
                if self._provider_name == "openai"
                else "OPENAI_COMPATIBLE_BASE_URL is not set"
            )
        if self._provider_name == "openai" and not (self.api_key or "").strip():
            raise LLMError("OPENAI_API_KEY is not set")
        if self._provider_name == "openai":
            chosen = _chosen_cloud_model(
                self.model, model=model, reasoning=reasoning, family="openai"
            )
        else:
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
        if reasoning and (
            self._provider_name != "openai" or _supports_openai_reasoning_effort(chosen)
        ):
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
                f"{self.name} HTTP {exc.code}: {_http_error_detail(exc)}"
            ) from exc
        except error.URLError as exc:
            raise LLMError(f"{self.name} unreachable: {exc.reason}") from exc
        except TimeoutError as exc:
            raise LLMError(f"{self.name} request timed out") from exc

        try:
            text = raw["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("Malformed chat completion response", status_code=502) from exc
        if not isinstance(text, str) or not text.strip():
            raise LLMError("Empty chat completion content", status_code=502)
        return strip_thinking_trace(text)

    def generate_text(
        self,
        prompt: str,
        *,
        system: str | None = None,
        timeout_s: float = 120.0,
        temperature: float | None = None,
        model: str | None = None,
    ) -> str:
        if self._provider_name == "openai" and not (self.api_key or "").strip():
            raise LLMError("OPENAI_API_KEY is not set")
        chosen = model or (resolve_bulk_model() if self._provider_name != "openai" else self.model)
        if self._provider_name == "openai":
            chosen = _chosen_cloud_model(self.model, model=model, reasoning=False, family="openai")
        url = f"{self.base_url}/chat/completions"
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        temp = 0.2 if temperature is None else temperature
        payload: dict[str, Any] = {
            "model": chosen,
            "messages": messages,
            "temperature": temp,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=body, headers=headers, method="POST")
        with request.urlopen(req, timeout=timeout_s) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        text = raw["choices"][0]["message"]["content"]
        if not isinstance(text, str) or not text.strip():
            raise LLMError("Empty chat completion content", status_code=502)
        return strip_thinking_trace(text)


class AnthropicProvider(LLMProvider):
    """Anthropic Messages API (Claude)."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.api_key = (api_key if api_key is not None else settings.anthropic_api_key) or ""
        self.model = model or (settings.anthropic_model or "").strip() or "claude-sonnet-4-5"
        self.base_url = (base_url or ANTHROPIC_DEFAULT_BASE).rstrip("/")

    @property
    def name(self) -> str:
        return "anthropic"

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        }

    def reachable(self, *, timeout_s: float = 2.0) -> tuple[bool, str]:
        if not self.api_key.strip():
            return False, "ANTHROPIC_API_KEY empty"
        req = request.Request(
            f"{self.base_url}/v1/models",
            method="GET",
            headers=self._headers(),
        )
        try:
            with request.urlopen(req, timeout=timeout_s) as resp:
                if 200 <= getattr(resp, "status", 200) < 300:
                    return True, f"reachable Anthropic model={self.model}"
                return False, f"HTTP {getattr(resp, 'status', '?')}"
        except error.HTTPError as exc:
            return False, f"HTTP {exc.code}: {_http_error_detail(exc)}"
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
        if not self.api_key.strip():
            raise LLMError("ANTHROPIC_API_KEY is not set")
        chosen = _chosen_cloud_model(
            self.model, model=model, reasoning=reasoning, family="anthropic"
        )
        user_content = prompt
        if reasoning:
            user_content = _MANUAL_COT_PREFIX + prompt
        sys_parts = [system or "", "Respond with valid JSON only. No markdown fences."]
        if format_schema:
            sys_parts.append("Match this JSON schema: " + json.dumps(format_schema)[:2000])
        payload: dict[str, Any] = {
            "model": chosen,
            "max_tokens": 16384 if reasoning else 8192,
            "temperature": 0.2 if temperature is None else temperature,
            "system": "\n\n".join(p for p in sys_parts if p).strip(),
            "messages": [{"role": "user", "content": user_content}],
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/v1/messages",
            data=body,
            headers=self._headers(),
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=timeout_s) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            raise LLMError(f"Anthropic HTTP {exc.code}: {_http_error_detail(exc)}") from exc
        except error.URLError as exc:
            raise LLMError(f"Anthropic unreachable: {exc.reason}") from exc
        except TimeoutError as exc:
            raise LLMError("Anthropic request timed out") from exc
        blocks = raw.get("content") if isinstance(raw, dict) else None
        if not isinstance(blocks, list):
            raise LLMError("Malformed Anthropic response", status_code=502)
        text = "".join(
            str(b.get("text") or "")
            for b in blocks
            if isinstance(b, dict) and b.get("type") == "text"
        )
        if not text.strip():
            raise LLMError("Empty Anthropic content", status_code=502)
        return strip_thinking_trace(text)

    def generate_text(
        self,
        prompt: str,
        *,
        system: str | None = None,
        timeout_s: float = 120.0,
        temperature: float | None = None,
        model: str | None = None,
    ) -> str:
        if not self.api_key.strip():
            raise LLMError("ANTHROPIC_API_KEY is not set")
        chosen = _chosen_cloud_model(self.model, model=model, reasoning=False, family="anthropic")
        payload: dict[str, Any] = {
            "model": chosen,
            "max_tokens": 4096,
            "temperature": 0.2 if temperature is None else temperature,
            "system": system or "",
            "messages": [{"role": "user", "content": prompt}],
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/v1/messages",
            data=body,
            headers=self._headers(),
            method="POST",
        )
        with request.urlopen(req, timeout=timeout_s) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        blocks = raw.get("content") if isinstance(raw, dict) else None
        text = "".join(
            str(b.get("text") or "")
            for b in (blocks or [])
            if isinstance(b, dict) and b.get("type") == "text"
        )
        if not text.strip():
            raise LLMError("Empty Anthropic content", status_code=502)
        return strip_thinking_trace(text)


class GeminiProvider(LLMProvider):
    """Google Gemini generateContent API."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.api_key = (
            api_key if api_key is not None else settings.resolved_gemini_api_key()
        ) or ""
        self.model = model or (settings.gemini_model or "").strip() or "gemini-2.5-flash"
        self.base_url = (base_url or GEMINI_DEFAULT_BASE).rstrip("/")

    @property
    def name(self) -> str:
        return "gemini"

    def _headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json", "x-goog-api-key": self.api_key}

    def reachable(self, *, timeout_s: float = 2.0) -> tuple[bool, str]:
        if not self.api_key.strip():
            return False, "GEMINI_API_KEY empty"
        url = f"{self.base_url}/models"
        req = request.Request(url, method="GET", headers=self._headers())
        try:
            with request.urlopen(req, timeout=timeout_s) as resp:
                if 200 <= getattr(resp, "status", 200) < 300:
                    return True, f"reachable Gemini model={self.model}"
                return False, f"HTTP {getattr(resp, 'status', '?')}"
        except error.HTTPError as exc:
            return False, f"HTTP {exc.code}: {_http_error_detail(exc)}"
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
        if not self.api_key.strip():
            raise LLMError("GEMINI_API_KEY is not set")
        chosen = _chosen_cloud_model(
            self.model, model=model, reasoning=reasoning, family="gemini"
        )
        user_content = prompt
        if reasoning:
            user_content = _MANUAL_COT_PREFIX + prompt
        sys_text = system or ""
        if sys_text:
            sys_text += "\nRespond with valid JSON only."
        else:
            sys_text = "Respond with valid JSON only."
        gen_cfg: dict[str, Any] = {
            "temperature": 0.2 if temperature is None else temperature,
            "responseMimeType": "application/json",
            "maxOutputTokens": 16384,
        }
        _ = format_schema  # Gemini responseSchema is a subset; mime-type JSON is enough
        payload: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": sys_text}]},
            "contents": [{"role": "user", "parts": [{"text": user_content}]}],
            "generationConfig": gen_cfg,
        }
        url = f"{self.base_url}/models/{chosen}:generateContent"
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url,
            data=body,
            headers=self._headers(),
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=timeout_s) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            _raise_http_llm_error("Gemini", exc)
        except error.URLError as exc:
            raise LLMError(f"Gemini unreachable: {exc.reason}") from exc
        except TimeoutError as exc:
            raise LLMError("Gemini request timed out") from exc
        if isinstance(raw, dict) and raw.get("error"):
            err = raw["error"]
            msg = err.get("message") if isinstance(err, dict) else str(err)
            status = str(err.get("status") or "") if isinstance(err, dict) else ""
            code = err.get("code") if isinstance(err, dict) else None
            blob = json.dumps(err, default=str) if isinstance(err, dict) else str(err)
            retry_after = None
            found = _RETRY_DELAY_RE.search(blob) or _RETRY_IN_RE.search(blob)
            if found:
                retry_after = float(found.group(1))
            if status == "RESOURCE_EXHAUSTED" or code == 429:
                sc = 429
            elif status == "UNAVAILABLE" or code == 503:
                sc = 503
            else:
                sc = 502
            raise LLMError(f"Gemini error: {msg}", status_code=sc, retry_after_s=retry_after)
        try:
            parts = raw["candidates"][0]["content"]["parts"]
            text = "".join(str(p.get("text") or "") for p in parts if isinstance(p, dict))
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("Malformed Gemini response", status_code=502) from exc
        if not text.strip():
            raise LLMError("Empty Gemini content", status_code=502)
        return strip_thinking_trace(text)

    def generate_text(
        self,
        prompt: str,
        *,
        system: str | None = None,
        timeout_s: float = 120.0,
        temperature: float | None = None,
        model: str | None = None,
    ) -> str:
        if not self.api_key.strip():
            raise LLMError("GEMINI_API_KEY is not set")
        chosen = _chosen_cloud_model(
            self.model, model=model, reasoning=False, family="gemini"
        )
        refine_model = (settings.ai_refine_model or "").strip()
        if refine_model and model is None:
            chosen = refine_model
        gen_cfg: dict[str, Any] = {
            "temperature": 0.2 if temperature is None else temperature,
            "maxOutputTokens": 4096,
        }
        payload: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system or ""}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": gen_cfg,
        }
        url = f"{self.base_url}/models/{chosen}:generateContent"
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=body, headers=self._headers(), method="POST")
        with request.urlopen(req, timeout=timeout_s) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        parts = raw["candidates"][0]["content"]["parts"]
        text = "".join(str(p.get("text") or "") for p in parts if isinstance(p, dict))
        if not text.strip():
            raise LLMError("Empty Gemini content", status_code=502)
        return strip_thinking_trace(text)


def _is_timeout_error(exc: LLMError) -> bool:
    msg = str(exc).lower()
    return "timed out" in msg or "timeout" in msg


def _is_rate_limit_error(exc: LLMError) -> bool:
    if _is_timeout_error(exc):
        return False
    if getattr(exc, "status_code", 0) == 429:
        return True
    msg = str(exc).lower()
    return (
        "http 429" in msg
        or "resource_exhausted" in msg
        or "rate limit" in msg
        or "quota exceeded" in msg
        or "too many requests" in msg
    )


def _is_hard_quota_error(exc: LLMError) -> bool:
    """Daily/plan quota — sleep-retrying the same key will not help."""
    if not _is_rate_limit_error(exc):
        return False
    msg = str(exc).lower()
    return (
        "exceeded your current quota" in msg
        or "free_tier" in msg
        or "check your plan and billing" in msg
        or "quota exceeded for metric" in msg
    )


def _is_unavailable_error(exc: LLMError) -> bool:
    msg = str(exc).lower()
    if _is_timeout_error(exc) or _is_rate_limit_error(exc):
        return False
    if getattr(exc, "status_code", 0) == 503:
        return True
    return "http 503" in msg or "unavailable" in msg or "high demand" in msg


_RATE_LIMIT_BACKOFF_S = (2.0, 8.0, 20.0)
_RATE_LIMIT_SLEEP_CAP_S = 25.0
_RATE_LIMIT_EXTRA_ATTEMPTS = 3
_OLLAMA_FALLBACK_TIMEOUT_S = 45.0


def _sleep_for_rate_limit(exc: LLMError, attempt_idx: int) -> None:
    hinted = getattr(exc, "retry_after_s", None)
    base = _RATE_LIMIT_BACKOFF_S[min(attempt_idx, len(_RATE_LIMIT_BACKOFF_S) - 1)]
    delay = float(hinted) if hinted and float(hinted) > 0 else base
    time.sleep(min(delay, _RATE_LIMIT_SLEEP_CAP_S))


def _kwargs_for_fallback(prov: LLMProvider, kwargs: dict[str, Any]) -> dict[str, Any]:
    out = dict(kwargs)
    out["model"] = None
    name = getattr(prov, "name", "") or ""
    if name == "ollama" or isinstance(prov, OllamaProvider):
        out["model"] = _ollama_local_model(getattr(prov, "model", None))
        # Cloud → local fallback must not burn the draft job on a hung Ollama generate.
        prior = float(out.get("timeout_s") or _OLLAMA_FALLBACK_TIMEOUT_S)
        out["timeout_s"] = min(prior, _OLLAMA_FALLBACK_TIMEOUT_S)
    return out


def _compose_fallback_failure(primary_exc: LLMError, last_exc: LLMError) -> LLMError:
    """Keep the cloud quota reason visible when Ollama/other fallbacks also fail."""
    primary = str(primary_exc).strip()
    last = str(last_exc).strip()
    if _is_hard_quota_error(primary_exc) or (
        _is_rate_limit_error(primary_exc) and "quota" in primary.lower()
    ):
        msg = (
            "Gemini quota/rate limit blocked authoring. "
            "Fallback model also failed. Wait for quota reset, enable billing on the "
            "Gemini key, or set AI_ASSIST=ollama when a local model is warm. "
            f"Primary: {primary[:160]} Fallback: {last[:120]}"
        )
        return LLMError(msg, status_code=429, retry_after_s=getattr(primary_exc, "retry_after_s", None))
    if primary and last and primary != last:
        return LLMError(
            f"{last} (after: {primary[:160]})",
            status_code=getattr(last_exc, "status_code", None) or getattr(primary_exc, "status_code", None),
        )
    return last_exc

def list_configured_fallback_providers(primary: LLMProvider) -> list[LLMProvider]:
    """Other configured backends after Gemini/cloud quota (429) or 503."""
    primary_name = getattr(primary, "name", "")
    if not isinstance(primary_name, str) or not primary_name:
        return []
    out: list[LLMProvider] = []

    def _add(prov: LLMProvider) -> None:
        if prov.name == primary_name:
            return
        if any(p.name == prov.name for p in out):
            return
        out.append(prov)

    if primary_name != "anthropic" and (settings.anthropic_api_key or "").strip():
        _add(AnthropicProvider())
    openai_key = (settings.openai_api_key or "").strip()
    if primary_name != "openai" and openai_key:
        _add(
            OpenAICompatibleProvider(
                base_url=OPENAI_DEFAULT_BASE,
                model=settings.openai_model or "gpt-4.1",
                api_key=openai_key,
                provider_name="openai",
            )
        )
    if primary_name != "gemini" and settings.resolved_gemini_api_key():
        _add(GeminiProvider())
    compat_key = (settings.openai_compatible_api_key or "").strip()
    compat_url = (settings.openai_compatible_base_url or "").strip()
    if primary_name != "openai-compatible" and compat_key and compat_url:
        _add(OpenAICompatibleProvider())
    if primary_name != "ollama":
        ollama = OllamaProvider()
        ok, _reason = ollama.reachable(timeout_s=1.5)
        if ok:
            _add(ollama)
    return out


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
    log_step: str = "generate_json",
) -> str:
    """Retry 429 with Retry-After, 503 with short backoff, timeout once; then other providers."""
    kwargs_base: dict[str, Any] = {
        "prompt": prompt,
        "system": system,
        "timeout_s": timeout_s,
        "reasoning": reasoning,
        "temperature": temperature,
        "format_schema": format_schema,
        "model": model,
    }

    def _call(prov: LLMProvider, kwargs: dict[str, Any]) -> str:
        return prov.generate_json(**kwargs)

    def _with_transient(prov: LLMProvider, kwargs: dict[str, Any]) -> str:
        try:
            return _call(prov, kwargs)
        except LLMError as exc:
            if _is_hard_quota_error(exc):
                # Same API key will keep failing — fall through to other providers.
                raise
            if _is_rate_limit_error(exc):
                last: LLMError = exc
                for i in range(_RATE_LIMIT_EXTRA_ATTEMPTS):
                    _sleep_for_rate_limit(last, i)
                    try:
                        return _call(prov, kwargs)
                    except LLMError as retry_exc:
                        last = retry_exc
                        if _is_hard_quota_error(retry_exc):
                            raise retry_exc
                        if not _is_rate_limit_error(retry_exc):
                            raise
                raise last
            if _is_unavailable_error(exc):
                delay = 0.4
                last = exc
                for _ in range(2):
                    time.sleep(delay)
                    delay *= 2
                    try:
                        return _call(prov, kwargs)
                    except LLMError as retry_exc:
                        last = retry_exc
                        if not _is_unavailable_error(retry_exc):
                            raise
                raise last
            raise

    try:
        from app.ai_llm_prompt_log import log_llm_prompt_payload

        log_llm_prompt_payload(
            step=log_step,
            prompt=prompt,
            system=system,
            provider=type(provider).__name__,
            model=model,
        )
    except Exception:  # noqa: BLE001
        pass

    try:
        return _with_transient(provider, kwargs_base)
    except LLMError as exc:
        if _is_timeout_error(exc):
            retry_model = resolve_bulk_model()
            if isinstance(provider, OllamaProvider):
                retry_model = _ollama_local_model(retry_model)
            kwargs: dict[str, Any] = {
                **kwargs_base,
                "timeout_s": max(60.0, timeout_s * 0.75),
                "reasoning": False,
                "model": retry_model,
            }
            if isinstance(provider, OllamaProvider):
                kwargs["num_predict"] = 2048
            return _call(provider, kwargs)
        if _is_rate_limit_error(exc) or _is_unavailable_error(exc):
            primary_exc = exc
            last = exc
            for alt in list_configured_fallback_providers(provider):
                try:
                    return _with_transient(alt, _kwargs_for_fallback(alt, kwargs_base))
                except LLMError as alt_exc:
                    last = alt_exc
                    if not (
                        _is_rate_limit_error(alt_exc)
                        or _is_unavailable_error(alt_exc)
                        or _is_timeout_error(alt_exc)
                    ):
                        raise _compose_fallback_failure(primary_exc, alt_exc) from alt_exc
                    continue
            raise _compose_fallback_failure(primary_exc, last) from last
        raise

class MockLLMProvider(LLMProvider):
    """Test double — canned JSON/text without network."""

    def __init__(
        self,
        *,
        json_response: str = '{"ok": true}',
        text_response: str = "Mock assistant reply.",
    ) -> None:
        self._json_response = json_response
        self._text_response = text_response

    @property
    def name(self) -> str:
        return "mock"

    def reachable(self, *, timeout_s: float = 2.0) -> tuple[bool, str]:
        return True, "mock provider"

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
        _ = (prompt, system, timeout_s, reasoning, temperature, format_schema, model)
        return self._json_response

    def generate_text(
        self,
        prompt: str,
        *,
        system: str | None = None,
        timeout_s: float = 120.0,
        temperature: float | None = None,
        model: str | None = None,
    ) -> str:
        _ = (prompt, system, timeout_s, temperature, model)
        return self._text_response


def get_llm_provider() -> LLMProvider | None:
    """Return active provider or None when AI_ASSIST=off (or auto with no keys)."""
    return get_llm_provider_for_tier("fast")


def resolve_tier_provider_mode(tier: str = "fast") -> str:
    tier_l = (tier or "fast").strip().lower()
    if tier_l == "refine":
        mode = (settings.ai_llm_tier_refine or "gemini").strip().lower()
    else:
        mode = (settings.ai_llm_tier_fast or "gemini").strip().lower()
    if mode in {"auto", ""}:
        return resolve_provider_mode()
    return mode


def get_llm_provider_for_tier(tier: str = "fast") -> LLMProvider | None:
    """Provider for fast generation or refine-tier chat — swappable by config."""
    mode = resolve_tier_provider_mode(tier)
    if mode == "off":
        return None
    if mode == "mock":
        return MockLLMProvider()
    if mode == "ollama":
        return OllamaProvider()
    if mode == "openai":
        key = (settings.openai_api_key or settings.openai_compatible_api_key or "").strip()
        if not key:
            return None
        return OpenAICompatibleProvider(
            base_url=OPENAI_DEFAULT_BASE,
            model=settings.openai_model or "gpt-4.1",
            api_key=key,
            provider_name="openai",
        )
    if mode == "anthropic":
        if not (settings.anthropic_api_key or "").strip():
            return None
        return AnthropicProvider()
    if mode == "gemini":
        if not settings.resolved_gemini_api_key():
            return None
        # Model-agnostic Studio: Flash is enough for correctness. Optional env
        # upgrades (gemini_refine_model / gemini_contract_model / ai_refine_model)
        # only swap the chat/refine weight when the operator pays for them.
        refine_model = (
            (settings.gemini_refine_model or "").strip()
            or (settings.ai_refine_model or "").strip()
        )
        contract_model = (settings.gemini_contract_model or "").strip()
        if tier == "refine" and refine_model:
            return GeminiProvider(model=refine_model)
        if tier in {"contract", "refine"} and contract_model and tier == "contract":
            return GeminiProvider(model=contract_model)
        return GeminiProvider()
    if mode == "openai-compatible":
        return OpenAICompatibleProvider()
    return get_llm_provider_legacy()


def get_llm_provider_legacy() -> LLMProvider | None:
    """Original AI_ASSIST resolution (used when tier mode is auto)."""
    mode = resolve_provider_mode()
    if mode == "off":
        return None
    if mode == "ollama":
        return OllamaProvider()
    if mode == "openai":
        key = (settings.openai_api_key or settings.openai_compatible_api_key or "").strip()
        if not key:
            return None
        return OpenAICompatibleProvider(
            base_url=OPENAI_DEFAULT_BASE,
            model=settings.openai_model or "gpt-4.1",
            api_key=key,
            provider_name="openai",
        )
    if mode == "anthropic":
        if not (settings.anthropic_api_key or "").strip():
            return None
        return AnthropicProvider()
    if mode == "gemini":
        if not settings.resolved_gemini_api_key():
            return None
        return GeminiProvider()
    if mode == "openai-compatible":
        return OpenAICompatibleProvider()
    return None


def ai_provider_enabled() -> bool:
    return get_llm_provider() is not None
