"""Apply ModuleSpec-like JSON to live Odoo: models, fields, views, menus, smart buttons."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from odoo_client import CreateFieldRequest, FieldType, OdooClient
from odoo_client.actions import CreateSmartButtonBundle, CreateUpdateFieldServerAction
from odoo_client.compat.capabilities import CapabilityId
from odoo_client.blueprint import auto_form_layout_for_model
from odoo_client.models import CreateViewRequest
from odoo_client.view_arch import (
    ButtonNode,
    FieldNode,
    FormViewSpec,
    GroupNode,
    render_form_arch,
)

from app.project_apply import ApplyResult, apply_project_spec
from app.ai_live_apply_contract import (
    MAIL_TODO_XML_ID,
    infer_trg_date_field,
    normalize_automation_trigger as _normalize_automation_trigger,
)


@dataclass
class UiApplyResult(ApplyResult):
    views_created: int = 0
    views_updated: int = 0
    menus_created: int = 0
    smart_buttons: int = 0
    automations_noted: int = 0
    automations_created: int = 0
    access_rights_created: int = 0
    record_rules_created: int = 0
    sequences_created: int = 0
    root_menu_id: int | None = None
    open_action_id: int | None = None
    open_model: str | None = None
    workflow_buttons_bound: int = 0
    automations_scrubbed: int = 0
    fields_relaxed: int = 0


def _selection_keys(selection: Any) -> list[str]:
    if not isinstance(selection, str):
        return []
    import re

    return re.findall(r"\('([^']+)'\s*,", selection)


def _apply_explicit_views(client: OdooClient, spec: dict[str, Any], result: UiApplyResult) -> None:
    views = spec.get("views") or []
    if not isinstance(views, list):
        return
    for view in views:
        if not isinstance(view, dict):
            continue
        model = view.get("model")
        vtype = view.get("type")
        arch = view.get("arch")
        name = view.get("name") or f"{model}.{vtype}"
        if not model or not vtype or not isinstance(arch, str) or not arch.strip():
            continue
        # Never overwrite stock module primary arches (Contacts phone xpath, etc.).
        if not str(model).startswith("x_"):
            result.warnings.append(
                f"Skip view {name}: refusing to rewrite stock model {model} "
                "(use Designer inherit / smart-button inject)"
            )
            continue
        if not client.model_exists(str(model)):
            result.warnings.append(f"Skip view {name}: model {model} missing")
            continue
        try:
            existing = client.find_view(str(model), str(vtype), primary_only=True)
            if existing is None:
                existing = client.find_view(str(model), str(vtype))
            if existing is None:
                client.create_view(
                    CreateViewRequest(
                        name=str(name),
                        model=str(model),
                        type=str(vtype),  # type: ignore[arg-type]
                        arch=arch,
                    )
                )
                result.views_created += 1
            else:
                client.update_view_arch(existing.id, arch)
                result.views_updated += 1
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"View {name} failed: {exc}")


_TRANSITION_DEST_RE = re.compile(
    r"""data-transition-to\s*=\s*['"]([^'"]+)['"]""", re.I
)
_BUTTON_TAG_RE = re.compile(r"<button\b[^>]*?/?>", re.I)
_TYPE_ATTR_RE = re.compile(r"""\btype\s*=\s*['"][^'"]*['"]""", re.I)
_NAME_ATTR_RE = re.compile(r"""\bname\s*=\s*['"][^'"]*['"]""", re.I)


def rewrite_transition_buttons_to_actions(
    arch: str, dest_to_action_id: dict[str, int]
) -> str:
    """Turn draft ``type=object`` + ``data-transition-to`` into live ``type=action``."""

    def repl(match: re.Match[str]) -> str:
        tag = match.group(0)
        dest_m = _TRANSITION_DEST_RE.search(tag)
        if not dest_m:
            return tag
        dest = dest_m.group(1)
        action_id = dest_to_action_id.get(dest)
        if not action_id:
            return tag
        tag = _TRANSITION_DEST_RE.sub("", tag)
        tag = re.sub(
            r"""\s*data-approval-role\s*=\s*['"][^'"]*['"]""",
            "",
            tag,
            flags=re.I,
        )
        if _TYPE_ATTR_RE.search(tag):
            tag = _TYPE_ATTR_RE.sub('type="action"', tag, count=1)
        else:
            tag = tag.replace("<button", '<button type="action"', 1)
        if _NAME_ATTR_RE.search(tag):
            tag = _NAME_ATTR_RE.sub(f'name="{int(action_id)}"', tag, count=1)
        else:
            tag = tag.replace("<button", f'<button name="{int(action_id)}"', 1)
        tag = re.sub(r"[ \t]{2,}", " ", tag)
        return tag.replace(" >", ">").replace(" />", "/>")

    return _BUTTON_TAG_RE.sub(repl, arch)


def _action_group_m2m_field(client: OdooClient) -> str | None:
    if client.field_exists("ir.actions.server", "group_ids"):
        return "group_ids"
    if client.field_exists("ir.actions.server", "groups_id"):
        return "groups_id"
    return None


def _manager_group_ids_for_spec(client: OdooClient, spec: dict[str, Any]) -> list[int]:
    flow = spec.get("_approval_flow") if isinstance(spec.get("_approval_flow"), dict) else {}
    refs: list[str] = []
    if flow.get("manager_group"):
        refs.append(str(flow["manager_group"]))
    for g in spec.get("groups") or []:
        if not isinstance(g, dict):
            continue
        gid = str(g.get("id") or "")
        if "manager" in gid.lower() or "manager" in str(g.get("name") or "").lower():
            refs.append(gid)
    out: list[int] = []
    seen: set[int] = set()
    for ref in refs:
        rid = _resolve_or_create_group_id(client, spec, ref)
        if rid is not None and rid not in seen:
            seen.add(rid)
            out.append(rid)
    return out


def _restrict_server_action_groups(
    client: OdooClient, action_id: int, group_ids: list[int]
) -> None:
    field = _action_group_m2m_field(client)
    if not field or not group_ids:
        return
    client.execute_kw(
        "ir.actions.server",
        "write",
        [[int(action_id)], {field: [(6, 0, group_ids)]}],
    )


def _approval_manager_dests(spec: dict[str, Any], arch: str) -> set[str]:
    flow = spec.get("_approval_flow")
    if isinstance(flow, dict) and flow.get("manager_dests"):
        return {str(x) for x in flow["manager_dests"]}
    dests: set[str] = set()
    for tag in _BUTTON_TAG_RE.findall(arch or ""):
        if not re.search(r"""data-approval-role\s*=\s*['"]manager['"]""", tag, re.I):
            continue
        dest_m = _TRANSITION_DEST_RE.search(tag)
        if dest_m:
            dests.add(dest_m.group(1))
    return dests


def _object_write_supported(client: Any) -> bool:
    caps = getattr(client, "capabilities", None)
    if caps is None:
        return True
    supports = getattr(caps, "supports", None)
    if not callable(supports):
        return True
    return bool(supports(CapabilityId.OBJECT_WRITE_UPDATE_PATH))


def _state_field_name(spec: dict[str, Any], model: str) -> str:
    for row in spec.get("models") or []:
        if not isinstance(row, dict) or str(row.get("model") or "") != model:
            continue
        sf = row.get("state_field")
        if isinstance(sf, dict) and sf.get("field"):
            return str(sf["field"])
    return "x_status"


def _transition_dests_for_model(spec: dict[str, Any], model: str, arch: str) -> list[str]:
    dests: list[str] = []
    for row in spec.get("models") or []:
        if not isinstance(row, dict) or str(row.get("model") or "") != model:
            continue
        sf = row.get("state_field")
        if not isinstance(sf, dict):
            break
        for tr in sf.get("transitions") or []:
            if isinstance(tr, (list, tuple)) and len(tr) >= 2:
                dests.append(str(tr[1]))
        break
    dests.extend(_TRANSITION_DEST_RE.findall(arch or ""))
    return list(dict.fromkeys(dests))


def _ensure_status_write_action(
    client: Any, *, model: str, field: str, value: str
) -> int:
    name = f"{model}: set {field} = {value}"
    existing = client.execute_kw(
        "ir.actions.server",
        "search",
        [[("name", "=", name)]],
        {"limit": 1},
    )
    if existing:
        return int(existing[0])
    info = client.create_update_field_server_action(
        CreateUpdateFieldServerAction(
            name=name,
            model=model,
            field_name=field,
            value=value,
            bind_to_model=False,
        )
    )
    return int(info.id)


