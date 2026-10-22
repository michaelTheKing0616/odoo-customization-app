"""Three-tier provider bindings. Wire helpers live in adapters/. No sockets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.llm_gateway.adapters.anthropic import anthropic_body, anthropic_error, parse_anthropic
from app.llm_gateway.adapters.gemini import gemini_body, gemini_error, parse_gemini
from app.llm_gateway.adapters.openai import openai_body, openai_error, parse_openai
from app.llm_gateway.types import LLMError, LLMResponse

ParseFn = Callable[[dict[str, Any]], LLMResponse]
BodyFn = Callable[[dict[str, Any]], dict[str, Any]]
ErrorFn = Callable[..., LLMError]

TIER_FRONTIER = "A"
TIER_CLOUD = "B"
TIER_LOCAL = "C"


@dataclass(frozen=True, slots=True)
class ProviderBinding:
    name: str
    tier: str
    build_body: BodyFn
    parse_response: ParseFn
    map_error: ErrorFn
    active_by_default: bool


BINDINGS: dict[str, ProviderBinding] = {
    "anthropic": ProviderBinding(
        name="anthropic",
        tier=TIER_FRONTIER,
        build_body=anthropic_body,
        parse_response=parse_anthropic,
        map_error=anthropic_error,
        active_by_default=False,
    ),
    "openai": ProviderBinding(
        name="openai",
        tier=TIER_CLOUD,
        build_body=openai_body,
        parse_response=parse_openai,
        map_error=openai_error,
        active_by_default=True,
    ),
    "gemini": ProviderBinding(
        name="gemini",
        tier=TIER_CLOUD,
        build_body=gemini_body,
        parse_response=parse_gemini,
        map_error=gemini_error,
        active_by_default=True,
    ),
}

# Local Qwen and other hosts reuse the OpenAI-compatible wire shape at the gateway.
QWEN_GATEWAY_PROVIDER = "openai"

# Vision reads these. Gemini is today's default. Claude is the frontier port.
FRONTIER_PROVIDER = "anthropic"
DEFAULT_VISION_PROVIDER = "gemini"


def vision_provider_name(override: str | None = None) -> str:
    """Resolve the vision binding. Only FRONTIER_PROVIDER leaves Gemini."""
    chosen = str(override or DEFAULT_VISION_PROVIDER).strip().lower()
    if chosen == FRONTIER_PROVIDER:
        return FRONTIER_PROVIDER
    return DEFAULT_VISION_PROVIDER


def vision_binding(name: str | None = None) -> ProviderBinding:
    """Same call site for Gemini or Claude. Switching is the name argument."""
    chosen = vision_provider_name(name)
    return require_provider(chosen, allow_frontier=(chosen == FRONTIER_PROVIDER))


def default_active_providers() -> frozenset[str]:
    return frozenset(name for name, binding in BINDINGS.items() if binding.active_by_default)


def is_frontier_provider(name: str) -> bool:
    binding = BINDINGS.get(name)
    return binding is not None and binding.tier == TIER_FRONTIER


def require_provider(name: str, *, allow_frontier: bool = False) -> ProviderBinding:
    binding = BINDINGS.get(name)
    if binding is None:
        raise LLMError("invalid_request", f"unknown provider {name}")
    if binding.tier == TIER_FRONTIER and not allow_frontier:
        raise LLMError("invalid_request", "frontier adapter inactive")
    if not binding.active_by_default and not allow_frontier:
        raise LLMError("invalid_request", "frontier adapter inactive")
    return binding


class ProviderReplayAdapter:
    """Replay canned provider payloads. Validates the wire body. Does not send HTTP."""

    def __init__(
        self,
        provider: str,
        payloads: list[dict[str, Any]],
        *,
        allow_frontier: bool = False,
    ) -> None:
        self._binding = require_provider(provider, allow_frontier=allow_frontier)
        self._payloads = list(payloads)
        self.provider = self._binding.name
        self.calls = 0
        self.last_request: dict[str, Any] | None = None
        self.last_body: dict[str, Any] | None = None

    def complete(self, request: dict[str, Any]) -> LLMResponse:
        self.calls += 1
        self.last_request = dict(request)
        if not self._payloads:
            raise LLMError("server", "replay exhausted")
        prepared = dict(request)
        prepared.setdefault("model_id", "configured")
        prepared.setdefault("max_output_tokens", 32)
        self.last_body = self._binding.build_body(prepared)
        return self._binding.parse_response(self._payloads.pop(0))
