"""Apply a compiled config plan to an in-memory database. The second apply writes nothing."""

from __future__ import annotations

from typing import Any


class MemoryDb:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}
        self.writes = 0

    def upsert(self, key: str, body: dict[str, Any]) -> bool:
        if self.rows.get(key) == body:
            return False
        self.rows[key] = dict(body)
        self.writes += 1
        return True


def apply_plan(db: MemoryDb, plan: list[dict[str, Any]]) -> int:
    written = 0
    for step in plan:
        key = f"{step['section']}:{step['index']}"
        if db.upsert(key, step["body"]):
            written += 1
    return written
