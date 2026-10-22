"""Version grammar facts, one place. Callers ask a question; they never compare majors."""
from __future__ import annotations


def list_view_tag(major: int) -> str:
    """Odoo <=17 list views are <tree>; 18+ use <list>."""
    return "tree" if major <= 17 else "list"


def kanban_card_template(major: int) -> str:
    return "kanban-box" if major <= 17 else "card"


def row_rules_model(major: int) -> str:
    """Odoo 20 expresses row-level limits as ir.access domains; earlier versions use ir.rule."""
    return "ir.access" if major >= 20 else "ir.rule"


def module_for_model(model: str, major: int | None = None) -> str:
    """Odoo app (technical module) that provides ``model`` on 17-20. One place for version renames."""
    from app.ai_host_install import HOST_APPS

    renamed: dict[tuple[str, int], str] = {}  # (model, major) -> module, when a version moves a model
    if major is not None and (model, major) in renamed:
        return renamed[(model, major)]
    hit = (HOST_APPS.get(model) or ("", ""))[0]
    if hit:
        return hit
    from app.ai_conversation.stock_routing import DOMAIN_APPS

    return next((mod for mod, (_n, m) in DOMAIN_APPS.items() if m == model), "")
