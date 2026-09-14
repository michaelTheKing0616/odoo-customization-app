"""Wake local Ollama and probe configured LLM backends for Retry recovery."""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib import error, request

from app.settings import settings

logger = logging.getLogger(__name__)


def warm_ollama_models(*, keep_alive: str | None = None) -> dict[str, Any]:
    """Ping Ollama generate with keep_alive so bulk + reasoning models stay loaded.

    Runs whenever ``OLLAMA_BASE_URL`` is set — including when primary AI is Gemini —
    so Retry can bring local fallback online after a cloud outage.
    """
    from app.llm_provider import resolve_bulk_model, resolve_reasoning_model

    base = (settings.ollama_base_url or "").strip().rstrip("/")
    if not base:
        return {"skipped": True, "reason": "no ollama_base_url"}

    alive = (keep_alive or settings.ollama_keep_alive or "30m").strip()
    models: list[str] = []
    for m in (resolve_bulk_model(), resolve_reasoning_model(), settings.ollama_model):
        tag = (m or "").strip()
        # Never POST a cloud model id to Ollama.
        if not tag or tag.startswith(("gemini-", "gpt-", "claude-", "o1", "o3")):
            continue
        if tag not in models:
            models.append(tag)
    if not models:
        models = ["qwen3:8b"]

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


def revive_llm_providers(*, timeout_s: float = 3.0) -> tuple[Any | None, list[str]]:
    """Warm local Ollama and return the first reachable configured provider.

    Used by Retry AI enrichment so production operators can wake Flash/local/cloud
    and finish work that failed on Create draft.
    """
    from app.llm_provider import (
        OllamaProvider,
        get_llm_provider,
        list_configured_fallback_providers,
    )

    notes: list[str] = []
    warm = warm_ollama_models()
    if warm.get("skipped"):
        notes.append(f"revive: ollama warm skipped ({warm.get('reason')})")
    else:
        for row in warm.get("models") or []:
            if isinstance(row, dict):
                notes.append(
                    f"revive: ollama {row.get('model')} → {row.get('status')}"
                )

    candidates: list[Any] = []
    primary = get_llm_provider()
    if primary is not None:
        candidates.append(primary)
        for alt in list_configured_fallback_providers(primary):
            candidates.append(alt)
    else:
        # AI_ASSIST may still leave Ollama usable as a local revive target.
        try:
            ollama = OllamaProvider()
            candidates.append(ollama)
        except Exception:  # noqa: BLE001
            pass

    seen: set[str] = set()
    for prov in candidates:
        name = str(getattr(prov, "name", type(prov).__name__) or "")
        if name in seen:
            continue
        seen.add(name)
        try:
            ok, detail = prov.reachable(timeout_s=timeout_s)
        except Exception as exc:  # noqa: BLE001
            notes.append(f"revive: {name} probe failed ({exc})")
            continue
        notes.append(f"revive: {name} → {detail}")
        if ok:
            return prov, notes

    notes.append("revive: no LLM reachable — residual recovery still applies")
    return None, notes


__all__ = ["revive_llm_providers", "warm_ollama_models"]
