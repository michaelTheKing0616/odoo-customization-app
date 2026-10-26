"""BOT-MODULE-AUTHORING: requirement -> reviewable module authoring result (data only).

No card exists in docs/build-plan/cards; scope derived from tiers.py (T3 needs
"module-authoring" + "module-test-gate") and the T3 card chain (req2mod, code_audit,
owned_change, module_test_gate, debug_notes).

Pipeline: req2mod spec -> module zip -> code_audit -> module_test_gate (sandbox) ->
debug_notes classification -> bounded repair loop (each repair is an owned_change ChangeSet
on the generated module only, re-audited and re-gated; stops on the first non-improving or
repeated failure) -> AuthoringResult. ``promotable`` is exactly gate_passed(report, hash).

It never installs on a client database and never applies anything outside its private
scratch copy of the generated module: the result is data for the approval spine.
It does not flip any tier: see ``tiers.MODULE_AUTHORING_REVIEWED`` and
``derived_capability``.
"""

from __future__ import annotations

import copy
import io
import tempfile
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from module_generator import build_module_zip

from app.bots import code_audit as ca
from app.bots import debug_notes as dn
from app.bots import module_test_gate as gate
from app.bots import owned_change as oc
from app.bots import req2mod as rm
from app.bots import tiers as tt

SCHEMA = "module-authoring/1"
MAX_ATTEMPTS = 5
DEFAULT_ATTEMPTS = 3
_BLOCK = ("high", "medium")
_CTX_KEYS = frozenset({"owner", "purpose", "decision", "approver", "ticket"})

Repairer = Callable[[Mapping[str, Any]], "list[oc.Edit] | None"]


class AuthoringError(ValueError):
    pass


@dataclass
class Attempt:
    n: int
    change_set_id: str = ""
    adopted: bool = False
    outcome: str = ""  # adopted | non-improving | repeated-failure | refused:<code> | no-repair
    score: tuple[int, int] | None = None
    failing: list[str] = field(default_factory=list)


@dataclass
class AuthoringResult:
    schema: str
    ok: bool  # pipeline ran to a verdict (not "the module is good": see promotable)
    stage: str  # where it stopped: input | spec | build | gate | done
    error: str
    module: str
    version: int | None
    owner_context: dict[str, str]
    module_hash: str = ""
    gate_report: dict[str, Any] | None = None
    audit_counts: dict[str, int] = field(default_factory=dict)
    trace: dict[str, list[str]] = field(default_factory=dict)  # requirement item -> spec elems
    assumptions: list[str] = field(default_factory=list)
    change_sets: list[dict[str, Any]] = field(default_factory=list)  # adopted, in order
    attempts: list[Attempt] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # debug_notes ids of remaining failures
    stop_reason: str = ""
    promotable: bool = False
    applied: bool = False  # always False: nothing is installed or applied anywhere
    files: dict[str, bytes] = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("files")
        return d

    def approval_plan(self) -> dict[str, Any]:
        """Facts for the approval spine (BOT-SPINE-WIRE). Always top tier, never auto-run."""
        return {
            "kind": "module_authoring",
            "schema": SCHEMA,
            "module": self.module,
            "version": self.version,
            "module_hash": self.module_hash,
            "promotable": self.promotable,
            "tier": "L3",
            "owner_context": self.owner_context,
            "change_set_ids": [c["change_set_id"] for c in self.change_sets],
            "stop_reason": self.stop_reason,
        }


# ---------------------------------------------------------------- helpers


def _files_of(zip_bytes: bytes) -> dict[str, bytes]:
    z = zipfile.ZipFile(io.BytesIO(zip_bytes))
    out = {}
    for n in z.namelist():
        if not n.endswith("/") and "/" in n:
            out[n.split("/", 1)[1]] = z.read(n)
    return out


