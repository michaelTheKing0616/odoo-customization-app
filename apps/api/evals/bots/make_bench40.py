"""Creates dev.json / holdout.json / seal_manifest.json (split by sha256 of task id).

Refuses to overwrite an existing bench; new tasks enter via bench40.append_candidate/promote.
A reviewed correction may rebuild it: ``EVAL_UNSEAL=yes python -m evals.bots.make_bench40
--correct <reviewer> <note>`` (recorded in the seal history).

Expectations are reasoned from real Odoo (manifests, field definitions in the odoo:17..20
images), never from tiers.py output. Installed lists are the owner's apps closed over real
manifest depends + auto_install (bench40.closure).
"""

from __future__ import annotations

import json
import os
import sys

from evals.bots import bench40 as b

APPS = [
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
VERSIONS = (17, 18, 19, 20)
# Field present in 17/18 only (verified in the odoo images' source): 19/20 removed it.
GONE_AFTER_18 = {"17": OK, "18": OK, "19": NIV, "20": NIV}


def t(i, task, about, expect, **kw):
    return {
        "id": f"b40-{i:02d}",
        "about": about,
        "expect": expect,
        "apps": APPS,
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
    t(23, "c:hr.employee:customize-field", "add a field to employees", OK),
    # portal is a real dependency of sale/account, so it is installed and the invite is ok.
    t(24, "t:Portal: User Invite:portal.wizard.user:send", "send a portal invite", OK),
    t(
        25,
        [
            "c:crm.lead:customize-field",
            {"task": "m:crm.lead:mass-write", "fields": ["x_rating"]},
        ],
        "add a field to leads and fill it",
        OK,
    ),
    t(
        26,
        [
            "v:res.partner:form",
            "c:res.partner:customize-field",
            {"task": "m:res.partner:mass-write", "fields": ["x_tier"], "module_hint": "base"},
        ],
        "add, show and fill a contact field",
        OK,
    ),
    t(27, "m:res.partner:export", "export contacts", OK),
    # ---- tier-boundary tasks: two per refusal grade, one in each split (ids chosen by hash)
    t(28, "m:mrp.production:create", "create a manufacturing order", STEP, module_hint="mrp"),
    t(
        29,
        "m:maintenance.request:create",
        "log an equipment repair request",
        STEP,
        module_hint="maintenance",
    ),
    t(30, "m:helpdesk.ticket:create", "log a support ticket", ED, module_hint="helpdesk"),
    t(31, "m:approval.request:create", "raise an approval request", ED, module_hint="approvals"),
    t(
        32,
        "m:crm.lead:mass-write",
        "fill the lead mobile number",
        GONE_AFTER_18,
        fields=["mobile"],
        module_hint="crm",
    ),
    t(
        33,
        "m:res.partner:mass-write",
        "fill the contact additional info",
        GONE_AFTER_18,
        fields=["additional_info"],
        module_hint="partner_autocomplete",
    ),
    t(34, "mod:project:uninstall", "remove the project app", APP),
    t(35, "mod:sale:uninstall", "remove the sales app", APP),
    t(
        36,
        ["c:sale.order:customize-field", "code:061:performance"],
        "add a field and speed up its compute in code",
        NBY,
        until_capability=3,
    ),
    t(37, "cron:Daily cleanup", "run a scheduled action", UNK),
    t(38, "m:stock.picking:delete", "delete draft transfers", OK),
    t(39, "code:040:migrate", "write a migration script", NBY, until_capability=3),
    t(40, "zz:do:anything", "an unrecognised kind of task", UNK),
]


def build() -> tuple[list, list]:
    out = []
    for x in TASKS:
        x = dict(x, installed={str(v): b.closure(x["apps"], v) for v in VERSIONS})
        b.check_task(x)
        out.append(x)
    dev = [x for x in out if b.split_of(x["id"]) == "dev"]
    hold = [x for x in out if b.split_of(x["id"]) == "holdout"]
    return dev, hold


if __name__ == "__main__":
    correct = sys.argv[1:2] == ["--correct"]
    if (b.DEV.exists() or b.HOLDOUT.exists()) and not correct:
        raise SystemExit("bench already created; use append_candidate/promote")
    if correct and (os.environ.get("EVAL_UNSEAL") != "yes" or len(sys.argv) < 4):
        raise SystemExit("--correct needs EVAL_UNSEAL=yes, a reviewer and a note")
    dev, hold = build()
    for path, rows in ((b.DEV, dev), (b.HOLDOUT, hold)):
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(rows, indent=1, sort_keys=True) + "\n")
        tmp.replace(path)
    b.CANDIDATES.touch()
    b.seal(
        sys.argv[2] if correct else os.environ.get("EVAL_REVIEWER", ""),
        note=" ".join(sys.argv[3:]) or "created",
    )
    print(len(dev), len(hold))
