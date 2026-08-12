"""Tests for l10n source chunks and localization guidance."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")

from app.expert.grounding import GroundingBundle  # noqa: E402
from app.expert.l10n_chunks import chunk_res_country_state_csv  # noqa: E402
from app.expert.l10n_guidance import (  # noqa: E402
    looks_like_l10n_state_question,
    try_rule_based_l10n_guidance,
)

CAPITAL_Q = (
    "Is Capital Governorate represented as a State on Odoo with Capital?"
)

_CSV = (
    Path(__file__).resolve().parents[3]
    / ".cache"
    / "expert"
    / "odoo_src_19"
    / "odoo"
    / "addons"
    / "base"
    / "data"
    / "res.country.state.csv"
)


def test_l10n_state_question_detected() -> None:
    assert looks_like_l10n_state_question(CAPITAL_Q)


def test_l10n_guidance_mentions_amman_not_capital_governorate() -> None:
    payload = try_rule_based_l10n_guidance(
        CAPITAL_Q,
        GroundingBundle(retrieval_version="19.0"),
        connection_id="c1",
    )
    assert payload is not None
    body = payload["answer_markdown"]
    assert "Capital Governorate" in body
    assert "Amman" in body
    assert "res.country.state" in body


def test_chunk_jordan_states_from_csv() -> None:
    if not _CSV.is_file():
        pytest.skip("odoo 19 source cache not present — run ingest once online")
    chunks = chunk_res_country_state_csv(_CSV, version="19.0")
    jo = next(c for c in chunks if "(jo)" in c.breadcrumb.lower())
    assert "Amman" in jo.text
    assert "JO-AM" in jo.text
