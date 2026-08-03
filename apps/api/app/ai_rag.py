"""Local embedding retrieval for domain packs (Step 0 RAG).

Uses ``sentence-transformers/all-MiniLM-L6-v2`` when the optional ``ai-rag``
extra is installed. Falls back to Jaccard tag scoring — never fails the draft
pipeline if the model is missing or unloadable.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import threading
from pathlib import Path
from typing import Any, Callable

from app.settings import settings

logger = logging.getLogger(__name__)

_MODEL_LOCK = threading.Lock()
_MODEL = None
_MODEL_LOAD_ATTEMPTED = False
_PACK_EMBED_CACHE: dict[str, list[float]] = {}


def rag_enabled() -> bool:
    return settings.ai_rag.strip().lower() in {"on", "true", "1", "yes", "auto"}


def rag_force() -> bool:
    """True when operator requires embeddings (fail soft still applies)."""
    return settings.ai_rag.strip().lower() in {"on", "true", "1", "yes"}


def _pack_document(pack_id: str, pack: dict[str, Any]) -> str:
    parts = [
        pack_id,
        str(pack.get("display_name") or ""),
        str(pack.get("domain_pack") or ""),
        " ".join(str(t) for t in (pack.get("tags") or [])),
    ]
    for m in pack.get("models") or []:
        if not isinstance(m, dict):
            continue
        parts.append(str(m.get("description") or ""))
        parts.append(str(m.get("model") or "").replace("_", " ").replace(".", " "))
        for f in m.get("fields") or []:
            if isinstance(f, dict):
                parts.append(str(f.get("string") or f.get("name") or ""))
    for a in pack.get("automations") or []:
        if isinstance(a, dict):
            parts.append(str(a.get("name") or ""))
            parts.append(str(a.get("description") or ""))
    return " ".join(p for p in parts if p).strip()


def _cache_dir() -> Path:
    root = Path(__file__).resolve().parents[3] / ".cache" / "ai_rag"
    root.mkdir(parents=True, exist_ok=True)
    return root


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two dense vectors (0.0 when invalid)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(dot / (na * nb))


def _load_model() -> Any | None:
    global _MODEL, _MODEL_LOAD_ATTEMPTED
    if _MODEL is not None:
        return _MODEL
    if _MODEL_LOAD_ATTEMPTED and _MODEL is None:
        return None
    with _MODEL_LOCK:
        if _MODEL is not None:
            return _MODEL
        if _MODEL_LOAD_ATTEMPTED and _MODEL is None:
            return None
        _MODEL_LOAD_ATTEMPTED = True
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError:
            logger.info(
                "sentence-transformers not installed — RAG uses Jaccard fallback "
                "(pip/uv install with extra ai-rag)"
            )
            return None
        model_name = settings.ai_rag_model.strip() or "sentence-transformers/all-MiniLM-L6-v2"
        try:
            _MODEL = SentenceTransformer(model_name)
            logger.info("Loaded RAG embedding model %s", model_name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load RAG model %s: %s", model_name, exc)
            _MODEL = None
        return _MODEL


def embed_texts(texts: list[str]) -> list[list[float]] | None:
    """Return dense vectors or None if embeddings unavailable."""
    if not texts:
        return []
    model = _load_model()
    if model is None:
        return None
    try:
        vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [list(map(float, row)) for row in vectors]
    except Exception as exc:  # noqa: BLE001
        logger.warning("RAG encode failed: %s", exc)
        return None


def _cached_pack_embedding(pack_id: str, doc: str) -> list[float] | None:
    digest = hashlib.sha256(doc.encode("utf-8")).hexdigest()[:16]
    key = f"{pack_id}:{digest}"
    if key in _PACK_EMBED_CACHE:
        return _PACK_EMBED_CACHE[key]
    path = _cache_dir() / f"{pack_id}.{digest}.json"
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list) and data:
                _PACK_EMBED_CACHE[key] = [float(x) for x in data]
                return _PACK_EMBED_CACHE[key]
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    encoded = embed_texts([doc])
    if not encoded:
        return None
    vec = encoded[0]
    _PACK_EMBED_CACHE[key] = vec
    try:
        path.write_text(json.dumps(vec), encoding="utf-8")
    except OSError:
        pass
    return vec


def score_packs_with_embeddings(
    prompt: str,
    packs: list[tuple[str, dict[str, Any]]],
) -> list[tuple[str, float]] | None:
    """Return [(pack_id, cosine_score)] sorted desc, or None if embeddings unavailable.

    Under ``AI_RAG=auto``, never trigger a cold model download on the request path —
    that previously froze the wizard (status) and Draft ModuleSpec for minutes.
    Use Jaccard until the model is already loaded, or set ``AI_RAG=on`` to force load.
    """
    if not rag_enabled() or not prompt.strip():
        return None
    mode = settings.ai_rag.strip().lower()
    if mode in {"auto"} and _MODEL is None:
        return None
    docs = [_pack_document(pid, pack) for pid, pack in packs]
    pack_vecs: list[list[float] | None] = []
    for (pid, _pack), doc in zip(packs, docs, strict=True):
        pack_vecs.append(_cached_pack_embedding(pid, doc))
    if any(v is None for v in pack_vecs):
        encoded = embed_texts(docs)
        if encoded is None:
            return None
        pack_vecs = encoded
    prompt_vecs = embed_texts([prompt.strip()])
    if not prompt_vecs:
        return None
    q = prompt_vecs[0]
    scored = [
        (pid, _cosine(q, vec or []))
        for (pid, _pack), vec in zip(packs, pack_vecs, strict=True)
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def retrieve_with_rag(
    prompt: str,
    *,
    pack_loader: Callable[[], list[tuple[str, dict[str, Any]]]],
    jaccard_retrieve: Callable[[str], tuple[str, dict[str, Any], float] | None],
    min_cosine: float | None = None,
) -> tuple[str, dict[str, Any], float, str]:
    """Return (pack_id, pack, score, method) where method is regex|embedding|jaccard|none.

    Always falls back to ``jaccard_retrieve`` (which includes regex) when embeddings
    are off or unavailable — stable under missing deps.
    """
    threshold = (
        min_cosine
        if min_cosine is not None
        else float(settings.ai_rag_min_score)
    )
    # Regex / Jaccard path first for strong lexical hits (score==1.0 from regex)
    lexical = jaccard_retrieve(prompt)
    if lexical is not None and lexical[2] >= 0.99:
        return lexical[0], lexical[1], lexical[2], "regex"

    packs = pack_loader()
    emb = score_packs_with_embeddings(prompt, packs) if rag_enabled() else None
    if emb:
        best_id, best_score = emb[0]
        if best_score >= threshold:
            pack = next(p for pid, p in packs if pid == best_id)
            import copy

            return best_id, copy.deepcopy(pack), float(best_score), "embedding"
        # Below threshold: still prefer embedding ranking over weak Jaccard if
        # we have any positive signal and no lexical hit
        if lexical is None and best_score > 0.15:
            pack = next(p for pid, p in packs if pid == best_id)
            import copy

            return best_id, copy.deepcopy(pack), float(best_score), "embedding_weak"

    if lexical is not None:
        return lexical[0], lexical[1], lexical[2], "jaccard"

    return "", {}, 0.0, "none"


def rag_status(*, probe_model: bool = False) -> dict[str, Any]:
    """Status for /api/ai/status — must stay fast (never download weights here).

    Set ``probe_model=True`` only from explicit admin/debug callers.
    """
    available = False
    detail = "disabled"
    package = False
    try:
        import importlib.util

        package = importlib.util.find_spec("sentence_transformers") is not None
    except Exception:  # noqa: BLE001
        package = False

    if rag_enabled():
        if _MODEL is not None:
            available = True
            detail = f"ready:{settings.ai_rag_model}"
        elif package:
            detail = (
                f"package_installed (lazy-load on first draft): {settings.ai_rag_model}"
            )
            if probe_model:
                model = _load_model()
                if model is not None:
                    available = True
                    detail = f"ready:{settings.ai_rag_model}"
                else:
                    detail = "fallback:jaccard (model failed to load)"
            else:
                # Treat as available for UI; actual encode may still fall back
                available = True
        else:
            detail = "fallback:jaccard (sentence-transformers not installed)"
    return {
        "ai_rag": settings.ai_rag,
        "rag_enabled": rag_enabled(),
        "embeddings_available": available,
        "embeddings_loaded": _MODEL is not None,
        "package_installed": package,
        "rag_model": settings.ai_rag_model,
        "rag_min_score": settings.ai_rag_min_score,
        "detail": detail,
    }


__all__ = [
    "cosine_similarity",
    "rag_enabled",
    "rag_status",
    "retrieve_with_rag",
    "score_packs_with_embeddings",
    "embed_texts",
]
