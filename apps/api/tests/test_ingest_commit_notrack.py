"""ING-8 — mail_notrack context on commit."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from app.ingest.commit import INGEST_BULK_CONTEXT, run_commit_plan
from app.ingest.order import build_plan
from app.ingest.schema import IngestBatch, IngestRow, IngestTable


def test_commit_passes_bulk_context() -> None:
    batch = IngestBatch(
        tables=[
            IngestTable(
                id="t1",
                model="res.partner",
                doc_type="customer_list",
                mapping={"name": "name"},
                natural_key_fields=["name"],
                rows=[IngestRow(raw={"name": "Acme"}, values={})],
            )
        ]
    )
    batch.plan = build_plan(batch)
    captured: list[dict[str, Any] | None] = []

    def _fake_dry_run_or_commit(*_a, **kwargs):
        captured.append(kwargs.get("rpc_context"))
        from app.data_import import ImportCommitResult

        return ImportCommitResult(ok=True, created=1, message="ok")

    with patch("app.ingest.commit.dry_run_or_commit", side_effect=_fake_dry_run_or_commit):
        run_commit_plan(object(), batch, dry_run=False)
    assert captured
    assert captured[0] == INGEST_BULK_CONTEXT
    assert captured[0]["mail_notrack"] is True
