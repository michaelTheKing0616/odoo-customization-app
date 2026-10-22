"""T8-OD-DRIFT answers for majors 17, 18, 19, and 20.

Facts already locked by ``test_read_group_compat``, ``test_name_search_compat``,
and ``test_odoo20_version_table`` are not restated: ``read_group`` versus
``formatted_read_group``, ``name_search`` (not ``name_get``), ``groups_id`` versus
``group_ids``, automation split from server actions, cron ``numbercall``,
accounting and stock renames, external API shape, and Odoo 20 ``ir.access``.

A cell is ``unknown`` when this table does not state it. Live Odoo 20
payloads for kanban, name_get, company-dependent fields, selection storage,
mail template syntax, and translations stay in the client test and are not
copied into this table.
"""

from __future__ import annotations

UNKNOWN = "unknown"
DRIFT_MAJORS: tuple[int, ...] = (17, 18, 19, 20)

# Remaining checklist rows. Covered rows stay on the version table.
DRIFT_ROWS: tuple[str, ...] = (
    "view_modifiers",
    "tree_vs_list",
    "kanban",
    "chatter",
    "get_view",
    "name_get",
    "translations",
    "company_dependent_fields",
    "selection_storage",
    "server_action_states",
    "mail_template_syntax",
)

# Only cells the repo already states. Sources are named in the test module.
_STATED: dict[str, dict[int, str]] = {
    # field_attrs.py: Odoo 16 uses attrs=; 17+ uses direct attributes.
    "view_modifiers": {
        17: "direct attributes",
        18: "direct attributes",
        19: "direct attributes",
        20: "direct attributes",
    },
    # views_v17 stores list as tree. views_v18/v19: list on 18+.
    # Major 20 matches views_v20.list_arch_root (list, including a tree alias).
    "tree_vs_list": {
        17: "tree",
        18: "list",
        19: "list",
        20: "list",
    },
    # ai_odoo_app_bar.inject_chatter_on_forms: Odoo 17+ form chatter sibling.
    "chatter": {
        17: "<chatter/> sibling",
        18: "<chatter/> sibling",
        19: "<chatter/> sibling",
        20: "<chatter/> sibling",
    },
    # OdooClient.get_combined_view_arch: Odoo 17+ get_views.
    "get_view": {
        17: "get_views",
        18: "get_views",
        19: "get_views",
        20: "get_views",
    },
    # i18n_probe: context lang reads are the 17–19 GA path.
    # config_ops export: Odoo 19 works without ir.translation. 20 is unstated.
    "translations": {
        17: "context lang reads",
        18: "context lang reads",
        19: "context lang reads; without ir.translation",
    },
    # automation_v17 / v18 / v19 / v20 comments and re-exports. Not a live probe.
    "server_action_states": {
        17: "same safe-subset encode as v19",
        18: "encoding shared for the safe subset",
        19: (
            "object_write, next_activity, object_create, mail_post, "
            "webhook, sms, followers, remove_followers"
        ),
        20: "re-exports v19 encode",
    },
}


class UnknownDriftRow(KeyError):
    """Named when a checklist row is not one of the remaining T8-OD-DRIFT rows."""


def drift_answer(row: str, major: int) -> str:
    """Return the fake answer for ``row`` at ``major``.

    Majors other than 17, 18, 19, and 20 are refused. Unstated cells are
    ``unknown``. This function does not call Odoo.
    """
    if row not in DRIFT_ROWS:
        raise UnknownDriftRow(row)
    if major not in DRIFT_MAJORS:
        raise ValueError(f"drift checklist is only majors 17–20, not {major}")
    return _STATED.get(row, {}).get(major, UNKNOWN)


def fake_drift_reply(row: str, major: int) -> dict[str, object]:
    """One fake answer. ``probed`` stays false; no live major was contacted."""
    return {
        "row": row,
        "major": major,
        "answer": drift_answer(row, major),
        "probed": False,
    }