def _ctx(owner_context: Any) -> dict[str, str]:
    if not isinstance(owner_context, Mapping) or set(owner_context) - _CTX_KEYS:
        raise AuthoringError(f"owner context keys must be a subset of {sorted(_CTX_KEYS)}")
    out = {}
    for k, v in owner_context.items():
        if not isinstance(v, str) or not 0 < len(v) <= 300 or dn._LINE_CTRL.search(v):
            raise AuthoringError(f"owner context {k} must be one line of 1-300 characters")
        out[k] = dn.redact(v)
    if not out.get("owner"):
        raise AuthoringError("owner context needs an owner")
    return out


def _blocking(rep: ca.Report) -> list[ca.Finding]:
    return [f for f in rep.findings if f.severity in _BLOCK]


def _failing(rep: gate.GateReport) -> list[str]:
    return sorted(
        f"{k}:{c.status}:{','.join(c.notes)}" for k, c in rep.checks.items() if c.status != "pass"
    )


def _score(rep: gate.GateReport, aud: ca.Report) -> tuple[int, int]:
    return (sum(c.status != "pass" for c in rep.checks.values()), len(_blocking(aud)))


def _key(rep: gate.GateReport, aud: ca.Report) -> tuple:
    return (tuple(_failing(rep)), tuple(sorted((f.code, f.file) for f in _blocking(aud))))


def restore_generated(ctx: Mapping[str, Any]) -> list[oc.Edit] | None:
    """Default repairer, deterministic: restore files implicated by blocking audit findings to
    what the generator produced from the spec. Returns None when nothing is implicated or the
    implicated files already match (a gate failure without a file is not guessed at)."""
    files, gen = ctx["files"], ctx["generated"]
    implicated = {f.file for f in ctx["audit_findings"] if f.file}
    if any(f.code == "access-missing" for f in ctx["audit_findings"]):
        implicated |= {p for p in gen if p.startswith("security/")}
    edits = []
    for p in sorted(implicated):
        if p in gen and files.get(p) != gen[p]:
            kind = "replace_file" if p in files else "add_file"
            edits.append(oc.Edit(p, kind, gen[p].decode("utf-8")))
        elif p not in gen and p in files:
            edits.append(oc.Edit(p, "delete_file"))
    return edits or None


def _run_gate(files, module, version, runner, tmp_root):
    return gate.run_gate(files, module=module, version=version, runner=runner, tmp_root=tmp_root)


# ---------------------------------------------------------------- entry point


