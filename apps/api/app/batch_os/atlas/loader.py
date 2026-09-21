"""Load and search the Config Atlas seed."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

_SEED = Path(__file__).resolve().parent / "seed" / "atlas.yaml"


@dataclass
class AtlasIntent:
    id: str
    title: str
    models: list[str] = field(default_factory=list)
    risk: str = "L1"
    recipe: str | None = None
    status: str = "stub"
    blurb: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AtlasClass:
    id: str
    title: str
    status: str
    blurb: str = ""
    intents: list[AtlasIntent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "blurb": self.blurb,
            "intents": [i.to_dict() for i in self.intents],
        }


@dataclass
class AtlasEntry:
    """Flattened search hit."""

    class_id: str
    class_title: str
    intent_id: str
    title: str
    models: list[str]
    risk: str
    recipe: str | None
    status: str
    blurb: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_yaml(text: str) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError:
        return _parse_yaml_minimal(text)
    data = yaml.safe_load(text)
    return data if isinstance(data, dict) else {}


def _parse_yaml_minimal(text: str) -> dict[str, Any]:
    """Tiny subset parser if PyYAML missing — prefer JSON sibling."""
    json_path = _SEED.with_suffix(".json")
    if json_path.is_file():
        import json

        return json.loads(json_path.read_text(encoding="utf-8"))
    raise RuntimeError("PyYAML not installed and atlas.json missing")


@lru_cache(maxsize=1)
def load_atlas() -> list[AtlasClass]:
    raw = _SEED.read_text(encoding="utf-8")
    data = _parse_yaml(raw)
    classes: list[AtlasClass] = []
    for c in data.get("classes") or []:
        intents = [
            AtlasIntent(
                id=str(i.get("id") or ""),
                title=str(i.get("title") or ""),
                models=list(i.get("models") or []),
                risk=str(i.get("risk") or "L1"),
                recipe=i.get("recipe"),
                status=str(i.get("status") or "stub"),
                blurb=str(i.get("blurb") or ""),
            )
            for i in (c.get("intents") or [])
        ]
        classes.append(
            AtlasClass(
                id=str(c.get("id") or ""),
                title=str(c.get("title") or ""),
                status=str(c.get("status") or "stub"),
                blurb=str(c.get("blurb") or ""),
                intents=intents,
            )
        )
    return classes


def list_atlas(*, class_id: str | None = None) -> list[dict[str, Any]]:
    classes = load_atlas()
    if class_id:
        classes = [c for c in classes if c.id == class_id]
    return [c.to_dict() for c in classes]


def search_atlas(q: str, *, class_id: str | None = None, risk: str | None = None) -> list[dict[str, Any]]:
    needle = (q or "").strip().lower()
    hits: list[AtlasEntry] = []
    for c in load_atlas():
        if class_id and c.id != class_id:
            continue
        for intent in c.intents:
            if risk and intent.risk != risk:
                continue
            blob = " ".join(
                [
                    c.id,
                    c.title,
                    intent.id,
                    intent.title,
                    intent.blurb,
                    " ".join(intent.models),
                    intent.recipe or "",
                ]
            ).lower()
            if needle and needle not in blob:
                continue
            hits.append(
                AtlasEntry(
                    class_id=c.id,
                    class_title=c.title,
                    intent_id=intent.id,
                    title=intent.title,
                    models=list(intent.models),
                    risk=intent.risk,
                    recipe=intent.recipe,
                    status=intent.status,
                    blurb=intent.blurb or c.blurb,
                )
            )
    return [h.to_dict() for h in hits]


def reload_atlas() -> None:
    load_atlas.cache_clear()
