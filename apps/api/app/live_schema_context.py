"""Live schema packet for later LLM surfaces that name Odoo structure.

Built from the request connection via ``ai_schema_client`` and
``odoo_client.schema_graph.SchemaGraph``. No second schema client. No L4.
No audit sink. Does not call a model.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Iterable, Mapping, Sequence
from xml.etree import ElementTree

from odoo_client.compat.read_group import aggregate_rpc_method
from odoo_client.compat.version_table import UnknownVersionFact, difference
from odoo_client.read_plane import ReadPlane
from odoo_client.schema_graph import SchemaGraph

from app.ai_schema_client import (
    SCHEMA_CATALOG_TTL_S,
    DenySchemaClient,
    SchemaClient,
    schema_client_for_draft,
)

VIEW_TYPES: tuple[str, ...] = ("form", "list", "search")

# Method names whose presence is decided by the version table for the major.
_VERSION_TABLE_METHODS: dict[str, str] = {
    "read_group": "read_group",
    "formatted_read_group": "read_group",
}

_PACKET_PROMPT_HEADER = (
    "LIVE SCHEMA PACKET (connected instance — do not invent a model, field, "
    "method, or view anchor outside this slice)"
)
_ANCHOR_ALIASES: dict[str, tuple[str, ...]] = {
    "customer": ("partner_id", "partner_invoice_id"),
    "customers": ("partner_id",),
    "client": ("partner_id",),
    "partner": ("partner_id",),
    "vendor": ("partner_id",),
    "supplier": ("partner_id",),
}
_TECH_NAME_RE = re.compile(r"\b(?:x_[a-z0-9_]+|[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+)\b")
_SNAKE_NAME_RE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")


class ConnectionRequiredError(ValueError):
    """Raised when a packet is requested with no connection."""


@dataclass(frozen=True, slots=True)
class PacketField:
    """One field the live (or fixture) schema client admitted.

    Inputs: ``fields_get`` meta. Side effects: none.
    """

    name: str
    type: str
    relation: str | None
    required: bool
    readonly: bool
    store: bool | None
    groups: str


@dataclass(frozen=True, slots=True)
class PacketModel:
    """One in-scope model: fields, view order, and methods that exist here.

    Inputs: schema-client field map plus SchemaGraph arches. Side effects: none.
    """

    name: str
    fields: dict[str, PacketField]
    views: dict[str, tuple[str, ...]]
    methods: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SchemaPacket:
    """Slice later generation reads. Empty when the catalog is stale.

    Inputs: connection version, installed modules, and per-model slices.
    Side effects: none. Contains no credentials.
    """

    server_version: str
    major: int | None
    modules: tuple[dict[str, str], ...]
    models: dict[str, PacketModel]

    def is_empty(self) -> bool:
        return not self.models and not self.modules

    def as_dict(self) -> dict[str, Any]:
        return {
            "server_version": self.server_version,
            "major": self.major,
            "modules": [dict(row) for row in self.modules],
            "models": {
                name: {
                    "name": model.name,
                    "fields": {
                        field_name: {
                            "name": field.name,
                            "type": field.type,
                            "relation": field.relation,
                            "required": field.required,
                            "readonly": field.readonly,
                            "store": field.store,
                            "groups": field.groups,
                        }
                        for field_name, field in model.fields.items()
                    },
                    "views": {view: list(order) for view, order in model.views.items()},
                    "methods": list(model.methods),
                }
                for name, model in self.models.items()
            },
        }


def empty_schema_packet(
    *,
    server_version: str = "",
    major: int | None = None,
) -> SchemaPacket:
    """Return a packet with no models, modules, or methods.

    Inputs: optional version labels from the connection (not from a catalog).
    Output: empty ``SchemaPacket``. Side effects: none.
    """

    return SchemaPacket(
        server_version=server_version,
        major=major,
        modules=(),
        models={},
    )


def build_schema_packet(
    connection: Any | None,
    *,
    models: Sequence[str],
    draft: Mapping[str, Any] | None = None,
    schema_client: SchemaClient | None = None,
    schema_graph: SchemaGraph | None = None,
    now: float | None = None,
    ttl_s: float = SCHEMA_CATALOG_TTL_S,
) -> SchemaPacket:
    """Build the live schema packet for ``models`` on ``connection``.

    Inputs: a connection (required), the model names in scope, and optional
    draft catalog / injected ``SchemaClient`` / ``SchemaGraph``. Tests pass a
    fixture client and graph. Production passes the request connection.
    Output: a ``SchemaPacket``. A stale catalog (past TTL) yields an empty
    packet, not catalog fields. Side effects: read-only SchemaGraph calls
    when a graph or RPC transport is present. Does not call a language model.
    """

    if not _has_connection(connection):
        raise ConnectionRequiredError("schema packet requires a connection")

    draft_map = dict(draft) if isinstance(draft, Mapping) else None
    server_version = _connection_server_version(connection)
    major = _connection_major(connection)

    if _catalog_is_stale(draft_map, now=now, ttl_s=ttl_s):
        return empty_schema_packet(server_version=server_version, major=major)

    client = _resolve_schema_client(
        connection,
        draft=draft_map,
        schema_client=schema_client,
        now=now,
        ttl_s=ttl_s,
    )
    if isinstance(client, DenySchemaClient):
        return empty_schema_packet(server_version=server_version, major=major)

    graph = _resolve_schema_graph(connection, schema_graph)
    packet_models: dict[str, PacketModel] = {}
    for model_name in models:
        name = str(model_name or "").strip()
        if not name or not client.model_exists(name):
            continue
        packet_models[name] = _packet_model(client, graph, name, major)

    return SchemaPacket(
        server_version=server_version,
        major=major,
        modules=_connection_modules(connection, draft_map),
        models=packet_models,
    )


def bind_schema_rpc(connection: Any, client: Any | None = None) -> Any:
    """Attach a read RPC client to ``connection`` the way Draft Studio does.

    Inputs: the request connection and an optional already-open client.
    Output: the same connection, or a namespace with ``client`` set.
    Side effects: none. Does not open a second schema client.
    """

    if connection is None or client is None:
        return connection
    return SimpleNamespace(
        id=_connection_attr(connection, "id"),
        server_version=_connection_server_version(connection),
        odoo_major=_connection_major(connection),
        installed_modules=_connection_attr(connection, "installed_modules"),
        client=client,
    )


def models_for_studio_packet(
    prompt: str,
    *,
    host: str | None = None,
    available: list[str] | None = None,
) -> list[str]:
    """Slice models the words point at. Does not ask the user for xmlids."""

    names: list[str] = []
    if host:
        names.append(str(host).strip())
    try:
        from app.ai_grain import HOST_ALIASES, preferred_inherit_host

        preferred = preferred_inherit_host(prompt)
        if preferred:
            names.append(preferred)
        low = (prompt or "").lower()
        for phrase, model in sorted(HOST_ALIASES.items(), key=lambda kv: -len(kv[0])):
            if phrase in low:
                names.append(model)
    except Exception:  # noqa: BLE001
        pass
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
    if out:
        return out
    if avail:
        try:
            from app.ai_grain import HOST_LABELS

            return [m for m in avail if m in HOST_LABELS][:8]
        except Exception:  # noqa: BLE001
            return list(avail)[:8]
    return names[:8]


def studio_schema_packet(
    connection: Any,
    *,
    prompt: str,
    host: str | None = None,
    available: list[str] | None = None,
    draft: dict[str, Any] | None = None,
    schema_client: SchemaClient | None = None,
    schema_graph: SchemaGraph | None = None,
) -> SchemaPacket | None:
    """Build the generate-path packet. No connection → None (out of scope).

    Same helper Draft Studio uses. Callers that already have a live RPC
    client should pass ``bind_schema_rpc(connection, client)``.
    """

    if connection is None:
        return None
    models = models_for_studio_packet(prompt, host=host, available=available)
    try:
        return build_schema_packet(
            connection,
            models=models,
            draft=draft,
            schema_client=schema_client,
            schema_graph=schema_graph,
        )
    except ConnectionRequiredError:
        return None
    except Exception:  # noqa: BLE001
        return None


def _has_connection(connection: Any) -> bool:
    if connection is None or connection is False:
        return False
    if isinstance(connection, str) and not connection.strip():
        return False
    return True


def _connection_attr(connection: Any, *names: str) -> Any:
    for name in names:
        if isinstance(connection, Mapping) and name in connection:
            value = connection[name]
            if value is not None:
                return value
        if not isinstance(connection, Mapping) and hasattr(connection, name):
            value = getattr(connection, name)
            if value is not None:
                return value
    return None


def _connection_server_version(connection: Any) -> str:
    value = _connection_attr(connection, "server_version", "version")
    return str(value) if value else ""


def _connection_major(connection: Any) -> int | None:
    major = _connection_attr(connection, "odoo_major", "major")
    if isinstance(major, int):
        return major
    if isinstance(major, str) and major.isdigit():
        return int(major)
    version = _connection_server_version(connection)
    if not version:
        return None
    try:
        from odoo_client.compat import parse_major

        return parse_major(version)
    except Exception:  # noqa: BLE001
        return None


def _normalize_module(row: Any) -> dict[str, str] | None:
    if isinstance(row, str):
        name = row.strip()
        return {"name": name, "state": "installed"} if name else None
    if not isinstance(row, Mapping):
        return None
    name = str(row.get("name") or "").strip()
    if not name:
        return None
    state = str(row.get("state") or "installed").strip() or "installed"
    return {"name": name, "state": state}


def _connection_modules(
    connection: Any,
    draft: Mapping[str, Any] | None,
) -> tuple[dict[str, str], ...]:
    raw = _connection_attr(connection, "installed_modules")
    if raw is None and isinstance(draft, Mapping):
        cat = draft.get("_connection_catalog")
        if isinstance(cat, Mapping):
            raw = cat.get("installed_modules")
    if not isinstance(raw, Iterable) or isinstance(raw, (str, bytes)):
        return ()
    modules: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in raw:
        item = _normalize_module(row)
        if item is None or item["name"] in seen:
            continue
        seen.add(item["name"])
        modules.append(item)
    return tuple(modules)


def _catalog_is_stale(
    draft: Mapping[str, Any] | None,
    *,
    now: float | None,
    ttl_s: float,
) -> bool:
    if not isinstance(draft, Mapping):
        return False
    cat = draft.get("_connection_catalog")
    if not isinstance(cat, Mapping):
        return False
    loaded = cat.get("loaded_at")
    try:
        loaded_at = float(loaded) if loaded is not None else None
    except (TypeError, ValueError):
        loaded_at = None
    if loaded_at is None:
        return True
    clock = time.time() if now is None else now
    return (clock - loaded_at) > ttl_s


def _rpc_from(connection: Any) -> Any | None:
    return _connection_attr(connection, "client", "rpc", "odoo")


def _resolve_schema_client(
    connection: Any,
    *,
    draft: dict[str, Any] | None,
    schema_client: SchemaClient | None,
    now: float | None,
    ttl_s: float,
) -> SchemaClient:
    if schema_client is not None:
        return schema_client
    return schema_client_for_draft(draft, _rpc_from(connection), now=now, ttl_s=ttl_s)


def _resolve_schema_graph(
    connection: Any,
    schema_graph: SchemaGraph | None,
) -> SchemaGraph | None:
    if schema_graph is not None:
        return schema_graph
    rpc = _rpc_from(connection)
    if rpc is None:
        return None
    if callable(rpc) and not hasattr(rpc, "execute_kw"):
        return SchemaGraph(ReadPlane(rpc))

    def transport(model: str, method: str, args: list[Any], kwargs: dict[str, Any]) -> Any:
        return rpc.execute_kw(model, method, args, kwargs)

    return SchemaGraph(ReadPlane(transport))


def _packet_field(name: str, meta: Mapping[str, Any]) -> PacketField:
    relation = meta.get("relation")
    store = meta.get("store")
    return PacketField(
        name=name,
        type=str(meta.get("type") or meta.get("ttype") or ""),
        relation=str(relation) if relation else None,
        required=bool(meta.get("required")),
        readonly=bool(meta.get("readonly")),
        store=bool(store) if store is not None else None,
        groups=str(meta.get("groups") or ""),
    )


def _field_names_in_arch(arch: str) -> list[str]:
    # PDF-05 / shared: refuse to parse arches that declare XXE payloads.
    from app.qweb_unsafe_gate import arch_has_xxe

    if arch_has_xxe(arch):
        return []
    try:
        root = ElementTree.fromstring(arch)
    except ElementTree.ParseError:
        return []
    names: list[str] = []
    seen: set[str] = set()
    for element in root.iter("field"):
        name = str(element.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def _view_field_order(
    graph: SchemaGraph | None,
    model: str,
    view_type: str,
    known_fields: set[str],
) -> tuple[str, ...]:
    if graph is None:
        return ()
    try:
        arch = graph.combined_arch(model, view_type)
    except Exception:  # noqa: BLE001
        return ()
    return tuple(name for name in _field_names_in_arch(arch) if name in known_fields)


def _version_table_allows_method(method: str, major: int | None) -> bool:
    area = _VERSION_TABLE_METHODS.get(method)
    if area is None:
        return True
    if major is None:
        return False
    try:
        fact = difference(area, major)
    except UnknownVersionFact:
        return False
    text = fact.strip().lower()
    if text == "removed" or text.startswith("absent"):
        return False
    if area == "read_group":
        try:
            return method == aggregate_rpc_method(major)
        except ValueError:
            return False
    return True


def _client_methods(client: SchemaClient, model: str) -> tuple[str, ...]:
    listed = getattr(client, "methods", None)
    if not isinstance(listed, Mapping):
        return ()
    raw = listed.get(model) or ()
    names: list[str] = []
    for item in raw:
        name = str(item or "").strip()
        if name and name not in names:
            names.append(name)
    return tuple(names)


def _packet_methods(client: SchemaClient, model: str, major: int | None) -> tuple[str, ...]:
    admitted: list[str] = []
    for method in _client_methods(client, model):
        if not client.method_exists(model, method):
            continue
        if not _version_table_allows_method(method, major):
            continue
        admitted.append(method)
    return tuple(admitted)


def _packet_model(
    client: SchemaClient,
    graph: SchemaGraph | None,
    model: str,
    major: int | None,
) -> PacketModel:
    raw_fields = client.fields_get(model) or {}
    fields = {
        name: _packet_field(name, meta)
        for name, meta in raw_fields.items()
        if isinstance(name, str) and name and isinstance(meta, Mapping)
    }
    known = set(fields)
    views = {
        view_type: _view_field_order(graph, model, view_type, known) for view_type in VIEW_TYPES
    }
    return PacketModel(
        name=model,
        fields=fields,
        views=views,
        methods=_packet_methods(client, model, major),
    )


def render_schema_packet(packet: SchemaPacket | None) -> str:
    """Render the slice the model must see before it answers.

    Inputs: a ``SchemaPacket`` (possibly empty). Output: operator-facing
    text with models, fields, and form/list/search order. Side effects: none.
    """

    if packet is None:
        return ""
    lines = [
        _PACKET_PROMPT_HEADER,
        f"server_version={packet.server_version} major={packet.major}",
    ]
    if packet.is_empty():
        lines.append("slice: empty — do not invent models or fields")
        return "\n".join(lines)
    if packet.modules:
        mods = ", ".join(f"{row['name']}:{row['state']}" for row in packet.modules)
        lines.append(f"modules: {mods}")
    for name, model in packet.models.items():
        lines.append(f"MODEL {name}")
        for field_name, field in model.fields.items():
            rel = f" relation={field.relation}" if field.relation else ""
            lines.append(f"  field {field_name} type={field.type}{rel}")
        for view_type, order in model.views.items():
            if order:
                lines.append(f"  {view_type} order: {', '.join(order)}")
        if model.methods:
            lines.append(f"  methods: {', '.join(model.methods)}")
    return "\n".join(lines)


def prepend_schema_packet(user_message: str, packet: SchemaPacket | None) -> str:
    """Prepend the live slice to the LLM user message.

    Inputs: the operator-facing user message and an optional packet.
    Output: ``packet + message`` when a packet is supplied; otherwise the
    original message. No connection → caller passes ``None`` (out of scope).
    Side effects: none.
    """

    if packet is None:
        return user_message
    block = render_schema_packet(packet)
    if not block:
        return user_message
    return f"{block}\n\n{user_message}"


def model_in_packet(packet: SchemaPacket | None, model: str | None) -> bool:
    """True when ``model`` is in the live slice.

    Inputs: packet and a technical model name. Empty packet admits nothing.
    ``packet is None`` (no connection) is out of scope and returns True so
    existing no-connection paths stay unchanged. Side effects: none.
    """

    name = str(model or "").strip()
    if not name:
        return False
    if packet is None:
        return True
    return name in packet.models


def field_in_packet(
    packet: SchemaPacket | None,
    field: str | None,
    *,
    model: str | None = None,
) -> bool:
    """True when ``field`` is on the slice (optionally scoped to ``model``).

    Inputs: packet, field name, optional model. ``packet is None`` is out of
    scope and returns True. Side effects: none.
    """

    name = str(field or "").strip()
    if not name:
        return False
    if packet is None:
        return True
    if model:
        row = packet.models.get(model)
        return bool(row and name in row.fields)
    return any(name in row.fields for row in packet.models.values())


def resolve_form_anchor(
    packet: SchemaPacket | None,
    phrase: str,
    *,
    model: str | None = None,
) -> str | None:
    """Resolve a placement phrase to a field in the packet's form order.

    Inputs: packet, operator words such as ``after the customer``, optional
    existing form. Output: the first matching form-order field (``partner_id``
    for customer on ``sale.order``). Side effects: none.
    """

    if packet is None or packet.is_empty():
        return None
    text = str(phrase or "").strip().lower()
    if not text:
        return None
    scoped = (
        [packet.models[model]]
        if model and model in packet.models
        else []
    )
    models = scoped + [row for row in packet.models.values() if row not in scoped]
    for row in models:
        order = row.views.get("form") or tuple(row.fields)
        for fname in order:
            if fname in text or fname.replace("_", " ") in text:
                return fname
        for alias, preferred in _ANCHOR_ALIASES.items():
            if re.search(rf"\b{re.escape(alias)}\b", text):
                for fname in preferred:
                    if fname in row.fields:
                        return fname
                for fname in order:
                    field = row.fields.get(fname)
                    if field and field.relation == "res.partner":
                        return fname
    return None


def drop_unknown_technical_names(text: str, packet: SchemaPacket | None) -> str:
    """Strip technical names the slice does not contain from LLM prose.

    Inputs: one constraint / summary string and the packet. ``packet is None``
    leaves the text unchanged. Side effects: none.
    """

    if packet is None or not text:
        return text
    known_models = set(packet.models)
    known_fields = {name for row in packet.models.values() for name in row.fields}

    def _keep(match: re.Match[str]) -> str:
        token = match.group(0)
        if token in known_models or token in known_fields:
            return token
        return ""

    cleaned = _TECH_NAME_RE.sub(_keep, text)
    return re.sub(r"\s{2,}", " ", cleaned).strip(" ,;.-")


def technical_names(text: str) -> list[str]:
    """Model, field, or method technical names written in ``text``.

    Inputs: any prose. Output: ``x_*``, dotted model names, and snake_case
    tokens in first-seen order. Abbreviations such as ``e.g`` are skipped.
    Side effects: none.
    """

    names: list[str] = []
    for regex in (_TECH_NAME_RE, _SNAKE_NAME_RE):
        for match in regex.finditer(text or ""):
            token = match.group(0)
            if token in names:
                continue
            if "." in token and any(len(part) < 2 for part in token.split(".")):
                continue
            names.append(token)
    return names


def unknown_technical_names(
    text: str,
    packet: SchemaPacket | None,
    *,
    allowed: Iterable[str] = (),
) -> list[str]:
    """Technical names in display text that neither the slice nor ``allowed`` holds.

    Inputs: generated display text, the packet, and names the caller already
    admitted (an applied patch, deterministic finding text). ``packet is None``
    admits no live names: with no connection the text may only repeat
    ``allowed``. Output: unknown names in first-seen order. Side effects: none.
    """

    known = {str(name) for name in allowed if name}
    if packet is not None:
        known.update(packet.models)
        for row in packet.models.values():
            known.update(row.fields)
            known.update(row.methods)
    return [name for name in technical_names(text) if name not in known]


_NO_CONNECTION_PROMPT = (
    "NO LIVE CONNECTION — do not name a field on a stock Odoo model. "
    "Propose only new x_* models and new x_* fields."
)
_DOTTED_NAME_RE = re.compile(r"\b[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+\b")
# String values under these keys are names the structural pass already judged.
_STRUCTURAL_KEYS = frozenset({"model", "relation", "name", "field", "ttype", "type"})
_DROP = object()


def stock_field_allowed(packet: SchemaPacket | None, model: str, field: str) -> bool:
    """True when ``model.field`` may appear in draft output.

    Inputs: packet (``None`` = no connection), model, field (a dotted path
    is judged by its first hop). New ``x_*`` models and ``x_*`` fields are
    always allowed: the draft proposes to create them. Any other field on a
    stock model must be in the packet; with no connection it is refused.
    Side effects: none.
    """

    name = str(field or "").split(".", 1)[0].strip()
    host = str(model or "").strip()
    if not name or not host or name.startswith("x_") or host.startswith("x_"):
        return True
    if packet is None:
        return False
    row = packet.models.get(host)
    return bool(row and name in row.fields)


def _drop_unknown_stock_field_refs(
    text: str, packet: SchemaPacket | None, dropped: list[str]
) -> str:
    if packet is None or "." not in text:
        return text

    def _keep(match: re.Match[str]) -> str:
        token = match.group(0)
        parts = token.split(".")
        for cut in range(len(parts) - 1, 0, -1):
            host = ".".join(parts[:cut])
            if host not in packet.models:
                continue
            rest = parts[cut:]
            if len(rest) == 1 and not stock_field_allowed(packet, host, rest[0]):
                dropped.append(token)
                return ""
            return token
        return token

    cleaned = _DOTTED_NAME_RE.sub(_keep, text)
    if cleaned == text:
        return text
    return re.sub(r"\s{2,}", " ", cleaned).strip()


def _ground_value(
    value: Any,
    packet: SchemaPacket | None,
    *,
    model: str | None,
    key: str | None,
    in_fields: bool,
    dropped: list[str],
) -> Any:
    if isinstance(value, Mapping):
        own = value.get("model")
        host = own.strip() if isinstance(own, str) and own.strip() else model
        fname = value.get("field")
        if not isinstance(fname, str):
            name = value.get("name")
            fname = name if isinstance(name, str) and (in_fields or "ttype" in value) else None
        if host and fname and not stock_field_allowed(packet, host, fname):
            dropped.append(f"{host}.{fname}")
            return _DROP
        out: dict[Any, Any] = {}
        for k, v in value.items():
            child = _ground_value(
                v,
                packet,
                model=host,
                key=str(k),
                in_fields=k == "fields",
                dropped=dropped,
            )
            if child is not _DROP:
                out[k] = child
        return out
    if isinstance(value, list):
        items = (
            _ground_value(
                v, packet, model=model, key=key, in_fields=in_fields, dropped=dropped
            )
            for v in value
        )
        return [item for item in items if item is not _DROP]
    if isinstance(value, str) and key not in _STRUCTURAL_KEYS:
        return _drop_unknown_stock_field_refs(value, packet, dropped)
    return value


@dataclass(frozen=True, slots=True)
class DraftGrounding:
    """Prompt prefix and output filter shared by the draft-pipeline LLM calls.

    ``packet is None`` means no connection: the prompt says so and the filter
    refuses every non-``x_*`` field on a stock model. Each call site keeps its
    own output format; the filter walks whatever JSON it returns.
    """

    packet: SchemaPacket | None

    def prompt(self, user_message: str) -> str:
        """Return ``user_message`` with the live slice (or no-connection rule) first."""

        if self.packet is None:
            return f"{_NO_CONNECTION_PROMPT}\n\n{user_message}"
        return prepend_schema_packet(user_message, self.packet)

    def filter(self, data: Any) -> tuple[Any, list[str]]:
        """Drop stock-model field references the slice does not contain.

        Inputs: parsed LLM JSON (any shape). A dict that names a field (``field``,
        or ``name`` on a field spec) under a ``model`` context is removed from its
        parent when ``stock_field_allowed`` refuses it. Dotted ``model.field``
        tokens in free text are removed the same way when the model is in the
        packet. Output: (filtered copy, dropped ``model.field`` names).
        Side effects: none; ``data`` is not mutated.
        """

        dropped: list[str] = []
        out = _ground_value(
            data, self.packet, model=None, key=None, in_fields=False, dropped=dropped
        )
        if out is _DROP:
            out = {} if isinstance(data, Mapping) else None
        return out, dropped


def draft_grounding(schema_packet: SchemaPacket | None = None) -> DraftGrounding:
    """Grounding for a draft-pipeline call: explicit packet, else the request's.

    Inputs: an explicit packet, or ``None`` to use the packet the request set
    with ``set_schema_packet``. Neither → no connection. Side effects: none.
    """

    if schema_packet is None:
        from app.ai_conversation.intent_llm import current_schema_packet

        schema_packet = current_schema_packet()
    return DraftGrounding(schema_packet)


__all__ = [
    "VIEW_TYPES",
    "ConnectionRequiredError",
    "DraftGrounding",
    "PacketField",
    "PacketModel",
    "SchemaPacket",
    "bind_schema_rpc",
    "build_schema_packet",
    "draft_grounding",
    "drop_unknown_technical_names",
    "empty_schema_packet",
    "field_in_packet",
    "model_in_packet",
    "models_for_studio_packet",
    "prepend_schema_packet",
    "render_schema_packet",
    "resolve_form_anchor",
    "stock_field_allowed",
    "studio_schema_packet",
    "technical_names",
    "unknown_technical_names",
]