def author(
    requirement: Any,
    *,
    version: Any,
    owner_context: Any,
    technical_name: Any,
    installed_modules: Any = ("base",),
    runner: gate.Runner | None = None,
    repairer: Repairer | None = restore_generated,
    max_attempts: int = DEFAULT_ATTEMPTS,
    seed: Callable[[dict[str, bytes]], dict[str, bytes]] | None = None,
    tmp_root: str = "/tmp",
) -> AuthoringResult:
    """Produce an AuthoringResult. Never raises on bad input; never installs or applies.

    ``seed`` mutates the generated files before the first audit (seeded-defect testing only);
    the repairer still sees the pristine generator output as ``generated``."""
    name = technical_name if isinstance(technical_name, str) else ""
    res = AuthoringResult(SCHEMA, False, "input", "", name, None, {})
    try:
        if type(version) is not int or version not in rm.VERSIONS:
            raise AuthoringError(f"version must be one of {rm.VERSIONS}")
        res.version = version
        res.owner_context = _ctx(owner_context)
        if type(max_attempts) is not int or not 0 <= max_attempts <= MAX_ATTEMPTS:
            raise AuthoringError(f"max_attempts must be 0..{MAX_ATTEMPTS}")
        if not isinstance(installed_modules, (list, tuple)):
            raise AuthoringError("installed modules must be a list")
    except AuthoringError as e:
        res.error = str(e)
        return res
    res.stage = "spec"
    built = rm.build(
        copy.deepcopy(requirement),
        version=version,
        installed_modules=list(installed_modules),
        technical_name=technical_name,
    )
    if not built.ok or built.spec is None:
        res.error = "; ".join(built.errors)[:2000] or "requirement not buildable"
        return res
    res.trace = {k: list(v) for k, v in built.trace.items()}
    res.assumptions = list(built.assumptions)
    res.stage = "build"
    try:
        generated = _files_of(build_module_zip(built.spec, odoo_major=version))
        files = dict(generated)
        if seed is not None:
            files = dict(seed(dict(files)))
    except Exception as e:  # noqa: BLE001 - fail closed
        res.error = f"module build failed ({type(e).__name__})"
        return res
    res.stage = "gate"
    try:
        aud = ca.audit(oc._zip(name, files), version=version, owned_names={name})
        rep = _run_gate(files, name, version, runner, tmp_root)
    except gate.GateError as e:
        res.error = f"gate refused: {e}"
        return res
    if not aud.ok:
        res.error = f"audit failed: {aud.error}"
        return res
    best, seen = _score(rep, aud), {_key(rep, aud)}
    for n in range(1, max_attempts + 1):
        if gate.gate_passed(rep, gate.module_hash(files)):
            break
        att = Attempt(n)
        res.attempts.append(att)
        ctx = {
            "files": dict(files),
            "generated": dict(generated),
            "audit_findings": _blocking(aud),
            "gate_report": rep,
            "notes": sorted({x for c in rep.checks.values() for x in c.notes}),
            "version": version,
        }
        edits = repairer(ctx) if repairer else None
        if not edits:
            att.outcome = "no-repair"
            break
        try:
            with tempfile.TemporaryDirectory(prefix="inauthor-", dir=tmp_root) as td:
                root = Path(td) / name
                for p, b in files.items():
                    (root / p).parent.mkdir(parents=True, exist_ok=True)
                    (root / p).write_bytes(b)
                cs = oc.build_change_set(
                    root,
                    oc.ChangeRequest(name, tuple(edits), f"authoring repair {n}"),
                    version=version,
                    owned_names={name},
                )
            new_files = oc.apply_change_set(files, cs, approved_id=cs.id)  # scratch copy only
        except oc.ChangeError as e:
            att.outcome = f"refused:{e.code}"
            break
        att.change_set_id = cs.id
        aud2 = ca.audit(oc._zip(name, new_files), version=version, owned_names={name})
        rep2 = _run_gate(new_files, name, version, runner, tmp_root)
        att.score, att.failing = _score(rep2, aud2), _failing(rep2)
        passed = gate.gate_passed(rep2, gate.module_hash(new_files))
        if not passed and _key(rep2, aud2) in seen:
            att.outcome = "repeated-failure"
            break
        if not passed and att.score >= best:
            att.outcome = "non-improving"
            break
        att.adopted, att.outcome = True, "adopted"
        res.change_sets.append({**cs.approval_plan(), "diff": cs.diff})
        files, aud, rep, best = new_files, aud2, rep2, att.score
        seen.add(_key(rep, aud))
    res.files = files
    res.module_hash = gate.module_hash(files)
    res.gate_report = rep.to_dict()
    res.audit_counts = dict(aud.counts)
    res.notes = sorted({x for c in rep.checks.values() if c.status != "pass" for x in c.notes})
    res.promotable = gate.gate_passed(rep, res.module_hash)
    if res.promotable:
        res.stop_reason = "passed"
    elif res.attempts and res.attempts[-1].outcome != "adopted":
        res.stop_reason = res.attempts[-1].outcome
    elif max_attempts == 0:
        res.stop_reason = "no-attempts-allowed"
    else:
        res.stop_reason = "max-attempts"
    res.ok, res.stage = True, "done"
    return res


# ---------------------------------------------------------------- readiness


_SELF_CHECK_REQ = {
    "name": "Authoring Self Check",
    "entities": [{"key": "item", "label": "Item", "fields": [{"key": "code", "type": "char"}]}],
    "roles": [{"key": "user", "label": "User", "access": {"item": "rwcd"}}],
}


def _check(fn: Callable[[], bool]) -> bool:
    try:
        return bool(fn())
    except Exception:  # noqa: BLE001 - a crashing self-check is a failing one
        return False


