"""Hierarchical spec.menus apply — not a flat child per x_* model."""

from __future__ import annotations

from typing import Any

from app.spec_apply_ui import UiApplyResult, _ensure_menus


class _MenuFakeClient:
    def __init__(self) -> None:
        self.menus: list[dict[str, Any]] = []
        self.actions: list[dict[str, Any]] = []
        self._nid = 1

    def _next(self) -> int:
        self._nid += 1
        return self._nid

    def field_exists(self, model: str, name: str) -> bool:
        return model == "ir.ui.menu" and name == "group_ids"

    def model_exists(self, model: str) -> bool:
        return str(model).startswith("x_")

    def create_window_action(
        self,
        *,
        name: str,
        model: str,
        view_mode: str = "list,form",
        domain: str | None = None,
        context: str | None = None,
    ) -> int:
        aid = self._next()
        self.actions.append(
            {"id": aid, "name": name, "model": model, "view_mode": view_mode}
        )
        return aid

    def create_menu(
        self,
        *,
        name: str,
        parent_id: int | None = None,
        action_id: int | None = None,
        sequence: int = 10,
        web_icon: str | None = None,
    ) -> int:
        mid = self._next()
        action = f"ir.actions.act_window,{action_id}" if action_id else False
        self.menus.append(
            {
                "id": mid,
                "name": name,
                "parent_id": parent_id,
                "action": action,
                "sequence": sequence,
                "web_icon": web_icon,
            }
        )
        return mid

    def ensure_app_menus(
        self,
        *,
        root_name: str,
        model_entries: list[tuple[str, str]],
        web_icon: str = "base,static/description/icon.png",
    ) -> list[int]:
        root_id = None
        for row in self.menus:
            if row["name"] == root_name and row["parent_id"] is None:
                root_id = row["id"]
                if not row.get("web_icon"):
                    row["web_icon"] = web_icon
                break
        if root_id is None:
            root_id = self.create_menu(name=root_name, sequence=10, web_icon=web_icon)
        ids = [root_id]
        first_action_id: int | None = None
        for seq, (model, label) in enumerate(model_entries, start=10):
            existing = next(
                (m for m in self.menus if m["name"] == label and m["parent_id"] == root_id),
                None,
            )
            if existing:
                ids.append(existing["id"])
                continue
            action_id = self.create_window_action(name=label, model=model)
            if first_action_id is None:
                first_action_id = action_id
            ids.append(
                self.create_menu(
                    name=label, parent_id=root_id, action_id=action_id, sequence=seq
                )
            )
        if first_action_id is not None:
            root = next(m for m in self.menus if m["id"] == root_id)
            if not root.get("action"):
                root["action"] = f"ir.actions.act_window,{first_action_id}"
        return ids

    def execute_kw(
        self, model: str, method: str, args: list[Any], kwargs: Any = None
    ) -> Any:
        kwargs = kwargs or {}
        if model != "ir.ui.menu":
            return []
        if method == "search":
            domain = args[0] if args else []
            name = None
            parent = None
            parent_false = False
            for term in domain:
                if not isinstance(term, (list, tuple)) or len(term) < 3:
                    continue
                field, _op, val = term[0], term[1], term[2]
                if field == "name":
                    name = val
                elif field == "parent_id" and val is False:
                    parent_false = True
                elif field == "parent_id":
                    parent = val
            hits = []
            for row in self.menus:
                if name is not None and row["name"] != name:
                    continue
                if parent_false and row["parent_id"] is not None:
                    continue
                if parent is not None and row["parent_id"] != parent:
                    continue
                hits.append(row["id"])
            limit = kwargs.get("limit")
            return hits[:limit] if limit else hits
        if method == "read":
            ids = args[0] if args else []
            fields = kwargs.get("fields") or ["name", "action", "web_icon", "parent_id"]
            out = []
            for row in self.menus:
                if row["id"] in ids:
                    out.append({k: row.get(k) for k in ["id", *fields]})
            return out
        if method == "write":
            ids, vals = args[0], args[1]
            for row in self.menus:
                if row["id"] in ids:
                    row.update(vals)
            return True
        if method == "unlink":
            ids = set(args[0])
            self.menus = [m for m in self.menus if m["id"] not in ids]
            return True
        return []


