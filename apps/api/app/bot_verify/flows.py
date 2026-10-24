"""BV-05: business-flow layer of VERIFY, run only on a disposable clone.

The clone is made from the source DB by the caller's ``make_clone`` and is
always dropped afterwards (the drop is checked). Each flow step acts over RPC
and then reads its record back; the read-back value is the only evidence.
A failed flow step sets the run to ``failed`` and applies the existing
verify.py rule: R2+ rolls back, lower risk is NEEDS_HUMAN with the runbook.
Platform notices (saved OK, Odoo shows non-admins an Access Error) and
change-sets that create a model with no access rule are findings that make
the run NEEDS_HUMAN, never a rollback.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.bot_verify.flow_library import APP_GROUPS, Ctx, Flow, flows_for
from app.bot_verify.targets import TargetNotAllowed, WalkTarget, resolve_target
from app.bot_verify.walkthrough import WalkGroups, groups_for, run_walkthrough, walk_user
from app.changeset import verify as verify_mod

CLONE_PREFIX = "ingenium_nf_bv_clone_"
CLONE_RX = re.compile(r"^ingenium_nf_bv_clone_[a-z0-9_]+$")
DIALOG_REASON = "present:.o_error_dialog"

NOTICE_ACCESS_DIALOG = (
    "Saved correctly. Odoo then shows non-admin users an Access Error "
    "(a platform permission notice, e.g. iap.account on Odoo 20). "
    "Nothing to roll back; a person should check whether users will see it."
)
NOTICE_MODEL_NO_ACL = (
    "The change creates the model {model} but gives no access rule for it, "
    "so only administrators can use it. Add an access rule for the right group."
)


@dataclass
class FlowStepResult:
    app: str
    flow: str
    step: str
    model: str | None
    res_id: int | None
    status: str  # passed | failed | skipped
    observed: Any = None
    reason: str | None = None
    screenshot_id: str | None = None


def clone_name(run_id: str | None = None) -> str:
    tail = re.sub(r"[^a-z0-9]", "", (run_id or uuid.uuid4().hex).lower())[:16] or "x"
    return CLONE_PREFIX + tail


def require_clone(port: Any, source_db: str | None = None) -> None:
    """AC2: flows refuse any DB that is not an ingenium_nf_bv_clone_* clone."""
    db = str(getattr(port, "db_name", "") or "")
    if not CLONE_RX.match(db) or (source_db is not None and db == source_db):
        raise TargetNotAllowed("business flows run only on an ingenium_nf_bv_clone_* clone")


def acl_gaps(changeset: Sequence[Mapping[str, Any]]) -> list[str]:
    created = [
        str((op.get("params") or {}).get("model") or "")
        for op in changeset
        if op.get("type") in ("model.create", "model.scaffold")
    ]
    covered = {
        str((op.get("params") or {}).get("model") or "")
        for op in changeset
        if op.get("type") in ("access.create", "access.update")
    }
    return [m for m in created if m and m not in covered]


def _read(port: Any, model: str, rid: int, fname: str) -> Any:
    rows = port.admin(model, "read", ([rid], [fname]))
    return rows[0].get(fname) if rows else None


def run_flow_steps(
    port: Any, flows: Sequence[Flow], *, source_db: str | None = None
) -> list[FlowStepResult]:
    require_clone(port, source_db)
    out: list[FlowStepResult] = []
    for flow in flows:
        ctx: Ctx = {}
        broken = False
        for st in flow.steps:
            if broken:
                out.append(
                    FlowStepResult(
                        flow.app,
                        flow.name,
                        st.name,
                        None,
                        None,
                        "skipped",
                        reason="earlier step failed",
                    )
                )
                continue
            try:
                model, rid = st.run(port, ctx)
                seen = _read(port, model, rid, st.field)
            except Exception as exc:  # noqa: BLE001 - Odoo refusals are the flow verdict
                msg = getattr(exc, "faultString", None) or str(exc)
                out.append(
                    FlowStepResult(
                        flow.app, flow.name, st.name, None, None, "failed", reason=_short(msg)
                    )
                )
                broken = True
                continue
            ok = seen in st.expect
            out.append(
                FlowStepResult(
                    flow.app,
                    flow.name,
                    st.name,
                    model,
                    rid,
                    "passed" if ok else "failed",
                    observed=seen,
                    reason=None
                    if ok
                    else f"{st.field}={seen!r}, expected one of {list(st.expect)!r}",
                )
            )
            broken = not ok
    return out


def _short(msg: str) -> str:
    lines = [ln.strip() for ln in str(msg).splitlines() if ln.strip()]
    return (lines[-1] if lines else "error")[:200]


def flow_groups(port: Any, apps: Sequence[str]) -> WalkGroups:
    """Least groups to open the flows' records: base.group_user + each app's user group."""
    extra: list[tuple[str, str]] = []
    for app in sorted(set(apps)):
        for g in APP_GROUPS.get(app, ()):
            if g not in extra:
                extra.append(g)
    return groups_for([], port, app_groups=extra)


def attach_screenshots(results: list[FlowStepResult], bundle: Mapping[str, Any]) -> list[str]:
    """Bind walkthrough 'open' screenshots to flow steps (op_index == result index).

    Returns platform notices (F6). A walk failure on a step whose RPC read-back
    passed is never a PASS: an Access Error dialog becomes a notice, anything
    else marks the step skipped with the walk reason.
    """
    notices: list[str] = []
    by_op: dict[int, list[Mapping[str, Any]]] = {}
    for s in bundle.get("steps") or []:
        if isinstance(s.get("op_index"), int):
            by_op.setdefault(s["op_index"], []).append(s)
    for i, r in enumerate(results):
        if r.status != "passed":
            continue
        walk = by_op.get(i) or []
        for s in walk:
            if s.get("action") == "open" and s.get("screenshot_id"):
                r.screenshot_id = s["screenshot_id"]
        bad = [s for s in walk if s.get("status") != "passed"]
        if not walk:
            r.status, r.reason = "skipped", "no walkthrough evidence"
        elif bad:
            why = str(bad[0].get("reason") or "")
            if why.startswith(DIALOG_REASON):
                if NOTICE_ACCESS_DIALOG not in notices:
                    notices.append(NOTICE_ACCESS_DIALOG)
                r.reason = "platform notice: " + NOTICE_ACCESS_DIALOG
            else:
                r.status, r.reason = "skipped", f"walkthrough: {why[:150] or 'failed'}"
    return notices


def walk_flow_steps(
    port: Any,
    results: list[FlowStepResult],
    *,
    url: str,
    bundle_dir: Path,
    runner: Callable[..., Any] | None = None,
) -> list[str]:
    """Screenshot each passed step's record list as a least-privilege walk user."""
    require_clone(port)
    target: WalkTarget = resolve_target(url=url, db_name=port.db_name, major=int(port.major))
    ops = [
        {"type": "view.inherit.update", "params": {"model": r.model or "res.partner"}}
        for r in results
    ]
    groups = flow_groups(port, sorted({r.app for r in results}))
    kw = {"runner": runner} if runner else {}
    with walk_user(target, port.admin, uuid.uuid4().hex, groups) as login:  # F5: always deleted
        bundle = run_walkthrough(ops, target, login, bundle_dir, **kw)
    return attach_screenshots(results, bundle)


