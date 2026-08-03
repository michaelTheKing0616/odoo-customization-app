"""Odoo XML-RPC client wrapping stdlib xmlrpc.client with typed helpers."""

from __future__ import annotations

import xmlrpc.client
from typing import Any, Literal
from urllib.parse import urljoin

from odoo_client.compat.capabilities import VersionCapabilities
from odoo_client.compat.registry import for_major, parse_major
from odoo_client.models import (
    ConnectionConfig,
    CreateFieldRequest,
    CreateModelRequest,
    CreateViewRequest,
    FieldInfo,
    FieldType,
    ModelInfo,
    ModuleInfo,
    ViewInfo,
)


class OdooClientError(Exception):
    """Raised when an Odoo RPC call fails or returns an unexpected shape."""


class OdooClient:
    """Synchronous XML-RPC client for Odoo Community 16–19 (17+18+19 GA)."""

    def __init__(self, config: ConnectionConfig) -> None:
        self.config = config
        self._uid: int | None = None
        # Default to 19 capabilities before connect; connect() refreshes from server.
        self.capabilities: VersionCapabilities = for_major(19)
        self._ir_fields_colnames: frozenset[str] | None = None
        self._common = xmlrpc.client.ServerProxy(
            urljoin(config.url + "/", "xmlrpc/2/common"),
            allow_none=True,
        )
        self._object = xmlrpc.client.ServerProxy(
            urljoin(config.url + "/", "xmlrpc/2/object"),
            allow_none=True,
        )

    @property
    def uid(self) -> int:
        if self._uid is None:
            raise OdooClientError("Not connected. Call connect() first.")
        return self._uid

    def _ir_model_fields_columns(self, wanted: list[str]) -> list[str]:
        """Filter read columns to those present on this Odoo (e.g. no currency_field on 16)."""
        if self._ir_fields_colnames is None:
            meta = self.execute_kw(
                "ir.model.fields",
                "fields_get",
                [],
                {"attributes": ["type"]},
            )
            self._ir_fields_colnames = frozenset(meta.keys())
        return [name for name in wanted if name in self._ir_fields_colnames]

    def _automation_adapter(self):  # noqa: ANN201
        major = self.capabilities.major
        if major == 16:
            from odoo_client.compat.adapters import automation_v16 as mod
        elif major == 17:
            from odoo_client.compat.adapters import automation_v17 as mod
        elif major == 18:
            from odoo_client.compat.adapters import automation_v18 as mod
        else:
            from odoo_client.compat.adapters import automation_v19 as mod
        return mod

    def _views_adapter(self):  # noqa: ANN201
        major = self.capabilities.major
        if major == 16:
            from odoo_client.compat.adapters import views_v16 as mod
        elif major == 17:
            from odoo_client.compat.adapters import views_v17 as mod
        elif major == 18:
            from odoo_client.compat.adapters import views_v18 as mod
        else:
            from odoo_client.compat.adapters import views_v19 as mod
        return mod

    def connect(self) -> int:
        """Authenticate and store uid. Returns the authenticated user id."""
        from odoo_client.compat.registry import supported_majors

        try:
            version = self._common.version()
        except Exception as exc:  # noqa: BLE001 — surface transport errors clearly
            raise OdooClientError(f"Failed to reach Odoo at {self.config.url}: {exc}") from exc

        server_version = str(version.get("server_version", ""))
        try:
            major = parse_major(server_version)
            self.capabilities = for_major(major)
        except Exception as exc:  # noqa: BLE001 — UnsupportedOdooMajorError etc.
            raise OdooClientError(
                f"Unsupported Odoo server_version={server_version!r}. "
                f"Supported majors: {sorted(supported_majors())}. ({exc})"
            ) from exc
        if major not in supported_majors():
            raise OdooClientError(
                f"Unsupported Odoo server_version={server_version!r}. "
                f"Supported majors: {sorted(supported_majors())} "
                "(19+18+17=GA; 16=experimental)."
            )

        uid = self._common.authenticate(
            self.config.db,
            self.config.username,
            self.config.password,
            {},
        )
        if not uid:
            raise OdooClientError(
                f"Authentication failed for db={self.config.db!r} user={self.config.username!r}"
            )
        self._uid = int(uid)
        return self._uid

    def execute_kw(
        self,
        model: str,
        method: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        return self._object.execute_kw(
            self.config.db,
            self.uid,
            self.config.password,
            model,
            method,
            args or [],
            kwargs or {},
        )

    def server_version(self) -> dict[str, Any]:
        return dict(self._common.version())

    def list_modules(
        self,
        *,
        installed_only: bool = True,
        applications_only: bool = False,
        limit: int = 500,
    ) -> list[ModuleInfo]:
        domain: list[Any] = []
        if installed_only:
            domain.append(("state", "=", "installed"))
        if applications_only:
            domain.append(("application", "=", True))
        rows = self.execute_kw(
            "ir.module.module",
            "search_read",
            [domain],
            {
                "fields": ["id", "name", "shortdesc", "state", "application"],
                "limit": limit,
                "order": "shortdesc, name",
            },
        )
        return [ModuleInfo.model_validate(row) for row in rows]

    def list_models(self, *, custom_only: bool = False, limit: int = 500) -> list[ModelInfo]:
        domain: list[Any] = [("transient", "=", False)]
        if custom_only:
            domain.append(("model", "=like", "x_%"))
        rows = self.execute_kw(
            "ir.model",
            "search_read",
            [domain],
            {"fields": ["id", "model", "name", "state", "transient"], "limit": limit, "order": "model"},
        )
        return [ModelInfo.model_validate(row) for row in rows]

    def list_models_with_custom_fields(self, *, limit: int = 200) -> list[str]:
        """Return distinct model names that have at least one manual ``x_*`` field.

        Used by export to package extensions on stock models (e.g. res.partner).
        """
        rows = self.execute_kw(
            "ir.model.fields",
            "search_read",
            [[("name", "=like", "x_%"), ("state", "=", "manual")]],
            {"fields": ["model"], "limit": max(limit * 20, 500), "order": "model, id"},
        )
        seen: list[str] = []
        for row in rows:
            model = row.get("model")
            if not model or model in seen:
                continue
            seen.append(str(model))
            if len(seen) >= limit:
                break
        return seen

    def list_extension_models(
        self, *, exclude: set[str] | None = None, limit: int = 200
    ) -> list[str]:
        """Models with custom x_* fields that are not themselves new custom models.

        Excludes ``x_*`` models by default (those are packaged as mode=new).
        """
        skip = exclude or set()
        out: list[str] = []
        for model in self.list_models_with_custom_fields(limit=limit):
            if model in skip:
                continue
            if model.startswith("x_"):
                continue
            out.append(model)
        return out

    def list_views(self, model: str, *, limit: int = 100) -> list[ViewInfo]:
        rows = self.execute_kw(
            "ir.ui.view",
            "search_read",
            [[("model", "=", model), ("type", "in", ["form", "list", "kanban", "search", "tree"])]],
            {
                "fields": ["id", "name", "model", "type", "arch"],
                "limit": limit,
                "order": "priority, id",
            },
        )
        return [ViewInfo.model_validate(row) for row in rows]

    def list_fields(self, model: str) -> list[FieldInfo]:
        rows = self.execute_kw(
            "ir.model.fields",
            "search_read",
            [[("model", "=", model)]],
            {
                "fields": self._ir_model_fields_columns(
                    [
                        "id",
                        "name",
                        "field_description",
                        "ttype",
                        "model_id",
                        "required",
                        "readonly",
                        "relation",
                        "relation_field",
                        "state",
                        "selection",
                        "help",
                        "related",
                        "currency_field",
                        "tracking",
                    ]
                ),
                "order": "name",
            },
        )
        return [FieldInfo.model_validate(row) for row in rows]

    def model_exists(self, model: str) -> bool:
        ids = self.execute_kw("ir.model", "search", [[("model", "=", model)]], {"limit": 1})
        return bool(ids)

    def field_exists(self, model: str, name: str) -> bool:
        ids = self.execute_kw(
            "ir.model.fields",
            "search",
            [[("model", "=", model), ("name", "=", name)]],
            {"limit": 1},
        )
        return bool(ids)

    def create_model(self, request: CreateModelRequest, *, with_defaults: bool = True) -> ModelInfo:
        if self.model_exists(request.model):
            raise OdooClientError(f"Model {request.model!r} already exists")

        model_id = self.execute_kw(
            "ir.model",
            "create",
            [
                {
                    "name": request.name,
                    "model": request.model,
                    "state": "manual",
                    "transient": request.transient,
                }
            ],
        )
        rows = self.execute_kw(
            "ir.model",
            "read",
            [[model_id]],
            {"fields": ["id", "model", "name", "state", "transient"]},
        )
        if not rows:
            raise OdooClientError(f"Created model id={model_id} but read returned empty")
        info = ModelInfo.model_validate(rows[0])

        if with_defaults:
            # Studio-like: name field + basic list/form so the model is usable immediately.
            if not self.field_exists(request.model, "x_name"):
                self.create_field(
                    CreateFieldRequest(
                        model=request.model,
                        name="x_name",
                        field_description="Name",
                        ttype=FieldType.CHAR,
                        required=True,
                    )
                )
            # Odoo ≤17 store list views as type/root ``tree``; 18+ accept ``list``.
            list_type = self._views_adapter().list_type_fallbacks("list")[0]
            list_tag = list_type  # arch root must match ir.ui.view.type
            self.create_view(
                CreateViewRequest(
                    name=f"{request.model}.list",
                    model=request.model,
                    type=list_type,
                    arch=(
                        f'<{list_tag} string="{request.name}">'
                        f'<field name="x_name"/></{list_tag}>'
                    ),
                )
            )
            self.create_view(
                CreateViewRequest(
                    name=f"{request.model}.form",
                    model=request.model,
                    type="form",
                    arch=(
                        f'<form string="{request.name}">'
                        f'<sheet><group><field name="x_name"/></group></sheet></form>'
                    ),
                )
            )
            self.create_view(
                CreateViewRequest(
                    name=f"{request.model}.search",
                    model=request.model,
                    type="search",
                    arch=(
                        f'<search string="{request.name}">'
                        f'<field name="x_name"/></search>'
                    ),
                )
            )
            # Studio-like default ACL so non-admin internal users can use the model.
            self.ensure_default_model_access(request.model)
        return info

    def resolve_xml_id(self, xml_id: str) -> int:
        """Resolve module.xml_id (e.g. base.group_user) to res_id."""
        if "." not in xml_id:
            raise OdooClientError(f"Invalid xml_id {xml_id!r} — expected module.name")
        module, name = xml_id.split(".", 1)
        rows = self.execute_kw(
            "ir.model.data",
            "search_read",
            [[("module", "=", module), ("name", "=", name)]],
            {"fields": ["res_id", "model"], "limit": 1},
        )
        if not rows:
            raise OdooClientError(f"xml_id {xml_id!r} not found")
        return int(rows[0]["res_id"])

    def ensure_default_model_access(
        self, model: str, *, group_xml_id: str = "base.group_user"
    ) -> Any:
        """Ensure Internal User (base.group_user) has full CRUD on model."""
        from odoo_client.security import CreateAccessRightRequest

        group_id = self.resolve_xml_id(group_xml_id)
        existing = self.execute_kw(
            "ir.model.access",
            "search",
            [[("model_id.model", "=", model), ("group_id", "=", group_id)]],
            {"limit": 1},
        )
        if existing:
            for row in self.list_access_rights(model=model, limit=50):
                if row.id == existing[0]:
                    return row
            return existing[0]

        return self.create_access_right(
            CreateAccessRightRequest(
                model=model,
                name=f"access_{model.replace('.', '_')}_user",
                group_id=group_id,
                perm_read=True,
                perm_write=True,
                perm_create=True,
                perm_unlink=True,
            )
        )

    def find_xml_id(self, model: str, res_id: int) -> str | None:
        rows = self.execute_kw(
            "ir.model.data",
            "search_read",
            [[("model", "=", model), ("res_id", "=", res_id)]],
            {"fields": ["module", "name"], "limit": 1},
        )
        if not rows:
            return None
        return f"{rows[0]['module']}.{rows[0]['name']}"

    def uninstall_module(self, module_name: str) -> dict[str, Any]:
        """Uninstall an installed module (advanced — may leave residual data)."""
        row = self.get_module_state(module_name)
        if not row:
            raise OdooClientError(f"Module {module_name!r} not found")
        if row["state"] == "uninstalled":
            return row
        if row["state"] not in {"installed", "to upgrade", "to remove"}:
            raise OdooClientError(
                f"Module {module_name!r} is in state {row['state']!r}; cannot uninstall"
            )
        self.execute_kw("ir.module.module", "button_immediate_uninstall", [[row["id"]]])
        refreshed = self.get_module_state(module_name)
        if not refreshed or refreshed.get("state") not in {"uninstalled", "to remove"}:
            # Some versions leave as uninstalled after immediate; accept either
            if refreshed and refreshed.get("state") == "installed":
                raise OdooClientError(f"Failed to uninstall module {module_name!r}")
        return refreshed or row

    def list_installed_modules(
        self, *, name_prefix: str | None = None, limit: int = 200
    ) -> list[ModuleInfo]:
        domain: list[Any] = [("state", "=", "installed")]
        if name_prefix:
            domain.append(("name", "=like", f"{name_prefix}%"))
        rows = self.execute_kw(
            "ir.module.module",
            "search_read",
            [domain],
            {
                "fields": ["id", "name", "shortdesc", "state", "application"],
                "limit": limit,
                "order": "name",
            },
        )
        return [ModuleInfo.model_validate(row) for row in rows]

    def create_field(self, request: CreateFieldRequest) -> FieldInfo:
        request.validate_type_requirements()
        if self.field_exists(request.model, request.name):
            raise OdooClientError(
                f"Field {request.name!r} already exists on model {request.model!r}"
            )

        model_ids = self.execute_kw(
            "ir.model",
            "search",
            [[("model", "=", request.model)]],
            {"limit": 1},
        )
        if not model_ids:
            raise OdooClientError(f"Model {request.model!r} not found")

        raw_ttype = request.ttype.value if isinstance(request.ttype, FieldType) else request.ttype
        # Odoo has no ttype="related"; related= is an attribute on a concrete ttype.
        # When related path is set, send the concrete request.ttype to Odoo.
        # Deprecated pseudo-type RELATED maps to many2one (if relation) else char.
        if raw_ttype == FieldType.RELATED.value:
            if not request.related:
                raise OdooClientError("related fields require a related path")
            odoo_ttype = "many2one" if request.relation else "char"
        else:
            odoo_ttype = raw_ttype

        vals: dict[str, Any] = {
            "name": request.name,
            "field_description": request.field_description,
            "model_id": model_ids[0],
            "ttype": odoo_ttype,
            "state": "manual",
            "required": request.required,
            "readonly": request.readonly or bool(request.related),
            "index": request.index,
        }
        if request.relation:
            vals["relation"] = request.relation
        if request.relation_field:
            vals["relation_field"] = request.relation_field
        if request.selection:
            vals["selection"] = request.selection
        if request.help:
            vals["help"] = request.help
        if request.related:
            vals["related"] = request.related
        if request.currency_field:
            # Odoo 16 ir.model.fields has no currency_field column — omit when absent.
            readable = self._ir_model_fields_columns(["currency_field"])
            if "currency_field" in readable:
                vals["currency_field"] = request.currency_field
        # Odoo 19: required many2one cannot use on_delete='set null'
        if odoo_ttype == "many2one":
            if request.on_delete:
                vals["on_delete"] = request.on_delete
            elif request.required:
                vals["on_delete"] = "restrict"
        if request.definition_record:
            readable = self._ir_model_fields_columns(
                ["definition_record", "definition_record_field"]
            )
            if "definition_record" in readable:
                vals["definition_record"] = request.definition_record
            if request.definition_record_field and "definition_record_field" in readable:
                vals["definition_record_field"] = request.definition_record_field

        field_id = self.execute_kw("ir.model.fields", "create", [vals])
        rows = self.execute_kw(
            "ir.model.fields",
            "read",
            [[field_id]],
            {
                "fields": self._ir_model_fields_columns(
                    [
                        "id",
                        "name",
                        "field_description",
                        "ttype",
                        "model_id",
                        "required",
                        "readonly",
                        "relation",
                        "relation_field",
                        "state",
                        "selection",
                        "help",
                        "related",
                        "currency_field",
                    ]
                )
            },
        )
        if not rows:
            raise OdooClientError(f"Created field id={field_id} but read returned empty")
        return FieldInfo.model_validate(rows[0])

    _SAFE_FIELD_UPDATE = frozenset(
        {"string", "field_description", "help", "required", "readonly", "tracking", "selection"}
    )
    _FORBIDDEN_FIELD_UPDATE = frozenset({"name", "ttype", "model", "model_id", "state", "relation"})

    def get_field(self, field_id: int) -> FieldInfo:
        rows = self.execute_kw(
            "ir.model.fields",
            "read",
            [[field_id]],
            {
                "fields": self._ir_model_fields_columns(
                    [
                        "id",
                        "name",
                        "field_description",
                        "ttype",
                        "model_id",
                        "required",
                        "readonly",
                        "relation",
                        "relation_field",
                        "state",
                        "help",
                        "tracking",
                        "selection",
                        "related",
                        "currency_field",
                    ]
                )
            },
        )
        if not rows:
            raise OdooClientError(f"Field id={field_id} not found")
        return FieldInfo.model_validate(rows[0])

    def read_field_raw(self, field_id: int) -> dict[str, Any]:
        """Full dump for snapshots (before destructive delete)."""
        rows = self.execute_kw(
            "ir.model.fields",
            "read",
            [[field_id]],
            {
                "fields": self._ir_model_fields_columns(
                    [
                        "id",
                        "name",
                        "field_description",
                        "ttype",
                        "model_id",
                        "model",
                        "required",
                        "readonly",
                        "relation",
                        "relation_field",
                        "selection",
                        "state",
                        "help",
                        "tracking",
                        "index",
                        "copied",
                        "store",
                        "currency_field",
                        "related",
                    ]
                )
            },
        )
        if not rows:
            raise OdooClientError(f"Field id={field_id} not found")
        return dict(rows[0])

    def update_field(self, field_id: int, **safe_attrs: Any) -> FieldInfo:
        """Update safe field metadata only — refuse renaming / ttype changes."""
        if not safe_attrs:
            raise OdooClientError("update_field requires at least one attribute")

        forbidden = set(safe_attrs) & self._FORBIDDEN_FIELD_UPDATE
        if forbidden:
            raise OdooClientError(
                f"Refusing to change {sorted(forbidden)} — rename/ttype/model are not allowed"
            )
        unknown = set(safe_attrs) - self._SAFE_FIELD_UPDATE
        if unknown:
            raise OdooClientError(
                f"Unsupported field attrs {sorted(unknown)}; "
                f"allowed: {sorted(self._SAFE_FIELD_UPDATE)}"
            )

        existing = self.read_field_raw(field_id)
        vals: dict[str, Any] = {}

        if "string" in safe_attrs or "field_description" in safe_attrs:
            label = safe_attrs.get("string", safe_attrs.get("field_description"))
            if label is not None:
                vals["field_description"] = label

        for key in ("help", "required", "readonly", "tracking"):
            if key in safe_attrs:
                vals[key] = safe_attrs[key]

        if "selection" in safe_attrs:
            if existing.get("ttype") != "selection":
                raise OdooClientError(
                    "selection can only be updated on fields with ttype='selection'"
                )
            vals["selection"] = safe_attrs["selection"]

        if not vals:
            raise OdooClientError("No writable attributes after validation")

        self.execute_kw("ir.model.fields", "write", [[field_id], vals])
        return self.get_field(field_id)

    def delete_field(self, field_id: int) -> None:
        """Unlink custom ir.model.fields only (name must start with x_)."""
        raw = self.read_field_raw(field_id)
        name = str(raw.get("name") or "")
        if not name.startswith("x_"):
            raise OdooClientError(
                f"Refusing to delete non-custom field {name!r} — only x_* fields allowed"
            )
        self.execute_kw("ir.model.fields", "unlink", [[field_id]])

    def read_model_raw(self, model_name: str) -> dict[str, Any]:
        rows = self.execute_kw(
            "ir.model",
            "search_read",
            [[("model", "=", model_name)]],
            {"fields": ["id", "model", "name", "state", "transient"], "limit": 1},
        )
        if not rows:
            raise OdooClientError(f"Model {model_name!r} not found")
        return dict(rows[0])

    def delete_model(self, model_name: str) -> None:
        """Unlink ir.model only for custom x_* models."""
        if not model_name.startswith("x_"):
            raise OdooClientError(
                f"Refusing to delete non-custom model {model_name!r} — only x_* models allowed"
            )
        raw = self.read_model_raw(model_name)
        self.execute_kw("ir.model", "unlink", [[int(raw["id"])]])

    def create_view(self, request: CreateViewRequest) -> ViewInfo:
        view_id = self.execute_kw(
            "ir.ui.view",
            "create",
            [
                {
                    "name": request.name,
                    "model": request.model,
                    "type": request.type,
                    "arch": request.arch,
                    "priority": request.priority,
                }
            ],
        )
        return self.get_view(int(view_id))

    def create_inherit_view(
        self,
        model: str,
        name: str,
        view_type: str,
        inherit_id: int,
        arch: str,
        priority: int = 99,
    ) -> ViewInfo:
        """Create an ir.ui.view extension (xpath) inheriting a primary view."""
        vals: dict[str, Any] = {
            "name": name,
            "model": model,
            "type": view_type,
            "inherit_id": inherit_id,
            "arch": arch,
            "priority": priority,
            "mode": "extension",
        }
        view_id = self.execute_kw("ir.ui.view", "create", [vals])
        return self.get_view(int(view_id))

    def inject_smart_buttons_into_form(
        self,
        model: str,
        buttons: list[Any],
        *,
        view_name: str | None = None,
    ) -> ViewInfo:
        """Upsert a stable inherit view that adds smart buttons; never mutates primary.

        Uses ``{model}.studio.smart_buttons`` so re-applies overwrite instead of stacking
        (see ERRORS.md duplicate header inherits).
        """
        from odoo_client.compat.capabilities import CapabilityId
        from odoo_client.view_arch import ButtonNode, render_inherit_smart_buttons_arch

        views_v = self._views_adapter()
        self.capabilities.require(CapabilityId.SMART_BUTTON_INHERIT_BOX)
        nodes: list[ButtonNode] = []
        for btn in buttons:
            if isinstance(btn, ButtonNode):
                nodes.append(btn)
            else:
                nodes.append(ButtonNode.model_validate(btn))
        if not nodes:
            raise OdooClientError("inject_smart_buttons_into_form requires buttons")

        primary = self.find_view(model, "form", primary_only=True) or self.find_view(
            model, "form"
        )
        if primary is None:
            raise OdooClientError(f"No form view found for model {model}")

        arch = render_inherit_smart_buttons_arch(nodes, parent_arch=primary.arch)
        child_name = views_v.smart_buttons_view_name(model, override=view_name)
        existing = self._find_view_by_exact_name(child_name)
        if existing is not None:
            # Ensure we still inherit the current primary if it was recreated
            if getattr(existing, "id", None):
                # Update arch; also re-point inherit_id if Odoo stored a stale parent
                self.execute_kw(
                    "ir.ui.view",
                    "write",
                    [[existing.id], {"arch": arch, "inherit_id": primary.id}],
                )
                return self.get_view(existing.id)
        return self.create_inherit_view(
            model=model,
            name=child_name,
            view_type=primary.type or "form",
            inherit_id=primary.id,
            arch=arch,
        )

    def get_view(self, view_id: int) -> ViewInfo:
        rows = self.execute_kw(
            "ir.ui.view",
            "read",
            [[view_id]],
            {"fields": ["id", "name", "model", "type", "arch"]},
        )
        if not rows:
            raise OdooClientError(f"View id={view_id} not found")
        return ViewInfo.model_validate(rows[0])

    def update_view_arch(self, view_id: int, arch: str) -> ViewInfo:
        self.execute_kw("ir.ui.view", "write", [[view_id], {"arch": arch}])
        return self.get_view(view_id)

    def _find_view_by_exact_name(self, name: str) -> ViewInfo | None:
        ids = self.execute_kw(
            "ir.ui.view",
            "search",
            [[("name", "=", name)]],
            {"limit": 1},
        )
        if not ids:
            return None
        return self.get_view(int(ids[0]))

    def inject_field_into_views(
        self,
        model: str,
        field_name: str,
        *,
        view_types: list[str] | None = None,
        strategy: Literal["inherit", "mutate"] = "inherit",
        widget: str | None = None,
    ) -> list[ViewInfo]:
        """Inject field into form/list/search views.

        Default ``inherit``: create/update a child extension view
        ``{model}.custom.{field_name}.{view_type}`` so module primary arches stay intact.
        ``mutate``: write the field into the parent arch (legacy; advanced).
        Optional ``widget`` (e.g. ``barcode``) is applied on form injects only.
        """
        from odoo_client.compat.capabilities import CapabilityId
        from odoo_client.view_arch import inject_field_into_arch, render_inherit_field_arch

        views_v = self._views_adapter()
        strategy = views_v.normalize_inject_strategy(strategy)
        if strategy == "mutate":
            self.capabilities.require(CapabilityId.VIEW_INJECT_MUTATE)
        else:
            self.capabilities.require(CapabilityId.VIEW_INJECT_INHERIT)
        types = view_types or views_v.default_field_inject_view_types()
        updated: list[ViewInfo] = []
        for vt in types:
            if strategy == "mutate":
                view = self.find_view(model, vt)
                if view is None or not view.arch:
                    continue
                form_widget = widget if vt == "form" else None
                new_arch = inject_field_into_arch(
                    view.arch, field_name, view_type=vt, widget=form_widget
                )
                if new_arch != view.arch:
                    updated.append(self.update_view_arch(view.id, new_arch))
                continue

            primary = self.find_view(model, vt, primary_only=True)
            if primary is None:
                primary = self.find_view(model, vt)
            if primary is None:
                continue
            child_name = views_v.custom_field_view_name(model, field_name, vt)
            arch = render_inherit_field_arch(
                field_name,
                primary.type or vt,
                parent_arch=primary.arch,
                widget=widget,
            )
            existing = self._find_view_by_exact_name(child_name)
            if existing is not None:
                updated.append(self.update_view_arch(existing.id, arch))
            else:
                updated.append(
                    self.create_inherit_view(
                        model=model,
                        name=child_name,
                        view_type=primary.type,
                        inherit_id=primary.id,
                        arch=arch,
                    )
                )
        return updated

    def find_view(
        self,
        model: str,
        view_type: str,
        *,
        prefer_name_contains: str | None = None,
        primary_only: bool = False,
    ) -> ViewInfo | None:
        domain: list[Any] = [("model", "=", model), ("type", "=", view_type)]
        if primary_only:
            domain.append(("mode", "=", "primary"))
        ids = self.execute_kw(
            "ir.ui.view",
            "search",
            [domain],
            {"limit": 20, "order": "priority, id"},
        )
        if not ids:
            # Odoo 17+ list may still be stored as tree in some DBs
            if view_type == "list":
                return self.find_view(
                    model,
                    "tree",
                    prefer_name_contains=prefer_name_contains,
                    primary_only=primary_only,
                )
            return None
        rows = self.execute_kw(
            "ir.ui.view",
            "read",
            [ids],
            {"fields": ["id", "name", "model", "type", "arch"]},
        )
        infos = [ViewInfo.model_validate(r) for r in rows]
        if prefer_name_contains:
            for info in infos:
                if prefer_name_contains in info.name:
                    return info
        return infos[0]

    def ensure_module_installed(self, module_name: str) -> None:
        rows = self.execute_kw(
            "ir.module.module",
            "search_read",
            [[("name", "=", module_name)]],
            {"fields": ["id", "state"], "limit": 1},
        )
        if not rows:
            raise OdooClientError(f"Module {module_name!r} not found on this instance")
        if rows[0]["state"] == "installed":
            return
        self.execute_kw("ir.module.module", "button_immediate_install", [[rows[0]["id"]]])
        refreshed = self.execute_kw(
            "ir.module.module",
            "read",
            [[rows[0]["id"]]],
            {"fields": ["state"]},
        )
        if not refreshed or refreshed[0]["state"] != "installed":
            raise OdooClientError(f"Failed to install module {module_name!r}")

    def update_module_list(self) -> None:
        self.execute_kw("ir.module.module", "update_list", [])

    def get_module_state(self, module_name: str) -> dict[str, Any] | None:
        rows = self.execute_kw(
            "ir.module.module",
            "search_read",
            [[("name", "=", module_name)]],
            {"fields": ["id", "name", "state"], "limit": 1},
        )
        return dict(rows[0]) if rows else None

    def install_module_by_name(self, module_name: str) -> dict[str, Any]:
        self.update_module_list()
        row = self.get_module_state(module_name)
        if not row:
            raise OdooClientError(
                f"Module {module_name!r} not found after update_list — "
                "is it on the addons path?"
            )
        if row["state"] != "installed":
            self.execute_kw("ir.module.module", "button_immediate_install", [[row["id"]]])
            row = self.get_module_state(module_name) or row
        if row.get("state") != "installed":
            raise OdooClientError(f"Failed to install module {module_name!r}")
        return row

    def import_module_zip(self, zip_bytes: bytes, *, force: bool = True) -> dict[str, Any]:
        """Install a data-only module zip via base_import_module (no Python models)."""
        import base64

        self.ensure_module_installed("base_import_module")
        b64 = base64.b64encode(zip_bytes).decode("ascii")
        wid = self.execute_kw(
            "base.import.module",
            "create",
            [{"module_file": b64, "force": force}],
        )
        try:
            self.execute_kw("base.import.module", "import_module", [[wid]])
        except Exception as exc:  # noqa: BLE001
            raise OdooClientError(f"base.import.module failed: {exc}") from exc
        rows = self.execute_kw(
            "base.import.module",
            "read",
            [[wid]],
            {"fields": ["state", "import_message"]},
        )
        return dict(rows[0]) if rows else {"id": wid}

    def _model_id(self, model: str) -> int:
        ids = self.execute_kw("ir.model", "search", [[("model", "=", model)]], {"limit": 1})
        if not ids:
            raise OdooClientError(f"Model {model!r} not found")
        return int(ids[0])

    def _field_id(self, model: str, name: str) -> int:
        ids = self.execute_kw(
            "ir.model.fields",
            "search",
            [[("model", "=", model), ("name", "=", name)]],
            {"limit": 1},
        )
        if not ids:
            raise OdooClientError(f"Field {name!r} not found on model {model!r}")
        return int(ids[0])

    def list_automations(self, *, model: str | None = None, limit: int = 200) -> list[Any]:
        from odoo_client.automation import AutomationInfo

        self.ensure_module_installed("base_automation")
        domain: list[Any] = []
        if model:
            domain.append(("model_id.model", "=", model))
        rows = self.execute_kw(
            "base.automation",
            "search_read",
            [domain],
            {
                "fields": [
                    "id",
                    "name",
                    "model_id",
                    "trigger",
                    "active",
                    "filter_domain",
                    "action_server_ids",
                ],
                "limit": limit,
                "order": "id desc",
            },
        )
        result: list[AutomationInfo] = []
        for row in rows:
            model_id = row["model_id"][0] if isinstance(row["model_id"], (list, tuple)) else row["model_id"]
            model_name = (
                row["model_id"][1]
                if isinstance(row["model_id"], (list, tuple)) and len(row["model_id"]) > 1
                else ""
            )
            # Prefer technical model name
            tech = self.execute_kw("ir.model", "read", [[model_id]], {"fields": ["model"]})
            technical = tech[0]["model"] if tech else model_name
            result.append(
                AutomationInfo(
                    id=row["id"],
                    name=row["name"],
                    model=technical,
                    model_id=model_id,
                    trigger=row["trigger"],
                    active=bool(row["active"]),
                    filter_domain=row.get("filter_domain") or None,
                    action_server_ids=list(row.get("action_server_ids") or []),
                )
            )
        return result

    def create_automation(self, request: Any) -> Any:
        """Create a base.automation with a single server action (safe or confirmed advanced)."""
        from odoo_client.automation import (
            ADVANCED_SERVER_STATES,
            CreateActivityAction,
            CreateAutomationRequest,
            CreateRecordAction,
            FollowersAction,
            MailPostAction,
            RelatedWriteAction,
            RemoveFollowersAction,
            SmsAction,
            UpdateFieldAction,
            WebhookAction,
            AutomationInfo,
        )
        from odoo_client.compat.capabilities import CapabilityId

        if not isinstance(request, CreateAutomationRequest):
            request = CreateAutomationRequest.model_validate(request)

        automation = self._automation_adapter()
        self.ensure_module_installed("base_automation")
        model_id = self._model_id(request.model)

        action = request.action
        allow_advanced = False
        if isinstance(action, UpdateFieldAction):
            self.capabilities.require(CapabilityId.OBJECT_WRITE_UPDATE_PATH)
            server_vals: dict[str, Any] = automation.encode_update_field_server_vals(
                name=request.name, model_id=model_id, action=action
            )
        elif isinstance(action, RelatedWriteAction):
            self.capabilities.require(CapabilityId.RELATED_WRITE_DOTTED_PATH)
            rel_rows = self.execute_kw(
                "ir.model.fields",
                "search_read",
                [
                    [
                        ("model", "=", request.model),
                        ("name", "=", action.relation_field),
                    ]
                ],
                {"fields": ["ttype", "relation"], "limit": 1},
            )
            if (
                not rel_rows
                or rel_rows[0].get("ttype") != "many2one"
                or not rel_rows[0].get("relation")
            ):
                raise OdooClientError(
                    f"{action.relation_field!r} is not a many2one on {request.model}"
                )
            related_model = str(rel_rows[0]["relation"])
            self._field_id(related_model, action.field_name)
            server_vals = automation.encode_related_write_server_vals(
                name=request.name, model_id=model_id, action=action
            )
        elif isinstance(action, CreateActivityAction):
            try:
                if action.user_type == "specific":
                    server_vals = automation.encode_create_activity_server_vals(
                        name=request.name, model_id=model_id, action=action
                    )
                else:
                    server_vals = automation.encode_create_activity_server_vals(
                        name=request.name,
                        model_id=model_id,
                        action=action,
                        activity_user_field_name=self._resolve_activity_user_field(
                            request.model, action.user_field_name
                        ),
                    )
            except ValueError as exc:
                raise OdooClientError(str(exc)) from exc
        elif isinstance(action, CreateRecordAction):
            self.capabilities.require(CapabilityId.OBJECT_CREATE_CRUD_MODEL)
            target_model_id = self._model_id(action.target_model)
            server_vals = automation.encode_create_record_server_vals(
                name=request.name,
                model_id=model_id,
                target_model=action.target_model,
                target_model_id=target_model_id,
                field_values=dict(action.field_values),
            )
        elif isinstance(action, MailPostAction):
            template_id = action.template_id
            if not template_id:
                template_id = self.create_mail_template(
                    name=f"{request.name} template",
                    model=request.model,
                    subject=action.subject or request.name,
                    body_html=action.body_html or "<p>Automated message</p>",
                    email_to=action.email_to or "",
                )
            server_vals = automation.encode_mail_post_server_vals(
                name=request.name,
                model_id=model_id,
                template_id=int(template_id),
                mail_post_method=action.mail_post_method,
            )
        elif isinstance(action, WebhookAction):
            allow_advanced = True
            webhook_field_ids: list[int] = []
            for fname in action.webhook_field_names:
                webhook_field_ids.append(self._field_id(request.model, fname))
            server_vals = automation.encode_webhook_server_vals(
                name=request.name,
                model_id=model_id,
                action=action,
                webhook_field_ids=webhook_field_ids or None,
            )
        elif isinstance(action, SmsAction):
            allow_advanced = True
            sms_template_id = action.sms_template_id
            if not sms_template_id:
                sms_template_id = self.create_sms_template(
                    name=f"{request.name} sms",
                    model=request.model,
                    body=action.body or "",
                )
            server_vals = automation.encode_sms_server_vals(
                name=request.name,
                model_id=model_id,
                action=action,
                sms_template_id=int(sms_template_id),
            )
        elif isinstance(action, FollowersAction):
            allow_advanced = True
            server_vals = automation.encode_followers_server_vals(
                name=request.name, model_id=model_id, action=action
            )
        elif isinstance(action, RemoveFollowersAction):
            allow_advanced = True
            server_vals = automation.encode_remove_followers_server_vals(
                name=request.name, model_id=model_id, action=action
            )
        else:
            raise OdooClientError(f"Unsupported action kind: {getattr(action, 'kind', action)}")

        if str(server_vals.get("state") or "") in ADVANCED_SERVER_STATES:
            allow_advanced = True

        trigger_field_ids = (
            [self._field_id(request.model, n) for n in request.trigger_field_names]
            if request.trigger_field_names
            else None
        )
        trg_date_id = None
        if request.trigger.value == "on_time" and request.trg_date_field_name:
            trg_date_id = self._field_id(request.model, request.trg_date_field_name)
        try:
            auto_vals = automation.build_automation_record_vals(
                name=request.name,
                model_id=model_id,
                trigger=request.trigger.value,
                active=request.active,
                server_vals=server_vals,
                filter_domain=request.filter_domain,
                filter_pre_domain=request.filter_pre_domain,
                trigger_field_ids=trigger_field_ids,
                trg_date_id=trg_date_id,
                trg_date_range=request.trg_date_range,
                trg_date_range_type=request.trg_date_range_type,
                trg_date_range_mode=request.trg_date_range_mode,
                allow_advanced=allow_advanced,
            )
        except ValueError as exc:
            raise OdooClientError(str(exc)) from exc

        auto_id = self.execute_kw("base.automation", "create", [auto_vals])
        rows = self.list_automations()
        for row in rows:
            if row.id == auto_id:
                return row
        # Fallback read
        raw = self.execute_kw(
            "base.automation",
            "read",
            [[auto_id]],
            {"fields": ["id", "name", "model_id", "trigger", "active", "filter_domain", "action_server_ids"]},
        )[0]
        mid = raw["model_id"][0]
        tech = self.execute_kw("ir.model", "read", [[mid]], {"fields": ["model"]})[0]["model"]
        return AutomationInfo(
            id=raw["id"],
            name=raw["name"],
            model=tech,
            model_id=mid,
            trigger=raw["trigger"],
            active=bool(raw["active"]),
            filter_domain=raw.get("filter_domain") or None,
            action_server_ids=list(raw.get("action_server_ids") or []),
        )

    def list_activity_types(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return self.execute_kw(
            "mail.activity.type",
            "search_read",
            [[]],
            {"fields": ["id", "name"], "limit": limit, "order": "name"},
        )

    def create_code_automation(
        self,
        *,
        name: str,
        model: str,
        trigger: str,
        code: str,
        filter_domain: str | None = None,
        active: bool = True,
    ) -> Any:
        """Advanced: create live base.automation with state=code server action.

        Caller must enforce UI/API confirmation. Prefer Option A module export for default UX.
        """
        from odoo_client.automation import AutomationInfo, SAFE_TRIGGERS

        if trigger not in SAFE_TRIGGERS and trigger not in {
            "on_webhook",
            "on_message_received",
            "on_message_sent",
            "on_change",
        }:
            # Still allow advanced triggers when explicitly requested via this API.
            pass

        self.ensure_module_installed("base_automation")
        model_id = self._model_id(model)
        server_vals = {
            "name": f"{name} (code)",
            "model_id": model_id,
            "state": "code",
            "code": code,
        }
        auto_vals: dict[str, Any] = {
            "name": name,
            "model_id": model_id,
            "trigger": trigger,
            "active": active,
            "action_server_ids": [(0, 0, server_vals)],
        }
        if filter_domain:
            auto_vals["filter_domain"] = filter_domain
        auto_id = self.execute_kw("base.automation", "create", [auto_vals])
        for row in self.list_automations():
            if row.id == auto_id:
                return row
        raw = self.execute_kw(
            "base.automation",
            "read",
            [[auto_id]],
            {"fields": ["id", "name", "model_id", "trigger", "active", "filter_domain", "action_server_ids"]},
        )[0]
        mid = raw["model_id"][0]
        tech = self.execute_kw("ir.model", "read", [[mid]], {"fields": ["model"]})[0]["model"]
        return AutomationInfo(
            id=raw["id"],
            name=raw["name"],
            model=tech,
            model_id=mid,
            trigger=raw["trigger"],
            active=bool(raw["active"]),
            filter_domain=raw.get("filter_domain") or None,
            action_server_ids=list(raw.get("action_server_ids") or []),
        )

    def set_automation_active(self, automation_id: int, active: bool) -> Any:
        from odoo_client.automation import AutomationInfo

        self.ensure_module_installed("base_automation")
        self.execute_kw("base.automation", "write", [[automation_id], {"active": active}])
        return self._read_automation_info(automation_id)

    def update_automation_model(self, automation_id: int, model: str) -> Any:
        from odoo_client.automation import AutomationInfo

        self.ensure_module_installed("base_automation")
        model_id = self.execute_kw(
            "ir.model",
            "search",
            [[("model", "=", model)]],
            {"limit": 1},
        )
        if not model_id:
            raise OdooClientError(f"Model {model!r} not found")
        self.execute_kw(
            "base.automation",
            "write",
            [[automation_id], {"model_id": model_id[0]}],
        )
        return self._read_automation_info(automation_id)

    def _read_automation_info(self, automation_id: int) -> Any:
        from odoo_client.automation import AutomationInfo

        for row in self.list_automations():
            if row.id == automation_id:
                return row
        raw = self.execute_kw(
            "base.automation",
            "read",
            [[automation_id]],
            {
                "fields": [
                    "id",
                    "name",
                    "model_id",
                    "trigger",
                    "active",
                    "filter_domain",
                    "action_server_ids",
                ]
            },
        )
        if not raw:
            raise OdooClientError(f"Automation {automation_id} not found after write")
        mid = raw[0]["model_id"][0]
        tech = self.execute_kw("ir.model", "read", [[mid]], {"fields": ["model"]})[0]["model"]
        return AutomationInfo(
            id=raw[0]["id"],
            name=raw[0]["name"],
            model=tech,
            model_id=mid,
            trigger=raw[0]["trigger"],
            active=bool(raw[0]["active"]),
            filter_domain=raw[0].get("filter_domain") or None,
            action_server_ids=list(raw[0].get("action_server_ids") or []),
        )

    def delete_automation(self, automation_id: int) -> None:
        self.ensure_module_installed("base_automation")
        existing = self.execute_kw(
            "base.automation",
            "search",
            [[("id", "=", automation_id)]],
            {"limit": 1},
        )
        if not existing:
            raise OdooClientError(f"Automation {automation_id} not found")
        self.execute_kw("base.automation", "unlink", [[automation_id]])

    # --- Access rights & record rules ---

    def list_groups(self, *, limit: int = 200) -> list[Any]:
        from odoo_client.security import GroupInfo

        rows = self.execute_kw(
            "res.groups",
            "search_read",
            [[]],
            {
                "fields": ["id", "name", "full_name", "share"],
                "limit": limit,
                "order": "full_name, name, id",
            },
        )
        return [GroupInfo.model_validate(r) for r in rows]

    def _model_tech_map(self, model_ids: list[int]) -> dict[int, str]:
        if not model_ids:
            return {}
        rows = self.execute_kw(
            "ir.model",
            "read",
            [list(set(model_ids))],
            {"fields": ["id", "model"]},
        )
        return {int(r["id"]): str(r["model"]) for r in rows}

    def list_access_rights(
        self, *, model: str | None = None, limit: int = 200
    ) -> list[Any]:
        from odoo_client.security import AccessRightInfo, _coerce_m2o, _coerce_m2o_name

        domain: list[Any] = []
        if model:
            domain.append(("model_id.model", "=", model))
        rows = self.execute_kw(
            "ir.model.access",
            "search_read",
            [domain],
            {
                "fields": [
                    "id",
                    "name",
                    "model_id",
                    "group_id",
                    "perm_read",
                    "perm_write",
                    "perm_create",
                    "perm_unlink",
                    "active",
                ],
                "limit": limit,
                "order": "id desc",
            },
        )
        mids = [_coerce_m2o(r.get("model_id")) for r in rows]
        tech_map = self._model_tech_map([m for m in mids if m is not None])
        out: list[AccessRightInfo] = []
        for raw in rows:
            mid = _coerce_m2o(raw.get("model_id"))
            if mid is None:
                continue
            out.append(
                AccessRightInfo(
                    id=raw["id"],
                    name=raw["name"],
                    model=tech_map.get(mid, ""),
                    model_id=mid,
                    group_id=_coerce_m2o(raw.get("group_id")),
                    group_name=_coerce_m2o_name(raw.get("group_id")),
                    perm_read=bool(raw.get("perm_read")),
                    perm_write=bool(raw.get("perm_write")),
                    perm_create=bool(raw.get("perm_create")),
                    perm_unlink=bool(raw.get("perm_unlink")),
                    active=bool(raw.get("active", True)),
                )
            )
        return out

    def create_access_right(self, request: Any) -> Any:
        from odoo_client.security import AccessRightInfo, CreateAccessRightRequest

        req = (
            request
            if isinstance(request, CreateAccessRightRequest)
            else CreateAccessRightRequest.model_validate(request)
        )
        model_id = self._model_id(req.model)
        vals: dict[str, Any] = {
            "name": req.name,
            "model_id": model_id,
            "perm_read": req.perm_read,
            "perm_write": req.perm_write,
            "perm_create": req.perm_create,
            "perm_unlink": req.perm_unlink,
            "active": req.active,
        }
        if req.group_id is not None:
            vals["group_id"] = req.group_id
        access_id = self.execute_kw("ir.model.access", "create", [vals])
        for row in self.list_access_rights(model=req.model, limit=50):
            if row.id == access_id:
                return row
        return AccessRightInfo(
            id=int(access_id),
            name=req.name,
            model=req.model,
            model_id=model_id,
            group_id=req.group_id,
            perm_read=req.perm_read,
            perm_write=req.perm_write,
            perm_create=req.perm_create,
            perm_unlink=req.perm_unlink,
            active=req.active,
        )

    def list_record_rules(
        self, *, model: str | None = None, limit: int = 100
    ) -> list[Any]:
        from odoo_client.security import RecordRuleInfo, _coerce_m2o

        domain: list[Any] = []
        if model:
            domain.append(("model_id.model", "=", model))
        rows = self.execute_kw(
            "ir.rule",
            "search_read",
            [domain],
            {
                "fields": [
                    "id",
                    "name",
                    "model_id",
                    "domain_force",
                    "groups",
                    "perm_read",
                    "perm_write",
                    "perm_create",
                    "perm_unlink",
                    "active",
                    "global",
                ],
                "limit": limit,
                "order": "id desc",
            },
        )
        mids = [_coerce_m2o(r.get("model_id")) for r in rows]
        tech_map = self._model_tech_map([m for m in mids if m is not None])
        out: list[RecordRuleInfo] = []
        for raw in rows:
            mid = _coerce_m2o(raw.get("model_id"))
            if mid is None:
                continue
            domain_force = raw.get("domain_force")
            if domain_force is False:
                domain_force = None
            out.append(
                RecordRuleInfo.model_validate(
                    {
                        "id": raw["id"],
                        "name": raw.get("name") or f"rule-{raw['id']}",
                        "model": tech_map.get(mid, ""),
                        "model_id": mid,
                        "domain_force": domain_force,
                        "group_ids": list(raw.get("groups") or []),
                        "perm_read": bool(raw.get("perm_read")),
                        "perm_write": bool(raw.get("perm_write")),
                        "perm_create": bool(raw.get("perm_create")),
                        "perm_unlink": bool(raw.get("perm_unlink")),
                        "active": bool(raw.get("active", True)),
                        "global": bool(raw.get("global")),
                    }
                )
            )
        return out

    def create_record_rule(self, request: Any) -> Any:
        from odoo_client.security import CreateRecordRuleRequest, RecordRuleInfo

        req = (
            request
            if isinstance(request, CreateRecordRuleRequest)
            else CreateRecordRuleRequest.model_validate(request)
        )
        model_id = self._model_id(req.model)
        vals: dict[str, Any] = {
            "name": req.name,
            "model_id": model_id,
            "domain_force": req.domain_force,
            "perm_read": req.perm_read,
            "perm_write": req.perm_write,
            "perm_create": req.perm_create,
            "perm_unlink": req.perm_unlink,
            "active": req.active,
        }
        if req.group_ids:
            vals["groups"] = [(6, 0, req.group_ids)]
        rule_id = self.execute_kw("ir.rule", "create", [vals])
        for row in self.list_record_rules(model=req.model, limit=50):
            if row.id == rule_id:
                return row
        return RecordRuleInfo.model_validate(
            {
                "id": int(rule_id),
                "name": req.name,
                "model": req.model,
                "model_id": model_id,
                "domain_force": req.domain_force,
                "group_ids": list(req.group_ids),
                "perm_read": req.perm_read,
                "perm_write": req.perm_write,
                "perm_create": req.perm_create,
                "perm_unlink": req.perm_unlink,
                "active": req.active,
                "global": not bool(req.group_ids),
            }
        )

    def get_access_right(self, access_id: int) -> Any:
        rows = self.list_access_rights(limit=500)
        for row in rows:
            if row.id == access_id:
                return row
        # Fallback: direct read when not in first page of list
        from odoo_client.security import AccessRightInfo, _coerce_m2o, _coerce_m2o_name

        raw_rows = self.execute_kw(
            "ir.model.access",
            "read",
            [[access_id]],
            {
                "fields": [
                    "id",
                    "name",
                    "model_id",
                    "group_id",
                    "perm_read",
                    "perm_write",
                    "perm_create",
                    "perm_unlink",
                    "active",
                ]
            },
        )
        if not raw_rows:
            raise OdooClientError(f"Access right {access_id} not found")
        raw = raw_rows[0]
        mid = _coerce_m2o(raw.get("model_id"))
        if mid is None:
            raise OdooClientError(f"Access right {access_id} has no model_id")
        tech = self._model_tech_map([mid]).get(mid, "")
        return AccessRightInfo(
            id=raw["id"],
            name=raw["name"],
            model=tech,
            model_id=mid,
            group_id=_coerce_m2o(raw.get("group_id")),
            group_name=_coerce_m2o_name(raw.get("group_id")),
            perm_read=bool(raw.get("perm_read")),
            perm_write=bool(raw.get("perm_write")),
            perm_create=bool(raw.get("perm_create")),
            perm_unlink=bool(raw.get("perm_unlink")),
            active=bool(raw.get("active", True)),
        )

    def update_access(self, access_id: int, request: Any) -> Any:
        from odoo_client.security import UpdateAccessRightRequest

        req = (
            request
            if isinstance(request, UpdateAccessRightRequest)
            else UpdateAccessRightRequest.model_validate(request)
        )
        vals: dict[str, Any] = {}
        if req.name is not None:
            vals["name"] = req.name
        if req.clear_group:
            vals["group_id"] = False
        elif req.group_id is not None:
            vals["group_id"] = req.group_id
        for key in ("perm_read", "perm_write", "perm_create", "perm_unlink", "active"):
            value = getattr(req, key)
            if value is not None:
                vals[key] = bool(value)
        if not vals:
            raise OdooClientError("update_access requires at least one attribute")
        self.execute_kw("ir.model.access", "write", [[access_id], vals])
        return self.get_access_right(access_id)

    def delete_access(self, access_id: int) -> None:
        existing = self.execute_kw(
            "ir.model.access", "search", [[("id", "=", access_id)]], {"limit": 1}
        )
        if not existing:
            raise OdooClientError(f"Access right {access_id} not found")
        self.execute_kw("ir.model.access", "unlink", [[access_id]])

    def get_record_rule(self, rule_id: int) -> Any:
        from odoo_client.security import RecordRuleInfo, _coerce_m2o

        raw_rows = self.execute_kw(
            "ir.rule",
            "read",
            [[rule_id]],
            {
                "fields": [
                    "id",
                    "name",
                    "model_id",
                    "domain_force",
                    "groups",
                    "perm_read",
                    "perm_write",
                    "perm_create",
                    "perm_unlink",
                    "active",
                    "global",
                ]
            },
        )
        if not raw_rows:
            raise OdooClientError(f"Record rule {rule_id} not found")
        raw = raw_rows[0]
        mid = _coerce_m2o(raw.get("model_id"))
        if mid is None:
            raise OdooClientError(f"Record rule {rule_id} has no model_id")
        domain_force = raw.get("domain_force")
        if domain_force is False:
            domain_force = None
        return RecordRuleInfo.model_validate(
            {
                "id": raw["id"],
                "name": raw.get("name") or f"rule-{raw['id']}",
                "model": self._model_tech_map([mid]).get(mid, ""),
                "model_id": mid,
                "domain_force": domain_force,
                "group_ids": list(raw.get("groups") or []),
                "perm_read": bool(raw.get("perm_read")),
                "perm_write": bool(raw.get("perm_write")),
                "perm_create": bool(raw.get("perm_create")),
                "perm_unlink": bool(raw.get("perm_unlink")),
                "active": bool(raw.get("active", True)),
                "global": bool(raw.get("global")),
            }
        )

    def update_rule(self, rule_id: int, request: Any) -> Any:
        from odoo_client.security import UpdateRecordRuleRequest

        req = (
            request
            if isinstance(request, UpdateRecordRuleRequest)
            else UpdateRecordRuleRequest.model_validate(request)
        )
        vals: dict[str, Any] = {}
        if req.name is not None:
            vals["name"] = req.name
        if req.domain_force is not None:
            vals["domain_force"] = req.domain_force
        if req.group_ids is not None:
            vals["groups"] = [(6, 0, req.group_ids)]
        for key in ("perm_read", "perm_write", "perm_create", "perm_unlink", "active"):
            value = getattr(req, key)
            if value is not None:
                vals[key] = bool(value)
        if not vals:
            raise OdooClientError("update_rule requires at least one attribute")
        self.execute_kw("ir.rule", "write", [[rule_id], vals])
        return self.get_record_rule(rule_id)

    def delete_rule(self, rule_id: int) -> None:
        existing = self.execute_kw(
            "ir.rule", "search", [[("id", "=", rule_id)]], {"limit": 1}
        )
        if not existing:
            raise OdooClientError(f"Record rule {rule_id} not found")
        self.execute_kw("ir.rule", "unlink", [[rule_id]])

    def create_window_action(
        self,
        *,
        name: str,
        model: str,
        view_mode: str = "list,form",
        domain: str | None = None,
        context: str | None = None,
    ) -> int:
        """Create ir.actions.act_window for a model. Returns action id.

        ``view_mode`` is normalized via the major's views adapter (``list``→``tree``
        on Odoo ≤17).
        """
        views_v = self._views_adapter()
        normalized = views_v.normalize_view_mode(view_mode)
        vals: dict[str, Any] = {
            "name": name,
            "res_model": model,
            "view_mode": normalized,
            "type": "ir.actions.act_window",
        }
        if domain:
            vals["domain"] = domain
        if context:
            vals["context"] = context
        return int(self.execute_kw("ir.actions.act_window", "create", [vals]))

    def list_server_actions(
        self, model: str | None = None, *, limit: int = 80
    ) -> list[Any]:
        """List ir.actions.server for a model (or all custom-ish recent)."""
        from odoo_client.actions import ServerActionInfo

        domain: list[Any] = [("usage", "=", "ir_actions_server")]
        if model:
            domain.append(("model_id.model", "=", model))
        rows = self.execute_kw(
            "ir.actions.server",
            "search_read",
            [domain],
            {
                "fields": [
                    "name",
                    "state",
                    "model_id",
                    "binding_model_id",
                    "binding_type",
                ],
                "limit": limit,
                "order": "id desc",
            },
        )
        out: list[ServerActionInfo] = []
        for row in rows:
            mid = row.get("model_id")
            model_id = int(mid[0]) if isinstance(mid, (list, tuple)) else int(mid or 0)
            model_name = mid[1] if isinstance(mid, (list, tuple)) and len(mid) > 1 else ""
            # Prefer technical name when we filtered by model
            tech = model or self._model_technical_name(model_id) or str(model_name)
            bind = row.get("binding_model_id")
            out.append(
                ServerActionInfo(
                    id=int(row["id"]),
                    name=row["name"],
                    model=tech if isinstance(tech, str) else str(tech),
                    model_id=model_id,
                    state=str(row.get("state") or ""),
                    binding_model_id=(
                        int(bind[0]) if isinstance(bind, (list, tuple)) else None
                    ),
                    binding_type=row.get("binding_type") or None,
                )
            )
        return out

    def _model_technical_name(self, model_id: int) -> str | None:
        if not model_id:
            return None
        rows = self.execute_kw(
            "ir.model",
            "read",
            [[model_id], ["model"]],
        )
        return rows[0]["model"] if rows else None

    def create_update_field_server_action(self, request: Any) -> Any:
        """Create safe object_write server action for form button binding."""
        from odoo_client.actions import (
            CreateUpdateFieldServerAction,
            ServerActionInfo,
            assert_safe_server_state,
        )
        from odoo_client.compat.capabilities import CapabilityId

        if not isinstance(request, CreateUpdateFieldServerAction):
            request = CreateUpdateFieldServerAction.model_validate(request)
        assert_safe_server_state("object_write")
        self.capabilities.require(CapabilityId.OBJECT_WRITE_UPDATE_PATH)
        model_id = self._model_id(request.model)
        # Ensure field exists
        self._field_id(request.model, request.field_name)
        vals = self._automation_adapter().encode_object_write_button_vals(
            name=request.name,
            model_id=model_id,
            field_name=request.field_name,
            value=request.value,
            bind_to_model=request.bind_to_model,
        )
        action_id = int(self.execute_kw("ir.actions.server", "create", [vals]))
        return ServerActionInfo(
            id=action_id,
            name=request.name,
            model=request.model,
            model_id=model_id,
            state="object_write",
            binding_model_id=model_id if request.bind_to_model else None,
            binding_type="action" if request.bind_to_model else None,
        )

    def _bind_server_action_vals(self, model_id: int, bind: bool) -> dict[str, Any]:
        if not bind:
            return {}
        return {
            "binding_model_id": model_id,
            "binding_type": "action",
            "binding_view_types": "form,list",
        }

    def _model_has_field(self, model: str, field_name: str) -> bool:
        try:
            self._field_id(model, field_name)
            return True
        except OdooClientError:
            return False

    def ensure_mail_mixins(self, model: str) -> dict[str, bool]:
        """Best-effort enable is_mail_thread / is_mail_activity on ir.model."""
        model_id = self._model_id(model)
        rows = self.execute_kw(
            "ir.model",
            "read",
            [[model_id]],
            {"fields": ["is_mail_thread", "is_mail_activity"]},
        )
        current = rows[0] if rows else {}
        write_vals: dict[str, Any] = {}
        fg = self.execute_kw("ir.model", "fields_get", [], {"attributes": ["type"]})
        if "is_mail_thread" in fg and not current.get("is_mail_thread"):
            write_vals["is_mail_thread"] = True
        if "is_mail_activity" in fg and not current.get("is_mail_activity"):
            write_vals["is_mail_activity"] = True
        if write_vals:
            self.execute_kw("ir.model", "write", [[model_id], write_vals])
        return {
            "is_mail_thread": bool(write_vals.get("is_mail_thread") or current.get("is_mail_thread")),
            "is_mail_activity": bool(
                write_vals.get("is_mail_activity") or current.get("is_mail_activity")
            ),
        }

    def _resolve_activity_user_field(self, model: str, preferred: str | None) -> str:
        """Pick a res.users-like field for next_activity generic assignee.

        Custom ``x_`` models often lack ``user_id``; ``create_uid`` always exists.
        """
        candidates = [preferred or "user_id", "user_id", "create_uid", "write_uid"]
        seen: set[str] = set()
        for name in candidates:
            if not name or name in seen:
                continue
            seen.add(name)
            if self._model_has_field(model, name):
                return name
        raise OdooClientError(
            f"Model {model!r} has no suitable user field for next_activity "
            "(tried user_id, create_uid, write_uid). Pass user_type=specific with user_id."
        )

    def create_next_activity_server_action(self, request: Any) -> Any:
        from odoo_client.actions import (
            CreateNextActivityServerAction,
            ServerActionInfo,
            assert_safe_server_state,
        )

        if not isinstance(request, CreateNextActivityServerAction):
            request = CreateNextActivityServerAction.model_validate(request)
        assert_safe_server_state("next_activity")
        self.ensure_module_installed("mail")
        self.ensure_mail_mixins(request.model)
        if not self._model_has_field(request.model, "activity_ids"):
            raise OdooClientError(
                f"Model {request.model!r} has no activities (activity_ids). "
                "Enable mail.activity mixin (ir.model is_mail_activity) or use Option A "
                "with mixins=['mail.thread','mail.activity.mixin']."
            )
        model_id = self._model_id(request.model)
        vals: dict[str, Any] = {
            "name": request.name,
            "model_id": model_id,
            "state": "next_activity",
            "activity_type_id": request.activity_type_id,
            "activity_summary": request.summary,
            "activity_user_type": request.user_type,
            "usage": "ir_actions_server",
            **self._bind_server_action_vals(model_id, request.bind_to_model),
        }
        if request.note:
            vals["activity_note"] = request.note
        if request.user_type == "specific":
            if not request.user_id:
                raise OdooClientError("user_type=specific requires user_id")
            vals["activity_user_id"] = request.user_id
        else:
            vals["activity_user_field_name"] = self._resolve_activity_user_field(
                request.model, request.user_field_name
            )
        action_id = int(self.execute_kw("ir.actions.server", "create", [vals]))
        return ServerActionInfo(
            id=action_id,
            name=request.name,
            model=request.model,
            model_id=model_id,
            state="next_activity",
            binding_model_id=model_id if request.bind_to_model else None,
            binding_type="action" if request.bind_to_model else None,
        )

    def create_mail_post_server_action(self, request: Any) -> Any:
        from odoo_client.actions import (
            CreateMailPostServerAction,
            ServerActionInfo,
            assert_safe_server_state,
        )

        if not isinstance(request, CreateMailPostServerAction):
            request = CreateMailPostServerAction.model_validate(request)
        assert_safe_server_state("mail_post")
        self.ensure_module_installed("mail")
        self.ensure_mail_mixins(request.model)
        model_id = self._model_id(request.model)
        template_id = request.template_id
        if not template_id:
            template_id = self.create_mail_template(
                name=f"{request.name} template",
                model=request.model,
                subject=request.subject or request.name,
                body_html=request.body_html or f"<p>{request.name}</p>",
                email_to=request.email_to or "",
            )
        vals: dict[str, Any] = {
            "name": request.name,
            "model_id": model_id,
            "state": "mail_post",
            "template_id": template_id,
            "mail_post_method": request.mail_post_method,
            "usage": "ir_actions_server",
            **self._bind_server_action_vals(model_id, request.bind_to_model),
        }
        action_id = int(self.execute_kw("ir.actions.server", "create", [vals]))
        return ServerActionInfo(
            id=action_id,
            name=request.name,
            model=request.model,
            model_id=model_id,
            state="mail_post",
            binding_model_id=model_id if request.bind_to_model else None,
            binding_type="action" if request.bind_to_model else None,
        )

    def run_server_action(
        self,
        action_id: int,
        *,
        model: str,
        record_id: int,
    ) -> Any:
        """Execute ir.actions.server.run for one record (form-button equivalent)."""
        return self.execute_kw(
            "ir.actions.server",
            "run",
            [[action_id]],
            {
                "context": {
                    "active_id": record_id,
                    "active_ids": [record_id],
                    "active_model": model,
                }
            },
        )

    def create_related_count_field(self, request: Any) -> FieldInfo:
        """Create non-stored computed integer = len(one2many_field)."""
        from odoo_client.actions import CreateRelatedCountField

        if not isinstance(request, CreateRelatedCountField):
            request = CreateRelatedCountField.model_validate(request)
        self._field_id(request.model, request.one2many_field)
        if self.field_exists(request.model, request.name):
            # Return existing
            fid = self._field_id(request.model, request.name)
            rows = self.execute_kw(
                "ir.model.fields",
                "read",
                [[fid]],
                {
                    "fields": [
                        "id",
                        "name",
                        "field_description",
                        "ttype",
                        "model_id",
                        "required",
                        "readonly",
                        "relation",
                        "state",
                    ]
                },
            )
            row = rows[0]
            mid = row["model_id"]
            return FieldInfo(
                id=int(row["id"]),
                name=row["name"],
                field_description=row["field_description"],
                ttype=row["ttype"],
                model_id=int(mid[0]) if isinstance(mid, (list, tuple)) else int(mid),
                required=bool(row.get("required")),
                readonly=bool(row.get("readonly")),
                relation=row.get("relation") or None,
                state=row.get("state"),
            )

        model_id = self._model_id(request.model)
        compute = (
            f"for rec in self:\n"
            f"    rec[{request.name!r}] = len(rec.{request.one2many_field})"
        )
        field_id = int(
            self.execute_kw(
                "ir.model.fields",
                "create",
                [
                    {
                        "name": request.name,
                        "field_description": request.field_description,
                        "model_id": model_id,
                        "ttype": "integer",
                        "state": "manual",
                        "store": False,
                        "readonly": True,
                        "compute": compute,
                        "depends": request.one2many_field,
                    }
                ],
            )
        )
        return FieldInfo(
            id=field_id,
            name=request.name,
            field_description=request.field_description,
            ttype="integer",
            model_id=model_id,
            required=False,
            readonly=True,
            relation=None,
            state="manual",
        )

    def create_smart_button_bundle(self, request: Any) -> Any:
        from odoo_client.actions import (
            CreateRelatedCountField,
            CreateRelatedWindowAction,
            CreateSmartButtonBundle,
            SmartButtonBundle,
        )

        if not isinstance(request, CreateSmartButtonBundle):
            request = CreateSmartButtonBundle.model_validate(request)
        window = self.create_related_window_action(
            CreateRelatedWindowAction(
                name=request.name,
                source_model=request.source_model,
                target_model=request.target_model,
                relation_field=request.relation_field,
                view_mode=request.view_mode,
            )
        )
        count_name: str | None = None
        count_id: int | None = None
        if request.create_count_field:
            o2m = request.one2many_field
            if not o2m:
                raise OdooClientError(
                    "create_count_field requires one2many_field on the source model"
                )
            count_name = request.count_field_name or f"x_{request.target_model.split('.')[-1]}_count".replace(
                "x_x_", "x_"
            )
            if not count_name.startswith("x_"):
                count_name = f"x_{count_name}"
            # sanitize: library style x_loan_count from target x_lib_loan
            if request.count_field_name:
                count_name = request.count_field_name
            else:
                stem = request.target_model.replace("x_", "").replace(".", "_")
                count_name = f"x_{stem}_count"
            field = self.create_related_count_field(
                CreateRelatedCountField(
                    model=request.source_model,
                    name=count_name,
                    field_description=request.name,
                    one2many_field=o2m,
                )
            )
            count_name = field.name
            count_id = field.id
        button_spec = {
            "kind": "button",
            "string": request.name,
            "name": str(window.id),
            "type": "action",
            "class": "oe_stat_button",
            "icon": request.icon,
            "count_field": count_name,
        }
        return SmartButtonBundle(
            window_action=window,
            count_field=count_name,
            count_field_id=count_id,
            button_spec=button_spec,
        )

    def list_window_actions(
        self, model: str | None = None, *, limit: int = 80
    ) -> list[Any]:
        from odoo_client.actions import WindowActionInfo

        domain: list[Any] = []
        if model:
            domain.append(("res_model", "=", model))
        rows = self.execute_kw(
            "ir.actions.act_window",
            "search_read",
            [domain],
            {
                "fields": ["name", "res_model", "view_mode", "domain", "context"],
                "limit": limit,
                "order": "id desc",
            },
        )
        return [
            WindowActionInfo(
                id=int(row["id"]),
                name=row["name"],
                res_model=str(row.get("res_model") or ""),
                view_mode=str(row.get("view_mode") or "list,form"),
                domain=row.get("domain") or None,
                context=row.get("context") or None,
            )
            for row in rows
        ]

    def create_related_window_action(self, request: Any) -> Any:
        """Create act_window filtered to related records of the active form record."""
        from odoo_client.actions import CreateRelatedWindowAction, WindowActionInfo

        if not isinstance(request, CreateRelatedWindowAction):
            request = CreateRelatedWindowAction.model_validate(request)
        # Validate relation field exists on target
        self._field_id(request.target_model, request.relation_field)
        domain = f"[('{request.relation_field}','=',active_id)]"
        # Intentionally uses active_id — only valid when opened from a parent form
        # (smart button / related). Open-in-Odoo must pick a standalone act_window
        # instead (see pickStandaloneWindowAction / standalone_only=true).
        context = (
            f"{{'default_{request.relation_field}': active_id, "
            f"'search_default_{request.relation_field}': active_id}}"
        )
        action_id = self.create_window_action(
            name=request.name,
            model=request.target_model,
            view_mode=request.view_mode,
            domain=domain,
            context=context,
        )
        return WindowActionInfo(
            id=action_id,
            name=request.name,
            res_model=request.target_model,
            view_mode=request.view_mode,
            domain=domain,
            context=context,
        )

    def list_bindable_actions(self, model: str, *, limit: int = 80) -> list[Any]:
        """Actions a Designer button on ``model`` can bind to."""
        from odoo_client.actions import BindableActionInfo

        out: list[BindableActionInfo] = []
        for sa in self.list_server_actions(model, limit=limit):
            out.append(
                BindableActionInfo(
                    id=sa.id,
                    name=sa.name,
                    action_type="ir.actions.server",
                    model=sa.model,
                    detail=sa.state,
                )
            )
        # Prefer related windows (domain uses active_id) and same-model windows
        for wa in self.list_window_actions(None, limit=max(limit, 120)):
            domain = wa.domain or ""
            related = "active_id" in domain
            same = wa.res_model == model
            if not (related or same):
                continue
            out.append(
                BindableActionInfo(
                    id=wa.id,
                    name=wa.name,
                    action_type="ir.actions.act_window",
                    model=wa.res_model,
                    detail=domain or wa.view_mode,
                )
            )
            if len(out) >= limit * 2:
                break
        return out

    def create_menu(
        self,
        *,
        name: str,
        parent_id: int | None = None,
        action_id: int | None = None,
        sequence: int = 10,
        web_icon: str | None = None,
    ) -> int:
        """Create ir.ui.menu. action_id is an ir.actions.act_window id.

        Root menus need ``web_icon`` (e.g. ``base,static/description/icon.png``)
        or Odoo 19's home / app switcher will not show them as apps.
        """
        vals: dict[str, Any] = {"name": name, "sequence": sequence}
        if parent_id is not None:
            vals["parent_id"] = parent_id
        if action_id is not None:
            vals["action"] = f"ir.actions.act_window,{action_id}"
        if web_icon:
            vals["web_icon"] = web_icon
        return int(self.execute_kw("ir.ui.menu", "create", [vals]))

    def ensure_app_menus(
        self,
        *,
        root_name: str,
        model_entries: list[tuple[str, str]],
        web_icon: str = "base,static/description/icon.png",
    ) -> list[int]:
        """Create root menu + child menus/actions for (model, label) pairs.

        Idempotent by name under the same root when a root with root_name already exists.
        Ensures the root has a ``web_icon`` so it appears on the Odoo home grid.
        Returns created/found menu ids (root first).
        """
        existing_roots = self.execute_kw(
            "ir.ui.menu",
            "search",
            [[("name", "=", root_name), ("parent_id", "=", False)]],
            {"limit": 1},
        )
        if existing_roots:
            root_id = int(existing_roots[0])
            root_rows = self.execute_kw(
                "ir.ui.menu",
                "read",
                [[root_id]],
                {"fields": ["web_icon", "action"]},
            )
            if root_rows and not root_rows[0].get("web_icon"):
                self.execute_kw(
                    "ir.ui.menu",
                    "write",
                    [[root_id], {"web_icon": web_icon}],
                )
        else:
            root_id = self.create_menu(
                name=root_name, sequence=10, web_icon=web_icon
            )
        menu_ids = [root_id]
        first_action_id: int | None = None
        for seq, (model, label) in enumerate(model_entries, start=10):
            child = self.execute_kw(
                "ir.ui.menu",
                "search",
                [[("name", "=", label), ("parent_id", "=", root_id)]],
                {"limit": 1},
            )
            if child:
                menu_ids.append(int(child[0]))
                if first_action_id is None:
                    child_rows = self.execute_kw(
                        "ir.ui.menu",
                        "read",
                        [[int(child[0])]],
                        {"fields": ["action"]},
                    )
                    action_ref = (child_rows[0].get("action") or "") if child_rows else ""
                    if isinstance(action_ref, str) and "," in action_ref:
                        try:
                            first_action_id = int(action_ref.split(",", 1)[1])
                        except ValueError:
                            first_action_id = None
                continue
            action_id = self.create_window_action(name=label, model=model)
            if first_action_id is None:
                first_action_id = action_id
            mid = self.create_menu(
                name=label,
                parent_id=root_id,
                action_id=action_id,
                sequence=seq,
            )
            menu_ids.append(mid)
        # Odoo webclient selectMenu() no-ops when the app root has no actionID.
        if first_action_id is not None:
            root_rows = self.execute_kw(
                "ir.ui.menu",
                "read",
                [[root_id]],
                {"fields": ["action"]},
            )
            if root_rows and not root_rows[0].get("action"):
                self.execute_kw(
                    "ir.ui.menu",
                    "write",
                    [[root_id], {"action": f"ir.actions.act_window,{first_action_id}"}],
                )
        return menu_ids

    def list_mail_templates(
        self, *, model: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        domain: list[Any] = []
        if model:
            domain.append(("model", "=", model))
        try:
            return self.execute_kw(
                "mail.template",
                "search_read",
                [domain],
                {
                    "fields": [
                        "id",
                        "name",
                        "model",
                        "subject",
                        "body_html",
                        "email_to",
                        "description",
                    ],
                    "limit": limit,
                    "order": "id desc",
                },
            )
        except Exception as exc:  # noqa: BLE001
            raise OdooClientError(f"list_mail_templates failed: {exc}") from exc

    def list_crons(
        self, *, model: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        domain: list[Any] = []
        if model:
            domain.append(("model_id.model", "=", model))
        return self.execute_kw(
            "ir.cron",
            "search_read",
            [domain],
            {
                "fields": [
                    "id",
                    "name",
                    "cron_name",
                    "model_id",
                    "state",
                    "code",
                    "interval_number",
                    "interval_type",
                    "active",
                ],
                "limit": limit,
                "order": "id desc",
            },
        )

    def create_mail_template(
        self,
        *,
        name: str,
        model: str,
        subject: str,
        body_html: str,
        email_to: str,
        description: str | None = None,
    ) -> int:
        model_id = self._model_id(model)
        vals: dict[str, Any] = {
            "name": name,
            "model_id": model_id,
            "subject": subject,
            "body_html": body_html,
            "email_to": email_to,
        }
        if description:
            vals["description"] = description
        return int(self.execute_kw("mail.template", "create", [vals]))

    def create_sms_template(
        self,
        *,
        name: str,
        model: str,
        body: str,
    ) -> int:
        """Create sms.template for advanced SMS automations (requires sms module)."""
        if not self.model_exists("sms.template"):
            raise OdooClientError(
                "sms.template is not available — install the sms module before "
                "creating SMS automations with a freeform body"
            )
        model_id = self._model_id(model)
        return int(
            self.execute_kw(
                "sms.template",
                "create",
                [
                    {
                        "name": name,
                        "model_id": model_id,
                        "body": body,
                    }
                ],
            )
        )

    def create_cron(
        self,
        *,
        name: str,
        model: str,
        code: str,
        interval_number: int = 1,
        interval_type: str = "days",
        active: bool = True,
    ) -> int:
        """Create ir.cron (Odoo 19: inherits ir.actions.server; no numbercall)."""
        model_id = self._model_id(model)
        vals = {
            "name": name,
            "model_id": model_id,
            "state": "code",
            "code": code,
            "interval_number": interval_number,
            "interval_type": interval_type,
            "active": active,
        }
        return int(self.execute_kw("ir.cron", "create", [vals]))
