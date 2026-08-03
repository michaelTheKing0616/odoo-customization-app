"""Multi-level approval process semantics (CMP-10)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

ProcessState = Literal["draft", "submitted", "approved", "refused"]
LevelDecision = Literal["approved", "refused"]


@dataclass(frozen=True)
class ProcessLevel:
    level: int
    min_approvals: int
    approver_user_ids: tuple[int, ...] = ()
    approver_group_id: int | None = None
    domain: str | None = None


@dataclass(frozen=True)
class LevelApproval:
    user_id: int
    status: LevelDecision


def parse_chain(raw: str | list[Any] | None) -> list[ProcessLevel]:
    if raw is None:
        return []
    data = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(data, list):
        return []
    out: list[ProcessLevel] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        users = row.get("approver_user_ids") or row.get("user_ids") or []
        if not isinstance(users, list):
            users = []
        out.append(
            ProcessLevel(
                level=int(row.get("level") or row.get("order") or len(out) + 1),
                min_approvals=max(1, int(row.get("min_approvals") or 1)),
                approver_user_ids=tuple(int(u) for u in users if u is not None),
                approver_group_id=int(row["approver_group_id"])
                if row.get("approver_group_id") is not None
                else (int(row["group_id"]) if row.get("group_id") is not None else None),
                domain=str(row["domain"]).strip() if row.get("domain") else None,
            )
        )
    return sorted(out, key=lambda lv: lv.level)


def parse_level_approvals(raw: str | dict[str, Any] | None) -> dict[int, list[LevelApproval]]:
    if raw is None:
        return {}
    data = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(data, dict):
        return {}
    levels = data.get("levels") if isinstance(data.get("levels"), dict) else data
    out: dict[int, list[LevelApproval]] = {}
    if not isinstance(levels, dict):
        return out
    for key, rows in levels.items():
        try:
            lvl = int(key)
        except (TypeError, ValueError):
            continue
        if not isinstance(rows, list):
            continue
        parsed: list[LevelApproval] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            status = str(row.get("status") or "approved")
            if status not in {"approved", "refused"}:
                status = "approved"
            parsed.append(
                LevelApproval(user_id=int(row["user_id"]), status=status)  # type: ignore[arg-type]
            )
        out[lvl] = parsed
    return out


def dump_level_approvals(levels: dict[int, list[LevelApproval]]) -> str:
    payload = {
        "levels": {
            str(lvl): [{"user_id": a.user_id, "status": a.status} for a in rows]
            for lvl, rows in sorted(levels.items())
        }
    }
    return json.dumps(payload)


def is_refused(levels: dict[int, list[LevelApproval]]) -> bool:
    return any(a.status == "refused" for rows in levels.values() for a in rows)


def level_approved_count(level: ProcessLevel, rows: list[LevelApproval]) -> int:
    approved_users = {a.user_id for a in rows if a.status == "approved"}
    return len(approved_users)


def level_satisfied(level: ProcessLevel, rows: list[LevelApproval]) -> bool:
    if is_refused({level.level: rows}):
        return False
    return level_approved_count(level, rows) >= level.min_approvals


def pending_level(
    chain: list[ProcessLevel],
    levels: dict[int, list[LevelApproval]],
) -> int | None:
    if is_refused(levels):
        return None
    for lv in chain:
        rows = levels.get(lv.level, [])
        if any(a.status == "refused" for a in rows):
            return None
        if not level_satisfied(lv, rows):
            return lv.level
    return None


def all_levels_satisfied(chain: list[ProcessLevel], levels: dict[int, list[LevelApproval]]) -> bool:
    if not chain:
        return True
    if is_refused(levels):
        return False
    return pending_level(chain, levels) is None


def level_applies_to_user(
    level: ProcessLevel,
    *,
    user_id: int,
    user_group_ids: set[int],
) -> bool:
    if user_id in level.approver_user_ids:
        return True
    if level.approver_group_id is not None and level.approver_group_id in user_group_ids:
        return True
    return False


def can_approve_at_level(
    *,
    level: ProcessLevel,
    pending: int | None,
    user_id: int,
    user_group_ids: set[int],
    existing: list[LevelApproval],
) -> tuple[bool, str]:
    if pending is None:
        return False, "Process is refused or complete"
    if level.level != pending:
        return False, f"Level {pending} must complete before level {level.level}"
    if not level_applies_to_user(level, user_id=user_id, user_group_ids=user_group_ids):
        return False, "User is not an approver for this level"
    if any(a.user_id == user_id and a.status == "approved" for a in existing):
        return False, "User already approved at this level"
    return True, "OK"


def approver_user_ids_for_level(level: ProcessLevel) -> list[int]:
    return list(level.approver_user_ids)