_SPEC = {
    "technical_name": "music_ops",
    "display_name": "Music Production",
    "models": [
        {"model": "x_engagement", "description": "Engagement", "mode": "new"},
        {"model": "x_equipment", "description": "Equipment", "mode": "new"},
        {"model": "x_equipment_line", "description": "Equipment Line", "mode": "new"},
        {"model": "x_artist", "description": "Artist", "mode": "new"},
    ],
    "actions": [
        {"technical_name": "action_x_engagement", "model": "x_engagement", "name": "Engagements"},
        {"technical_name": "action_x_equipment", "model": "x_equipment", "name": "Equipment"},
        {"technical_name": "action_x_equipment_line", "model": "x_equipment_line", "name": "Lines"},
        {"technical_name": "action_x_artist", "model": "x_artist", "name": "Artists"},
    ],
    "menus": [
        {
            "name": "Music Production",
            "xml_id": "menu_root_music",
            "technical_name": "menu_root_music",
            "web_icon": "fa-music,#714B67",
        },
        {
            "name": "Operations",
            "parent_xml_id": "menu_root_music",
            "xml_id": "menu_sub_operations",
            "sequence": 10,
        },
        {
            "name": "Inventory",
            "parent_xml_id": "menu_root_music",
            "xml_id": "menu_sub_inventory",
            "sequence": 20,
        },
        {
            "name": "People",
            "parent_xml_id": "menu_root_music",
            "xml_id": "menu_sub_people",
            "sequence": 30,
        },
        {
            "name": "Engagements",
            "parent_xml_id": "menu_sub_operations",
            "action_xml_id": "action_x_engagement",
        },
        {
            "name": "Equipment",
            "parent_xml_id": "menu_sub_inventory",
            "action_xml_id": "action_x_equipment",
        },
        {
            "name": "Equipment Lines",
            "parent_xml_id": "menu_sub_inventory",
            "action_xml_id": "action_x_equipment_line",
        },
        {
            "name": "Artists",
            "parent_xml_id": "menu_sub_people",
            "action_xml_id": "action_x_artist",
        },
    ],
}


def test_ensure_menus_applies_spec_tree_and_hides_lines() -> None:
    client = _MenuFakeClient()
    result = UiApplyResult()
    _ensure_menus(client, _SPEC, result)
    names = {(m["name"], m["parent_id"]) for m in client.menus}
    root = next(m for m in client.menus if m["parent_id"] is None)
    assert root["name"] == "Music Production"
    assert root["web_icon"] == "base,static/description/icon.png"
    assert result.root_menu_id == root["id"]
    ops = next(m for m in client.menus if m["name"] == "Operations")
    assert ops["parent_id"] == root["id"]
    eng = next(m for m in client.menus if m["name"] == "Engagements")
    assert eng["parent_id"] == ops["id"]
    assert "Equipment Lines" not in {m["name"] for m in client.menus}
    assert result.open_action_id is not None
    assert not any(m["parent_id"] == root["id"] and m["name"] == "Engagements" for m in client.menus)
    _ = names


def test_ensure_menus_unlinks_old_flat_root_children() -> None:
    client = _MenuFakeClient()
    result = UiApplyResult()
    root_id = client.create_menu(name="Music Production", web_icon="fa-music,#714B67")
    stale_action = client.create_window_action(name="Engagements", model="x_engagement")
    client.create_menu(name="Engagements", parent_id=root_id, action_id=stale_action)
    client.create_menu(
        name="Equipment Lines",
        parent_id=root_id,
        action_id=client.create_window_action(name="Lines", model="x_equipment_line"),
    )
    _ensure_menus(client, _SPEC, result)
    root_children = [m["name"] for m in client.menus if m["parent_id"] == root_id]
    assert "Engagements" not in root_children
    assert "Equipment Lines" not in root_children
    assert "Operations" in root_children
    assert "Inventory" in root_children
    assert "People" in root_children


def test_live_safe_web_icon_rejects_font_awesome() -> None:
    from app.spec_apply_ui import _live_safe_web_icon, _spec_web_icon

    assert _live_safe_web_icon("fa-book,#714B67") == "base,static/description/icon.png"
    assert _live_safe_web_icon("fa-th-large,#714B67") == "base,static/description/icon.png"
    assert (
        _live_safe_web_icon("base,static/description/icon.png")
        == "base,static/description/icon.png"
    )
    spec = {
        "menus": [
            {
                "name": "Visitor Log",
                "web_icon": "fa-book,#714B67",
            }
        ]
    }
    assert _spec_web_icon(spec) == "base,static/description/icon.png"


def test_ensure_menus_fallback_excludes_line_models() -> None:
    client = _MenuFakeClient()
    result = UiApplyResult()
    spec = {
        "display_name": "Bare App",
        "models": [
            {"model": "x_job", "description": "Job", "mode": "new"},
            {"model": "x_job_line", "description": "Job Line", "mode": "new"},
        ],
        "menus": [],
        "actions": [],
    }
    _ensure_menus(client, spec, result)
    names = {m["name"] for m in client.menus}
    assert "Bare App" in names
    assert "Job" in names
    assert "Job Line" not in names
    assert result.root_menu_id is not None
