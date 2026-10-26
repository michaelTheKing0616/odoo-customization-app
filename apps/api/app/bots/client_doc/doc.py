"""Pure functions: spec / review / fit-gap / run / verify / cards -> documents.

Never writes to Odoo, never imports RPC, never calls a model. Every line carries a ``source``
tag naming the input it came from; anything not derivable stays ``TBC``. Same input -> same
output (stable ordering, no clocks). Item values are untrusted: rendering escapes them.
"""

from __future__ import annotations

import html
import json
import re
import unicodedata
from collections.abc import Mapping
from typing import Any

from app.bots import versioncaps as vc

TBC = "to be confirmed"
NOT_PROVIDED = "not provided"
UNREADABLE = "unreadable value"
NOTHING_TO_UNDO = "nothing was written; nothing to undo"
EARLIER = TBC + " (earlier session)"
MAX_LINES = 1500
MAX_TEXT = 300
STRONG = frozenset({"strong pattern", "strong + context"})
POLICY_DEFAULT = "leave it unconfigured; nothing is changed until this is answered"
CATEGORIES = (
    "duplicate-ref",
    "conflict",
    "needs-review",
    "needs-custom",
    "missing-value",
    "low-confidence",
    "version-or-edition",
    "other-review",
)
_MD = re.compile(r"([\\`*_{}\[\]()#+\-.!|~>])")


def _emoji(c: str) -> bool:
    return unicodedata.category(c) == "So" or 0x1F3FB <= ord(c) <= 0x1F3FF


def _clean(t: str) -> str:
    """Drop Cc/Cf (tab/newline/CR kept for folding); keep ZWJ only between two emoji."""
    out = []
    for n, c in enumerate(t):
        if c in "\t\n\r" or unicodedata.category(c) not in ("Cc", "Cf"):
            out.append(c)
        elif c == "\u200d" and 0 < n < len(t) - 1 and _emoji(t[n - 1]) and _emoji(t[n + 1]):
            out.append(c)
    return "".join(out)


def _s(v: Any) -> str:
    """Untrusted value -> one bounded line (JSON for non-strings, newlines folded)."""
    if v is None:
        return TBC
    try:
        t = v if isinstance(v, str) else json.dumps(v, sort_keys=True, default=str)
        if not isinstance(t, str):
            return UNREADABLE
        t = _clean(t)
    except Exception:  # noqa: BLE001 - untrusted objects may fail in any way
        return UNREADABLE
    t = " ".join(t.split())
    return t if len(t) <= MAX_TEXT else t[: MAX_TEXT - 1] + "…"


def _m(x: Any) -> Mapping[str, Any]:
    return x if isinstance(x, Mapping) else {}


def _l(x: Any) -> list[Any]:
    return list(x) if isinstance(x, (list, tuple)) else []


class _Doc:
    def __init__(self, kind: str) -> None:
        self.kind = kind
        self.sections: dict[str, list[dict[str, Any]]] = {}
        self.n = 0
        self.truncated = False

    def add(self, section: str, source: str, **fields: Any) -> None:
        sec = self.sections.setdefault(section, [])
        if self.n >= MAX_LINES:
            self.truncated = True
            return
        self.n += 1
        sec.append({k: _s(v) for k, v in fields.items()} | {"source": _s(source)})

    def empty(self, section: str, source: str) -> None:
        if not self.sections.get(section):
            self.sections[section] = []
            self.add(section, source, text=NOT_PROVIDED)

    def out(self, meta: dict[str, Any]) -> dict[str, Any]:
        return {
            "doc": self.kind,
            "writes": 0,
            "meta": {k: _s(v) for k, v in sorted(meta.items())},
            "truncated": self.truncated,
            "sections": {k: v for k, v in self.sections.items()},
        }


def _canon(v: Any) -> str:
    try:
        return json.dumps(v, sort_keys=True, default=str)
    except Exception:  # noqa: BLE001
        return UNREADABLE


