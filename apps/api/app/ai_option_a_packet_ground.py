"""GND-G-OPTA — custom code authoring grounded on the live schema packet.

Puts the host-model slice in the LLM prompt and statically refuses authored
references that the packet does not contain (before zip / sandbox).
"""

from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Any

from app.ai_option_a_view_fields import collect_draft_python_fields
from app.live_schema_context import (
    SchemaPacket,
    build_schema_packet,
    prepend_schema_packet,
)

_ENV_MODEL_RE = re.compile(
    r"""(?:self\.)?env\s*\[\s*['\"]([^'\"]+)['\"]\s*\]"""
)
_INHERIT_RE = re.compile(r"""_inherit\s*=\s*['\"]([^'\"]+)['\"]""")
_NAME_RE = re.compile(r"""_name\s*=\s*['\"]([^'\"]+)['\"]""")
_DEPENDS_RE = re.compile(r"""@api\.depends\(([^)]*)\)""", re.S)
_DEPENDS_FIELD_RE = re.compile(r"""['\"]([a-zA-Z_][\w.]*)['\"]""")
_XPATH_FIELD_RE = re.compile(r"""field\[@name=['\"]([^'\"]+)['\"]\]""")
_RELATED_RE = re.compile(
    r"""related\s*=\s*['\"]([a-zA-Z_][\w.]*)['\"]"""
)


def option_a_host_models(draft: dict[str, Any] | None, prompt: str = "") -> list[str]:
    """Host models the custom-code slice should cover."""
    names: list[str] = []
    if isinstance(draft, dict):
        for row in draft.get("models") or []:
            if not isinstance(row, dict):
                continue
            mid = str(row.get("model") or "").strip()
            if mid:
                names.append(mid)
        for block in draft.get("custom_code_blocks") or []:
            if not isinstance(block, dict):
                continue
            content = str(block.get("content") or "")
            names.extend(_INHERIT_RE.findall(content))
    try:
        from app.ai_grain import preferred_inherit_host

        preferred = preferred_inherit_host(prompt or "")
        if preferred:
            names.append(preferred)
    except Exception:  # noqa: BLE001
        pass
    out: list[str] = []
    seen: set[str] = set()
    for name in names:
        if not name or name in seen or name.startswith("x_"):
            continue
        seen.add(name)
        out.append(name)
    return out


def resolve_option_a_schema_packet(draft: dict[str, Any] | None) -> SchemaPacket | None:
    """Packet stamped on the draft, else the request-scoped current packet."""
    if isinstance(draft, dict):
        raw = draft.get("_schema_packet")
        if isinstance(raw, SchemaPacket):
            return raw
    try:
        from app.ai_conversation.intent_llm import current_schema_packet

        return current_schema_packet()
    except Exception:  # noqa: BLE001
        return None


def ensure_option_a_schema_packet(
    draft: dict[str, Any],
    *,
    prompt: str = "",
    client: Any | None = None,
    odoo_major: int = 19,
    schema_client: Any | None = None,
    schema_graph: Any | None = None,
    connection: Any | None = None,
) -> SchemaPacket | None:
    """Stamp ``draft['_schema_packet']`` when a live/fixture slice is available.

    Inputs: draft, optional connection/client/graph. No connection and no
    injected packet → None (existing no-connection authoring stays unchanged).
    Side effects: may set ``draft['_schema_packet']``. Does not call a model.
    """
    existing = resolve_option_a_schema_packet(draft)
    if existing is not None:
        draft["_schema_packet"] = existing
        return existing

    hosts = option_a_host_models(draft, prompt)
    if not hosts and schema_client is None and client is None and connection is None:
        return None

    conn = connection
    if conn is None and (client is not None or schema_client is not None):
        conn = SimpleNamespace(
            id="option-a",
            server_version=f"{int(odoo_major)}.0",
            odoo_major=int(odoo_major),
            client=client,
        )
    if conn is None:
        return None

    try:
        packet = build_schema_packet(
            conn,
            models=hosts or ["sale.order"],
            draft=draft,
            schema_client=schema_client,
            schema_graph=schema_graph,
        )
    except Exception:  # noqa: BLE001
        return None
    draft["_schema_packet"] = packet
    return packet


def user_prompt_with_schema_packet(
    user_message: str,
    draft: dict[str, Any] | None,
) -> str:
    """Prepend the live host slice when a packet is on the draft / context."""
    schema_packet = resolve_option_a_schema_packet(draft)
    return prepend_schema_packet(user_message, schema_packet)


def _arch_field_names(packet: SchemaPacket, model: str) -> set[str]:
    row = packet.models.get(model)
    if row is None:
        return set()
    names: set[str] = set()
    for order in row.views.values():
        names.update(order)
    return names


def _model_field_names(packet: SchemaPacket, model: str) -> set[str]:
    row = packet.models.get(model)
    if row is None:
        return set()
    return set(row.fields)


def _py_xml_blocks(draft: dict[str, Any]) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    py: list[tuple[str, str]] = []
    xml: list[tuple[str, str]] = []
    for block in draft.get("custom_code_blocks") or []:
        if not isinstance(block, dict):
            continue
        path = str(block.get("source_file") or block.get("path") or "block")
        content = str(block.get("content") or "")
        kind = str(block.get("kind") or "")
        if path.endswith(".py") or kind == "python":
            py.append((path, content))
        elif path.endswith(".xml") or kind in {"xml", "qweb"}:
            xml.append((path, content))
    return py, xml


