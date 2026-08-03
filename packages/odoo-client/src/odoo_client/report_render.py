"""QWeb PDF report rendering — probe RPC vs HTTP session paths (BLK-8)."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any
from urllib import error, request
from urllib.parse import quote

from odoo_client.client import OdooClient, OdooClientError

_RPC_CANDIDATES = (
    "render_qweb_pdf",
    "_render_qweb_pdf",
    "render_pdf",
    "_render",
)


@dataclass(frozen=True)
class ReportRenderProbe:
    major: int
    rpc_methods: dict[str, str] = field(default_factory=dict)
    http_report_pdf: bool = False
    primary_path: str = "none"
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "major": self.major,
            "rpc_methods": dict(self.rpc_methods),
            "http_report_pdf": self.http_report_pdf,
            "primary_path": self.primary_path,
            "message": self.message,
        }


def _pdf_from_rpc_result(result: Any) -> bytes | None:
    if isinstance(result, (list, tuple)) and result:
        chunk = result[0]
    else:
        chunk = result
    if isinstance(chunk, bytes):
        return chunk
    if isinstance(chunk, str):
        try:
            return base64.b64decode(chunk)
        except Exception:  # noqa: BLE001
            return None
    return None


def _session_opener(client: OdooClient) -> request.OpenerDirector:
    auth_url = f"{client.config.url}/web/session/authenticate"
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "db": client.config.db,
                "login": client.config.username,
                "password": client.config.password,
            },
            "id": 1,
        }
    ).encode()
    req = request.Request(
        auth_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    opener = request.build_opener(request.HTTPCookieProcessor())
    try:
        with opener.open(req, timeout=client.config.timeout) as resp:
            body = json.loads(resp.read().decode())
    except error.URLError as exc:
        raise OdooClientError(f"Report session authenticate failed: {exc}") from exc
    uid = (body.get("result") or {}).get("uid")
    if not uid:
        raise OdooClientError("Report session authenticate failed — no uid in response")
    return opener


def _http_render_pdf(client: OdooClient, report_name: str, res_ids: list[int]) -> bytes:
    if not res_ids:
        raise OdooClientError("record_ids must not be empty for report render")
    docids = ",".join(str(int(i)) for i in res_ids)
    path = f"/report/pdf/{quote(report_name, safe='.')}/{docids}"
    url = f"{client.config.url}{path}"
    opener = _session_opener(client)
    req = request.Request(url, method="GET")
    try:
        with opener.open(req, timeout=client.config.timeout) as resp:
            data = resp.read()
    except error.URLError as exc:
        raise OdooClientError(f"HTTP report render failed for {report_name!r}: {exc}") from exc
    if not data.startswith(b"%PDF"):
        snippet = data[:200].decode("utf-8", errors="replace")
        raise OdooClientError(
            f"HTTP report render for {report_name!r} did not return PDF bytes: {snippet!r}"
        )
    return data


def _read_report(client: OdooClient, report_id: int) -> dict[str, Any]:
    rows = client.execute_kw(
        "ir.actions.report",
        "read",
        [[int(report_id)]],
        {"fields": ["name", "model", "report_type", "report_name"]},
    )
    if not rows:
        raise OdooClientError(f"ir.actions.report id={report_id} not found")
    return rows[0]


def probe_report_render(
    client: OdooClient,
    *,
    sample_report_id: int | None = None,
    sample_res_id: int | None = None,
) -> ReportRenderProbe:
    """Record which render path works on this instance (RPC vs HTTP session)."""
    major = client.capabilities.major
    rpc_results: dict[str, str] = {}
    http_ok = False

    report_id = sample_report_id
    res_id = sample_res_id
    if report_id is None:
        rows = client.execute_kw(
            "ir.actions.report",
            "search_read",
            [[("report_type", "=", "qweb-pdf")]],
            {"fields": ["id", "model"], "limit": 1, "order": "id"},
        )
        if rows:
            report_id = int(rows[0]["id"])
            model = str(rows[0].get("model") or "")
            if res_id is None and model:
                found = client.execute_kw(model, "search", [[]], {"limit": 1})
                if found:
                    res_id = int(found[0])

    if report_id is None or res_id is None:
        return ReportRenderProbe(
            major=major,
            rpc_methods=rpc_results,
            http_report_pdf=False,
            primary_path="none",
            message="No qweb-pdf report / sample record available to probe render path.",
        )

    for method in _RPC_CANDIDATES:
        try:
            result = client.execute_kw(
                "ir.actions.report",
                method,
                [[int(report_id)], [int(res_id)]],
            )
            pdf = _pdf_from_rpc_result(result)
            if pdf and pdf.startswith(b"%PDF"):
                rpc_results[method] = "ok"
            else:
                rpc_results[method] = "unexpected_shape"
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            if "Private methods" in msg:
                rpc_results[method] = "private_method"
            elif "cannot be called remotely" in msg:
                rpc_results[method] = "not_remote"
            else:
                rpc_results[method] = msg.split("\n", 1)[0][:120]

    report_name = str(_read_report(client, int(report_id)).get("report_name") or "")
    if report_name:
        try:
            pdf = _http_render_pdf(client, report_name, [int(res_id)])
            http_ok = bool(pdf.startswith(b"%PDF"))
        except OdooClientError as exc:
            rpc_results["http_report_pdf"] = str(exc)[:120]

    primary = "none"
    for method in _RPC_CANDIDATES:
        if rpc_results.get(method) == "ok":
            primary = f"rpc:{method}"
            break
    if primary == "none" and http_ok:
        primary = "http_session:/report/pdf"

    if primary == "none":
        message = (
            "No working report render path found on this instance — merged PDF unavailable."
        )
    elif primary.startswith("rpc:"):
        message = f"Report PDF via RPC method {primary.split(':', 1)[1]!r}."
    else:
        message = "Report PDF via authenticated HTTP /report/pdf/<report_name>/<ids>."

    return ReportRenderProbe(
        major=major,
        rpc_methods=rpc_results,
        http_report_pdf=http_ok,
        primary_path=primary,
        message=message,
    )


def render_report_pdf(
    client: OdooClient,
    report_id: int,
    res_ids: list[int],
    *,
    probe: ReportRenderProbe | None = None,
) -> bytes:
    """Render one QWeb PDF report for the given record ids."""
    ids = [int(i) for i in res_ids if int(i) > 0]
    if not ids:
        raise OdooClientError("res_ids must contain at least one positive id")

    row = _read_report(client, int(report_id))
    report_type = str(row.get("report_type") or "")
    if report_type and report_type != "qweb-pdf":
        raise OdooClientError(
            f"Report {report_id!r} has report_type={report_type!r}; only qweb-pdf is supported"
        )
    report_name = str(row.get("report_name") or "").strip()
    if not report_name:
        raise OdooClientError(f"Report {report_id!r} has no report_name")

    probe = probe or probe_report_render(client, sample_report_id=int(report_id), sample_res_id=ids[0])
    if probe.primary_path.startswith("rpc:"):
        method = probe.primary_path.split(":", 1)[1]
        result = client.execute_kw("ir.actions.report", method, [[int(report_id)], ids])
        pdf = _pdf_from_rpc_result(result)
        if pdf and pdf.startswith(b"%PDF"):
            return pdf
        raise OdooClientError(f"RPC render via {method!r} did not return PDF bytes")

    if probe.http_report_pdf or probe.primary_path == "http_session:/report/pdf":
        return _http_render_pdf(client, report_name, ids)

    raise OdooClientError(probe.message or "Report rendering is unavailable on this instance")
