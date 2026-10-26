"""Walks an operator through a process_design spec, one plain-language step at a time.

``OperatorFlow.cards()`` turns each spec item into a ``StepCard``: what will change (the
walker's own preview lines), what it risks (design risk + walker class/tier), how it is undone,
and whether this Odoo version can do it at all (``versioncaps.availability``: an uninstalled
module reads "available in Odoo N via module M; needs install"). Read-only.

``OperatorFlow.run()`` executes only steps the operator approved in ``Decisions`` (a store the
flow owns; the caller never hands in an approval level), only through ``Walker.plan`` /
``Walker.apply`` (WriteGate + before_image RouteA + audit + kill switch + lockout + ledger), then
re-checks the result with ``configverify.verify``. Every step ends executed, skipped-by-operator
or blocked with a reason; until the operator decides it stays pending. Flow state is on disk
(atomic replace): a re-run never repeats an executed step.

Not here (fail closed, blocked with a reason): steps needing a crafted or promoted module
("needs module build": AS-CRAFT-MODULE / AS-PROMOTE do not exist yet), module installs,
settings apply, and linked-record relations. Session-bound approvals are BOT-SPINE-WIRE.
"""

from __future__ import annotations

import contextlib
import dataclasses
import fcntl
import hashlib
import json
import os
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.bots import configverify as cv
from app.bots import guard as gd
from app.bots import versioncaps as vc
from app.bots import walker as wk
from app.bots.risk.rules import Refusal

EXECUTED, SKIPPED, BLOCKED, PENDING = "executed", "skipped-by-operator", "blocked", "pending"
ALREADY = "already-done"  # approved, live state already matched: nothing written
DONE_OK = frozenset({EXECUTED, ALREADY})  # what a later dependent step may build on
FINAL = frozenset({EXECUTED, ALREADY, SKIPPED})
CHANGED = (
    "design changed since approval; re-approve"  # blocked steps are re-examined on the next run
)
NEEDS_BUILD = (
    "needs module build: this step needs a custom module crafted and promoted, "
    "which this flow cannot do yet"
)
RA = {"context": {"active_test": False}}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class _Json:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            d = json.loads(self.path.read_text())
        except (OSError, ValueError) as exc:
            raise RuntimeError(f"flow store unreadable: {self.path.name}") from exc
        if not isinstance(d, dict):
            raise RuntimeError(f"flow store corrupt: {self.path.name}")
        return d

    def save(self, d: dict[str, Any]) -> None:
        fd, tmp = tempfile.mkstemp(prefix=self.path.name, suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w") as fh:
                json.dump(d, fh, sort_keys=True, default=str)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            with contextlib.suppress(OSError):
                os.remove(tmp)
            raise

    @contextlib.contextmanager
    def locked(self) -> Any:
        """Exclusive lock for a whole read-modify-write (other threads and processes wait)."""
        with open(self.path.with_name(self.path.name + ".lock"), "a") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)

    def update(self, fn: Any) -> Any:
        with self.locked():
            d = self.load()
            out = fn(d)
            self.save(d)
            return out


class Decisions(_Json):
    """Operator decisions, owned by the store, bound to the exact card shown (``digest``).
    The level and actor are self-asserted until BOT-SPINE-WIRE binds them to the session."""

    def approve(self, plan_id: str, card: StepCard, actor: str, level: int) -> None:
        if not actor or level not in (1, 2, 3):
            raise ValueError("approval needs an actor and a level 1-3")
        self._put(plan_id, card, {"decision": "approve", "actor": actor, "level": level})

    def skip(self, plan_id: str, card: StepCard, actor: str) -> None:
        if not actor:
            raise ValueError("skip needs an actor")
        self._put(plan_id, card, {"decision": "skip", "actor": actor})

    def _put(self, plan_id: str, card: StepCard, rec: dict[str, Any]) -> None:
        if not card.digest:
            raise ValueError("card has no digest: preview it first")
        row = rec | {"hash": card.digest, "at": _now()}
        self.update(lambda d: d.setdefault(plan_id, {}).__setitem__(card.slot, row))

    def get(self, plan_id: str, card: StepCard) -> dict[str, Any] | None:
        r = self.load().get(plan_id, {}).get(card.slot)
        return r if isinstance(r, dict) else None

    def invalidate(self, plan_id: str, card: StepCard) -> None:
        """A decision whose card changed is spent: it never applies again, even if reverted."""

        def f(d: dict[str, Any]) -> None:
            r = d.get(plan_id, {}).get(card.slot)
            if isinstance(r, dict):
                r["decision"], r["stale_at"] = "stale", _now()

        self.update(f)

    def approval_for(self, plan_id: str, card: StepCard) -> gd.Approval | None:
        r = self.get(plan_id, card)
        if not r or r.get("decision") != "approve" or r.get("level") not in (1, 2, 3):
            return None
        if r.get("hash") != card.digest:
            return None
        return gd.Approval(int(r["level"]), str(r.get("actor") or "") or None)