def _bind_workflow_transition_buttons(
    client: OdooClient, spec: dict[str, Any], result: UiApplyResult
) -> None:
    """Bind Confirm/Cancel header buttons to object_write server actions.

    Draft arches use ``type=object`` + ``data-transition-to`` as a marker. Live
    ``x_*`` models have no Python methods — Option A is the only path for
    ``type=object``. MEMORY: form buttons are ``type=action`` + numeric id.
    """
    if not _object_write_supported(client):
        result.warnings.append(
            "Workflow Confirm/Cancel skipped: object_write is not available "
            "on this Odoo major (16 is experimental)."
        )
        return
    models: set[str] = set()
    for row in spec.get("models") or []:
        if not isinstance(row, dict):
            continue
        mid = str(row.get("model") or "")
        if mid.startswith("x_") and (
            row.get("is_workflow") or isinstance(row.get("state_field"), dict)
        ):
            models.add(mid)
    for view in spec.get("views") or []:
        if not isinstance(view, dict) or view.get("type") != "form":
            continue
        arch = str(view.get("arch") or "")
        if "data-transition-to" in arch:
            mid = str(view.get("model") or "")
            if mid.startswith("x_"):
                models.add(mid)
    for mid in sorted(models):
        if not client.model_exists(mid):
            continue
        try:
            existing = client.find_view(mid, "form", primary_only=True)
            if existing is None:
                existing = client.find_view(mid, "form")
            if existing is None:
                continue
            arch = str(getattr(existing, "arch", "") or "")
            if "data-transition-to" not in arch:
                continue
            field = _state_field_name(spec, mid)
            dest_to_id: dict[str, int] = {}
            manager_dests = _approval_manager_dests(spec, arch)
            manager_gids = (
                _manager_group_ids_for_spec(client, spec) if manager_dests else []
            )
            for dest in _transition_dests_for_model(spec, mid, arch):
                dest_to_id[dest] = _ensure_status_write_action(
                    client, model=mid, field=field, value=dest
                )
                if dest in manager_dests and manager_gids:
                    try:
                        _restrict_server_action_groups(
                            client, dest_to_id[dest], manager_gids
                        )
                    except Exception as exc:  # noqa: BLE001
                        result.warnings.append(
                            f"Approve/Refuse group on {mid}={dest} failed: {exc}"
                        )
            rewritten = rewrite_transition_buttons_to_actions(arch, dest_to_id)
            if rewritten == arch:
                result.warnings.append(
                    f"Workflow buttons on {mid} still type=object — "
                    "could not bind data-transition-to"
                )
                continue
            client.update_view_arch(int(existing.id), rewritten)
            bound = rewritten.count('type="action"') - arch.count('type="action"')
            result.workflow_buttons_bound += max(bound, 1)
            result.views_updated += 1
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Workflow buttons on {mid} failed: {exc}")


def _polish_forms_with_statusbar(
    client: OdooClient, spec: dict[str, Any], result: UiApplyResult
) -> None:
    """If draft has no form arch for a model, apply heuristic layout + statusbar."""
    models = spec.get("models") or []
    if not isinstance(models, list):
        return
    views = spec.get("views") or []
    form_models = {
        v.get("model")
        for v in views
        if isinstance(v, dict) and v.get("type") == "form" and v.get("arch")
    }
    smart_by_model: dict[str, list[dict[str, Any]]] = {}
    for btn in spec.get("smart_buttons") or []:
        if not isinstance(btn, dict):
            continue
        norm = _normalize_smart_button(btn)
        if norm.get("on_model"):
            smart_by_model.setdefault(str(norm["on_model"]), []).append(norm)

    for model_entry in models:
        if not isinstance(model_entry, dict):
            continue
        model = model_entry.get("model")
        if not model or not isinstance(model, str):
            continue
        if not model.startswith("x_"):
            continue
        if model in form_models:
            continue
        if not client.model_exists(model):
            continue
        try:
            layout = auto_form_layout_for_model(
                client, model, string=str(model_entry.get("description") or model)
            )
            if layout is None:
                continue
            # Rebuild with statusbar via FormViewSpec when x_status exists
            field_rows = client.execute_kw(
                "ir.model.fields",
                "search_read",
                [[("model", "=", model), ("name", "=", "x_status")]],
                {"fields": ["selection"], "limit": 1},
            )
            button_box: list[ButtonNode] = []
            # Smart buttons injected after bundles created — polish here without actions
            statusbar = "x_status" if field_rows else None
            statusbar_visible = None
            if field_rows:
                # selection on ir.model.fields may be list of tuples already
                sel = field_rows[0].get("selection")
                if isinstance(sel, list):
                    keys = [str(t[0]) for t in sel if isinstance(t, (list, tuple)) and t]
                    statusbar_visible = ",".join(keys[:6]) if keys else None
                elif isinstance(sel, str):
                    keys = _selection_keys(sel)
                    statusbar_visible = ",".join(keys[:6]) if keys else None

            children: list[Any] = []
            for group in layout.groups:
                nodes = [FieldNode(name=f) for f in group.fields if f != "x_status"]
                if nodes:
                    children.append(GroupNode(string=group.string, children=nodes))

            arch = render_form_arch(
                FormViewSpec(
                    string=layout.string,
                    statusbar_field=statusbar,
                    statusbar_visible=statusbar_visible,
                    button_box=button_box,
                    children=children,
                )
            )
            primary = client.find_view(model, "form", primary_only=True) or client.find_view(
                model, "form"
            )
            if primary is None:
                client.create_view(
                    CreateViewRequest(
                        name=f"{model}.form",
                        model=model,
                        type="form",
                        arch=arch,
                    )
                )
                result.views_created += 1
            else:
                client.update_view_arch(primary.id, arch)
                result.views_updated += 1
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Form polish {model} failed: {exc}")


_SAFE_LIVE_WEB_ICON = "base,static/description/icon.png"


def _live_safe_web_icon(icon: str | None) -> str:
    """Odoo 19 RPC rejects Font Awesome ``fa-book,#hex`` — it treats it as a file path.

    Live Apply must use ``module,static/...`` (or omit). Draft JSON may still keep FA
    for documentation / future zip packaging.
    """
    raw = str(icon or "").strip()
    if not raw:
        return _SAFE_LIVE_WEB_ICON
    module = raw.split(",", 1)[0].strip().lower()
    if module.startswith("fa-") or "/" in module or module.startswith("#"):
        return _SAFE_LIVE_WEB_ICON
    if "," not in raw:
        return _SAFE_LIVE_WEB_ICON
    return raw


def _spec_web_icon(spec: dict[str, Any]) -> str:
    for menu in spec.get("menus") or []:
        if not isinstance(menu, dict):
            continue
        if menu.get("parent_xml_id") or menu.get("action_xml_id"):
            continue
        icon = str(menu.get("web_icon") or "").strip()
        if icon:
            return _live_safe_web_icon(icon)
    icon = str(spec.get("web_icon") or "").strip()
    return _live_safe_web_icon(icon)


