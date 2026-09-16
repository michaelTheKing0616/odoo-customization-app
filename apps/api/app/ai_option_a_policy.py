"""Fail-closed policy for LLM-authored Option A modules.

Gold templates skip this module. Authored drafts must not ship secrets, SSRF,
invented taxes, or live ``state=code``.
"""

from __future__ import annotations

import ipaddress
import re
from typing import Any
from urllib.parse import urlparse

from app.ai_host_install import enrich_model_missing_finding
from app.ai_option_a_view_fields import view_field_consistency_findings

_URL_RE = re.compile(r"https?://[^\s'\"<>]+", re.I)
_TAX_CREATE_RE = re.compile(
    r"""(?:env\s*\[\s*['\"]account\.tax['\"]\s*\]|\.env\s*\[\s*['\"]account\.tax['\"]\s*\])\s*\.create\b"""
    r"""|['\"]account\.tax['\"]\s*\)\s*\.create\b""",
    re.I,
)
_SECRET_RE = re.compile(
    r"(?i)(sk_live_|sk_test_|api[_-]?secret|BEGIN (?:RSA |OPENSSH )?PRIVATE KEY"
    r"|password\s*=\s*['\"][^'\"]{8,})"
)
_STATE_CODE_RE = re.compile(r"""['\"]state['\"]\s*:\s*['\"]code['\"]|state\s*=\s*['\"]code['\"]""")
_STOCK_COMPUTE_AMOUNT_RE = re.compile(r"""\bdef\s+_compute_amount\s*\(""")
_PRICE_SUBTOTAL_FIELD_RE = re.compile(r"""\bprice_subtotal\s*=\s*fields\.""")