def _slot_key(s: Mapping[str, Any]) -> tuple[Any, ...]:
    slot = s.get("slot")
    head, _, rest = (str(slot) if isinstance(slot, (str, int)) else "").partition(":")
    n = int(head) if head.isdigit() else (slot if isinstance(slot, int) else 10**9)
    return (n, rest, _s(s.get("ref")), _canon(s))


def _items(spec: Any) -> list[dict[str, Any]]:
    items = [i for i in _l(_m(spec).get("items")) if isinstance(i, Mapping)]
    return sorted((dict(i) for i in items), key=lambda i: (_s(i.get("ref")), _canon(i)))


def _caps(major: Any, caps_ctx: Any, it: Mapping[str, Any]) -> tuple[str, str] | None:
    """(status, reason) from the version catalogue, or None when context is absent."""
    c = _m(caps_ctx)
    if major is None or not isinstance(c.get("edition"), str) or "installed" not in c:
        return None
    flds = sorted(k for k in _m(it.get("expected")) if isinstance(k, str))
    v = vc.availability(
        major, c["edition"], _l(c.get("installed")), it.get("model"), flds, it.get("module") or None
    )
    return v.status, v.reason


def clarification(
    spec: Any = None, review: Any = None, fit: Any = None, caps_ctx: Any = None
) -> dict[str, Any]:
    """Questions for the client from what the design could not decide."""
    d = _Doc("clarification")
    sp = _m(spec)
    major = sp.get("odoo_major")
    qs: list[tuple[str, str, dict[str, Any]]] = []

    def q(cat: str, src: str, question: str, why: str, options: Any) -> None:
        qs.append(
            (
                cat,
                src,
                {
                    "question": question,
                    "why": why,
                    "options": options,
                    "default": POLICY_DEFAULT,
                    "category": cat,
                },
            )
        )

    if spec is None:
        d.empty("design", "input:spec")
    refs = [_s(i.get("ref")) for i in _items(spec)]
    conflict_refs = set()
    for r in map(_s, _l(review)):
        hits = [x for x in set(refs) if r.startswith(f"conflict on {x}: ")]
        if hits:
            conflict_refs.add(max(hits, key=len))
    for ref in sorted({r for r in refs if refs.count(r) > 1}):
        q(
            "duplicate-ref",
            f"spec:item:{ref}",
            f"Several items share {ref}; which one is intended?",
            "the check treats duplicated items as not designed",
            "keep one; merge them; rename one",
        )
    for it in _items(spec):
        ref, src = _s(it.get("ref")), f"spec:item:{_s(it.get('ref'))}"
        verdict = it.get("verdict")
        if verdict == "needs review" and ref not in conflict_refs:
            q(
                "needs-review",
                src,
                f"How should {ref} be set up?",
                f"the design could not decide it: {_s(it.get('reason') or TBC)}",
                "confirm the proposed values; give different values; drop this item",
            )
        elif verdict == "needs-custom":
            q(
                "needs-custom",
                src,
                f"Is custom development acceptable for {ref}?",
                f"stock Odoo does not cover it: {_s(it.get('reason') or TBC)}",
                "approve a custom module; adapt the process to stock Odoo; drop this item",
            )
        for k, v in sorted(_m(it.get("expected")).items(), key=lambda kv: _s(kv[0])):
            if v is None or (isinstance(v, str) and not v.strip()):
                q(
                    "missing-value",
                    src,
                    f"What value should {_s(k)} have on {ref}?",
                    "the design has no value for it",
                    "give the value; leave it empty",
                )
        cv = _caps(major, caps_ctx, it)
        if cv and cv[0] != "installed-ok":
            q(
                "version-or-edition",
                f"caps:{_s(major)}:{_s(it.get('model'))}",
                f"May we proceed with {ref} given its availability?",
                cv[1],
                "install the named module; change edition or version; drop this item",
            )
    if review is None:
        d.empty("design review", "input:review")
    for n, r in enumerate(_l(review)):
        txt = _s(r)
        cat = "conflict" if txt.startswith("conflict") else "other-review"
        q(
            cat,
            f"design:review:{n}",
            f"Please resolve: {txt}",
            "the design found conflicting values across steps"
            if cat == "conflict"
            else "the design flagged it for a person to decide",
            "pick one of the values named; give another value"
            if cat == "conflict"
            else "confirm; correct; drop",
        )
    if fit is None:
        d.empty("fit-gap", "input:fit")
    for s in sorted(
        (x for x in _l(_m(fit).get("steps")) if isinstance(x, Mapping)),
        key=lambda x: _s(x.get("step_id")),
    ):
        conf = s.get("match_confidence")
        if conf not in STRONG or s.get("needs_human") or s.get("gap"):
            q(
                "low-confidence",
                f"fitgap:step:{_s(s.get('step_id'))}",
                f"Did we understand step {_s(s.get('step_id'))} correctly: {_s(s.get('text'))}?",
                f"the match to stock Odoo is not strong (confidence: {_s(conf)})",
                "confirm; describe the step differently",
            )
    order = {c: i for i, c in enumerate(CATEGORIES)}
    for _cat, src, f in sorted(
        qs, key=lambda t: (order[t[0]], t[1], t[2]["question"], _canon(t[2]))
    ):
        d.add("questions", src, **f)
    if not qs:
        d.add("questions", "derived:none", text="no open questions found in the supplied input")
    return d.out(
        {
            "odoo_major": major if major is not None else TBC,
            "spec_status": sp.get("status") or NOT_PROVIDED,
            "questions": len(qs),
        }
    )


