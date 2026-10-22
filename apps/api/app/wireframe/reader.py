"""Deterministic sketch reader — no live vision, no model call.

A checked-in fixture (JSON transcription of a photograph or a digital
sketch) is the test reader. Live qwen3-vl stays behind this same region
schema when a later card turns it on.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_MISREAD_LABELS = frozenset({"unknown", "unclear", "?", "???", "illegible"})
_CONFIDENCE_FLOOR = 0.5


def _read_box(raw: Any) -> tuple[float, float, float, float] | None:
    """Accept [x, y, w, h] fractions; anything malformed or off the page is dropped, never guessed."""
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        return None
    try:
        x, y, w, h = (float(v) for v in raw)
    except (TypeError, ValueError):
        return None
    if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > 1.001 or y + h > 1.001:
        return None
    return (round(x, 4), round(y, 4), round(w, 4), round(h, 4))


@dataclass
class SketchRegion:
    id: str
    label: str = ""
    hint: str = ""
    widget: str | None = None
    relation: str | None = None
    confidence: float = 1.0
    misread: bool = False
    # Q6: where the region sits on the sketch, as fractions [x, y, w, h] in 0..1 (None if unknown).
    box: tuple[float, float, float, float] | None = None

    def is_unlabeled(self) -> bool:
        return not (self.label or "").strip()

    def is_misread(self) -> bool:
        if self.misread:
            return True
        if self.confidence < _CONFIDENCE_FLOOR:
            return True
        label = (self.label or "").strip().lower()
        if "???" in label or label in _MISREAD_LABELS:
            return True
        return False

    def needs_clarify(self) -> bool:
        return self.is_unlabeled() or self.is_misread()


@dataclass
class Sketch:
    title: str
    prompt: str
    source: str
    regions: list[SketchRegion] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def first_unclear(self) -> SketchRegion | None:
        for region in self.regions:
            if region.needs_clarify():
                return region
        return None


def read_sketch(source: Path | str | dict[str, Any]) -> Sketch:
    """Load a sketch fixture. Paths and JSON strings are allowed; no network."""
    payload = _load(source)
    if not isinstance(payload, dict):
        raise ValueError("Sketch fixture must be a JSON object")
    regions_raw = payload.get("regions")
    if not isinstance(regions_raw, list) or not regions_raw:
        raise ValueError("Sketch fixture must list at least one region")
    title = str(payload.get("title") or "Custom app").strip() or "Custom app"
    prompt = str(payload.get("prompt") or title).strip()
    regions = [_region(item, index) for index, item in enumerate(regions_raw)]
    return Sketch(
        title=title,
        prompt=prompt,
        source=str(payload.get("source") or "sketch"),
        regions=regions,
        raw=payload,
    )


def _load(source: Path | str | dict[str, Any]) -> Any:
    if isinstance(source, dict):
        return source
    if isinstance(source, Path):
        return json.loads(source.read_text(encoding="utf-8"))
    text = str(source).strip()
    if text.startswith("{"):
        return json.loads(text)
    return json.loads(Path(text).read_text(encoding="utf-8"))


def _region(raw: Any, index: int) -> SketchRegion:
    if not isinstance(raw, dict):
        raise ValueError(f"Region {index} must be an object")
    rid = str(raw.get("id") or f"r{index + 1}")
    widget = raw.get("widget")
    return SketchRegion(
        id=rid,
        label=str(raw.get("label") or ""),
        hint=str(raw.get("hint") or raw.get("kind") or "").strip().lower(),
        widget=str(widget) if widget else None,
        relation=str(raw["relation"]) if raw.get("relation") else None,
        confidence=float(raw.get("confidence") if raw.get("confidence") is not None else 1.0),
        misread=bool(raw.get("misread")),
        box=_read_box(raw.get("box")),
    )