def decide(
    changeset: list[dict[str, Any]],
    results: Sequence[FlowStepResult],
    findings: Sequence[str] = (),
) -> dict[str, Any]:
    """Run status from flow evidence; reuses verify.py's R2 rollback floor."""
    failed = [r for r in results if r.status == "failed"]
    skipped = [r for r in results if r.status == "skipped"]
    risk = verify_mod._plan_risk(changeset)
    runbook = None
    compensations: list[dict[str, Any]] = []
    if failed:
        layer = "failed"
        if verify_mod._rank(risk) >= verify_mod._rank(verify_mod._ROLLBACK_FLOOR):
            status = "rolled_back"
            compensations = verify_mod._compensations(changeset)
            verify_mod._ROLLBACK_LOG.append(
                {
                    "risk": risk,
                    "compensations": list(compensations),
                    "status": "ROLLED_BACK",
                    "layer": "flows",
                }
            )
        else:
            status, runbook = "needs_human", verify_mod.RUNBOOK_VERIFY_FAILED
    elif not results:
        layer, status = "skipped", ("needs_human" if findings else "passed")
    elif skipped or findings:
        layer, status = ("skipped" if skipped else "passed"), "needs_human"
    else:
        layer, status = "passed", "passed"
    return {
        "status": status,
        "layer": {"layer": "flows", "status": layer},
        "risk": risk,
        "runbook": runbook,
        "compensations": compensations,
        "findings": list(findings),
        "failed": [f"{r.app}.{r.flow}.{r.step}" for r in failed],
    }


def run_flows(
    changeset: list[dict[str, Any]],
    *,
    source_db: str,
    installed: set[str],
    make_clone: Callable[[str, str], Any],
    drop_clone: Callable[[str], None],
    clone_exists: Callable[[str], bool],
    walk: Callable[[Any, list[FlowStepResult]], list[str]] | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Clone -> run flows -> (walk) -> decide; the clone is dropped on every path."""
    name = clone_name(run_id)
    if name == source_db or not CLONE_RX.match(name):
        raise TargetNotAllowed("clone name must differ from the source DB")
    flows = flows_for(changeset, installed)
    findings = [NOTICE_MODEL_NO_ACL.format(model=m) for m in acl_gaps(changeset)]
    results: list[FlowStepResult] = []
    try:
        port = make_clone(source_db, name)
        require_clone(port, source_db)
        results = run_flow_steps(port, flows, source_db=source_db)
        if walk is not None and results:
            findings += walk(port, results)
    finally:
        drop_clone(name)
        if clone_exists(name):
            raise RuntimeError(f"clone {name} was not dropped")
    report = decide(changeset, results, findings)
    report.update(clone=name, clone_dropped=True, steps=[asdict(r) for r in results])
    return report
