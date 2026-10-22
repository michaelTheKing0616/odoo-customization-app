"""GND-EXPERT: Expert answers field facts from the live schema packet (no invent)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

from app.expert.grounding import extract_model_field_refs
from app.live_schema_context import (
    ConnectionRequiredError,
    SchemaPacket,
    build_schema_packet,
    field_in_packet,
    model_in_packet,
    render_schema_packet,
    resolve_form_anchor,
)
from app.ai_schema_client import FakeSchemaClient, LiveSchemaClient, SchemaClient

_PACKET_CITATION_BREADCRUMB = "LIVE SCHEMA PACKET"

_FIELD_ON_INSTANCE_RE = re.compile(
    r"(?i)\b("
    r"on this (instance|connection|database)|"
    r"this instance|"
    r"what type is|"
    r"what field|"
    r"which field|"
    r"does .+ have|"
    r"is there a field|"
    r"where is .+ on|"
    r"on quotations?|"
    r"on sales orders?|"
    r"on invoices?"
    r")\b"
)
_X_FIELD_RE = re.compile(r"\b(x_[a-z][a-z0-9_]*)\b", re.I)


@dataclass(frozen=True, slots=True)
class ExpertSchemaState:
    """Fixture or live packet plus how many read passes built it."""

    packet: SchemaPacket
    read_passes: int


def schema_packet_citation(packet: SchemaPacket) -> Any:
    from app.expert.ask import ExpertCitation

    version = packet.server_version or "?"
    return ExpertCitation(
        source="live_schema",
        version=version,
        breadcrumb=_PACKET_CITATION_BREADCRUMB,
        chunk_id="schema-packet",
        source_index=1,
    )


def looks_like_instance_field_question(question: str) -> bool:
    text = (question or "").strip()
    if not text:
        return False
    if extract_model_field_refs(text):
        return True
    if _X_FIELD_RE.search(text):
        return True
    return bool(_FIELD_ON_INSTANCE_RE.search(text))


def _models_for_expert_packet(
    question: str,
    *,
    ui_context: dict[str, Any] | None,
    available: Sequence[str] | None,
) -> list[str]:
    names: list[str] = []
    if ui_context:
        model = str(ui_context.get("model") or "").strip()
        if model:
            names.append(model)
    try:
        from app.ai_grain import HOST_ALIASES, preferred_inherit_host

        preferred = preferred_inherit_host(question)
        if preferred:
            names.append(preferred)
        low = (question or "").lower()
        for phrase, model in sorted(HOST_ALIASES.items(), key=lambda kv: -len(kv[0])):
            if phrase in low:
                names.append(model)
    except Exception:  # noqa: BLE001
        pass
    for model, _fld in extract_model_field_refs(question):
        names.append(model)
    avail = {str(m).strip() for m in (available or []) if str(m).strip()}
    out: list[str] = []
    seen: set[str] = set()
    for name in names:
        if not name or name in seen:
            continue
        if avail and name not in avail:
            continue
        seen.add(name)
        out.append(name)
    return out[:8]


def _iter_client_models(client: SchemaClient) -> list[str]:
    if isinstance(client, FakeSchemaClient):
        return sorted(set(client.models) | set(client.fields.keys()))
    models_attr = getattr(client, "models", None)
    if isinstance(models_attr, set):
        return sorted(models_attr)
    return []


def _field_tokens(question: str) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for _model, fld in extract_model_field_refs(question):
        if fld and fld.lower() not in seen:
            seen.add(fld.lower())
            tokens.append(fld)
    for match in _X_FIELD_RE.finditer(question):
        name = match.group(1)
        if name.lower() not in seen:
            seen.add(name.lower())
            tokens.append(name)
    return tokens


def _models_from_field_search(client: SchemaClient, question: str) -> list[str]:
    """Second read: find models whose fields match the user's words."""
    tokens = _field_tokens(question)
    hits: list[str] = []
    seen: set[str] = set()
    for model in _iter_client_models(client):
        fields = client.fields_get(model) or {}
        for token in tokens:
            if token in fields and model not in seen:
                seen.add(model)
                hits.append(model)
                break
        else:
            low_q = question.lower()
            for fname in fields:
                if fname.replace("_", " ") in low_q or fname in low_q:
                    if model not in seen:
                        seen.add(model)
                        hits.append(model)
                    break
    return hits


def _resolve_schema_client(
    connection: Any,
    client: Any | None,
    *,
    schema_client: SchemaClient | None,
) -> SchemaClient | None:
    if schema_client is not None:
        return schema_client
    if client is None:
        return None
    if isinstance(client, (FakeSchemaClient, LiveSchemaClient)):
        return client
    try:
        return LiveSchemaClient(client)
    except Exception:  # noqa: BLE001
        return None


