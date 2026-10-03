"""LLM gateway. Thin in-house adapters. No LiteLLM. No Odoo."""

from app.llm_gateway.gateway import Gateway
from app.llm_gateway.types import LLMError, LLMResponse

__all__ = ["Gateway", "LLMError", "LLMResponse"]