def _primary_host(draft: dict[str, Any], inherits: set[str]) -> str | None:
    for row in draft.get("models") or []:
        if not isinstance(row, dict):
            continue
        mid = str(row.get("model") or "").strip()
        if mid and not mid.startswith("x_"):
            return mid
    for mid in sorted(inherits):
        if not mid.startswith("x_"):
            return mid
    return None


def packet_ground_findings(
    draft: dict[str, Any],
    *,
    packet: SchemaPacket | None = None,
) -> list[dict[str, str]]:
    """Refuse authored names the live packet does not contain.

    Checks ``_inherit`` / ``_name`` hosts, ``self.env['…']`` models, field
    names referenced on known hosts, and view xpath targets against the
    packet's combined_arch field order. ``packet is None`` → no findings
    (no-connection authoring stays unchanged). New ``x_*`` models/fields the
    module defines are allowed.
    """
    schema_packet = packet if packet is not None else resolve_option_a_schema_packet(draft)
    if schema_packet is None:
        return []

    findings: list[dict[str, str]] = []
    defined = collect_draft_python_fields(draft)
    py_blocks, xml_blocks = _py_xml_blocks(draft)

    inherits: set[str] = set()
    new_models: set[str] = set()
    for path, content in py_blocks:
        for mid in _INHERIT_RE.findall(content):
            inherits.add(mid)
            if mid.startswith("x_"):
                new_models.add(mid)
            elif mid not in schema_packet.models:
                findings.append(
                    {
                        "code": "packet_host_missing",
                        "message": (
                            f"Host model '{mid}' is not in the live schema packet "
                            f"— refuse naming a missing host before zip/sandbox."
                        ),
                        "file": path,
                    }
                )
        for mid in _NAME_RE.findall(content):
            if mid.startswith("x_"):
                new_models.add(mid)
                continue
            if mid not in schema_packet.models and mid not in inherits:
                findings.append(
                    {
                        "code": "packet_host_missing",
                        "message": (
                            f"Model '{mid}' (_name) is not in the live schema packet "
                            f"— refuse naming a missing model before zip/sandbox."
                        ),
                        "file": path,
                    }
                )
        for mid in _ENV_MODEL_RE.findall(content):
            if mid.startswith("x_") or mid in new_models:
                continue
            if mid not in schema_packet.models:
                findings.append(
                    {
                        "code": "packet_env_model_missing",
                        "message": (
                            f"self.env['{mid}'] names a model missing from the live "
                            f"schema packet — refused before zip/sandbox."
                        ),
                        "file": path,
                    }
                )

    host = _primary_host(draft, inherits)
    known_hosts = {
        mid
        for mid in set(inherits) | set(schema_packet.models) | ({host} if host else set())
        if mid and mid in schema_packet.models
    }

    for path, content in py_blocks:
        for dep_blob in _DEPENDS_RE.findall(content):
            for raw in _DEPENDS_FIELD_RE.findall(dep_blob):
                root = raw.split(".", 1)[0]
                if not root or root.startswith("x_"):
                    continue
                # Attribute path on a related model — only check the root on the host.
                if host and host in known_hosts:
                    allowed = _model_field_names(schema_packet, host) | defined.get(host, set())
                    if root not in allowed:
                        findings.append(
                            {
                                "code": "packet_field_missing",
                                "message": (
                                    f"Field '{root}' is missing on host '{host}' in the "
                                    f"live schema packet — refused before zip/sandbox."
                                ),
                                "file": path,
                            }
                        )
        for related in _RELATED_RE.findall(content):
            root = related.split(".", 1)[0]
            if not root or root.startswith("x_") or not host or host not in known_hosts:
                continue
            allowed = _model_field_names(schema_packet, host) | defined.get(host, set())
            if root not in allowed:
                findings.append(
                    {
                        "code": "packet_field_missing",
                        "message": (
                            f"Field '{root}' is missing on host '{host}' in the "
                            f"live schema packet — refused before zip/sandbox."
                        ),
                        "file": path,
                    }
                )

    for path, content in xml_blocks:
        view_host = host
        # Prefer model declared on the view record when present.
        model_m = re.search(
            r"""<field\s+name=["']model["']\s*>([^<]+)</field>""",
            content,
            flags=re.I,
        )
        if model_m:
            view_host = model_m.group(1).strip() or view_host
        if not view_host or view_host not in schema_packet.models:
            # Still check xpath targets against any known host arch when possible.
            if known_hosts:
                view_host = sorted(known_hosts)[0]
            else:
                continue
        arch_names = _arch_field_names(schema_packet, view_host)
        local_defined = defined.get(view_host, set())
        for target in _XPATH_FIELD_RE.findall(content):
            if target.startswith("x_") or target in local_defined:
                continue
            if target not in arch_names:
                findings.append(
                    {
                        "code": "packet_xpath_missing",
                        "message": (
                            f"xpath target '{target}' is missing from host "
                            f"'{view_host}' combined_arch — refused before zip/sandbox."
                        ),
                        "file": path,
                    }
                )

    # De-dupe by code+message+file while preserving order.
    seen: set[tuple[str, str, str]] = set()
    unique: list[dict[str, str]] = []
    for row in findings:
        key = (row.get("code", ""), row.get("message", ""), row.get("file", ""))
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


__all__ = [
    "ensure_option_a_schema_packet",
    "option_a_host_models",
    "packet_ground_findings",
    "resolve_option_a_schema_packet",
    "user_prompt_with_schema_packet",
]
