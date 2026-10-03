"""Plan cards cover every catalog op. Recovery never calls a partial apply finished."""

from __future__ import annotations

from app.changeset.ops import OP_CATALOG
from app.changeset.plan_card import PLAN_CARD_SECTIONS, render_plan_card
from app.changeset.recovery import recover


def _journal(kill: str, *, mode: str, count: int) -> list[dict]:
    entries: list[dict] = []
    if kill == "before_intent":
        return entries
    entries.append({"kind": "INTENT", "mode": mode})
    if kill == "after_intent":
        return entries
    for index in range(count):
        entries.append({"kind": "INTENT", "index": index})
        entries.append({"kind": "BEFORE", "index": index})
        if kill in {"after_before", "mid_execute"} and index == 0:
            return entries
        entries.append({"kind": "RESULT", "index": index})
    if kill == "after_result":
        return entries
    if kill == "mid_verify":
        entries.append({"kind": "VERIFYING"})
        return entries
    if kill == "verified":
        entries.append({"kind": "VERIFIED"})
        return entries
    if kill == "mid_rollback":
        entries.append({"kind": "COMPENSATE", "index": count - 1})
        return entries
    return entries


def test_every_catalog_op_has_a_nine_section_card() -> None:
    for op_type in OP_CATALOG:
        card = render_plan_card(
            [{"type": op_type, "params": {"model": "sale.order", "name": "x_demo", "module": "sale"}}],
            goal="show the change",
            assumptions=["staging"],
            environment="staging",
        )
        assert tuple(card) == PLAN_CARD_SECTIONS or set(PLAN_CARD_SECTIONS) <= set(card)
        assert all(section in card for section in PLAN_CARD_SECTIONS)
        assert op_type in card["changes"][0]["description"]
        for name in ("data.delete", "module.uninstall", "rpc.write"):
            if name == op_type:
                assert name not in card["not_changing"]
            else:
                assert name in card["not_changing"]
        assert card["verification"] == [f"postcondition:{op_type}"]
        if op_type == "field.create":
            assert card["rollback"] == [{"op": "field.create", "inverse": "field.deprecate", "irreversible": False}]
        if op_type == "data.delete":
            assert card["rollback"][0]["irreversible"] is True


def test_crash_matrix_never_reports_a_partial_apply_as_verified() -> None:
    points = ("before_intent", "after_intent", "after_before", "mid_execute", "after_result", "mid_verify", "mid_rollback")
    for mode in ("T", "C"):
        for point in points:
            decision = recover(_journal(point, mode=mode, count=2), mode=mode, expected_ops=2)
            assert decision["status"] in {"VERIFIED", "ROLLED_BACK", "NEEDS_HUMAN"}
            assert decision["status"] != "APPLIED"
            if point == "after_result":
                assert decision["status"] == "NEEDS_HUMAN"
            if point in {"before_intent", "after_intent", "after_before", "mid_execute"}:
                assert decision["status"] == "ROLLED_BACK"
            if point == "mid_verify":
                assert decision["status"] == "NEEDS_HUMAN"
            if point == "mid_rollback":
                assert decision["status"] == "NEEDS_HUMAN"
        verified = recover(_journal("verified", mode=mode, count=2), mode=mode, expected_ops=2)
        assert verified["status"] == "VERIFIED"
        partial = recover(
            [{"kind": "RESULT", "index": 0}],
            mode="T",
            expected_ops=2,
        )
        assert partial["status"] == "ROLLED_BACK"
        assert partial["report"]["missing"] == [1]
        stuck = recover(
            [{"kind": "RESULT", "index": 0}, {"kind": "RESULT", "index": 1}],
            mode="C",
            expected_ops=2,
        )
        assert stuck["status"] == "NEEDS_HUMAN"
        compensated = recover(
            [
                {"kind": "RESULT", "index": 0},
                {"kind": "RESULT", "index": 1},
                {"kind": "COMPENSATE", "index": 1},
                {"kind": "COMPENSATE", "index": 0},
            ],
            mode="C",
            expected_ops=2,
        )
        assert compensated["status"] == "ROLLED_BACK"
        contradictory = recover([{"kind": "VERIFYING"}], mode="T", expected_ops=2)
        assert contradictory["status"] == "NEEDS_HUMAN"
        assert contradictory["report"]["missing"] == [0, 1]
        false_verified = recover([{"kind": "RESULT", "index": 0}, {"kind": "VERIFIED"}], mode="T", expected_ops=2)
        assert false_verified["status"] == "NEEDS_HUMAN"
        partial_c = recover([{"kind": "RESULT", "index": 0}], mode="C", expected_ops=2)
        assert partial_c["status"] == "NEEDS_HUMAN"
