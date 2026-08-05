"""Keep Ollama models warm — reduces cold-start timeouts on draft generation."""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib import error, request

from app.llm_provider import resolve_bulk_model, resolve_reasoning_model
from app.settings import settings

logger = logging.getLogger(__name__)


def warm_ollama_models(*, keep_alive: str | None = None) -> dict[str, Any]:
    """Ping Ollama generate with keep_alive so bulk + reasoning models stay loaded."""
    mode = settings.ai_assist.strip().lower()
    if mode != "ollama":
        return {"skipped": True, "reason": f"ai_assist={mode}"}

    alive = (keep_alive or settings.ollama_keep_alive or "30m").strip()
    base = settings.ollama_base_url.rstrip("/")
    models = []
    for m in (resolve_bulk_model(), resolve_reasoning_model()):
        if m and m not in models:
            models.append(m)

    results: list[dict[str, str]] = []
    for model in models:
        payload = {
            "model": model,
            "prompt": "ping",
            "stream": False,
            "keep_alive": alive,
            "options": {"num_predict": 1, "temperature": 0},
        }
        url = f"{base}/api/generate"
        try:
            req = request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req, timeout=15.0) as resp:
                if 200 <= getattr(resp, "status", 200) < 300:
                    results.append({"model": model, "status": "warm"})
                else:
                    results.append({"model": model, "status": "http_error"})
        except error.URLError as exc:
            logger.warning("ollama warm failed for %s: %s", model, exc.reason)
            results.append({"model": model, "status": f"unreachable: {exc.reason}"})
        except Exception as exc:  # noqa: BLE001
            logger.warning("ollama warm failed for %s: %s", model, exc)
            results.append({"model": model, "status": str(exc)[:120]})

    return {"keep_alive": alive, "models": results}


__all__ = ["warm_ollama_models"]
