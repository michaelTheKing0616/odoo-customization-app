"""HOWDO-01: the how-do-I assistant request/response contract.

Field lists follow docs/build-plan/new-features/AI_IN_ODOO.md §HOWDO §6 exactly
(pinned 2026-10-22). Shapes only: no Odoo call, nothing stored, no token crypto.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# B5 error codes this epic uses (subset of app.scans.contract.ERROR_HTTP).
HowdoErrorCode = Literal["ROLE_DENIED", "VALIDATION", "NOT_FOUND"]
HOWDO_ERROR_CODES: tuple[str, ...] = ("ROLE_DENIED", "VALIDATION", "NOT_FOUND")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssistTokenRequest(_Strict):
    connection_id: str = Field(min_length=1)
    odoo_uid: int | None = None


class HowdoToken(_Strict):
    token: str
    expires_at: datetime
    scope: Literal["ask"] = "ask"


class AssistAsk(_Strict):
    """No connection_id: /ask takes its connection from the short token."""

    question: str = Field(min_length=1)
    page_context: dict[str, str] | None = None  # usual keys: model, view_type, action_id


class AssistStep(_Strict):
    text: str
    menu_path: str | None = None
    deep_link: str | None = None


class AssistCitation(_Strict):
    kind: Literal["doc", "field", "menu"]
    tech_name: str


class AssistAnswer(_Strict):
    answer_md: str
    steps: list[AssistStep] = Field(default_factory=list)
    citations: list[AssistCitation] = Field(default_factory=list)
    refused: str | None = None  # the reason; null means the answer was given


MintFn = Callable[[Any, AssistTokenRequest], HowdoToken]
AskFn = Callable[[Any, AssistAsk], AssistAnswer]