@dataclass
class StepCard:
    n: int
    ref: str
    kind: str
    model: str
    title: str
    changes: list[str] = field(default_factory=list)
    risk: str | None = None
    tier: int | None = None
    undo_how: str = ""
    availability: str = ""
    blocked: str | None = None
    step: wk.Step | None = None
    walk: Any = None
    noop: str | None = None
    item_hash: str = ""
    digest: str = ""
    links: tuple[str, ...] = ()
    deps: tuple[int, ...] = ()

    @property
    def slot(self) -> str:
        return f"{self.n}:{self.ref}"

    def seal(self) -> None:
        """Hash of everything the operator is approving: the item and the planned change."""
        st = self.step
        body = {
            "item": self.item_hash,
            "step": None
            if st is None
            else [st.kind, st.model, list(st.ids), dict(st.values), st.method],
            "tier": self.tier,
            "noop": self.noop,
            "blocked": self.blocked,
        }
        self.digest = _h(body)

    def to_dict(self) -> dict[str, Any]:
        d = {k: v for k, v in dataclasses.asdict(self).items() if k not in ("step", "walk")}
        d["slot"] = self.slot
        return d


class OperatorFlow:
    def __init__(
        self,
        spec: Any,
        walker: wk.Walker,
        decisions: Decisions,
        state_path: Path,
        base: gd.RunSpec,
        *,
        plan_id: str,
        edition: str = "community",
        installed: Sequence[str] = (),
        companies: Sequence[int] | None = None,
    ) -> None:
        self.spec, self.w, self.dec, self.base = spec, walker, decisions, base
        self.state = _Json(state_path)
        self.plan_id, self.edition, self.installed = plan_id, edition, list(installed)
        self.companies = list(companies) if companies else None
        self.done: dict[str, wk.Done] = {}

    # ------------------------------------------------------------ preview
    def _spec_problem(self) -> str | None:
        s = self.spec
        if not isinstance(s, dict) or s.get("spec_version") != 1:
            return "not a version-1 design spec"
        if s.get("status") != "designed" or not isinstance(s.get("items"), list) or not s["items"]:
            return "design is not complete (status must be 'designed' with items)"
        refs = [i.get("ref") for i in s["items"] if isinstance(i, Mapping)]
        if len(refs) != len(set(map(str, refs))):
            return "design has duplicate step refs: every step needs its own ref"
        if s.get("odoo_major") != self.w.version:
            return f"design is for Odoo {s.get('odoo_major')}, database is Odoo {self.w.version}"
        return None

    def cards(self) -> list[StepCard]:
        bad = self._spec_problem()
        items = self.spec.get("items") if isinstance(self.spec, dict) else None
        out = []
        for n, it in enumerate(items if isinstance(items, list) else [], 1):
            c = self._card(n, it, bad)
            c.deps = tuple(e.n for e in out if (e.model and e.model == c.model) or e.ref in c.links)
            c.seal()
            out.append(c)
        if not out:
            out.append(StepCard(0, "", "", "", "nothing to do", blocked=bad or "empty design"))
        return out

    def _card(self, n: int, it: Any, bad: str | None) -> StepCard:
        if not isinstance(it, Mapping):
            c = StepCard(n, f"#{n}", "", "", "unreadable step", blocked="needs review: bad item")
            c.item_hash = _h(repr(it))
            return c
        kind, model = str(it.get("kind") or ""), str(it.get("model") or "")
        key = it.get("key") if isinstance(it.get("key"), dict) else {}
        exp = it.get("expected") if isinstance(it.get("expected"), dict) else {}
        ref = str(it.get("ref") or f"#{n}")
        c = StepCard(n, ref, kind, model, _title(kind, model, key, it.get("module")))
        c.item_hash = _h({k: it.get(k) for k in ITEM_KEYS})
        rel = it.get("relations") if isinstance(it.get("relations"), dict) else {}
        c.links = tuple(str(x) for x in rel.values())
        c.risk = it.get("risk") if isinstance(it.get("risk"), str) else None
        av = vc.availability(
            self.w.version,
            self.edition,
            self.installed,
            model or "?",
            [f for f in {**key, **exp} if isinstance(f, str)],
            it.get("module") or None,
        )
        c.availability = _plain_av(av)
        c.blocked = bad or self._preblock(it, kind, c, av)
        if c.blocked:
            return c
        try:
            self._build(c, model, key, exp)
        except Exception as exc:  # noqa: BLE001 - any read fault means a person looks
            c.blocked = f"needs review: could not read current state ({str(exc)[:120]})"
        return c

    def _preblock(self, it: Mapping, kind: str, c: StepCard, av: vc.Verdict) -> str | None:
        verdict = it.get("verdict")
        if verdict == "needs-custom":
            return NEEDS_BUILD
        if verdict not in ("stock", "stock-install"):
            return f"needs review: {it.get('reason') or 'design did not confirm this step'}"
        if c.risk in (None, "unclassified"):
            return "needs review: risk not classified"
        if kind == "module":
            if av.status == "installed-ok" and it.get("module") in self.installed:
                return None
            return f"module install is not run by this flow: {c.availability}"
        if kind == "setting":
            return "needs review: settings are not applied by this flow yet"
        if kind != "record":
            return f"needs review: unknown step kind {kind!r}"
        if it.get("relations"):
            return "needs review: linked records are not resolved by this flow yet"
        if av.status != "installed-ok":
            return f"not possible on this database now: {c.availability}"
        return None

    def _build(self, c: StepCard, model: str, key: dict, exp: dict) -> None:
        if c.kind == "module":
            c.noop = "already installed"
            return
        if not key:
            c.blocked = "needs review: record has no identifying key"
            return
        dom = [(k, "=", v) for k, v in sorted(key.items())]
        rows = self.w.read(model, "search_read", [dom], {**RA, "fields": sorted(exp), "limit": 2})
        if len(rows) > 1:
            c.blocked = "needs review: more than one record matches the key"
            return
        if rows:
            diff = {k: v for k, v in exp.items() if _val(rows[0].get(k)) != v}
            if not diff:
                c.noop = "already matches the design"
                return
            c.step = wk.Step("write", model, (int(rows[0]["id"]),), diff)
        else:
            c.step = wk.Step("create", model, values={**key, **exp})
        r = self.w.plan([c.step], f"{self.plan_id}:{c.n}")
        if isinstance(r, Refusal):
            c.blocked = f"refused by safety checks: {r.reason}"
            return
        c.walk = r
        p = r.steps[0]
        c.changes, c.tier = list(p.lines), r.tier
        c.undo_how = vars(p)["undo"]  # kill_audit bans a bare .undo attribute in bots
        c.risk = f"{c.risk}; class {p.cls}, needs L{r.tier} approval"

    # ------------------------------------------------------------ run
    def run(self) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        status: dict[int, str] = {}
        for c in self.cards():
            prev = self.state.load().get(self.plan_id, {}).get(c.slot)
            if prev and prev.get("status") in FINAL and prev.get("item_hash") == c.item_hash:
                r = prev | {"resumed": True}
            else:
                r = self._run1(c, status) | {"at": _now(), "item_hash": c.item_hash}
                self.state.update(
                    lambda d, r=r, c=c: d.setdefault(self.plan_id, {}).__setitem__(c.slot, r)
                )
            status[c.n] = r["status"]
            results.append(r | {"ref": c.ref, "slot": c.slot})
        return self._verify(results)

    def _run1(self, c: StepCard, status: Mapping[int, str]) -> dict[str, Any]:
        base = {"title": c.title, "availability": c.availability}
        d = self.dec.get(self.plan_id, c)
        if d is not None and (d.get("decision") == "stale" or d.get("hash") != c.digest):
            if d.get("decision") != "stale":
                self.dec.invalidate(self.plan_id, c)
            return base | {"status": BLOCKED, "reason": CHANGED}
        if c.blocked:
            return base | {"status": BLOCKED, "reason": c.blocked}
        if d is None:
            return base | {"status": PENDING, "reason": "waiting for the operator's decision"}
        if d.get("decision") == "skip":
            return base | {"status": SKIPPED, "by": d.get("actor")}
        ap = self.dec.approval_for(self.plan_id, c)
        if ap is None:
            return base | {"status": BLOCKED, "reason": "needs review: approval record unusable"}
        wait = [
            f"step {m} ({status.get(m, PENDING)})" for m in c.deps if status.get(m) not in DONE_OK
        ]
        if wait:
            return base | {"status": BLOCKED, "reason": "waits on earlier " + ", ".join(wait)}
        if c.noop:
            return base | {
                "status": ALREADY,
                "note": f"{c.noop}; nothing written",
                "by": ap.approver,
            }
        if c.walk is None or c.tier is None:
            return base | {"status": BLOCKED, "reason": "needs review: no safe plan"}
        if ap.level < c.tier:
            return base | {
                "status": BLOCKED,
                "reason": f"needs L{c.tier} approval, has L{ap.level}",
            }
        spec = dataclasses.replace(self.base, approval=ap)  # actor stays the bot
        try:
            done = self.w.apply(c.walk, spec)
        except Exception as exc:  # noqa: BLE001 - never a silent skip
            return base | {"status": BLOCKED, "reason": f"needs review: {str(exc)[:160]}"}
        last = done[-1] if done else None
        if last is None or last.status != "done":
            why = last.refusal.reason if last and last.refusal else (last.status if last else "?")
            return base | {"status": BLOCKED, "reason": f"not applied: {why}"}
        self.done[c.slot] = last
        return base | {
            "status": EXECUTED,
            "record_ids": list(last.record_ids),
            "undo": c.undo_how,
            "by": ap.approver,
            "replayed": last.replayed,
        }

    def _verify(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            rep = cv.verify(self.spec, cv.read_only(self.w.read), companies=self.companies)
        except Exception as exc:  # noqa: BLE001
            rep = {"status": "cannot-read", "items": [], "error": str(exc)[:160]}
        by = {i.get("ref"): i for i in rep.get("items", []) if isinstance(i, dict)}
        for r in results:
            v = by.get(r["ref"])
            r["verified"] = v.get("status") if v else "cannot-read"
            if r["status"] in DONE_OK and r["verified"] != "matches":
                r["needs_review"] = f"after the run the check says {r['verified']}"
        counts = {
            s: sum(r["status"] == s for r in results)
            for s in (EXECUTED, ALREADY, SKIPPED, BLOCKED, PENDING)
        }
        done = not counts[PENDING] and not counts[BLOCKED]
        clean = done and not any(r.get("needs_review") for r in results)
        return {
            "plan_id": self.plan_id,
            "status": "complete" if clean else "attention",
            "counts": counts,
            "steps": results,
            "verify": rep.get("status"),
        }

    def undo_plan(self) -> list[wk.Step] | Refusal:
        """Inverse steps for what this session executed; they go through plan + apply again."""
        if not self.done:
            return Refusal(wk.RF, wk.MISS, "nothing executed in this session to undo")
        return self.w.undo_steps(list(self.done.values()))


ITEM_KEYS = ("kind", "model", "key", "expected", "relations", "module", "verdict", "risk", "ref")


def _h(x: Any) -> str:
    return hashlib.sha256(json.dumps(x, sort_keys=True, default=repr).encode()).hexdigest()


def _val(v: Any) -> Any:
    if isinstance(v, list) and len(v) == 2 and isinstance(v[0], int):
        return v[0]
    return v


def _title(kind: str, model: str, key: Mapping, module: Any) -> str:
    what = ", ".join(f"{k} = {v}" for k, v in sorted(key.items())) or "no key"
    if kind == "module":
        return f"Make sure module {module or model} is installed"
    if kind == "setting":
        return f"Set configuration on {model}"
    return f"Make sure a {model} record exists ({what}) with the designed values"


def _plain_av(av: vc.Verdict) -> str:
    if av.status == "installed-ok":
        return "available on this database"
    return av.reason
