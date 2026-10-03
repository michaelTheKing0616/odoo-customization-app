"""Adopt l10n_ng taxes by xmlid. Do not invent a second tax."""

from __future__ import annotations

import pytest

from app.config_as_code.l10n_ng import adopt_or_refuse, l10n_ng_xmlid


def test_xmlid_shape() -> None:
    assert l10n_ng_xmlid(1, "vat_out_75") == "account.1_l10n_ng_vat_out_75"


def test_adopts_existing_tax() -> None:
    xmlid = "account.1_l10n_ng_vat_out_75"
    assert adopt_or_refuse({xmlid}, 1, "vat_out_75") == xmlid


def test_refuses_to_duplicate_a_missing_tax() -> None:
    with pytest.raises(ValueError, match="refusing"):
        adopt_or_refuse(set(), 1, "vat_out_75")
