"""CMP-3 automation trigger probe matrix."""

from __future__ import annotations

from typing import Any

from app.automation_trigger_probe import (
    TRIGGER_PROBE_FALLBACK,
    probe_automation_triggers,
    probe_table_for_major,
)


class _FakeClient:
    def __init__(self, major: int, *, triggers: list[tuple[str, str]] | None = None) -> None:
        self.capabilities = type("Caps", (), {"major": major})()
        self._triggers = triggers

    def model_exists(self, model: str) -> bool:
        return model == "base.automation"

    def execute_kw(
        self,
        model: str,
        method: str,
        args: list[Any],
        kwargs: dict[str, Any],
    ) -> Any:
        if self._triggers is None:
            raise RuntimeError("probe failed")
        return {
            "trigger": {
                "selection": self._triggers,
                "type": "selection",
            },
            "on_change_field_ids": {"type": "many2many"},
        }


def test_probe_table_for_major_16_experimental() -> None:
    row = probe_table_for_major(16)[0]
    assert row["on_webhook"] is False
    assert row["on_change"] is False


def test_probe_table_for_major_19() -> None:
    row = probe_table_for_major(19)[0]
    assert row["on_webhook"] is True
    assert row["on_change"] is True


def test_live_probe_reads_fields_get() -> None:
    client = _FakeClient(
        19,
        triggers=[
            ("on_create", "On create"),
            ("on_webhook", "On webhook"),
            ("on_change", "On UI change"),
        ],
    )
    data = probe_automation_triggers(client)
    assert data["source"] == "live"
    assert "on_webhook" in data["supported_triggers"]
    assert "on_change" in data["supported_triggers"]
    assert data["probe_table"][0]["on_change_field_ids"] is True


def test_fallback_when_probe_fails() -> None:
    client = _FakeClient(17, triggers=None)
    data = probe_automation_triggers(client)
    assert data["source"] == "fallback"
    fb = TRIGGER_PROBE_FALLBACK[17]
    assert data["probe_table"][0]["on_webhook"] == fb["on_webhook"]
    assert "on_create" in data["supported_triggers"]
