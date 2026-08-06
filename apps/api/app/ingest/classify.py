"""Stage 1 — document classification (ING-2)."""

from __future__ import annotations

import json
import re
from typing import Any

from app.ingest.constants import CLASSIFY_HEADER_SIGNALS, CLASSIFY_MIN_CONFIDENCE
from app.ingest.schema import ClassificationResult, DocType, validate_doc_type
from app.llm_provider import LLMError, get_llm_provider
from app.settings import settings

_FILENAME_HINTS: list[tuple[DocType, re.Pattern[str]]] = [
    ("coa", re.compile(r"\b(coa|chart.?of.?account|gl.?chart|ledger)\b", re.I)),
    ("bom", re.compile(r"\b(bom|bill.?of.?material|components?)\b", re.I)),
    ("product_catalog", re.compile(r"\b(product|catalog|sku|items?)\b", re.I)),
    ("customer_list", re.compile(r"\b(customer|client|contact)s?\b", re.I)),
    ("vendor_list", re.compile(r"\b(vendor|supplier)s?\b", re.I)),
    ("price_list", re.compile(r"\b(price|pricelist)\b", re.I)),
    ("employee_roster", re.compile(r"\b(employee|staff|roster|hr)\b", re.I)),
    ("opening_trial_balance", re.compile(r"\b(trial.?balance|opening)\b", re.I)),
    ("inventory_count", re.compile(r"\b(inventory|stock.?count)\b", re.I)),
]


def _normalize_headers(headers: list[str]) -> set[str]:
    out: set[str] = set()
    for h in headers:
        for tok in re.findall(r"[a-z0-9_]+", h.lower()):
            if len(tok) > 1:
                out.add(tok)
            for part in tok.split("_"):
                if len(part) > 1:
                    out.add(part)
    return out


def _score_doc_type(headers: set[str], doc_type: DocType) -> tuple[float, list[str]]:
    signals = CLASSIFY_HEADER_SIGNALS.get(doc_type, frozenset())
    if not signals:
        return 0.0, []
    hits = sorted(headers & signals)
    if not hits:
        return 0.0, []
    score = min(1.0, len(hits) / max(3, len(signals) * 0.35))
    return score, hits


def classify_structured(
    *,
    filename: str,
    headers: list[str],
) -> ClassificationResult:
    header_set = _normalize_headers(headers)
    scores: list[tuple[DocType, float, list[str]]] = []
    for doc_type in CLASSIFY_HEADER_SIGNALS:
        if doc_type == "other":
            continue
        score, hits = _score_doc_type(header_set, doc_type)
        if score > 0:
            scores.append((doc_type, score, hits))

    for doc_type, pat in _FILENAME_HINTS:
        if pat.search(filename):
            scores.append((doc_type, 0.45, [f"filename:{pat.pattern}"]))

    if not scores:
        return ClassificationResult(
            doc_type="other",
            confidence=0.0,
            needs_user_confirm=True,
            method="structured",
            signals=[],
        )

    # Keep best score per doc_type (email+phone hits both customer and vendor lists).
    best_by_type: dict[DocType, tuple[float, list[str]]] = {}
    for doc_type, score, hits in scores:
        prev = best_by_type.get(doc_type)
        if prev is None or score > prev[0]:
            best_by_type[doc_type] = (score, hits)
    scores = [(dt, sc, h) for dt, (sc, h) in best_by_type.items()]

    scores.sort(key=lambda t: (-t[1], t[0]))
    best_type, best_score, hits = scores[0]
    second_score = scores[1][1] if len(scores) > 1 else 0.0
    second_type = scores[1][0] if len(scores) > 1 else None
    confidence = best_score
    if second_type and second_type != best_type and second_score >= best_score * 0.85:
        confidence *= 0.7
    threshold = float(getattr(settings, "ingest_classify_min_confidence", CLASSIFY_MIN_CONFIDENCE))
    needs_confirm = confidence < threshold or best_type == "other"
    return ClassificationResult(
        doc_type=best_type,
        confidence=round(confidence, 3),
        needs_user_confirm=needs_confirm,
        method="structured",
        signals=hits[:8],
    )


_CLASSIFY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "doc_type": {
            "type": "string",
            "enum": sorted(t for t in CLASSIFY_HEADER_SIGNALS if t != "other") + ["other"],
        },
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
    },
    "required": ["doc_type", "confidence"],
}


def classify_with_llm(
    *,
    filename: str,
    headers: list[str],
    sample_rows: list[dict[str, str]],
) -> ClassificationResult | None:
    provider = get_llm_provider()
    if provider is None:
        return None
    preview = sample_rows[:3]
    prompt = (
        "Classify this business document into exactly one doc_type from the closed vocabulary.\n"
        "Types: coa, bom, product_catalog, customer_list, vendor_list, price_list, "
        "employee_roster, opening_trial_balance, inventory_count, other.\n"
        f"Filename: {filename}\n"
        f"Headers: {headers[:30]}\n"
        f"Sample rows: {json.dumps(preview, ensure_ascii=False)[:1200]}\n"
        "Return JSON only."
    )
    try:
        raw = provider.generate_json(
            prompt,
            system=(
                "You classify migration documents for Odoo import. "
                "Use structural cues only. If unsure, doc_type=other and low confidence."
            ),
            temperature=0.15,
            format_schema=_CLASSIFY_SCHEMA,
        )
        data = json.loads(raw) if isinstance(raw, str) else raw
        doc_type = validate_doc_type(str(data.get("doc_type") or "other"))
        confidence = float(data.get("confidence") or 0.0)
        threshold = float(getattr(settings, "ingest_classify_min_confidence", CLASSIFY_MIN_CONFIDENCE))
        return ClassificationResult(
            doc_type=doc_type,
            confidence=min(1.0, max(0.0, confidence)),
            needs_user_confirm=confidence < threshold or doc_type == "other",
            method="llm",
            signals=[str(data.get("reason") or "")[:200]],
        )
    except (LLMError, json.JSONDecodeError, ValueError, TypeError):
        return None


def classify_upload(
    *,
    filename: str,
    headers: list[str] | None = None,
    sample_rows: list[dict[str, str]] | None = None,
    force_doc_type: DocType | None = None,
) -> ClassificationResult:
    if force_doc_type:
        validate_doc_type(force_doc_type)
        return ClassificationResult(
            doc_type=force_doc_type,
            confidence=1.0,
            needs_user_confirm=False,
            method="user",
            signals=["forced"],
        )

    hdrs = headers or []
    structured = classify_structured(filename=filename, headers=hdrs)
    threshold = float(getattr(settings, "ingest_classify_min_confidence", CLASSIFY_MIN_CONFIDENCE))
    if structured.confidence >= threshold and not structured.needs_user_confirm:
        return structured

    llm = classify_with_llm(
        filename=filename,
        headers=hdrs,
        sample_rows=sample_rows or [],
    )
    if llm and llm.confidence > structured.confidence:
        return llm
    return structured