def _py_blocks(draft: dict[str, Any]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for block in draft.get("custom_code_blocks") or []:
        if not isinstance(block, dict):
            continue
        path = str(block.get("source_file") or block.get("path") or "block")
        content = str(block.get("content") or "")
        kind = str(block.get("kind") or "")
        if path.endswith(".py") or kind == "python":
            out.append((path, content))
    return out


def _host_is_blocked(host: str) -> bool:
    h = (host or "").strip().lower().rstrip(".")
    if not h:
        return True
    if h in {"localhost", "localhost.localdomain"}:
        return True
    if h.endswith(".local") or h.endswith(".internal"):
        return True
    try:
        ip = ipaddress.ip_address(h)
    except ValueError:
        return False
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def extract_http_hosts(text: str) -> list[str]:
    hosts: list[str] = []
    seen: set[str] = set()
    for match in _URL_RE.finditer(text or ""):
        parsed = urlparse(match.group(0).rstrip(").,]"))
        host = (parsed.hostname or "").lower()
        if host and host not in seen:
            seen.add(host)
            hosts.append(host)
    return hosts


def extract_disclosure_ir(draft: dict[str, Any]) -> dict[str, Any]:
    """Audit view of authored code — does not decide whether the job is allowed."""
    py_blobs: list[str] = []
    xml_blobs: list[str] = []
    files: list[str] = []
    for block in draft.get("custom_code_blocks") or []:
        if not isinstance(block, dict):
            continue
        path = str(block.get("source_file") or block.get("path") or "")
        content = str(block.get("content") or "")
        files.append(path)
        kind = str(block.get("kind") or "")
        if path.endswith(".py") or kind == "python":
            py_blobs.append(content)
        elif path.endswith(".xml") or kind in {"xml", "qweb"}:
            xml_blobs.append(content)
    blob = "\n".join(py_blobs + xml_blobs)
    inherits = set(re.findall(r"""_inherit\s*=\s*['\"]([^'\"]+)['\"]""", "\n".join(py_blobs)))
    # Draft models with mode=inherit are hosts even when Python uses models.Model + _inherit
    # only on a thin extension, or when XML-only inherits land first.
    for row in draft.get("models") or []:
        if not isinstance(row, dict):
            continue
        mid = str(row.get("model") or "").strip()
        mode = str(row.get("mode") or "").strip().lower()
        if mid and mode == "inherit" and not mid.startswith("x_"):
            inherits.add(mid)
    inherits_sorted = sorted(inherits)
    names = sorted(
        set(re.findall(r"""_name\s*=\s*['\"]([^'\"]+)['\"]""", "\n".join(py_blobs)))
    )
    report_xmlids = sorted(
        set(
            re.findall(
                r"""inherit_id=["']([^"']+)["']""",
                "\n".join(xml_blobs),
            )
        )
    )
    tax_xmlids = sorted(
        set(
            re.findall(
                r"""(?:ref\(|env\.ref\()['\"]([^'\"]*account[^'\"]*tax[^'\"]*)['\"]""",
                blob,
                flags=re.I,
            )
        )
    )
    return {
        "http_hosts": extract_http_hosts(blob),
        "inherit_models": inherits_sorted,
        "new_models": names,
        "report_xmlids": report_xmlids,
        "tax_xmlids_used": tax_xmlids,
        "files": [f for f in files if f],
        "secrets_stripped": True,
    }


def policy_findings(draft: dict[str, Any]) -> list[dict[str, str]]:
    """Return blocking findings. Empty means policy pass."""
    findings: list[dict[str, str]] = []
    for block in draft.get("custom_code_blocks") or []:
        if not isinstance(block, dict):
            continue
        path = str(block.get("source_file") or block.get("path") or "block")
        content = str(block.get("content") or "")
        if _TAX_CREATE_RE.search(content):
            findings.append(
                {
                    "code": "tax_create_forbidden",
                    "message": "Modules must not create account.tax records — map existing l10n xmlids.",
                    "file": path,
                }
            )
        if _SECRET_RE.search(content):
            findings.append(
                {
                    "code": "secret_in_module",
                    "message": "API keys / passwords must not be written into the module. Operator pastes them in Odoo after Promote.",
                    "file": path,
                }
            )
        if _STATE_CODE_RE.search(content):
            findings.append(
                {
                    "code": "live_state_code",
                    "message": "Live ir.actions.server state=code is refused. Ship an installable module instead.",
                    "file": path,
                }
            )
        for host in extract_http_hosts(content):
            if _host_is_blocked(host):
                findings.append(
                    {
                        "code": "ssrf_host",
                        "message": f"HTTP host {host} is private/link-local — blocked.",
                        "file": path,
                    }
                )

    # CE sale inherit killers — should already be stripped by harden_authored_python;
    # fail closed if anything remains so zip never ships a known sandbox Fault.
    for path, content in _py_blocks(draft):
        if "sale.order" not in content or "_inherit" not in content:
            continue
        if _STOCK_COMPUTE_AMOUNT_RE.search(content):
            findings.append(
                {
                    "code": "stock_compute_amount_override",
                    "message": (
                        "Do not redefine stock _compute_amount on sale.order / sale.order.line. "
                        "Add x_* markup/WHT computes instead (CE uses tax_ids, not tax_id)."
                    ),
                    "file": path,
                }
            )
        if _PRICE_SUBTOTAL_FIELD_RE.search(content):
            findings.append(
                {
                    "code": "stock_price_subtotal_redeclare",
                    "message": (
                        "Do not redeclare stock price_subtotal. Use x_* monetary computes for markup."
                    ),
                    "file": path,
                }
            )
        if re.search(r"""(['"])tax_id\1|\.tax_id\b""", content):
            findings.append(
                {
                    "code": "sale_line_tax_id",
                    "message": (
                        "sale.order.line taxes field is tax_ids (Many2many) — never tax_id."
                    ),
                    "file": path,
                }
            )

    # OWL killer: arch field name missing from authored Python / non-x_* invent.
    findings.extend(view_field_consistency_findings(draft))
    return findings


def rpc_verify_findings(
    draft: dict[str, Any],
    client: Any | None,
) -> list[dict[str, str]]:
    """When a connection client is present, referenced xmlids/models must exist."""
    if client is None:
        return []
    ir = extract_disclosure_ir(draft)
    findings: list[dict[str, str]] = []
    execute_kw = getattr(client, "execute_kw", None)
    if execute_kw is None:
        search = getattr(client, "search", None)
        if search is None:
            return []

        def _count(model: str, domain: list[Any]) -> int:
            ids = search(model, domain, limit=1)
            return len(ids or [])

    else:

        def _count(model: str, domain: list[Any]) -> int:
            return int(execute_kw(model, "search_count", [domain]) or 0)

    try:
        for model in ir.get("inherit_models") or []:
            if not model:
                continue
            if _count("ir.model", [("model", "=", model)]) < 1:
                findings.append(
                    enrich_model_missing_finding(
                        {
                            "code": "model_missing",
                            "message": f"Inherit model {model} is not on this connection.",
                            "file": "models",
                        },
                        model,
                    )
                )
        for xmlid in ir.get("tax_xmlids_used") or []:
            if "." not in xmlid:
                continue
            module, name = xmlid.split(".", 1)
            if _count("ir.model.data", [("module", "=", module), ("name", "=", name)]) < 1:
                findings.append(
                    {
                        "code": "tax_xmlid_missing",
                        "message": (
                            f"Tax xmlid {xmlid} is not on this connection. "
                            "Configure l10n WHT first — we will not invent account.tax."
                        ),
                        "file": "data",
                    }
                )
    except Exception as exc:  # noqa: BLE001
        findings.append(
            {
                "code": "rpc_verify_failed",
                "message": f"Could not verify xmlids on the connection: {exc}",
                "file": "rpc",
            }
        )
    return findings
