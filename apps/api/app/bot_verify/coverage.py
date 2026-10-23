"""BV-03: coverage guarantee. Every OP_CATALOG op kind maps to a read-back
(BV-02 ``readback.READBACKS`` key) and a walkthrough step template id.

Pure module: constants only, no RPC/DB/network. BV-04 replaces
STEP_LIBRARY_STUB with its step library and must keep the id set as a superset.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

STEP_LIBRARY_STUB: frozenset[str] = frozenset(
    {
        "walk.model.open_list",
        "walk.field.open_form",
        "walk.constraint.check_state",
        "walk.view.render",
        "walk.action.open",
        "walk.menu.open",
        "walk.filter.apply",
        "walk.report.render",
        "walk.automation.trigger",
        "walk.cron.check_state",
        "walk.config.open",
        "walk.access.as_persona",
        "walk.user.check_state",
        "walk.setting.open",
        "walk.module.check_state",
        "walk.data.list",
        "walk.translation.render",
    }
)

_STEP_BY_OP: dict[str, str] = {
    "model.create": "walk.model.open_list",
    "model.scaffold": "walk.model.open_list",
    "field.create": "walk.field.open_form",
    "field.update": "walk.field.open_form",
    "field.deprecate": "walk.field.open_form",
    "field.delete": "walk.field.open_form",
    "selection.update": "walk.field.open_form",
    "constraint.sql": "walk.constraint.check_state",
    "view.inherit.create": "walk.view.render",
    "view.inherit.update": "walk.view.render",
    "view.archive": "walk.view.render",
    "view.create_base": "walk.view.render",
    "action.window.create": "walk.action.open",
    "action.window.update": "walk.action.open",
    "menu.create": "walk.menu.open",
    "menu.update": "walk.menu.open",
    "menu.archive": "walk.menu.open",
    "filter.create": "walk.filter.apply",
    "filter.update": "walk.filter.apply",
    "report.inherit": "walk.report.render",
    "report.action.create": "walk.report.render",
    "report.action.update": "walk.report.render",
    "server_action.create": "walk.automation.trigger",
    "server_action.update": "walk.automation.trigger",
    "automation.create": "walk.automation.trigger",
    "automation.update": "walk.automation.trigger",
    "automation.disable": "walk.automation.trigger",
    "cron.create": "walk.cron.check_state",
    "cron.update": "walk.cron.check_state",
    "cron.disable": "walk.cron.check_state",
    "sequence.create": "walk.config.open",
    "sequence.update": "walk.config.open",
    "mail_template.create": "walk.config.open",
    "mail_template.update": "walk.config.open",
    "activity_type.create": "walk.config.open",
    "activity_type.update": "walk.config.open",
    "stage.upsert": "walk.config.open",
    "stage.reorder": "walk.config.open",
    "stage.archive": "walk.config.open",
    "config_record.upsert": "walk.config.open",
    "company.update": "walk.config.open",
    "group.create": "walk.access.as_persona",
    "access.create": "walk.access.as_persona",
    "access.update": "walk.access.as_persona",
    "rule.create": "walk.access.as_persona",
    "rule.update": "walk.access.as_persona",
    "field.groups.set": "walk.access.as_persona",
    "user.groups.assign": "walk.access.as_persona",
    "user.create": "walk.user.check_state",
    "user.archive": "walk.user.check_state",
    "setting.set": "walk.setting.open",
    "config_param.set": "walk.setting.open",
    "module.install": "walk.module.check_state",
    "module.upgrade": "walk.module.check_state",
    "module.uninstall": "walk.module.check_state",
    "data.create_batch": "walk.data.list",
    "data.update_batch": "walk.data.list",
    "data.unlink": "walk.data.list",
    "data.archive_batch": "walk.data.list",
    "data.import_upsert": "walk.data.list",
    "data.merge": "walk.data.list",
    "data.delete": "walk.data.list",
    "translation.upsert": "walk.translation.render",
}

# Read-back name is the op kind key in readback.READBACKS (BV-02 binds per op).
COVERAGE: dict[str, tuple[str, str]] = {op: (op, step) for op, step in _STEP_BY_OP.items()}


def check_coverage(
    catalog: Iterable[str],
    coverage: Mapping[str, tuple[str | None, str | None]],
    step_ids: Iterable[str],
) -> list[str]:
    """Return one error per problem; each names the op kind. [] means covered."""
    cat = set(catalog)
    steps = set(step_ids)
    errs: list[str] = []
    for op in sorted(cat - set(coverage)):
        errs.append(f"{op}: op kind has no coverage entry (readback + step)")
    for op in sorted(set(coverage) - cat):
        errs.append(f"{op}: coverage lists unknown op kind")
    for op in sorted(cat & set(coverage)):
        rb, step = coverage[op]
        if not rb:
            errs.append(f"{op}: missing readback")
        if not step:
            errs.append(f"{op}: missing walkthrough step")
        elif step not in steps:
            errs.append(f"{op}: walkthrough step {step!r} not in step library")
    return errs
