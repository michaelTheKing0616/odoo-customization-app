"""CMP-7 property fields probe matrix."""

from __future__ import annotations

from typing import Any

from app.property_fields_probe import (
    PROPERTY_PROBE_FALLBACK,
    probe_property_fields,
    probe_table_for_major,
)


class _FakeClient:
    def __init__(self, major: int, *, ttypes: set[str] | None = None) -> None:
        self.capabilities = type("Caps", (), {"major": major})()
        self._ttypes = ttypes

    def execute_kw(
        self,
        model: str,
        method: str,
        args: list[Any],
        kwargs: dict[str, Any],
    ) -> Any:
        if self._ttypes is None:
            raise RuntimeError("probe failed")
        return {
            "ttype": {
                "selection": [(t, t) for t in sorted(self._ttypes)],
                "type": "selection",
            },
            "definition_record": {"type": "char"},
            "definition_record_field": {"type": "char"},
        }


def test_probe_table_for_major_16_unsupported() -> None:
    row = probe_table_for_major(16)[0]
    assert row["supported"] is False


def test_probe_table_for_major_19_supported() -> None:
    row = probe_table_for_major(19)[0]
    assert row["supported"] is True


def test_live_probe_reads_ttype_selection() -> None:
    client = _FakeClient(19, ttypes={"properties", "properties_definition", "char"})
    data = probe_property_fields(client)
    assert data["source"] == "live"
    assert data["supported"] is True
    assert data["probe_table"][0]["ttype_properties"] is True


def test_fallback_when_probe_fails() -> None:
    client = _FakeClient(17, ttypes=None)
    data = probe_property_fields(client)
    assert data["source"] == "fallback"
    assert data["probe_table"][0]["supported"] == PROPERTY_PROBE_FALLBACK[17]["supported"]