def handoff(
    spec: Any = None, run: Any = None, verify: Any = None, cards: Any = None, caps_ctx: Any = None
) -> dict[str, Any]:
    """What was configured, how to test it, what was left undone, limits, and undo."""
    d = _Doc("handoff")
    sp = _m(spec)
    major = sp.get("odoo_major")
    items = {_s(i.get("ref")): i for i in _items(spec)}
    ver = {_s(i.get("ref")): i for i in _l(_m(verify).get("items")) if isinstance(i, Mapping)}
    del cards  # accepted for the contract; card undo_how is never shown as an instruction
    steps = sorted(
        (s for s in _l(_m(run).get("steps")) if isinstance(s, Mapping)),
        key=_slot_key,
    )
    for name, val in (("spec", spec), ("run", run), ("verify", verify)):
        if val is None:
            d.add("inputs", f"input:{name}", text=f"{name}: {NOT_PROVIDED}")
    for st in steps:
        ref = _s(st.get("ref"))
        status, src = st.get("status"), f"run:step:{_s(st.get('slot') or ref)}"
        v = ver.get(ref)
        vstat = (
            _s(v.get("status")) if v else (_s(st.get("verified")) if st.get("verified") else TBC)
        )
        vsrc = f"verify:{ref}" if v else src
        if status in ("executed", "already-done"):
            d.add(
                "configured",
                src,
                ref=ref,
                title=st.get("title") or TBC,
                outcome=status,
                check=vstat,
            )
            it = items.get(ref)
            if it:
                key = ", ".join(
                    f"{_s(k)} = {_s(x)}"
                    for k, x in sorted(_m(it.get("key")).items(), key=lambda kv: _s(kv[0]))
                )
                exp = ", ".join(
                    f"{_s(k)} = {_s(x)}"
                    for k, x in sorted(_m(it.get("expected")).items(), key=lambda kv: _s(kv[0]))
                )
                d.add(
                    "how to test",
                    f"spec:item:{ref}",
                    ref=ref,
                    steps=f"open {_s(it.get('model'))}; find the record where {key or TBC}",
                    expected=exp or TBC,
                )
            else:
                d.add("how to test", src, ref=ref, steps=TBC, expected=TBC)
            if status != "executed":
                how = NOTHING_TO_UNDO
            elif st.get("resumed"):
                how = EARLIER
            else:
                how = st.get("undo") or TBC
            d.add("undo", src, ref=ref, how=how)
            if vstat != "matches":
                d.add(
                    "known limits",
                    vsrc,
                    ref=ref,
                    text=st.get("needs_review") or f"after the run the check says {vstat}",
                )
        else:
            reason = st.get("reason") or (
                f"skipped by {_s(st.get('by'))}" if status == "skipped-by-operator" else TBC
            )
            d.add("not done", src, ref=ref, outcome=status or TBC, reason=reason)
            it = items.get(ref)
            cv = _caps(major, caps_ctx, it) if it else None
            if cv and cv[0] != "installed-ok":
                d.add(
                    "not done",
                    f"caps:{_s(major)}:{_s(it.get('model'))}",
                    ref=ref,
                    outcome="version-or-edition",
                    reason=cv[1],
                )
    ran = {_s(s.get("ref")) for s in steps}
    for ref, it in items.items():
        if ref not in ran and run is not None:
            d.add(
                "not done",
                f"spec:item:{ref}",
                ref=ref,
                outcome="not run",
                reason=it.get("reason") or _s(it.get("verdict")),
            )
    if _m(verify).get("truncated"):
        d.add("known limits", "verify:truncated", text="the check stopped at its item limit")
    if _m(verify).get("company_view") not in (None, "full"):
        d.add(
            "known limits",
            "verify:company_view",
            text=f"the check saw a partial company view: {_s(_m(verify).get('company_view'))}",
        )
    for sec, src in (
        ("configured", "run:none"),
        ("not done", "run:none"),
        ("known limits", "derived:none"),
    ):
        if sec not in d.sections:
            d.add(sec, src, text="nothing recorded")
    c = _m(_m(run).get("counts"))
    return d.out(
        {
            "odoo_major": major if major is not None else TBC,
            "run_status": _m(run).get("status") or NOT_PROVIDED,
            "plan_id": _m(run).get("plan_id") or NOT_PROVIDED,
            "counts": dict(sorted((_s(k), _s(v)) for k, v in c.items())) if c else NOT_PROVIDED,
        }
    )


