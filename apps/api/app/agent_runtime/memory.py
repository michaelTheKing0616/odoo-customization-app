"""Four-class memory for one run. Confirmation is a human action.

Working memory is written by the engine and is trusted.
Tenant or database memory is created by ``memory_propose`` as a pending
item and becomes a fact only when a human confirms.
Global knowledge is not written here. It enters through a pull request
plus eval.
Episodic memory is never auto-injected.

Confirmed tenant and database facts are the only items from this book
that the runtime may place in the prompt memory layer. Pending items,
episodic memory, and global knowledge stay out of that layer. The 5%
budget in ``agent_runtime.prompt`` fits the string the runtime passes.

This module does not call a model, does not call the prompt assembler,
and does not open a network connection.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

HUMAN_CONFIRMED = frozenset({"tenant", "database"})
_TOOL_CLASSES = HUMAN_CONFIRMED | frozenset({"episodic"})
_SOURCE_KEYS = ("source", "kind", "origin", "channel", "note_type")
_TEXT_KEYS = ("proposal", "text", "note", "body")
_ROLE_NOTE = "role note"
_ROLE_TEXT_MARKERS = (
    "you are now",
    "your role is",
    "your new role",
    "act as ",
    "from now on you",
    "system role",
    "role note:",
    "role note :",
)


class MemoryRefused(Exception):
    """The memory write is not allowed.

    ``code`` is a stable token such as ``RT-47`` or ``CONFIRM_REQUIRED``.
    """

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class MemoryItem:
    """One memory item on a run book.

    ``status`` is ``pending`` or ``confirmed``. ``confirmed`` is true after
    a human confirm, and immediately for engine working memory.
    ``confirmed_by`` is the human identity. It stays empty on working notes.
    """

    item_id: str
    memory_class: str
    text: str
    status: str
    confirmed: bool
    confirmed_by: str


def _norm_token(value: str) -> str:
    return " ".join(value.strip().lower().replace("_", " ").replace("-", " ").split())


def _requested_class(args: Mapping[str, Any]) -> str | None:
    for key in ("memory_class", "class", "scope"):
        raw = args.get(key)
        if not isinstance(raw, str):
            continue
        phrase = _norm_token(raw)
        if phrase in {"global", "global knowledge"}:
            return "global"
        token = phrase.replace(" ", "_")
        if token in {"working", "tenant", "database", "global", "episodic"}:
            return token
    return None


def _primary_text(args: Mapping[str, Any]) -> Any:
    for key in _TEXT_KEYS:
        if key in args:
            return args.get(key)
    return None


def is_role_note(args: Mapping[str, Any]) -> bool:
    """True when the proposal is a role note (RT-47).

    Inputs: tool arguments or a mapping with the same keys.
    Outputs: true when a source token is ``role note`` or the text assigns
    a role. False for ordinary tenant proposals.
    Side effects: none.
    """
    for key in _SOURCE_KEYS:
        raw = args.get(key)
        if isinstance(raw, str) and _norm_token(raw) == _ROLE_NOTE:
            return True
    for key in _TEXT_KEYS:
        raw = args.get(key)
        if not isinstance(raw, str):
            continue
        low = raw.lower()
        if any(marker in low for marker in _ROLE_TEXT_MARKERS):
            return True
    return False


class MemoryBook:
    """In-process memory for one run. Not a global knowledge store.

    The book lives on the runtime that owns the run. It is not written to
    disk or a database. ``prompt_text`` is the confirmed tenant and
    database text the runtime reads when it builds the memory layer.
    """

    def __init__(self) -> None:
        self._items: list[MemoryItem] = []
        self._seq = 0

    def items(self) -> tuple[MemoryItem, ...]:
        """Return every stored item, pending and confirmed.

        Inputs: none.
        Outputs: a tuple copy of the book. Global knowledge is never present.
        Side effects: none.
        """
        return tuple(self._items)

    def pending(self) -> tuple[MemoryItem, ...]:
        """Return items still waiting for a human.

        Inputs: none.
        Outputs: pending items only.
        Side effects: none.
        """
        return tuple(item for item in self._items if item.status == "pending" and not item.confirmed)

    def confirmed_tenant_facts(self) -> tuple[MemoryItem, ...]:
        """Return human-confirmed tenant or database facts.

        Inputs: none.
        Outputs: confirmed items whose class is tenant or database.
        Working, episodic, pending, and refused notes are omitted.
        Side effects: none.
        """
        return tuple(
            item
            for item in self._items
            if item.memory_class in HUMAN_CONFIRMED and item.status == "confirmed" and item.confirmed
        )

    def prompt_text(self) -> str:
        """Render confirmed tenant and database facts for the prompt layer.

        Inputs: none.
        Outputs: one ``class: text`` line per confirmed tenant or database
        fact, in book order. Empty when none are confirmed. Pending items,
        working notes, episodic memory, global knowledge, and refused role
        notes are omitted.
        Side effects: none. Does not call the prompt assembler.
        """
        return "\n".join(
            f"{item.memory_class}: {item.text}" for item in self.confirmed_tenant_facts()
        )

    def eligible_for_memory_layer(self) -> tuple[MemoryItem, ...]:
        """Return engine working notes and confirmed tenant or database facts.

        Inputs: none.
        Outputs: trusted working items and human-confirmed tenant or
        database facts. Episodic items are omitted, including after confirm.
        Pending items are omitted.
        Side effects: none. Does not call the prompt assembler. The prompt
        memory layer uses ``prompt_text``, which is confirmed tenant and
        database facts only. Working notes returned here stay on the book.
        """
        selected: list[MemoryItem] = []
        for item in self._items:
            if item.memory_class == "episodic" or item.memory_class == "global":
                continue
            if not item.confirmed or item.status != "confirmed":
                continue
            if item.memory_class == "working" or item.memory_class in HUMAN_CONFIRMED:
                selected.append(item)
        return tuple(selected)

    def propose(self, args: Mapping[str, Any]) -> dict[str, Any]:
        """Create a pending item, or refuse a write the tool must not make.

        Inputs: tool arguments. ``confirmed``, ``status``, and
        ``confirmed_by`` in the arguments are ignored.
        Outputs: a result dict. An allowed tenant, database, or episodic
        proposal has ``status`` pending and ``confirmed`` false. A role
        note, a working-memory write, and global knowledge are refused
        and are not stored.
        Side effects: appends one pending item when the proposal is
        allowed. Does not confirm. Does not write global knowledge.
        Does not call a model.
        """
        raw_text = _primary_text(args)
        if is_role_note(args):
            return {
                "status": "refused",
                "confirmed": False,
                "code": "RT-47",
                "reason": "role note",
                "proposal": raw_text,
            }
        requested = _requested_class(args)
        if requested == "global":
            return {
                "status": "refused",
                "confirmed": False,
                "code": "GLOBAL_REQUIRES_PR_EVAL",
                "reason": "global knowledge enters only through a pull request plus eval",
                "proposal": raw_text,
            }
        if requested == "working":
            return {
                "status": "refused",
                "confirmed": False,
                "code": "WORKING_IS_ENGINE",
                "reason": "working memory is engine-trusted",
                "proposal": raw_text,
            }
        if raw_text is not None and not isinstance(raw_text, str):
            return {
                "status": "refused",
                "confirmed": False,
                "code": "SCHEMA_INVALID",
                "reason": "proposal text must be a string",
                "proposal": None,
            }
        memory_class = requested if requested in _TOOL_CLASSES else "tenant"
        text = raw_text if isinstance(raw_text, str) else ""
        self._seq += 1
        item = MemoryItem(
            item_id=f"mem_{self._seq}",
            memory_class=memory_class,
            text=text,
            status="pending",
            confirmed=False,
            confirmed_by="",
        )
        self._items.append(item)
        return {
            "status": "pending",
            "confirmed": False,
            "proposal": raw_text,
            "item_id": item.item_id,
            "memory_class": memory_class,
        }

    def confirm(self, item_id: str, *, confirmed_by: str) -> MemoryItem:
        """Confirm one pending item as a human.

        Inputs: the item id and a non-empty human identity.
        Outputs: the confirmed item. Episodic items stay out of tenant
        facts and out of ``eligible_for_memory_layer``.
        Side effects: replaces that item in this book. Does not write
        global knowledge. Does not call a model.
        Raises MemoryRefused when the identity is blank, the id is
        unknown, the text is blank, or the text is a role note.
        """
        if not isinstance(confirmed_by, str) or not confirmed_by.strip():
            raise MemoryRefused("CONFIRM_REQUIRED", "a human identity is required")
        if not isinstance(item_id, str) or not item_id:
            raise MemoryRefused("UNKNOWN_ITEM", "no pending memory item")
        index = next((pos for pos, item in enumerate(self._items) if item.item_id == item_id), None)
        if index is None:
            raise MemoryRefused("UNKNOWN_ITEM", "no pending memory item")
        item = self._items[index]
        if is_role_note({"proposal": item.text}):
            raise MemoryRefused("RT-47", "role note")
        if item.status == "confirmed" and item.confirmed:
            return item
        if not item.text.strip():
            raise MemoryRefused("EMPTY", "blank memory cannot be confirmed")
        updated = replace(
            item,
            status="confirmed",
            confirmed=True,
            confirmed_by=confirmed_by.strip(),
        )
        self._items[index] = updated
        return updated

    def record_working(self, text: str) -> MemoryItem:
        """Record one engine-trusted working note.

        Inputs: non-empty note text written by the engine.
        Outputs: a confirmed working item.
        Side effects: appends that item. Does not create a tenant fact.
        Does not write global knowledge. Does not call a model.
        Raises MemoryRefused when the text is a role note.
        Raises ValueError when the text is blank.
        """
        if not isinstance(text, str) or not text.strip():
            raise ValueError("working memory text must be a non-empty string")
        if is_role_note({"proposal": text}):
            raise MemoryRefused("RT-47", "role note")
        self._seq += 1
        item = MemoryItem(
            item_id=f"mem_{self._seq}",
            memory_class="working",
            text=text,
            status="confirmed",
            confirmed=True,
            confirmed_by="",
        )
        self._items.append(item)
        return item
