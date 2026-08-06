"""Per-connection ingest preference persistence."""

from __future__ import annotations

from types import SimpleNamespace

from app.ingest.prefs import get_ingest_prefs, set_ingest_prefs


class _FakeDb:
    def add(self, _row: object) -> None:
        return None

    def commit(self) -> None:
        return None

    def refresh(self, _row: object) -> None:
        return None


def test_ingest_prefs_defaults_and_set() -> None:
    row = SimpleNamespace(ingest_prefs_json=None)
    defaults = get_ingest_prefs(row)  # type: ignore[arg-type]
    assert defaults["notify_mode"] == "batch_summary"
    assert defaults["allow_coa_as_is_default"] is False
    assert defaults["coa_auto_remap_default"] is False

    out = set_ingest_prefs(
        _FakeDb(),  # type: ignore[arg-type]
        row,  # type: ignore[arg-type]
        notify_mode="individual",
        allow_coa_as_is_default=True,
        coa_auto_remap_default=True,
    )
    assert out["notify_mode"] == "individual"
    assert out["allow_coa_as_is_default"] is True
    assert out["coa_auto_remap_default"] is True
    assert get_ingest_prefs(row)["notify_mode"] == "individual"  # type: ignore[arg-type]
