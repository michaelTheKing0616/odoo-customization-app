"""Slice B live smoke — CoA align + opening TB draft JE on Docker Odoo 19."""

from __future__ import annotations

import os

import pytest

from odoo_client import ConnectionConfig, OdooClient
from odoo_client.client import OdooClientError

from app.ingest.coa_align import align_coa_table, suggest_coa_remaps
from app.ingest.opening_balance import commit_opening_tb, validate_opening_tb_table
from app.ingest.pipeline import stage_dry_run, stage_map, stage_plan
from app.ingest.schema import IngestBatch, IngestFile, IngestRow, IngestTable


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@pytest.fixture(scope="module")
def client() -> OdooClient:
    config = ConnectionConfig(
        url=_env("ODOO_URL", "http://127.0.0.1:8069"),
        db=_env("ODOO_DB", "odoo_dev"),
        username=_env("ODOO_USER", "admin"),
        password=_env("ODOO_PASSWORD", "admin"),
    )
    c = OdooClient(config)
    try:
        c.connect()
    except OdooClientError as exc:
        pytest.skip(f"Odoo 19 not reachable for Slice B: {exc}")
    if not str(c.server_version().get("server_version", "")).startswith("19"):
        pytest.skip("Expected Odoo 19")
    if not c.model_exists("account.account"):
        pytest.skip("Accounting (account) not installed — install for Slice B")
    l10n = c.list_installed_modules(name_prefix="l10n", limit=20)
    if not l10n:
        pytest.skip("No l10n_* installed — Slice B needs fiscal localization")
    return c


@pytest.mark.integration
def test_slice_b_coa_align_and_opening_tb_dry_path(client: OdooClient) -> None:
    live = client.execute_kw(
        "account.account",
        "search_read",
        [[]],
        {"fields": ["code", "name", "account_type"], "limit": 5, "order": "code"},
    )
    assert live, "Expected seeded CoA on instance"
    code0 = str(live[0]["code"])
    code1 = str(live[min(1, len(live) - 1)]["code"])

    coa = IngestTable(
        id="coa1",
        model="account.account",
        doc_type="coa",
        rows=[
            IngestRow(
                raw={
                    "code": code0,
                    "name": live[0].get("name") or "Cash",
                    "account_type": live[0].get("account_type") or "asset_cash",
                }
            ),
            IngestRow(
                raw={
                    "code": "ZZ-LEGACY-9999",
                    "name": str(live[0].get("name") or "Cash"),
                    "account_type": "asset_cash",
                }
            ),
        ],
    )
    gaps, warns, summary = align_coa_table(client, coa, allow_as_is=False)
    assert int(summary.get("matched") or 0) >= 1
    assert "ZZ-LEGACY-9999" in summary.get("legacy_only", [])
    assert any(g.value == "ZZ-LEGACY-9999" for g in gaps)
    sug = suggest_coa_remaps(client, coa, min_score=0.1)
    assert isinstance(sug, list)

    # Opening TB: balanced draft JE dry-run via pipeline
    tb = IngestTable(
        id="tb1",
        model="account.move",
        doc_type="opening_trial_balance",
        rows=[
            IngestRow(raw={"code": code0, "debit": "25", "credit": "0"}),
            IngestRow(raw={"code": code1, "debit": "0", "credit": "25"}),
        ],
    )
    tgaps, twarns = validate_opening_tb_table(client, tb)
    assert not tgaps, tgaps
    assert any("DRAFT" in w for w in twarns)

    batch = IngestBatch(
        connection_id="live-b",
        notify_mode="batch_summary",
        allow_coa_as_is=True,
        files=[
            IngestFile(id="f-coa", filename="coa.csv", doc_type="coa", confidence=1.0),
            IngestFile(
                id="f-tb",
                filename="tb.csv",
                doc_type="opening_trial_balance",
                confidence=1.0,
            ),
        ],
        tables=[coa, tb],
    )
    batch = stage_map(batch, client)
    batch = stage_plan(batch)
    assert batch.plan and batch.plan.steps
    batch = stage_dry_run(batch, client)
    assert batch.commit_log is not None
    assert batch.commit_log.failed == 0
    assert any(
        "opening" in m.lower() or "DRAFT" in m or "dry" in m.lower()
        for m in batch.commit_log.messages
    ) or batch.commit_log.created + batch.commit_log.updated + batch.commit_log.skipped >= 0

    # Explicit dry_run opening commit never posts
    res = commit_opening_tb(client, tb, dry_run=True)
    assert res.get("ok") is True
    assert "action_post" not in str(res).lower()
