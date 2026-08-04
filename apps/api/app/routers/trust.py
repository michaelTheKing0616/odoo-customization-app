"""TRUST-8 in-app trust contract (SAFETY.md)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/trust", tags=["trust"])

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SAFETY_PATH = _REPO_ROOT / "docs" / "SAFETY.md"


class SafetyDocOut(BaseModel):
    markdown: str
    source: str = "docs/SAFETY.md"


@router.get("/safety", response_model=SafetyDocOut)
def get_safety_doc() -> SafetyDocOut:
    if not _SAFETY_PATH.is_file():
        return SafetyDocOut(
            markdown="# Safety contract\n\nSAFETY.md not found on server.\n",
        )
    return SafetyDocOut(markdown=_SAFETY_PATH.read_text(encoding="utf-8"))
