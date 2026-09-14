"""Log exact final LLM prompt payloads for hop-boundary UAT debugging.

Enable with AI_LOG_LLM_PROMPTS=1 (writes under .cache/ai_llm_prompts/). Always
records a short logger line with step + byte lengths so failures are findable
without dumping full prompts in production logs.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(__file__).resolve().parents[3] / ".cache" / "ai_llm_prompts"


def log_llm_prompt_payload(
    *,
    step: str,
    prompt: str,
    system: str | None = None,
    provider: str = "",
    model: str | None = None,
    extra: dict[str, Any] | None = None,
) -> str | None:
    """Persist the verbatim final prompt when enabled. Returns log path or None."""
    sys_s = system or ""
    prompt_s = prompt or ""
    digest = hashlib.sha256((sys_s + "\n" + prompt_s).encode("utf-8")).hexdigest()[:12]
    logger.info(
        "llm_prompt step=%s bytes_system=%s bytes_prompt=%s sha256_12=%s provider=%s model=%s",
        step,
        len(sys_s.encode("utf-8")),
        len(prompt_s.encode("utf-8")),
        digest,
        provider or "-",
        model or "-",
    )
    try:
        from app.settings import settings

        if not bool(getattr(settings, "ai_log_llm_prompts", False)):
            return None
    except Exception:  # noqa: BLE001
        return None

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%S")
    path = _CACHE_DIR / f"{stamp}_{step}_{digest}.json"
    payload = {
        "step": step,
        "provider": provider,
        "model": model,
        "sha256_12": digest,
        "system": sys_s,
        "prompt": prompt_s,
        "extra": extra or {},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("llm_prompt_saved path=%s", path)
    return str(path)


__all__ = ["log_llm_prompt_payload"]