def _available_models(schema_client: SchemaClient | None, client: Any | None) -> list[str]:
    if schema_client is not None:
        return _iter_client_models(schema_client)
    if client is not None and hasattr(client, "list_models"):
        try:
            return [
                str(getattr(row, "model", "") or row.get("model", ""))
                for row in (client.list_models(custom_only=False, limit=400) or [])
                if getattr(row, "model", None) or (isinstance(row, dict) and row.get("model"))
            ]
        except Exception:  # noqa: BLE001
            return []
    return []


def resolve_expert_schema_packet(
    connection: Any,
    *,
    question: str,
    ui_context: dict[str, Any] | None = None,
    client: Any | None = None,
    schema_client: SchemaClient | None = None,
    schema_graph: Any | None = None,
    draft: dict[str, Any] | None = None,
) -> ExpertSchemaState | None:
    """Build the expert slice; widen with a second read when a field is missing."""
    if connection is None:
        return None
    resolved = _resolve_schema_client(connection, client, schema_client=schema_client)
    if resolved is None:
        return None
    available = _available_models(resolved, client)
    models = _models_for_expert_packet(question, ui_context=ui_context, available=available)
    if not models and available:
        models = list(available)[:4]
    try:
        packet = build_schema_packet(
            connection,
            models=models,
            draft=draft,
            schema_client=resolved,
            schema_graph=schema_graph,
        )
    except ConnectionRequiredError:
        return None
    except Exception:  # noqa: BLE001
        return None

    read_passes = 1
    if looks_like_instance_field_question(question) and not _question_fields_satisfied(
        question, packet
    ):
        widen = _models_from_field_search(resolved, question)
        alias_models = _models_for_expert_packet(
            question, ui_context=ui_context, available=available
        )
        merged: list[str] = []
        seen_m: set[str] = set()
        for name in list(packet.models.keys()) + widen + alias_models:
            if name and name not in seen_m:
                seen_m.add(name)
                merged.append(name)
        if not merged and available:
            merged = list(available)[:12]
        read_passes = 2
        try:
            packet = build_schema_packet(
                connection,
                models=merged[:12],
                draft=draft,
                schema_client=resolved,
                schema_graph=schema_graph,
            )
        except Exception:  # noqa: BLE001
            pass

    return ExpertSchemaState(packet=packet, read_passes=read_passes)


def _question_fields_satisfied(question: str, packet: SchemaPacket) -> bool:
    tokens = _field_tokens(question)
    if not tokens:
        return True
    for token in tokens:
        if field_in_packet(packet, token):
            return True
    for model, fld in extract_model_field_refs(question):
        if fld and field_in_packet(packet, fld, model=model):
            return True
    return not tokens


def _target_model_and_field(question: str, packet: SchemaPacket) -> tuple[str | None, str | None]:
    refs = extract_model_field_refs(question)
    for model, fld in refs:
        if fld:
            return model, fld
    tokens = _field_tokens(question)
    field = tokens[0] if tokens else None
    model: str | None = None
    if refs:
        model = refs[0][0]
    if not model and packet.models:
        try:
            from app.ai_grain import preferred_inherit_host

            model = preferred_inherit_host(question)
        except Exception:  # noqa: BLE001
            model = None
    if not model and len(packet.models) == 1:
        model = next(iter(packet.models))
    return model, field


def _stock_place_to_add(packet: SchemaPacket, model: str | None) -> bool:
    if model and model_in_packet(packet, model):
        return True
    if model:
        try:
            from app.ai_grain import module_for_model

            mod = module_for_model(model)
        except Exception:  # noqa: BLE001
            mod = None
        if mod and packet.modules:
            return any(row.get("name") == mod and row.get("state") == "installed" for row in packet.modules)
    return False