TITLES = {"clarification": "Clarification questions", "handoff": "Handoff and test pack"}


def _esc_md(t: str) -> str:
    return _MD.sub(r"\\\1", html.escape(t, quote=False))


def render_markdown(doc: Any) -> str:
    doc = _m(doc)
    out = [f"# {TITLES.get(_s(doc.get('doc')), 'Document')}", ""]
    for k, v in _m(doc.get("meta")).items():
        out.append(f"- {_esc_md(_s(k))}: {_esc_md(_s(v))}")
    for sec, lines in _m(doc.get("sections")).items():
        out += ["", f"## {_esc_md(_s(sec).capitalize())}", ""]
        for ln in (x for x in _l(lines) if isinstance(x, Mapping)):
            parts = [f"{_esc_md(_s(k))}: {_esc_md(_s(v))}" for k, v in ln.items() if k != "source"]
            src = _esc_md(_s(ln.get("source", TBC)))
            out.append(f"- {'; '.join(parts)} \\[source: {src}\\]")
    if doc.get("truncated"):
        out += ["", f"_Truncated at {MAX_LINES} lines\\._"]
    return "\n".join(out) + "\n"


def render_html(doc: Any) -> str:
    doc = _m(doc)
    e = html.escape
    out = [f"<h1>{e(TITLES.get(_s(doc.get('doc')), 'Document'))}</h1><ul>"]
    out += [f"<li>{e(_s(k))}: {e(_s(v))}</li>" for k, v in _m(doc.get("meta")).items()]
    out.append("</ul>")
    for sec, lines in _m(doc.get("sections")).items():
        out.append(f"<h2>{e(_s(sec).capitalize())}</h2><ul>")
        for ln in (x for x in _l(lines) if isinstance(x, Mapping)):
            parts = "; ".join(f"{e(_s(k))}: {e(_s(v))}" for k, v in ln.items() if k != "source")
            src = e(_s(ln.get("source", TBC)))
            out.append(f'<li>{parts} <small data-source="{src}">[source: {src}]</small></li>')
        out.append("</ul>")
    if doc.get("truncated"):
        out.append(f"<p><em>Truncated at {MAX_LINES} lines.</em></p>")
    return "\n".join(out) + "\n"
