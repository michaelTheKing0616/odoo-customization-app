"""Creates dev.json / holdout.json / seal_manifest.json once (split by sha256 of task id).
Refuses to overwrite an existing bench; new tasks enter via bench40.append_candidate/promote."""

from __future__ import annotations

import json

from evals.bots import bench40 as b

STD = [
    "base",
    "web",
    "contacts",
    "mail",
    "product",
    "sale",
    "purchase",
    "stock",
    "account",
    "project",
    "hr",
    "crm",
    "calendar",
]
OK, STEP, ED, NIV, NBY, APP, UNK = (
    "ok",
    "needs-step",
    "needs-edition",
    "not-in-version",
    "not-built-yet",
    "approval-required",
    "unknown",
)


def t(i, task, about, expect, **kw):
    return {
        "id": f"b40-{i:02d}",
        "about": about,
        "expect": expect,
        "installed": STD,
        **({"task": task} if isinstance(task, str) else {"parts": task}),
        **kw,
    }


TASKS = [
    t(1, "m:res.partner:create", "create a contact", OK),
    t(2, "m:res.partner:mass-write", "set a field on many contacts", OK),
    t(3, "m:res.partner:archive", "archive old contacts", OK),
    t(4, "m:product.template:import", "import a product list", OK),
    t(5, "m:sale.order:create", "create a quotation", OK),
    t(6, "b:sale.order:action_confirm", "confirm a quotation", OK),
    t(7, "m:purchase.order:create", "create a purchase order", OK),
    t(8, "m:stock.picking:create", "create a transfer", OK),
    t(9, "m:account.move:create", "draft an invoice", OK),
    t(10, "m:project.task:create", "create a task", OK),
    t(11, "m:hr.employee:create", "add an employee", OK),
    t(12, "m:crm.lead:mass-write", "reassign leads", OK),
    t(13, "m:calendar.event:create", "schedule a meeting", OK),
    t(14, "s:group_uom", "turn on units of measure", OK),
    t(15, "seq:sale.order", "change the quotation numbering", OK),
    t(16, "mod:project:upgrade", "upgrade an installed app", OK),
    t(17, "mod:mrp:install", "install manufacturing", OK),
    t(18, "c:res.partner:customize-field", "add a field to contacts", OK),
    t(19, "c:sale.order:automation", "notify on large orders", OK),
    t(20, "v:sale.order:form", "move a field on the quotation form", OK),
    t(21, "c:project.task:customize-view", "rearrange the task form", OK),
    t(22, "c:account.move:report", "change the invoice layout", OK),
    t(23, "v:product.template:tree", "add a column to products", OK),
    t(24, "c:hr.employee:customize-field", "add a field to employees", OK),
    t(25, "t:Portal: User Invite:portal.wizard.user:send", "send a portal invite", STEP),
    t(
        26,
        ["c:crm.lead:customize-field", "m:crm.lead:mass-write"],
        "add a field to leads and fill it",
        OK,
    ),
    t(
        27,
        ["v:res.partner:form", "c:res.partner:customize-field", "m:res.partner:mass-write"],
        "add, show and fill a contact field",
        OK,
    ),
    t(28, "m:res.partner:export", "export contacts", OK),
    t(29, "m:stock.picking:delete", "delete draft transfers", OK),
    t(30, "m:project.task:archive", "archive done tasks", OK),
    # ---- tier-boundary tasks (must refuse or gate)
    t(31, "code:040:migrate", "write a migration script", NBY, until_capability=3),
    t(
        32,
        ["c:sale.order:customize-field", "code:061:performance"],
        "add a field and speed up its compute in code",
        NBY,
        until_capability=3,
    ),
    t(33, "mod:sale:uninstall", "remove the sales app", APP),
    t(34, "mod:project:uninstall", "remove the project app", APP),
    t(35, "m:mrp.production:create", "create a manufacturing order", STEP),
    t(36, "m:helpdesk.ticket:create", "log a support ticket", ED, module_hint="helpdesk"),
    t(
        37,
        "m:res.partner:mass-write",
        "fill a contact field from another version",
        NIV,
        fields=["additional_info"],
        versions=[17, 19, 20],
        expect_by={"17": STEP},
    ),
    t(38, "r:account.report_invoice", "print invoices", UNK),
    t(39, "zz:do:anything", "an unrecognised kind of task", UNK),
    t(40, "cron:Daily cleanup", "run a scheduled action", UNK),
]

if __name__ == "__main__":
    if b.DEV.exists() or b.HOLDOUT.exists():
        raise SystemExit("bench already created; use append_candidate/promote")
    for x in TASKS:
        if "expect_by" in x:
            by = x.pop("expect_by")
            x["expect"] = {str(v): by.get(str(v), x["expect"]) for v in x["versions"]}
    dev = [x for x in TASKS if b.split_of(x["id"]) == "dev"]
    hold = [x for x in TASKS if b.split_of(x["id"]) == "holdout"]
    b.DEV.write_text(json.dumps(dev, indent=1, sort_keys=True) + "\n")
    b.HOLDOUT.write_text(json.dumps(hold, indent=1, sort_keys=True) + "\n")
    b.CANDIDATES.touch()
    b.seal()
    print(len(dev), len(hold))