def authoring_ready(version: int = 17) -> dict[str, Any]:
    """Which prerequisites are present and pass their own checks (offline, no docker).

    Live sandbox evidence cannot be proven from code: it is listed under ``human`` and is
    what the reviewer verifies before flipping tiers.MODULE_AUTHORING_REVIEWED."""
    state: dict[str, Any] = {}
    b = rm.build(
        copy.deepcopy(_SELF_CHECK_REQ),
        version=version,
        installed_modules=["base"],
        technical_name="x_authoring_selfcheck",
    )
    state["req2mod"] = bool(b.ok and b.spec and b.trace)
    files: dict[str, bytes] = {}
    if state["req2mod"]:
        files = _files_of(build_module_zip(b.spec, odoo_major=version))
    z = oc._zip("x_authoring_selfcheck", files) if files else b""
    state["code_audit"] = _check(
        lambda: (r := ca.audit(z, version=version)).ok and not _blocking(r)
    ) and _check(
        lambda: any(
            f.code == "dangerous-call"
            for f in ca.audit(
                oc._zip(
                    "x_t",
                    {
                        "__manifest__.py": b"{'name': 't'}",
                        "a.py": b"import os as o\no.system('x')\n",
                    },
                ),
                version=version,
            ).findings
        )
    )

    def _oc() -> bool:
        with tempfile.TemporaryDirectory(prefix="inauthor-") as td:
            root = Path(td) / "x_authoring_selfcheck"
            for p, body in files.items():
                (root / p).parent.mkdir(parents=True, exist_ok=True)
                (root / p).write_bytes(body)
            readme = oc.Edit("doc/SELF_CHECK.md", "add_file", "self check\n")
            cs = oc.build_change_set(
                root,
                oc.ChangeRequest("x_authoring_selfcheck", (readme,)),
                version=version,
                owned_names={"x_authoring_selfcheck"},
            )
            try:
                oc.build_change_set(
                    root,
                    oc.ChangeRequest("x_authoring_selfcheck", (readme,)),
                    version=version,
                    owned_names=set(),
                )
                return False
            except oc.ChangeError:
                pass
            return bool(cs.id) and oc.apply_change_set(files, cs, approved_id=cs.id) != files

    state["owned_change"] = bool(files) and _check(_oc)

    def _gate() -> bool:
        rep = gate.run_gate(files, module="x_authoring_selfcheck", version=version, runner=None)
        try:
            gate.validate_argv(["docker", "run", "--privileged", "odoo:17"], "/tmp")
            return False
        except gate.GateError:
            pass
        return rep.checks["audit"].status == "pass" and not gate.gate_passed(rep, rep.module_hash)

    state["module_test_gate"] = bool(files) and _check(_gate)
    state["debug_notes"] = _check(
        lambda: (
            dn.match("Invalid field 'x' on model 'y'", version=version).status == "matched"
            and "s3cr3tvalue" not in dn.redact("password=s3cr3tvalue")
        )
    )
    met = all(
        state[k]
        for k in ("req2mod", "code_audit", "owned_change", "module_test_gate", "debug_notes")
    )
    return {
        "prerequisites": state,
        "all_met": met,
        "reviewed_flag": tt.MODULE_AUTHORING_REVIEWED,
        "capability": derived_capability(met),
        "human": list(gate.T3_SWITCH_PRECONDITIONS) + list(REVIEW_CHECKLIST),
    }


REVIEW_CHECKLIST = (
    "module-authoring: live end-to-end author() run on every supported version (17-20) from a "
    "requirement to promotable=True, results recorded in the run summary.",
    "module-authoring: seeded-failure run shows the repair loop stops (non-improving, repeated, "
    "no-repair or max-attempts) and reports promotable=False honestly.",
    "module-authoring: the spine (BOT-SPINE-WIRE) re-verifies gate_passed(report, module_hash) "
    "on the stored result and installs only the exact hashed files, after owner approval.",
    "module-authoring: every change set in the result was reviewed as a diff by a human.",
)


def derived_capability(prerequisites_met: Any) -> bool:
    """How tiers' 'module-authoring' capability WOULD be derived: prerequisites met in code AND
    the human review flag flipped in tiers.py. Not wired into tiers.REQUIRED/_CAPABILITIES."""
    return prerequisites_met is True and tt.MODULE_AUTHORING_REVIEWED is True
