"""Studio-doc feature recipes → public ORM honesty (M2-P0c).

Maps the 14 Studio "suggested features" to what this app can do via
``ir.model.fields`` / ``ir.ui.view`` / Option A — never Studio source.
"""

from __future__ import annotations

from typing import Any, Literal

Status = Literal["supported", "partial", "option_a", "module_gated", "unavailable"]

FEATURE_RECIPES: list[dict[str, Any]] = [
    {
        "id": "contact_details",
        "name": "Contact details",
        "status": "partial",
        "how": (
            "Add many2one → res.partner (or related phone/email fields) in Builder; "
            "enable Map view on Designer with res_partner pointing at that m2o."
        ),
        "app_surfaces": ["builder", "designer:map"],
    },
    {
        "id": "user_assignment",
        "name": "User assignment",
        "status": "partial",
        "how": "Add many2one → res.users in Builder; show on form/list/kanban.",
        "app_surfaces": ["builder", "designer"],
    },
    {
        "id": "date_calendar",
        "name": "Date & Calendar",
        "status": "supported",
        "how": "Date/datetime field + Designer Calendar view (date_start required).",
        "app_surfaces": ["builder", "designer:calendar"],
    },
    {
        "id": "date_range_gantt",
        "name": "Date range & Gantt",
        "status": "module_gated",
        "how": (
            "Designer Gantt arch (date_start/date_stop). Requires web_gantt / project "
            "(or equivalent) on the target DB — grey-out/honesty when absent."
        ),
        "app_surfaces": ["designer:gantt"],
    },
    {
        "id": "pipeline_kanban",
        "name": "Pipeline stages",
        "status": "supported",
        "how": "Selection/many2one stage field + Designer Kanban default_group_by.",
        "app_surfaces": ["builder", "designer:kanban"],
    },
    {
        "id": "picture",
        "name": "Picture",
        "status": "supported",
        "how": "Binary field + widget image on form.",
        "app_surfaces": ["builder", "designer:form"],
    },
    {
        "id": "lines",
        "name": "Lines (O2M)",
        "status": "partial",
        "how": "one2many field + embedded list; deep line editor polish still evolving.",
        "app_surfaces": ["builder", "designer:form"],
    },
    {
        "id": "notes",
        "name": "Notes (HTML)",
        "status": "supported",
        "how": "Html field on form.",
        "app_surfaces": ["builder", "designer:form"],
    },
    {
        "id": "monetary_graph_pivot",
        "name": "Monetary + Graph/Pivot",
        "status": "supported",
        "how": (
            "Monetary field with currency_field in Builder; Designer Graph/Pivot views "
            "for measures/axes."
        ),
        "app_surfaces": ["builder", "designer:graph", "designer:pivot"],
    },
    {
        "id": "company",
        "name": "Company",
        "status": "supported",
        "how": "many2one → res.company (multi-company aware on target).",
        "app_surfaces": ["builder"],
    },
    {
        "id": "custom_sorting",
        "name": "Custom Sorting (handle)",
        "status": "partial",
        "how": "Integer sequence field + list widget=handle; default_order on list root.",
        "app_surfaces": ["builder", "designer:list"],
    },
    {
        "id": "chatter",
        "name": "Chatter",
        "status": "option_a",
        "how": "mail.thread mixins usually need module inherit (Option A) or mail helpers.",
        "app_surfaces": ["option_a", "mail"],
    },
    {
        "id": "archiving",
        "name": "Archiving",
        "status": "partial",
        "how": "Boolean active field; archive automations via on_archive triggers.",
        "app_surfaces": ["builder", "automations"],
    },
    {
        "id": "existing_fields_inject",
        "name": "Add existing fields to views",
        "status": "supported",
        "how": "Designer / Builder inject existing ir.model.fields into form/list/search arches.",
        "app_surfaces": ["builder", "designer"],
    },
]

def list_feature_recipes() -> list[dict[str, Any]]:
    return [dict(r) for r in FEATURE_RECIPES]
