"""BV-04: browser walkthrough runner (headless Chromium via the existing @playwright/test).

The script comes only from the change-set: each op kind maps to its BV-03 step id
(coverage.COVERAGE) and this module expands the step id into open/fill/click/assert
steps. The browser returns per-step booleans only; page text never changes the plan.
Logins (D-BV-2): a throwaway ``ingenium_walk_<run>`` user on a disposable clone, or the
integration-key session on an owner-approved connection. Secrets travel by env only.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import tempfile
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from app.bot_verify.coverage import COVERAGE, STEP_LIBRARY_STUB
from app.bot_verify.targets import RESERVED_PORTS, TargetNotAllowed, WalkTarget, is_disposable

STEP_TIMEOUT_S = 20
RUN_TIMEOUT_S = 600
RETRIES = 1
RUN_MJS = Path(__file__).resolve().parents[3] / "web" / "src" / "testing" / "odooWalk" / "run.mjs"
FILL_VALUE = "NF walk value"

Action = Literal["open", "click", "fill", "assert"]

# walk.config.open split per config area (op family -> model).
CONFIG_AREAS: dict[str, str] = {
    "sequence": "ir.sequence",
    "mail_template": "mail.template",
    "activity_type": "mail.activity.type",
    "stage": "crm.stage",
    "config_record": "res.partner",
    "company": "res.company",
}
_TECH_MODEL: dict[str, str] = {
    "walk.constraint.check_state": "ir.model.constraint",
    "walk.action.open": "ir.actions.act_window",
    "walk.menu.open": "ir.ui.menu",
    "walk.filter.apply": "ir.filters",
    "walk.report.render": "ir.actions.report",
    "walk.cron.check_state": "ir.cron",
    "walk.user.check_state": "res.users",
    "walk.module.check_state": "ir.module.module",
    "walk.setting.open": "ir.config_parameter",
}
_AUTOMATION_MODEL = {"server_action": "ir.actions.server", "automation": "base.automation"}
_STEP_IDS = frozenset(STEP_LIBRARY_STUB)
_MODEL_RX = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$")


@dataclass(frozen=True)
class PlanStep:
    index: int
    op_index: int | None
    step_id: str
    action: Action
    target: str
    model: str | None = None
    view: str | None = None
    selector: str | None = None
    value: str | None = None


@dataclass
class WalkStep:
    index: int
    op_index: int | None
    action: Action
    target: str
    passed: bool
    screenshot_id: str | None
    dom_assertion: str | None
    status: Literal["passed", "failed", "skipped"] = "failed"
    reason: str | None = None


@dataclass
class WalkLogin:
    kind: Literal["password", "session"]
    login: str = ""
    secret: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        if len(self.secret) < MIN_SECRET_LEN:
            raise ValueError("walk secret too short")

    def env(self) -> dict[str, str]:
        if self.kind == "session":
            return {"WALK_SESSION": self.secret}
        return {"WALK_LOGIN": self.login, "WALK_PASSWORD": self.secret}


def family_of(kind: str) -> str:
    return kind.rsplit(".", 1)[0]


def _safe_model(m: Any) -> str | None:
    return m if isinstance(m, str) and _MODEL_RX.match(m) else None


def model_for(op: Mapping[str, Any], step_id: str, major: int) -> str:
    kind = str(op.get("type", ""))
    fam = family_of(kind)
    pm = _safe_model((op.get("params") or {}).get("model"))
    if step_id == "walk.config.open":
        return pm if fam in ("stage", "config_record") and pm else CONFIG_AREAS[fam]
    if step_id == "walk.access.as_persona":
        if fam in ("access", "rule"):
            return (
                "ir.access" if major >= 20 else ("ir.rule" if fam == "rule" else "ir.model.access")
            )
        return {"group": "res.groups", "user": "res.users"}.get(fam, "ir.model.fields")
    if step_id == "walk.automation.trigger":
        return _AUTOMATION_MODEL[fam]
    if step_id == "walk.report.render":
        return "ir.actions.report"
    if step_id in _TECH_MODEL:
        return _TECH_MODEL[step_id]
    if step_id == "walk.view.render":
        return pm or "ir.ui.view"
    if step_id == "walk.translation.render":
        return pm or "ir.model.fields"
    return pm or "ir.model"


def build_plan(ops: Sequence[Mapping[str, Any]], *, major: int, disposable: bool) -> list[PlanStep]:
    """Plan from op kinds only; params feed just a validated model name and field name."""
    steps: list[PlanStep] = []

    def add(**kw: Any) -> None:
        steps.append(PlanStep(index=len(steps), **kw))

    # Fill+save only when the same change-set also puts the field's model on a view.
    viewed = {
        _safe_model((o.get("params") or {}).get("model"))
        for o in ops
        if str(o.get("type", "")).startswith("view.inherit.")
    }
    for i, op in enumerate(ops):
        kind = str(op.get("type", ""))
        if kind not in COVERAGE:
            raise ValueError(f"{kind}: op kind has no walkthrough coverage")
        step_id = COVERAGE[kind][1]
        assert step_id in _STEP_IDS
        model = model_for(op, step_id, major)
        view = "form" if step_id == "walk.field.open_form" else "list"
        add(
            op_index=i,
            step_id=step_id,
            action="open",
            target=f"{model}:{view}",
            model=model,
            view=view,
        )
        add(op_index=i, step_id=step_id, action="assert", target=f"{model}:{view}", view=view)
        params = op.get("params") or {}
        fname = params.get("name")
        if (
            disposable
            and kind == "field.create"
            and model in viewed
            and params.get("field_type") == "char"
            and isinstance(fname, str)
            and re.fullmatch(r"x_[a-z0-9_]+", fname)
        ):
            # Record name first when the form has one (often required); optional step.
            add(
                op_index=i,
                step_id=step_id,
                action="fill",
                target="name?",
                selector='.o_field_widget[name="name"] input',
                value=FILL_VALUE,
            )
            sel = f'.o_field_widget[name="{fname}"] input'
            add(
                op_index=i,
                step_id=step_id,
                action="fill",
                target=fname,
                selector=sel,
                value=FILL_VALUE,
            )
            add(op_index=i, step_id=step_id, action="click", target="save", selector="save")
            add(op_index=i, step_id=step_id, action="assert", target=f"{model}:saved", view="saved")
    return steps


def merge_results(plan: Sequence[PlanStep], raw: Any) -> list[WalkStep]:
    """Bind runner output to plan steps by index+action; anything else is dropped."""
    by_idx: dict[int, Mapping[str, Any]] = {}
    for r in raw if isinstance(raw, list) else []:
        if isinstance(r, Mapping) and isinstance(r.get("index"), int):
            by_idx.setdefault(r["index"], r)
    out: list[WalkStep] = []
    for p in plan:
        r = by_idx.get(p.index)
        if r is None or r.get("action") != p.action:
            out.append(
                WalkStep(
                    p.index,
                    p.op_index,
                    p.action,
                    p.target,
                    False,
                    None,
                    None,
                    "failed",
                    "no result",
                )
            )
            continue
        status = r.get("status") if r.get("status") in ("passed", "failed", "skipped") else "failed"
        sid = r.get("screenshot_id")
        sid = sid if isinstance(sid, str) and re.fullmatch(r"[0-9a-f]{32}", sid) else None
        dom = r.get("dom_assertion") if isinstance(r.get("dom_assertion"), str) else None
        reason = r.get("reason") if isinstance(r.get("reason"), str) else None
        out.append(
            WalkStep(
                p.index,
                p.op_index,
                p.action,
                p.target,
                status == "passed",
                sid,
                (dom or "")[:200] or None,
                status,
                (reason or "")[:200] or None,
            )
        )
    return out


_SYSTEM_PREFIXES = ("ir.", "base.", "res.config")
_SYSTEM_MODELS = frozenset(
    {"mail.template", "mail.activity.type", "res.groups", "res.users", "res.company"}
)
# App models -> the least group that can open them (not the app manager unless needed).
_APP_GROUPS: dict[str, tuple[str, str]] = {"crm.": ("sales_team", "group_sale_salesman")}
MIN_SECRET_LEN = 16


@dataclass(frozen=True)
class WalkGroups:
    """Groups derived from a change-set by groups_for; the only input create_walk_user takes."""

    ids: tuple[int, ...]
    xmlids: tuple[str, ...]
    system_gid: int
    system: bool


def needs_system(model: str) -> bool:
    return model.startswith(_SYSTEM_PREFIXES) or model in _SYSTEM_MODELS


def groups_for(ops: Sequence[Mapping[str, Any]], port: Any) -> WalkGroups:
    """D-BV-2: minimum groups for the walk; base.group_user always."""
    major = int(getattr(port, "major", 17))
    plan = build_plan(ops, major=major, disposable=True)
    want: list[tuple[str, str]] = [("base", "group_user")]
    system = False
    for p in plan:
        if p.model and needs_system(p.model):
            system = True
        for prefix, grp in _APP_GROUPS.items():
            if p.model and p.model.startswith(prefix) and grp not in want:
                want.append(grp)
        # A new-record form needs create rights on res.partner (Odoo 19/20 enforce it).
        if p.action == "open" and p.view == "form" and p.model == "res.partner":
            if ("base", "group_partner_manager") not in want:
                want.append(("base", "group_partner_manager"))
    if system:
        want.append(("base", "group_system"))
    sys_gid = int(port.xmlid("base", "group_system"))
    ids = tuple(int(port.xmlid(m, n)) for m, n in want)
    return WalkGroups(ids, tuple(f"{m}.{n}" for m, n in want), sys_gid, system)


def create_walk_user(
    target: WalkTarget, admin: Callable[..., Any], run_id: str, groups: WalkGroups
) -> WalkLogin:
    """D-BV-2: throwaway least-privilege user on a disposable clone only."""
    if target.kind != "disposable_clone" or not is_disposable(target.db_name):
        raise TargetNotAllowed("walk users are only created on disposable clones")
    if not isinstance(groups, WalkGroups):
        raise TypeError("groups must come from groups_for()")
    if groups.system_gid in groups.ids and not groups.system:
        raise TargetNotAllowed("group_system not required by this change-set")
    login = f"ingenium_walk_{re.sub(r'[^a-z0-9]', '', run_id.lower())[:16]}"
    pw = secrets.token_urlsafe(24)
    gkey = "groups_id" if target.major < 19 else "group_ids"
    admin(
        "res.users",
        "create",
        ({"name": login, "login": login, "password": pw, gkey: [(6, 0, list(groups.ids))]},),
    )
    return WalkLogin("password", login, pw)


def session_login(target: WalkTarget, session_id: str) -> WalkLogin:
    if target.kind != "approved_connection":
        raise TargetNotAllowed("integration-key session is for approved connections only")
    return WalkLogin("session", "", session_id)


def _scrub(text: str, secret: str) -> str:
    return text.replace(secret, "***") if secret else text


def _node_runner(
    plan_path: Path, out_dir: Path, env: dict[str, str]
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["node", str(RUN_MJS), "--plan", str(plan_path), "--out", str(out_dir)],
        capture_output=True,
        text=True,
        env=env,
        timeout=RUN_TIMEOUT_S + 30,
    )


def run_walkthrough(
    ops: Sequence[Mapping[str, Any]],
    target: WalkTarget,
    login: WalkLogin,
    bundle_dir: Path,
    *,
    runner: Callable[[Path, Path, dict[str, str]], Any] = _node_runner,
) -> dict[str, Any]:
    """Walk the change-set; write screenshots + bundle.json to bundle_dir; return the bundle."""
    plan = build_plan(ops, major=target.major, disposable=target.kind == "disposable_clone")
    bundle_dir.mkdir(parents=True, exist_ok=True)
    doc = {
        "base_url": target.url,
        "host": target.host,
        "major": target.major,
        "db": target.db_name,
        "step_timeout_ms": STEP_TIMEOUT_S * 1000,
        "run_timeout_ms": RUN_TIMEOUT_S * 1000,
        "retries": RETRIES,
        "reserved_ports": sorted(RESERVED_PORTS),
        "steps": [asdict(p) for p in plan],
    }
    with tempfile.TemporaryDirectory(prefix="ingenium_walk_") as td:
        plan_path = Path(td) / "plan.json"
        plan_path.write_text(json.dumps(doc))
        env = {
            k: v for k, v in os.environ.items() if k in ("PATH", "HOME") or k.startswith("NODE_")
        }
        env.update(login.env())
        try:
            cp = runner(plan_path, bundle_dir, env)
            raw_text = (
                (bundle_dir / "results.json").read_text()
                if (bundle_dir / "results.json").exists()
                else "[]"
            )
            err = _scrub(str(getattr(cp, "stderr", "") or ""), login.secret)[-500:]
        except subprocess.TimeoutExpired:
            raw_text, err = "[]", "run timeout"
    try:
        raw = json.loads(raw_text)
    except ValueError:
        raw = []
    (bundle_dir / "results.json").unlink(missing_ok=True)
    steps = merge_results(plan, raw)
    for s in steps:
        if s.screenshot_id and not (bundle_dir / f"{s.screenshot_id}.png").exists():
            s.screenshot_id = None
    bundle = {
        "run_id": uuid.uuid4().hex,
        "db": target.db_name,
        "major": target.major,
        "status": "passed" if steps and all(s.passed for s in steps) else "failed",
        "steps": [asdict(s) for s in steps],
        "runner_error": err or None,
    }
    text = json.dumps(bundle)
    text = _scrub(text, login.secret)
    (bundle_dir / "bundle.json").write_text(text)
    return bundle
