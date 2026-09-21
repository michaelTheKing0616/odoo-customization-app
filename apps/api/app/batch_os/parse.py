"""Tabular intake — reuses data_import.parse_tabular (CSV + xlsx)."""

from __future__ import annotations

from app.data_import import parse_tabular


def parse_upload(raw: bytes, filename: str) -> tuple[list[str], list[dict[str, str]]]:
    return parse_tabular(raw, filename)