def try_schema_packet_field_answer(
    question: str,
    state: ExpertSchemaState,
) -> Any | None:
    """Deterministic field lookup from the packet — no LLM."""
    from app.expert.ask import ExpertAskResult

    if not looks_like_instance_field_question(question):
        return None
    packet = state.packet
    model, field = _target_model_and_field(question, packet)
    if not field:
        anchor = resolve_form_anchor(packet, question, model=model)
        if anchor and model and model in packet.models:
            row = packet.models[model]
            meta = row.fields.get(anchor)
            rel = f", relation `{meta.relation}`" if meta and meta.relation else ""
            answer = (
                f"On this connection, **`{anchor}`** on **`{model}`** is in the live form order "
                f"(type `{meta.type}`{rel}). [{_PACKET_CITATION_BREADCRUMB}]"
            )
            return ExpertAskResult(
                answer_markdown=answer,
                citations=[schema_packet_citation(packet)],
                grounded=True,
                declined=False,
                caution_flags=[f"schema_packet_reads:{state.read_passes}"],
                retrieval_version=packet.server_version or None,
            )
        return None

    if field_in_packet(packet, field, model=model):
        host = model
        if not host:
            for name, row in packet.models.items():
                if field in row.fields:
                    host = name
                    break
        if not host:
            return None
        meta = packet.models[host].fields[field]
        rel = f", relates to **`{meta.relation}`**" if meta.relation else ""
        form_order = packet.models[host].views.get("form") or ()
        placement = ""
        if field in form_order:
            placement = f" Form order shows it after `{form_order[max(form_order.index(field) - 1, 0)]}`."
        answer = (
            f"**`{field}`** on **`{host}`** is in the live schema packet: type **`{meta.type}`**"
            f"{rel}.{placement} [{_PACKET_CITATION_BREADCRUMB}]"
        )
        return ExpertAskResult(
            answer_markdown=answer,
            citations=[schema_packet_citation(packet)],
            grounded=True,
            declined=False,
            caution_flags=[f"schema_packet_reads:{state.read_passes}"],
            retrieval_version=packet.server_version or None,
        )

    if state.read_passes < 2:
        return None

    if _stock_place_to_add(packet, model):
        host = model or "the existing form"
        answer = (
            f"**`{field}`** is not on **`{host}`** in the live schema packet from this connection. "
            f"The model is present, so you can add a custom field via **Designer → Models & Fields** "
            f"or an inherit in App Studio — I only report fields the packet contains. "
            f"[{_PACKET_CITATION_BREADCRUMB}]"
        )
        return ExpertAskResult(
            answer_markdown=answer,
            citations=[schema_packet_citation(packet)],
            grounded=True,
            declined=False,
            caution_flags=[
                f"schema_packet_reads:{state.read_passes}",
                "schema_field_absent",
            ],
            retrieval_version=packet.server_version or None,
        )

    caution_flags = [f"schema_packet_reads:{state.read_passes}", "schema_field_absent"]
    install_hint = _stock_app_install_hint(question, packet, model)
    if install_hint:
        caution_flags.append(f"stock_app_install:{install_hint[0]}")
        tail = install_hint[1]
    else:
        tail = (
            "There is no stock model in the packet to attach it to without installing another app first."
        )
    answer = (
        f"I cannot find **`{field}`** on this connection after reading the live schema slice twice "
        f"(including a search from your wording). {tail} [{_PACKET_CITATION_BREADCRUMB}]"
    )
    return ExpertAskResult(
        answer_markdown=answer,
        citations=[schema_packet_citation(packet)],
        grounded=True,
        declined=True,
        caution_flags=caution_flags,
        retrieval_version=packet.server_version or None,
    )


def _stock_app_install_hint(
    question: str,
    packet: SchemaPacket,
    model: str | None,
) -> tuple[str, str] | None:
    """Same stock-app map and copy as the App Studio install confirm (GND-MOD)."""
    from app.stock_app_install import InstallFacts, match_stock_app, proposal_for

    match = match_stock_app(question, host_model=model if model and model not in packet.models else None)
    if match is None or match.model in packet.models:
        return None
    state = next(
        (str(row.get("state") or "") for row in packet.modules if row.get("name") == match.app.module),
        "uninstalled" if match.app.is_community else None,
    )
    proposal = proposal_for(match, InstallFacts(model_present=False, module_state=state))
    if proposal is None:
        return None
    if proposal.installable:
        return proposal.module, (
            f"{proposal.reason} App Studio can install {proposal.app_label} after you confirm, "
            "then continue the same request."
        )
    return proposal.module, proposal.reason


def expert_schema_grounding_block(state: ExpertSchemaState | None) -> str:
    if state is None:
        return ""
    block = render_schema_packet(state.packet)
    if not block:
        return ""
    return (
        f"{block}\n\n"
        "EXPERT SCHEMA RULE: Name only models and fields that appear in LIVE SCHEMA PACKET above. "
        "SOURCE EXCERPTS cannot introduce field names absent from the packet."
    )


__all__ = [
    "ExpertSchemaState",
    "expert_schema_grounding_block",
    "looks_like_instance_field_question",
    "resolve_expert_schema_packet",
    "schema_packet_citation",
    "try_schema_packet_field_answer",
]
