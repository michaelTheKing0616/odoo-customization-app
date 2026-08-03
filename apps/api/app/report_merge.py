"""Merge multiple Odoo QWeb PDF renders into one document (BLK-8)."""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

from odoo_client import OdooClient
from odoo_client.client import OdooClientError
from odoo_client.report_render import ReportRenderProbe, probe_report_render, render_report_pdf
from pypdf import PdfReader, PdfWriter


class ReportMergeError(Exception):
    pass


@dataclass
class MergePrintItemResult:
    report_id: int
    report_name: str | None
    record_ids: list[int]
    page_count: int
    bytes_len: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "report_name": self.report_name,
            "record_ids": list(self.record_ids),
            "page_count": self.page_count,
            "bytes_len": self.bytes_len,
        }


@dataclass
class MergePrintResult:
    items: list[MergePrintItemResult] = field(default_factory=list)
    total_pages: int = 0
    probe: ReportRenderProbe | None = None
    filename: str = "merged-report.pdf"

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": [i.to_dict() for i in self.items],
            "total_pages": self.total_pages,
            "probe": self.probe.to_dict() if self.probe else None,
            "filename": self.filename,
        }


def merge_pdf_bytes(chunks: list[bytes]) -> tuple[bytes, int]:
    if not chunks:
        raise ReportMergeError("No PDF chunks to merge")
    writer = PdfWriter()
    total_pages = 0
    for chunk in chunks:
        reader = PdfReader(BytesIO(chunk))
        total_pages += len(reader.pages)
        for page in reader.pages:
            writer.add_page(page)
    out = BytesIO()
    writer.write(out)
    return out.getvalue(), total_pages


def pdf_page_count(pdf_bytes: bytes) -> int:
    return len(PdfReader(BytesIO(pdf_bytes)).pages)


def run_merge_print(
    client: OdooClient,
    *,
    items: list[dict[str, Any]],
    order: list[int] | None = None,
) -> tuple[bytes, MergePrintResult]:
    if not items:
        raise ReportMergeError("items must not be empty")

    normalized: list[tuple[int, list[int]]] = []
    for raw in items:
        report_id = int(raw["report_id"])
        record_ids = [int(i) for i in raw["record_ids"]]
        if not record_ids:
            raise ReportMergeError(f"report_id={report_id} has empty record_ids")
        normalized.append((report_id, record_ids))

    indices = list(order) if order is not None else list(range(len(normalized)))
    if sorted(indices) != list(range(len(normalized))):
        raise ReportMergeError("order must be a permutation of item indices")
    ordered = [normalized[i] for i in indices]

    probe = probe_report_render(client)
    if probe.primary_path == "none":
        raise ReportMergeError(probe.message or "Report rendering unavailable on this instance")

    rendered: list[bytes] = []
    item_results: list[MergePrintItemResult] = []
    for report_id, record_ids in ordered:
        try:
            rows = client.execute_kw(
                "ir.actions.report",
                "read",
                [[report_id]],
                {"fields": ["report_name"]},
            )
        except OdooClientError as exc:
            raise ReportMergeError(str(exc)) from exc
        if not rows:
            raise ReportMergeError(f"Report id={report_id} not found")
        report_name = rows[0].get("report_name")
        try:
            pdf = render_report_pdf(client, report_id, record_ids, probe=probe)
        except OdooClientError as exc:
            raise ReportMergeError(
                f"Failed to render report id={report_id} ({report_name!r}): {exc}"
            ) from exc
        pages = pdf_page_count(pdf)
        rendered.append(pdf)
        item_results.append(
            MergePrintItemResult(
                report_id=report_id,
                report_name=str(report_name) if report_name else None,
                record_ids=record_ids,
                page_count=pages,
                bytes_len=len(pdf),
            )
        )

    merged, total_pages = merge_pdf_bytes(rendered)
    meta = MergePrintResult(
        items=item_results,
        total_pages=total_pages,
        probe=probe,
    )
    return merged, meta