def _menu_keys(menu: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for raw in (
        menu.get("xml_id"),
        menu.get("technical_name"),
        menu.get("name"),
    ):
        text = str(raw or "").strip()
        if not text:
            continue
        keys.append(text)
        short = text.split(".")[-1]
        if short and short not in keys:
            keys.append(short)
    return keys


def _is_spec_root_menu(menu: dict[str, Any]) -> bool:
    return not menu.get("parent_xml_id") and not menu.get("action_xml_id")


def _find_spec_action(spec: dict[str, Any], action_ref: str) -> dict[str, Any] | None:
    short = str(action_ref or "").split(".")[-1]
    if not short:
        return None
    for action in spec.get("actions") or []:
        if not isinstance(action, dict):
            continue
        for key in ("technical_name", "xml_id", "id"):
            val = str(action.get(key) or "")
            if val == short or val.split(".")[-1] == short:
                return action
    return None


def _bind_root_menu_action(client: OdooClient, root_id: int, action_id: int) -> None:
    rows = client.execute_kw(
        "ir.ui.menu",
        "read",
        [[int(root_id)]],
        {"fields": ["action"]},
    )
    if rows and not rows[0].get("action"):
        client.execute_kw(
            "ir.ui.menu",
            "write",
            [[int(root_id)], {"action": f"ir.actions.act_window,{int(action_id)}"}],
        )


def _ensure_root_menu(
    client: OdooClient, *, name: str, web_icon: str
) -> int:
    existing = client.execute_kw(
        "ir.ui.menu",
        "search",
        [[("name", "=", name), ("parent_id", "=", False)]],
        {"limit": 1},
    )
    if existing:
        root_id = int(existing[0])
        rows = client.execute_kw(
            "ir.ui.menu",
            "read",
            [[root_id]],
            {"fields": ["web_icon"]},
        )
        if rows and not rows[0].get("web_icon"):
            client.execute_kw(
                "ir.ui.menu",
                "write",
                [[root_id], {"web_icon": web_icon}],
            )
        try:
            from app.app_icons import stamp_menu_icon_png

            stamp_menu_icon_png(client, root_id, name)
        except Exception:  # noqa: BLE001
            pass
        return root_id
    root_id = int(client.create_menu(name=name, sequence=10, web_icon=web_icon))
    try:
        from app.app_icons import stamp_menu_icon_png

        stamp_menu_icon_png(client, root_id, name)
    except Exception:  # noqa: BLE001
        pass
    return root_id


def _ensure_spec_menu_tree(
    client: OdooClient, spec: dict[str, Any], result: UiApplyResult
) -> bool:
    """Apply spec.menus (root → submenus → leaves). Returns True when a tree was applied."""
    menus = [m for m in (spec.get("menus") or []) if isinstance(m, dict)]
    if not menus:
        return False
    root_spec = next((m for m in menus if _is_spec_root_menu(m)), None)
    if not root_spec:
        return False
    display = str(
        root_spec.get("name")
        or spec.get("display_name")
        or spec.get("technical_name")
        or "Custom App"
    )
    web_icon = _spec_web_icon(spec)
    root_id = _ensure_root_menu(client, name=display, web_icon=web_icon)
    result.root_menu_id = root_id
    created = 1
    xml_to_id: dict[str, int] = {}
    for key in _menu_keys(root_spec):
        xml_to_id[key] = root_id

    pending = [m for m in menus if not _is_spec_root_menu(m)]
    first_action_id: int | None = None
    guard = 0
    while pending and guard < 40:
        guard += 1
        leftover: list[dict[str, Any]] = []
        progressed = False
        for menu in pending:
            parent_ref = str(menu.get("parent_xml_id") or "").strip()
            parent_id = xml_to_id.get(parent_ref) or xml_to_id.get(
                parent_ref.split(".")[-1]
            )
            if parent_id is None:
                leftover.append(menu)
                continue
            progressed = True
            name = str(menu.get("name") or "Menu")
            seq = int(menu.get("sequence") or 10)
            existing = client.execute_kw(
                "ir.ui.menu",
                "search",
                [[("name", "=", name), ("parent_id", "=", parent_id)]],
                {"limit": 1},
            )
            action_ref = str(menu.get("action_xml_id") or "").strip()
            action_id: int | None = None
            existing_action_id: int | None = None
            if existing:
                rows = client.execute_kw(
                    "ir.ui.menu",
                    "read",
                    [[int(existing[0])]],
                    {"fields": ["action"]},
                )
                action_ref_val = (rows[0].get("action") or "") if rows else ""
                if isinstance(action_ref_val, str) and "," in action_ref_val:
                    try:
                        existing_action_id = int(action_ref_val.split(",", 1)[1])
                    except ValueError:
                        existing_action_id = None
            if action_ref and existing_action_id is None:
                action = _find_spec_action(spec, action_ref)
                model = str((action or {}).get("model") or "")
                if model.endswith("_line"):
                    continue
                if not action or not model:
                    result.warnings.append(
                        f"Menu {menu.get('name')!r} skipped: action {action_ref} missing"
                    )
                    continue
                label = str(menu.get("name") or action.get("name") or model)
                action_id = int(
                    client.create_window_action(
                        name=label,
                        model=model,
                        view_mode=str(action.get("view_mode") or "list,form"),
                    )
                )
            elif existing_action_id is not None:
                action_id = existing_action_id
            if first_action_id is None and action_id is not None:
                first_action_id = action_id
            if existing:
                menu_id = int(existing[0])
                if action_id is not None and existing_action_id is None:
                    client.execute_kw(
                        "ir.ui.menu",
                        "write",
                        [[menu_id], {"action": f"ir.actions.act_window,{action_id}"}],
                    )
            else:
                menu_id = int(
                    client.create_menu(
                        name=name,
                        parent_id=parent_id,
                        action_id=action_id,
                        sequence=seq,
                    )
                )
                created += 1
            for key in _menu_keys(menu):
                xml_to_id[key] = menu_id
        pending = leftover
        if not progressed:
            break
    for menu in pending:
        result.warnings.append(
            f"Menu {menu.get('name')!r} skipped: parent {menu.get('parent_xml_id')} not found"
        )

    spec_direct = {
        str(m.get("name") or "")
        for m in menus
        if str(m.get("parent_xml_id") or "").strip()
        in {k for k in _menu_keys(root_spec)}
        and str(m.get("name") or "")
    }
    child_ids = client.execute_kw(
        "ir.ui.menu",
        "search",
        [[("parent_id", "=", root_id)]],
    )
    stale_ids: list[int] = []
    if child_ids:
        children = client.execute_kw(
            "ir.ui.menu",
            "read",
            [list(child_ids)],
            {"fields": ["name"]},
        )
        for row in children or []:
            if str(row.get("name") or "") not in spec_direct:
                stale_ids.append(int(row["id"]))
    if stale_ids:
        client.execute_kw("ir.ui.menu", "unlink", [stale_ids])

    if first_action_id is not None:
        _bind_root_menu_action(client, root_id, first_action_id)
        result.open_action_id = first_action_id
    result.menus_created = created
    _apply_root_menu_groups(client, spec, root_id, result)
    return True


def _ensure_menus(client: OdooClient, spec: dict[str, Any], result: UiApplyResult) -> None:
    display = str(spec.get("display_name") or spec.get("technical_name") or "Custom App")
    models = [
        m
        for m in (spec.get("models") or [])
        if isinstance(m, dict)
        and m.get("model")
        and (m.get("mode") or "new") == "new"
        and str(m["model"]).startswith("x_")
    ]
    if not models:
        return
    try:
        if _ensure_spec_menu_tree(client, spec, result):
            return
        entries = [
            (str(m["model"]), str(m.get("description") or m["model"]))
            for m in models
            if not str(m["model"]).endswith("_line")
        ]
        web_icon = _spec_web_icon(spec)
        if not entries:
            root_id = _ensure_root_menu(client, name=display, web_icon=web_icon)
            result.root_menu_id = root_id
            result.menus_created = 1
            _apply_root_menu_groups(client, spec, root_id, result)
            return
        menu_ids = client.ensure_app_menus(
            root_name=display, model_entries=entries, web_icon=web_icon
        )
        result.menus_created = len(menu_ids)
        result.root_menu_id = menu_ids[0] if menu_ids else None
        if menu_ids and len(menu_ids) > 1:
            child_rows = client.execute_kw(
                "ir.ui.menu",
                "read",
                [[int(menu_ids[1])]],
                {"fields": ["action"]},
            )
            action_ref = (child_rows[0].get("action") or "") if child_rows else ""
            if isinstance(action_ref, str) and "," in action_ref:
                try:
                    result.open_action_id = int(action_ref.split(",", 1)[1])
                except ValueError:
                    result.open_action_id = None
        _apply_root_menu_groups(client, spec, menu_ids[0] if menu_ids else None, result)
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(f"Menus skipped: {exc}")


def _group_name_by_ref(spec: dict[str, Any], ref: str) -> str | None:
    short = str(ref).split(".")[-1]
    for g in spec.get("groups") or []:
        if isinstance(g, dict) and str(g.get("id") or "") == short:
            return str(g.get("name") or short)
    if short.startswith("group_"):
        return short.replace("group_", "").replace("_", " ").title()
    return None


def _resolve_or_create_group_id(
    client: OdooClient, spec: dict[str, Any], ref: str
) -> int | None:
    """Resolve base.group_user xml_ids, or create the draft's User/Manager group by name.

    Draft ACL uses bare ids (`group_{technical_name}_user`). Live Odoo xml_ids need
    `module.name` — name lookup + create is the live-apply path.
    """
    raw = str(ref or "").strip()
    if not raw:
        return None
    if "." in raw:
        try:
            return int(client.resolve_xml_id(raw))
        except Exception:  # noqa: BLE001 — fall through to name create
            pass
    name = _group_name_by_ref(spec, raw)
    if not name:
        return None
    found = client.execute_kw(
        "res.groups", "search", [[("name", "=", name)]], {"limit": 1}
    )
    if found:
        return int(found[0])
    return int(client.execute_kw("res.groups", "create", [{"name": name}]))


def _menu_group_m2m_field(client: OdooClient) -> str | None:
    """Odoo 19 renamed ir.ui.menu.groups_id → group_ids (17/18 keep groups_id)."""
    if client.field_exists("ir.ui.menu", "group_ids"):
        return "group_ids"
    if client.field_exists("ir.ui.menu", "groups_id"):
        return "groups_id"
    return None


def _collect_app_group_refs(spec: dict[str, Any]) -> list[str]:
    """Bare group ids / xml_ids from menus + access_rules (deduped, order kept)."""
    out: list[str] = []
    seen: set[str] = set()

    def _add(ref: str) -> None:
        raw = str(ref or "").strip()
        if not raw or raw in seen:
            return
        seen.add(raw)
        out.append(raw)

    for menu in spec.get("menus") or []:
        if not isinstance(menu, dict):
            continue
        for ref in menu.get("groups") or menu.get("group_xml_ids") or []:
            _add(str(ref))
    for rule in spec.get("access_rules") or []:
        if not isinstance(rule, dict):
            continue
        _add(str(rule.get("group") or rule.get("group_xml_id") or ""))
    return out


def _user_group_m2m_field(client: OdooClient) -> str | None:
    """Odoo 19 renamed res.users.groups_id → group_ids (17/18 keep groups_id)."""
    if client.field_exists("res.users", "group_ids"):
        return "group_ids"
    if client.field_exists("res.users", "groups_id"):
        return "groups_id"
    return None


def _ensure_apply_user_in_app_groups(
    client: OdooClient,
    spec: dict[str, Any],
    result: UiApplyResult,
) -> None:
    """Add draft app groups to the connection login so the restricted root menu is visible.

    Live Apply creates ``Visitor Log User`` and binds the root menu to it, but Odoo
    hides that app from users who are not in the group — including the admin who
    just Applied unless we link them here.
    """
    refs = _collect_app_group_refs(spec)
    if not refs:
        return
    group_ids: list[int] = []
    for ref in refs:
        # Skip Internal User — already implied for the applying login.
        if str(ref).endswith("group_user") and str(ref).startswith("base."):
            continue
        gid = _resolve_or_create_group_id(client, spec, str(ref))
        if gid is not None:
            group_ids.append(gid)
    if not group_ids:
        return
    try:
        uid = int(client.uid)
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(f"Apply-user group membership skipped (no uid): {exc}")
        return
    field = _user_group_m2m_field(client)
    if not field:
        result.warnings.append(
            "Apply-user group membership skipped: res.users has no group_ids/groups_id"
        )
        return
    try:
        rows = client.execute_kw(
            "res.users",
            "read",
            [[uid]],
            {"fields": [field]},
        )
        current = {
            int(i)
            for i in ((rows[0].get(field) if rows else None) or [])
        }
        missing = [gid for gid in group_ids if gid not in current]
        if not missing:
            return
        client.execute_kw(
            "res.users",
            "write",
            [[uid], {field: [(4, gid) for gid in missing]}],
        )
        result.warnings.append(
            "Apply login added to app group(s) so the home menu is visible: "
            + ", ".join(str(r) for r in refs if not str(r).startswith("base."))
        )
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(f"Apply-user group membership failed: {exc}")


def _apply_root_menu_groups(
    client: OdooClient,
    spec: dict[str, Any],
    root_menu_id: int | None,
    result: UiApplyResult,
) -> None:
    """Restrict root app menu to the module user group when draft menus specify groups."""
    if not root_menu_id:
        return
    menus = spec.get("menus") or []
    root_spec = next(
        (
            m
            for m in menus
            if isinstance(m, dict)
            and not m.get("parent_xml_id")
            and not m.get("action_xml_id")
        ),
        None,
    )
    if not root_spec:
        return
    refs = list(root_spec.get("groups") or root_spec.get("group_xml_ids") or [])
    if not refs:
        return
    group_ids: list[int] = []
    for ref in refs:
        gid = _resolve_or_create_group_id(client, spec, str(ref))
        if gid is not None:
            group_ids.append(gid)
    if not group_ids:
        return
    field = _menu_group_m2m_field(client)
    if not field:
        result.warnings.append(
            "Root menu group assignment skipped: ir.ui.menu has no group_ids/groups_id"
        )
        return
    try:
        client.execute_kw(
            "ir.ui.menu",
            "write",
            [[int(root_menu_id)], {field: [(6, 0, group_ids)]}],
        )
        result.warnings.append(
            f"Root menu restricted to app group(s): {', '.join(str(r) for r in refs)}"
        )
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(f"Root menu group assignment failed: {exc}")


# AI / client aliases → ModuleSpec smart-button keys
_SMART_BUTTON_KEY_ALIASES: dict[str, str] = {
    "source_model": "on_model",
    "target_model": "related_model",
    "field": "relation_field",
    "m2o_field": "relation_field",
}


def _normalize_smart_button(btn: dict[str, Any]) -> dict[str, Any]:
    """Map draft/API key aliases onto on_model / related_model / relation_field."""
    out = dict(btn)
    for alias, canonical in _SMART_BUTTON_KEY_ALIASES.items():
        if out.get(canonical) in (None, "") and out.get(alias) not in (None, ""):
            out[canonical] = out[alias]
    return out


def _default_inverse_m2o_name(source_model: str) -> str:
    stem = str(source_model).replace(".", "_")
    if stem.startswith("x_"):
        stem = stem[2:]
    return f"x_{stem}_id"


def _ensure_m2o_on_target_for_smart_button(
    client: OdooClient,
    btn: dict[str, Any],
    result: UiApplyResult,
) -> str | None:
    """Ensure relation_field is a Many2one on *target* pointing at *source*.

    Odoo related-window domain is ``[('relation_field','=',active_id)]`` on the
    target model. AI drafts often put the M2O on the source (button host) or omit
    it — create / remap so apply does not skip the button.
    """
    source = btn.get("on_model")
    target = btn.get("related_model")
    rel = btn.get("relation_field")
    if not source or not target or not rel:
        return None
    source_s, target_s, rel_s = str(source), str(target), str(rel)

    if client.field_exists(target_s, rel_s):
        return rel_s

    # AI put FK on the button host instead of the related list model → create inverse.
    if client.field_exists(source_s, rel_s):
        inverse = _default_inverse_m2o_name(source_s)
        if client.field_exists(target_s, inverse):
            result.warnings.append(
                f"Smart button {source_s}→{target_s}: used {target_s}.{inverse} "
                f"(draft relation_field {rel_s!r} is on source, not target)"
            )
            return inverse
        try:
            client.create_field(
                CreateFieldRequest(
                    model=target_s,
                    name=inverse,
                    field_description=str(btn.get("label") or source_s),
                    ttype=FieldType.MANY2ONE,
                    relation=source_s,
                    on_delete="set_null",
                )
            )
            result.fields_created += 1
            result.warnings.append(
                f"Created {target_s}.{inverse} → {source_s} for smart button "
                f"(draft had {rel_s!r} on {source_s})"
            )
            return inverse
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(
                f"Smart button M2O on {target_s} failed (needed inverse of "
                f"{source_s}.{rel_s}): {exc}"
            )
            return None

    # Missing entirely — create the named M2O on target.
    try:
        name = rel_s if rel_s.startswith("x_") else f"x_{rel_s}"
        if not client.field_exists(target_s, name):
            client.create_field(
                CreateFieldRequest(
                    model=target_s,
                    name=name,
                    field_description=str(btn.get("label") or source_s),
                    ttype=FieldType.MANY2ONE,
                    relation=source_s,
                    on_delete="set_null",
                )
            )
            result.fields_created += 1
            result.warnings.append(
                f"Created {target_s}.{name} → {source_s} for smart button"
            )
        return name
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(f"Smart button M2O on {target_s} failed: {exc}")
        return None


def _ensure_o2m_for_smart_button(
    client: OdooClient,
    btn: dict[str, Any],
    result: UiApplyResult,
) -> str | None:
    o2m = btn.get("one2many_field")
    source = btn.get("on_model")
    target = btn.get("related_model")
    rel = btn.get("relation_field")
    if not source or not target or not rel:
        return None
    if o2m and client.field_exists(str(source), str(o2m)):
        return str(o2m)
    # Create O2M if missing
    name = str(o2m or f"x_{str(target).replace('x_', '').replace('.', '_')}_ids")
    if not name.startswith("x_"):
        name = f"x_{name}"
    if client.field_exists(str(source), name):
        return name
    # PCM: never invent one2many on tier-1 stock hosts — button still works without a count.
    try:
        from app.protected_enforcement import check_field_create
        from app.protected_modules import community_manifest_for_version

        major = int(getattr(getattr(client, "capabilities", None), "major", None) or 19)
        manifest = community_manifest_for_version(f"{major}.0")
        viol = check_field_create(
            manifest,
            model=str(source),
            ttype="one2many",
            relation=str(target),
            field_name=name,
        )
        if viol:
            result.warnings.append(
                f"O2M for smart button skipped on {source} (PCM): count badge omitted; "
                f"button still injected"
            )
            return None
    except Exception:  # noqa: BLE001
        pass
    try:
        client.create_field(
            CreateFieldRequest(
                model=str(source),
                name=name,
                field_description=str(btn.get("label") or "Related"),
                ttype=FieldType.ONE2MANY,
                relation=str(target),
                relation_field=str(rel),
            )
        )
        result.fields_created += 1
        return name
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(f"O2M for smart button skipped: {exc}")
        return None


def _apply_smart_buttons(
    client: OdooClient, spec: dict[str, Any], result: UiApplyResult
) -> None:
    buttons = spec.get("smart_buttons") or []
    if not isinstance(buttons, list):
        return
    # Collect button specs per source model then rewrite forms
    by_model: dict[str, list[ButtonNode]] = {}
    for raw_btn in buttons:
        if not isinstance(raw_btn, dict):
            continue
        btn = _normalize_smart_button(raw_btn)
        source = btn.get("on_model")
        target = btn.get("related_model")
        rel = btn.get("relation_field")
        if not source or not target or not rel:
            result.warnings.append(
                "Smart button skipped (need on_model/related_model/relation_field "
                f"or source_model/target_model aliases): {raw_btn!r}"
            )
            continue
        if not client.model_exists(str(source)) or not client.model_exists(str(target)):
            result.warnings.append(
                f"Smart button skipped (missing model): {source} → {target}"
            )
            continue
        resolved_rel = _ensure_m2o_on_target_for_smart_button(client, btn, result)
        if not resolved_rel:
            result.warnings.append(
                f"Smart button skipped (no M2O on {target} → {source}): "
                f"{btn.get('label') or rel}"
            )
            continue
        btn = {**btn, "relation_field": resolved_rel}
        o2m = _ensure_o2m_for_smart_button(client, btn, result)
        try:
            bundle = client.create_smart_button_bundle(
                CreateSmartButtonBundle(
                    name=str(btn.get("label") or "Open"),
                    source_model=str(source),
                    target_model=str(target),
                    relation_field=str(resolved_rel),
                    one2many_field=o2m,
                    create_count_field=bool(o2m),
                    icon=str(btn.get("icon") or "fa-list"),
                )
            )
            node = ButtonNode(
                string=str(btn.get("label") or "Open"),
                name=str(bundle.window_action.id),
                type="action",
                class_name="oe_stat_button",
                icon=str(btn.get("icon") or "fa-list"),
                count_field=bundle.count_field,
            )
            by_model.setdefault(str(source), []).append(node)
            result.smart_buttons += 1
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Smart button failed: {exc}")

    for model, nodes in by_model.items():
        try:
            _inject_button_box(client, model, nodes, result)
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Inject smart buttons on {model}: {exc}")

def _inject_button_box(
    client: OdooClient,
    model: str,
    nodes: list[ButtonNode],
    result: UiApplyResult,
) -> None:
    """Inject smart buttons via a stable inherit view — never mutate the primary form.

    Stock forms (res.partner, …) keep their fields/xpaths intact; custom x_ forms
    get a button_box created if missing.
    """
    if not nodes:
        return
    info = client.inject_smart_buttons_into_form(model, nodes)
    result.views_updated += 1
    if not model.startswith("x_"):
        result.warnings.append(
            f"Smart buttons on {model} added via inherit view "
            f"{getattr(info, 'name', model + '.studio.smart_buttons')!s} "
            "(primary Contacts/stock form unchanged)"
        )


def _iter_safe_actions(auto: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize ModuleSpec automation shapes into action dicts."""
    actions: list[dict[str, Any]] = []
    for key in ("safe_actions", "actions"):
        raw = auto.get(key)
        if isinstance(raw, list):
            actions.extend([a for a in raw if isinstance(a, dict)])
    # Flat single-action drafts from older generators
    kind = auto.get("action_kind") or auto.get("kind")
    if kind and not actions:
        flat = {k: v for k, v in auto.items() if k not in {"name", "model", "trigger", "description"}}
        flat["kind"] = kind
        actions.append(flat)
    return actions


def _infer_trg_date_field(
    client: OdooClient, spec: dict[str, Any], auto: dict[str, Any]
) -> str | None:
    """on_time requires a date field; drafts often only put it in filter_domain."""

    def _exists(model: str, name: str) -> bool:
        try:
            return bool(client.field_exists(model, name))
        except Exception:  # noqa: BLE001
            return False

    return infer_trg_date_field(spec, auto, field_exists=_exists)


def _action_from_spec(action: dict[str, Any]) -> Any | None:
    """Map draft action → typed safe action, or None if unsupported."""
    from odoo_client import (
        CreateActivityAction,
        RelatedWriteAction,
        UpdateFieldAction,
    )

    kind = str(action.get("kind") or action.get("action_kind") or "").strip()
    field = action.get("field_name") or action.get("field")
    value = action.get("value")
    # Kind omitted but field+value present → assume update / related write
    if not kind and field is not None and value is not None:
        if action.get("relation_field") or "." in str(field):
            kind = "related_write"
        else:
            kind = "update_field"
    if kind in {"related_write"}:
        relation = action.get("relation_field")
        if not relation and field and "." in str(field):
            relation, _, field = str(field).partition(".")
        if not relation or not field or value is None:
            return None
        return RelatedWriteAction(
            relation_field=str(relation),
            field_name=str(field),
            value=str(value),
        )
    if kind in {"update_field", "object_write", "set", "write_field"}:
        if not field or value is None:
            return None
        # Dotted path without explicit related_write → treat as related_write
        if "." in str(field) and not action.get("relation_field"):
            rel, _, fname = str(field).partition(".")
            if rel and fname:
                return RelatedWriteAction(
                    relation_field=rel, field_name=fname, value=str(value)
                )
        return UpdateFieldAction(field_name=str(field), value=str(value))
    if kind in {"create_activity", "next_activity"}:
        type_id = action.get("activity_type_id")
        if not type_id:
            return None
        raw_user_type = str(
            action.get("user_type") or action.get("activity_user_type") or "generic"
        )
        user_type: Literal["specific", "generic"] = (
            "specific" if raw_user_type == "specific" else "generic"
        )
        raw_uid = action.get("user_id") or action.get("activity_user_id")
        if isinstance(raw_uid, (list, tuple)) and raw_uid:
            raw_uid = raw_uid[0]
        user_id: int | None
        try:
            user_id = int(raw_uid) if raw_uid not in (None, False, "") else None
        except (TypeError, ValueError):
            user_id = None
        return CreateActivityAction(
            activity_type_id=int(type_id),
            summary=str(action.get("summary") or "Follow up"),
            note=action.get("note"),
            user_type=user_type,
            user_id=user_id,
            user_field_name=action.get("user_field_name")
            or action.get("activity_user_field_name"),
        )
    return None


def _default_activity_type_id(
    client: OdooClient, *, model: str | None = None
) -> int | None:
    """Draft next_activity rows only send a summary — pick a generic To Do type."""
    try:
        return int(client.resolve_xml_id(MAIL_TODO_XML_ID))
    except Exception:  # noqa: BLE001
        pass
    try:
        types = client.list_activity_types(limit=50)
    except Exception:  # noqa: BLE001
        return None
    named_todo: list[dict[str, Any]] = []
    generic: list[dict[str, Any]] = []
    matching: list[dict[str, Any]] = []
    for row in types or []:
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        res_model = str(row.get("res_model") or "") or None
        if res_model and model and res_model != model:
            continue
        name = str(row.get("name") or "").lower()
        if "to do" in name or name in {"todo", "to-do"}:
            named_todo.append(row)
        elif not res_model:
            generic.append(row)
        elif res_model == model:
            matching.append(row)
    for bucket in (named_todo, generic, matching):
        if bucket:
            return int(bucket[0]["id"])
    return None


def _live_filter_domain_broken(fd: Any) -> bool:
    """True when Odoo safe_eval(filter_domain) would SyntaxError on write."""
    from app.ai_odoo_app_bar import _filter_domain_is_invalid

    if fd in (None, False, "", "[]", "False"):
        return False
    text = str(fd).strip()
    if _filter_domain_is_invalid(text):
        return True
    try:
        compile(text, "<filter_domain>", "eval")
    except SyntaxError:
        return True
    return False


def _scrub_live_broken_automations(
    client: OdooClient, spec: dict[str, Any], result: UiApplyResult
) -> None:
    """Unlink leftover x_* automations whose filter_domain crashes record write.

    Closer drops these from the draft; earlier applies can leave them on the
    sandbox. Confirm/object_write then SyntaxErrors in base.automation.
    """
    _ = spec
    exists = getattr(client, "model_exists", None)
    if not callable(exists) or not exists("base.automation"):
        return
    try:
        rows = client.execute_kw(
            "base.automation",
            "search_read",
            [[("model_id.model", "=like", "x_%")]],
            {
                "fields": [
                    "id",
                    "name",
                    "filter_domain",
                    "filter_pre_domain",
                ]
            },
        )
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(f"Automation scrub skipped: {exc}")
        return
    broken_ids: list[int] = []
    names: list[str] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        if _live_filter_domain_broken(row.get("filter_domain")) or _live_filter_domain_broken(
            row.get("filter_pre_domain")
        ):
            broken_ids.append(int(row["id"]))
            names.append(str(row.get("name") or row["id"]))
    if not broken_ids:
        return
    try:
        client.execute_kw("base.automation", "unlink", [broken_ids])
    except Exception:
        try:
            client.execute_kw(
                "base.automation",
                "write",
                [broken_ids, {"active": False, "filter_domain": "[]", "filter_pre_domain": False}],
            )
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Could not remove broken automations {names}: {exc}")
            return
    result.automations_scrubbed += len(broken_ids)
    result.warnings.append(
        "Removed leftover automation(s) with invalid filter_domain "
        f"(would crash Confirm/write): {', '.join(names)}"
    )


def _relax_leftover_required_fields(
    client: OdooClient, spec: dict[str, Any], result: UiApplyResult
) -> None:
    """Set required=False on live x_* fields that are not in this spec.

    Earlier applies can leave required columns that the current draft dropped.
    Walkthrough/Confirm then fail on missing values. Relax leftover required
    flags; do not drop columns (data-preserving).
    """
    models = spec.get("models") or []
    if not isinstance(models, list):
        return
    for entry in models:
        if not isinstance(entry, dict):
            continue
        model = str(entry.get("model") or "")
        if not model.startswith("x_"):
            continue
        spec_names = {
            str(f.get("name"))
            for f in (entry.get("fields") or [])
            if isinstance(f, dict) and f.get("name")
        }
        try:
            rows = client.execute_kw(
                "ir.model.fields",
                "search_read",
                [[("model", "=", model), ("name", "=like", "x_%"), ("required", "=", True)]],
                {"fields": ["id", "name", "required"]},
            )
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Leftover required scan skipped for {model}: {exc}")
            continue
        relax_ids: list[int] = []
        names: list[str] = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            fname = str(row.get("name") or "")
            if fname and fname not in spec_names:
                relax_ids.append(int(row["id"]))
                names.append(fname)
        if not relax_ids:
            continue
        try:
            client.execute_kw("ir.model.fields", "write", [relax_ids, {"required": False}])
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Could not relax leftover required on {model}: {exc}")
            continue
        result.fields_relaxed += len(relax_ids)
        result.warnings.append(
            f"Relaxed leftover required field(s) on {model} (not in spec): {', '.join(names)}"
        )


def _apply_safe_automations(
    client: OdooClient, spec: dict[str, Any], result: UiApplyResult
) -> None:
    """Create safe automations from ModuleSpec (related_write, update_field, activity)."""
    from odoo_client import CreateAutomationRequest
    from odoo_client.automation import AutomationTrigger

    _scrub_live_broken_automations(client, spec, result)

    autos = spec.get("automations") or []
    if not isinstance(autos, list):
        return

    for auto in autos:
        if not isinstance(auto, dict):
            continue
        name = auto.get("name")
        model = auto.get("model")
        trigger_raw = auto.get("trigger") or "on_write"
        if not name or not model:
            result.warnings.append(f"Skipped automation missing name/model: {auto!r}")
            result.automations_noted += 1
            continue
        if _live_filter_domain_broken(auto.get("filter_domain")):
            result.warnings.append(
                f"Skipped automation {name!r}: invalid filter_domain "
                "(not a Python domain; Confirm/write would crash)"
            )
            result.automations_noted += 1
            continue
        if not client.model_exists(str(model)):
            result.warnings.append(
                f"Skipped automation {name!r}: model {model} not found"
            )
            result.automations_noted += 1
            continue
        trigger_norm = _normalize_automation_trigger(trigger_raw)
        if not trigger_norm:
            result.warnings.append(
                f"Skipped automation {name!r}: unsupported trigger {trigger_raw!r}"
            )
            result.automations_noted += 1
            continue
        try:
            trigger = AutomationTrigger(trigger_norm)
        except ValueError:
            result.warnings.append(
                f"Skipped automation {name!r}: unsupported trigger {trigger_raw!r}"
            )
            result.automations_noted += 1
            continue

        actions = _iter_safe_actions(auto)
        if not actions:
            result.warnings.append(f"Automation {name!r} has no safe_actions")
            result.automations_noted += 1
            continue

        created_any = False
        default_activity_type: int | None | str = ""
        for idx, action_spec in enumerate(actions):
            row = dict(action_spec)
            kind_raw = str(row.get("kind") or row.get("action_kind") or "")
            if kind_raw in {"create_activity", "next_activity"} and not row.get(
                "activity_type_id"
            ):
                xml_id = str(row.get("activity_type_xml_id") or MAIL_TODO_XML_ID)
                try:
                    row["activity_type_id"] = int(client.resolve_xml_id(xml_id))
                except Exception:  # noqa: BLE001
                    if default_activity_type == "":
                        default_activity_type = _default_activity_type_id(
                            client, model=str(model)
                        )
                    if default_activity_type:
                        row["activity_type_id"] = default_activity_type
            typed = _action_from_spec(row)
            if typed is None:
                kind = row.get("kind") or row.get("action_kind")
                result.warnings.append(
                    f"Automation {name!r}: skipped unsupported/incomplete action {kind!r}"
                )
                result.automations_noted += 1
                continue
            auto_name = str(name) if idx == 0 else f"{name} ({idx + 1})"
            try:
                kwargs: dict[str, Any] = {
                    "name": auto_name,
                    "model": str(model),
                    "trigger": trigger,
                    "action": typed,
                    "filter_domain": auto.get("filter_domain"),
                    "filter_pre_domain": auto.get("filter_pre_domain"),
                    "active": bool(auto.get("active", True)),
                }
                names = auto.get("trigger_field_names") or auto.get("trigger_fields") or []
                if isinstance(names, list) and names:
                    kwargs["trigger_field_names"] = [str(n) for n in names if n]
                if trigger.value.startswith("on_time"):
                    date_field = _infer_trg_date_field(client, spec, auto) or (
                        action_spec.get("trg_date_field_name")
                    )
                    if not date_field:
                        result.warnings.append(
                            f"Skipped time automation {auto_name!r}: needs trg_date_field_name"
                        )
                        result.automations_noted += 1
                        continue
                    kwargs["trg_date_field_name"] = str(date_field)
                    if auto.get("trg_date_range") is not None:
                        try:
                            kwargs["trg_date_range"] = int(auto["trg_date_range"])
                        except (TypeError, ValueError):
                            pass
                    if auto.get("trg_date_range_type"):
                        kwargs["trg_date_range_type"] = str(auto["trg_date_range_type"])
                    if auto.get("trg_date_range_mode"):
                        kwargs["trg_date_range_mode"] = str(auto["trg_date_range_mode"])
                client.create_automation(CreateAutomationRequest(**kwargs))
                result.automations_created += 1
                created_any = True
            except Exception as exc:  # noqa: BLE001
                result.warnings.append(f"Automation {auto_name!r} failed: {exc}")
                result.automations_noted += 1
        if not created_any and actions:
            pass  # warnings already recorded


def _resolve_draft_model_name(client: OdooClient, raw: Any) -> str | None:
    """Map access_rules model stubs (model_x_patient or x_patient) → live technical name."""
    if raw in (None, False, ""):
        return None
    m = str(raw).strip()
    if client.model_exists(m):
        return m
    if m.startswith("model_"):
        cand = m[len("model_") :]
        if client.model_exists(cand):
            return cand
    return None


def _apply_access_rules(
    client: OdooClient, spec: dict[str, Any], result: UiApplyResult
) -> None:
    """Apply draft access_rules: ir.model.access stubs and ir.rule when domain present."""
    from odoo_client.security import CreateAccessRightRequest, CreateRecordRuleRequest

    rules = spec.get("access_rules") or []
    if not isinstance(rules, list):
        return

    for rule in rules:
        if not isinstance(rule, dict):
            continue
        model = _resolve_draft_model_name(client, rule.get("model"))
        if not model:
            result.warnings.append(
                f"Access rule skipped (unknown model): {rule.get('model')!r}"
            )
            continue
        name = str(rule.get("name") or f"access_{model.replace('.', '_')}")
        domain = rule.get("domain_force") or rule.get("domain")
        try:
            if domain not in (None, False, ""):
                client.create_record_rule(
                    CreateRecordRuleRequest(
                        model=model,
                        name=name,
                        domain_force=str(domain),
                        perm_read=bool(rule.get("perm_read", True)),
                        perm_write=bool(rule.get("perm_write", True)),
                        perm_create=bool(rule.get("perm_create", True)),
                        perm_unlink=bool(rule.get("perm_unlink", True)),
                        active=bool(rule.get("active", True)),
                    )
                )
                result.record_rules_created += 1
                continue

            group_ref = str(rule.get("group") or rule.get("group_xml_id") or "base.group_user")
            group_id = None
            if group_ref:
                group_id = _resolve_or_create_group_id(client, spec, group_ref)
                if group_id is None:
                    result.warnings.append(
                        f"Access {name!r}: group {group_ref!r} unresolved; "
                        "creating without group"
                    )
            # Idempotent: skip if same group already has a row
            existing = client.execute_kw(
                "ir.model.access",
                "search",
                [
                    [
                        ("model_id.model", "=", model),
                        ("group_id", "=", group_id) if group_id else ("group_id", "=", False),
                    ]
                ],
                {"limit": 1},
            )
            if existing:
                continue
            client.create_access_right(
                CreateAccessRightRequest(
                    model=model,
                    name=name,
                    group_id=group_id,
                    perm_read=bool(rule.get("perm_read", 1)),
                    perm_write=bool(rule.get("perm_write", 1)),
                    perm_create=bool(rule.get("perm_create", 1)),
                    perm_unlink=bool(rule.get("perm_unlink", 1)),
                    active=bool(rule.get("active", True)),
                )
            )
            result.access_rights_created += 1
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Access rule {name!r} failed: {exc}")


def _apply_draft_record_rules(
    client: OdooClient, spec: dict[str, Any], result: UiApplyResult
) -> None:
    """Apply draft record_rules (multi-company + branch scope) via ir.rule RPC."""
    from odoo_client.security import CreateRecordRuleRequest

    rules = spec.get("record_rules") or []
    if not isinstance(rules, list):
        return

    for rule in rules:
        if not isinstance(rule, dict):
            continue
        model = _resolve_draft_model_name(client, rule.get("model"))
        if not model:
            result.warnings.append(
                f"Record rule skipped (unknown model): {rule.get('model')!r}"
            )
            continue
        name = str(rule.get("name") or f"rule_{model.replace('.', '_')}")
        domain = rule.get("domain_force") or rule.get("domain")
        if domain in (None, False, ""):
            result.warnings.append(f"Record rule {name!r} skipped: empty domain")
            continue
        try:
            existing = client.list_record_rules(model=model, limit=50)
            if any(r.name == name for r in existing):
                result.skipped.append(f"record_rule:{model}:{name}")
                continue
            client.create_record_rule(
                CreateRecordRuleRequest(
                    model=model,
                    name=name,
                    domain_force=str(domain),
                    perm_read=bool(rule.get("perm_read", True)),
                    perm_write=bool(rule.get("perm_write", True)),
                    perm_create=bool(rule.get("perm_create", True)),
                    perm_unlink=bool(rule.get("perm_unlink", True)),
                    active=bool(rule.get("active", True)),
                )
            )
            result.record_rules_created += 1
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Record rule {name!r} failed: {exc}")


def _note_automations(spec: dict[str, Any], result: UiApplyResult) -> None:
    """Legacy note path — prefer _apply_safe_automations when apply_automations=True."""
    autos = spec.get("automations") or []
    if not isinstance(autos, list):
        return
    result.automations_noted = len([a for a in autos if isinstance(a, dict)])
    if result.automations_noted:
        result.warnings.append(
            f"{result.automations_noted} automation(s) in draft — not applied "
            "(apply_automations=false). Review Automations page or re-run with apply."
        )


def _warn_custom_code_blocks(spec: dict[str, Any], result: UiApplyResult) -> None:
    """Live apply skips opaque custom logic — explicit per-block warnings (AI-7)."""
    from app.module_spec_codec import merge_custom_code_blocks

    for block in merge_custom_code_blocks(spec):
        src = block.get("source_file") or block.get("path") or "custom"
        kind = block.get("kind") or "opaque"
        model = block.get("model")
        label = f"{src} [{kind}]"
        if model:
            label = f"{label} on {model}"
        result.warnings.append(
            f"Custom logic skipped (view as code, not live-applied): {label}"
        )


def _workflow_models(spec: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for model in spec.get("models") or []:
        if not isinstance(model, dict):
            continue
        if (model.get("mode") or "new") != "new":
            continue
        model_name = model.get("model")
        if not model_name or not str(model_name).startswith("x_"):
            continue
        if model.get("is_workflow") or model.get("state_field"):
            out.append(model)
    return out


def _reference_field_name(model: dict[str, Any]) -> str:
    names = {
        str(f.get("name"))
        for f in (model.get("fields") or [])
        if isinstance(f, dict) and f.get("name")
    }
    if "x_code" in names:
        return "x_code"
    if "x_reference" in names:
        return "x_reference"
    return "x_code"


def _sequence_prefix_for_model(model: str) -> str:
    from module_generator import sequence_prefix_for_model

    return sequence_prefix_for_model(model)


def _apply_workflow_sequences(
    client: OdooClient, spec: dict[str, Any], result: UiApplyResult
) -> None:
    """Create ir.sequence rows for workflow models (config_ops parity)."""
    from app.id_generator import IdGeneratorConfig, create_reference_sequence

    for model in _workflow_models(spec):
        model_name = str(model["model"])
        if not client.model_exists(model_name):
            result.warnings.append(
                f"Skip sequence for {model_name}: model not on instance yet"
            )
            continue
        prefix_token = _sequence_prefix_for_model(model_name).rstrip("/")
        config = IdGeneratorConfig(prefix=prefix_token, separator="/", padding=5)
        try:
            create_reference_sequence(
                client,
                model=model_name,
                config=config,
                sequence_name=f"{model.get('description') or model_name} Reference",
            )
            result.sequences_created += 1
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Sequence for {model_name} failed: {exc}")


def _apply_component_inherit(client: OdooClient, spec: dict[str, Any], result: UiApplyResult) -> None:
    """Inject inherit fields/views onto stock hosts (any grain)."""
    has_inherit = any(
        isinstance(m, dict) and str(m.get("mode") or "new") == "inherit"
        for m in (spec.get("models") or [])
    )
    has_extension = any(
        isinstance(v, dict) and str(v.get("mode") or "") == "extension"
        for v in (spec.get("views") or [])
    )
    if not has_inherit and not has_extension:
        return

    from app.ai_connect_points import unique_inherit_view_name
    from app.ai_grain import INHERIT_FORM_XPATH

    extension_field_names: set[str] = set()
    for view in spec.get("views") or []:
        if not isinstance(view, dict) or str(view.get("mode") or "") != "extension":
            continue
        arch = str(view.get("arch") or "")
        extension_field_names.update(re.findall(r'name="(x_[^"]+)"', arch))

    for model_entry in spec.get("models") or []:
        if not isinstance(model_entry, dict):
            continue
        if str(model_entry.get("mode") or "new") != "inherit":
            continue
        host = str(model_entry.get("model") or "")
        if not host or not client.model_exists(host):
            result.warnings.append(f"Skip inherit fields: host {host} missing")
            continue
        for field_entry in model_entry.get("fields") or []:
            if not isinstance(field_entry, dict):
                continue
            fname = field_entry.get("name")
            ttype = str(field_entry.get("ttype") or "")
            if not fname or ttype == "one2many":
                continue
            if str(fname) in extension_field_names:
                # Extension view already places the field — avoid duplicate injects.
                continue
            if not client.field_exists(host, str(fname)):
                continue
            try:
                updated = client.inject_field_into_views(host, str(fname), strategy="inherit")
                if updated:
                    result.views_created += len(updated)
            except Exception as exc:  # noqa: BLE001
                result.warnings.append(f"Inherit inject {host}.{fname} failed: {exc}")

    for view in spec.get("views") or []:
        if not isinstance(view, dict):
            continue
        if str(view.get("mode") or "") != "extension":
            continue
        model = str(view.get("model") or "")
        vtype = str(view.get("type") or "form")
        arch = view.get("arch")
        if not model or not isinstance(arch, str) or not arch.strip():
            continue
        preferred = INHERIT_FORM_XPATH.get(model)
        if preferred and 'expr="//sheet"' in arch:
            arch = arch.replace('expr="//sheet"', f'expr="{preferred}"', 1)
        primary = client.find_view(model, vtype, primary_only=True) or client.find_view(model, vtype)
        if primary is None:
            result.warnings.append(f"Skip inherit view: no primary {vtype} for {model}")
            continue
        vname = unique_inherit_view_name(model, str(view.get("name") or "extension"))
        try:
            existing = client._find_view_by_exact_name(vname)  # noqa: SLF001
            if existing is not None:
                client.update_view_arch(existing.id, arch)
                result.views_updated += 1
            else:
                client.create_inherit_view(
                    model=model,
                    name=vname,
                    view_type=primary.type or vtype,
                    inherit_id=primary.id,
                    arch=arch,
                )
                result.views_created += 1
        except Exception as exc:  # noqa: BLE001
            detail = f"Inherit view {vname} failed: {exc}"
            result.warnings.append(detail)
            result.skipped.append(detail)


def inherit_host_model_from_spec(spec: dict[str, Any]) -> str | None:
    """Stock host a field pack / inherit draft extends — not a new x_* app."""
    for row in spec.get("models") or []:
        if not isinstance(row, dict):
            continue
        mid = str(row.get("model") or "").strip()
        if not mid or mid.endswith("_line") or mid.endswith("_party"):
            continue
        mode = str(row.get("mode") or "new")
        if mode == "inherit" or not mid.startswith("x_"):
            return mid
    return None


def resolve_inherit_open_target(
    client: Any,
    spec: dict[str, Any],
) -> tuple[str | None, int | None]:
    """Window action for Open in Odoo after inherit apply (no new home-grid tile)."""
    from app.ai_grain import inherit_open_xml_ids
    from app.config_packet.rpc import xml_id

    host = inherit_host_model_from_spec(spec)
    if not host:
        return None, None
    prompt = " ".join(
        [
            str(spec.get("_user_prompt") or ""),
            str(spec.get("display_name") or ""),
        ]
    )
    for xid in inherit_open_xml_ids(host, prompt):
        action_id = xml_id(client, xid)
        if action_id:
            return host, action_id
    try:
        rows = client.execute_kw(
            "ir.actions.act_window",
            "search_read",
            [[("res_model", "=", host)]],
            {"fields": ["id", "name", "domain", "context"], "limit": 16},
        )
    except Exception:  # noqa: BLE001
        return host, None
    text = prompt.lower()
    prefer_bill = bool(re.search(r"\b(vendor\s+bills?|supplier\s+bills?)\b", text))
    for row in rows or []:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        blob = f"{row.get('name') or ''} {row.get('domain') or ''} {row.get('context') or ''}".lower()
        if "active_id" in blob:
            continue
        if prefer_bill and ("in_invoice" in blob or "vendor bill" in blob or "bills" in blob):
            return host, int(row["id"])
        if not prefer_bill and host == "account.move" and (
            "out_invoice" in blob or "customer invoice" in blob
        ):
            return host, int(row["id"])
    for row in rows or []:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        blob = f"{row.get('domain') or ''} {row.get('context') or ''}".lower()
        if "active_id" in blob:
            continue
        return host, int(row["id"])
    return host, None


def apply_module_spec_ui(
    client: OdooClient,
    spec: dict[str, Any],
    *,
    apply_views: bool = True,
    apply_menus: bool = True,
    apply_smart_buttons: bool = True,
    apply_automations: bool = True,
    apply_access: bool = True,
) -> UiApplyResult:
    """Create models/fields then generate UI from ModuleSpec JSON."""
    base = apply_project_spec(client, spec)
    result = UiApplyResult(
        models_created=base.models_created,
        fields_created=base.fields_created,
        skipped=base.skipped,
        warnings=list(base.warnings),
        message="",
    )

    _warn_custom_code_blocks(spec, result)
    _apply_workflow_sequences(client, spec, result)

    if apply_views:
        _apply_explicit_views(client, spec, result)
        _polish_forms_with_statusbar(client, spec, result)
        _apply_component_inherit(client, spec, result)
        _bind_workflow_transition_buttons(client, spec, result)
    if apply_menus:
        _ensure_menus(client, spec, result)
    if apply_smart_buttons:
        _apply_smart_buttons(client, spec, result)
    _scrub_live_broken_automations(client, spec, result)
    _relax_leftover_required_fields(client, spec, result)
    if apply_automations:
        _apply_safe_automations(client, spec, result)
    else:
        _note_automations(spec, result)
    if apply_access:
        _apply_access_rules(client, spec, result)
        _apply_draft_record_rules(client, spec, result)
    if apply_menus or apply_access:
        _ensure_apply_user_in_app_groups(client, spec, result)

    result.message = (
        f"UI apply: {len(result.models_created)} model(s), {result.fields_created} field(s), "
        f"{result.views_created} view(s) created, {result.views_updated} updated, "
        f"{result.menus_created} menu(s), {result.smart_buttons} smart button(s), "
        f"{result.automations_created} automation(s), "
        f"{result.access_rights_created} access + {result.record_rules_created} record rule(s), "
        f"{result.sequences_created} sequence(s)"
    )
    if result.workflow_buttons_bound:
        result.message += f", {result.workflow_buttons_bound} workflow button(s)"
    if result.automations_scrubbed:
        result.message += f", {result.automations_scrubbed} leftover automation(s) removed"
    if result.fields_relaxed:
        result.message += f", {result.fields_relaxed} leftover required field(s) relaxed"
    if result.root_menu_id:
        result.message += f". Open the app (menu_id={result.root_menu_id})"
    elif not result.open_action_id:
        host, action_id = resolve_inherit_open_target(client, spec)
        result.open_model = host
        if action_id:
            result.open_action_id = action_id
            result.message += f". Open the existing {host} list in Odoo (not a new app tile)"
        elif host:
            result.message += f". Fields are on {host} — open that form in Odoo (not a new app tile)"
    return result


__all__ = [
    "UiApplyResult",
    "apply_module_spec_ui",
    "inherit_host_model_from_spec",
    "resolve_inherit_open_target",
    "rewrite_transition_buttons_to_actions",
]
