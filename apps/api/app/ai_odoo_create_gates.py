"""Odoo create-gates — preempt backend Invalid Operation hard blocks.

Some Community models refuse create/write from a normal backend form (PoS orders,
sessions, etc.). Flash often still emits many2one links to them.

Policies (expand when UAT hits a new hard block — do not invent entries):
  no_create — keep the M2O; stamp view ``options`` so operators pick existing
              records only. Create stays blocked; that is correct when the DB
              already has PoS tickets.
  strip — relation is not a useful form FK for our residuals; drop the field.

Completeness ≠ Cert ≠ Autopilot. Promote stays human.
"""

from __future__ import annotations

import re
from typing import Any, Literal

CreateGatePolicy = Literal["no_create", "strip"]

# Verified against Odoo Community create constraints / operator UAT.
# Add a row when a new Invalid Operation appears — cite the error in MEMORY.
CREATE_GATE_BY_MODEL: dict[str, dict[str, str]] = {
    "pos.order": {
        "policy": "no_create",
        "help": (
            "Select an existing Point of Sale order. "
            "New tickets must be created from the PoS app — not from this form."
        ),
    },
    "pos.session": {
        "policy": "no_create",
        "help": (
            "Select an existing PoS session. "
            "Open/close sessions from the Point of Sale app."
        ),
    },
    "pos.order.line": {
        "policy": "strip",
        "help": "",
    },
    "pos.payment": {
        "policy": "strip",
        "help": "",
    },
    "pos.payment.method": {
        "policy": "no_create",
        "help": "Select a configured PoS payment method (Settings / PoS).",
    },
    "pos.pack.operation.lot": {
        "policy": "strip",
        "help": "",
    },
}

_NO_CREATE_OPTIONS: dict[str, bool] = {
    "no_create": True,
    "no_create_edit": True,
}


def create_gate_for_relation(relation: str) -> dict[str, str] | None:
    rel = str(relation or "").strip()
    return CREATE_GATE_BY_MODEL.get(rel)


def field_needs_no_create(field: dict[str, Any]) -> bool:
    gate = create_gate_for_relation(str(field.get("relation") or ""))
    if not gate or gate.get("policy") != "no_create":
        return False
    opts = field.get("options") if isinstance(field.get("options"), dict) else {}
    return not (opts.get("no_create") is True)


def _options_literal(opts: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, val in opts.items():
        if val is True:
            parts.append(f"'{key}': True")
        elif val is False:
            parts.append(f"'{key}': False")
        else:
            parts.append(f"'{key}': {repr(val)}")
    return "{" + ", ".join(parts) + "}"


def _stamp_field_options_in_arch(arch: str, name: str, opts: dict[str, Any]) -> str:
    """Ensure ``<field name="…"/>`` carries options= for no_create gates."""
    if not arch or not name:
        return arch
    lit = _options_literal(opts)
    pattern = re.compile(
        rf'(<field\b[^>]*\bname="{re.escape(name)}"[^>]*?)(?:\s*/>|>)',
        re.IGNORECASE,
    )

    def _repl(match: re.Match[str]) -> str:
        open_tag = match.group(1)
        if re.search(r"\boptions=", open_tag, flags=re.IGNORECASE):
            open_tag = re.sub(
                r'\boptions="[^"]*"',
                f'options="{lit}"',
                open_tag,
                count=1,
                flags=re.IGNORECASE,
            )
        else:
            open_tag = f'{open_tag} options="{lit}"'
        closer = match.group(0)[len(match.group(1)) :]
        return open_tag + closer

    return pattern.sub(_repl, arch, count=1)


def apply_odoo_create_gates(draft: dict[str, Any]) -> list[str]:
    """Apply create-gate policies on x_* many2one fields (and scrub arches)."""
    notes: list[str] = []
    stripped: list[str] = []
    gated: list[str] = []

    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_"):
            continue
        fields = [f for f in (model.get("fields") or []) if isinstance(f, dict)]
        kept: list[dict[str, Any]] = []
        removed: set[str] = set()
        stamp_opts: list[tuple[str, dict[str, Any]]] = []
        for field in fields:
            rel = str(field.get("relation") or "")
            name = str(field.get("name") or "")
            gate = create_gate_for_relation(rel)
            if not gate:
                kept.append(field)
                continue
            policy = str(gate.get("policy") or "strip")
            if policy == "strip":
                removed.add(name)
                stripped.append(f"{mid}.{name}→{rel}")
                continue
            # no_create — keep link to existing records (correct when DB already has PoS tickets).
            opts = dict(field.get("options") or {}) if isinstance(field.get("options"), dict) else {}
            changed = False
            for key, val in _NO_CREATE_OPTIONS.items():
                if opts.get(key) is not True:
                    opts[key] = val
                    changed = True
            field["options"] = opts
            help_txt = str(gate.get("help") or "").strip()
            if help_txt and not str(field.get("help") or "").strip():
                field["help"] = help_txt
                changed = True
            if changed:
                gated.append(f"{mid}.{name}→{rel}")
            if name:
                stamp_opts.append((name, opts))
            kept.append(field)
        model["fields"] = kept
        for v in draft.get("views") or []:
            if not isinstance(v, dict) or v.get("model") != mid:
                continue
            arch = str(v.get("arch") or "")
            new_arch = arch
            for n in removed:
                if n:
                    new_arch = re.sub(
                        rf'<field name="{re.escape(n)}"(?:[^>]*)?/?>',
                        "",
                        new_arch,
                    )
            for fname, fopts in stamp_opts:
                new_arch = _stamp_field_options_in_arch(new_arch, fname, fopts)
            if new_arch != arch:
                v["arch"] = new_arch

    if stripped:
        notes.append(
            "create_gate: stripped unusable form FKs "
            + ", ".join(stripped[:8])
        )
        # Catalog suggestions that push strip-policy models are noise.
        reuse = draft.get("reuse") if isinstance(draft.get("reuse"), dict) else {}
        if reuse:
            strip_models = {
                m
                for m, g in CREATE_GATE_BY_MODEL.items()
                if g.get("policy") == "strip"
            }
            sugg = [
                row
                for row in (reuse.get("catalog_suggestions") or [])
                if not (
                    isinstance(row, dict) and str(row.get("model") or "") in strip_models
                )
            ]
            if sugg != list(reuse.get("catalog_suggestions") or []):
                reuse["catalog_suggestions"] = sugg
                draft["reuse"] = reuse
    if gated:
        notes.append(
            "create_gate: no_create on "
            + ", ".join(gated[:8])
            + " (pick existing records — backend create is blocked by Odoo)"
        )
    return notes


def draft_has_unguarded_create_gates(draft: dict[str, Any]) -> bool:
    """True when a create-blocked M2O is missing no_create options (Retry/Expert)."""
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        if not str(model.get("model") or "").startswith("x_"):
            continue
        for field in model.get("fields") or []:
            if isinstance(field, dict) and field_needs_no_create(field):
                return True
            rel = str(field.get("relation") or "") if isinstance(field, dict) else ""
            gate = create_gate_for_relation(rel)
            if gate and gate.get("policy") == "strip":
                return True
    return False


__all__ = [
    "CREATE_GATE_BY_MODEL",
    "apply_odoo_create_gates",
    "create_gate_for_relation",
    "draft_has_unguarded_create_gates",
    "field_needs_no_create",
]
