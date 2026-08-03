"""PCM-4 — enforce protected-module tiers on mutating API surfaces.

AI path uses ``strip_protected_module_effects`` (PCM-3). This module gates Builder,
ModuleSpec apply, and Automations with the same effect-not-mechanism rules:

- Tier-1: no field/model mutations ON protected models; link-only relational fields
  FROM custom (``x_*``) models INTO protected models are allowed.
- Tier-2: additive custom fields allowed; delete/rename of stock (non-``x_*``) fields
  blocked.
- Automations: reject writes targeting tier-1 unless chatter/activity-only.
- Power Ops account-move recipes are intentionally exempt (see ``power_ops_recipes``).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from app.protected_modules import (
    community_manifest_for_version,
    manifest_from_json,
    protected_models_for,
    safe_alternative_for,
)

PROTECTED_DOCS_LINK = "plans/cards/WAVE-1-PCM.md#pcm-4-enforcement-beyond-ai--ui-badges--adversarial-tests-grok-45-card"

_RELATIONAL_TTYPES = frozenset({"many2one", "one2many", "many2many"})

_CHATTER_ACTION_KINDS = frozenset(
    {
        "create_activity",
        "mail_post",
        "followers",
        "remove_followers",
        "next_activity",
        "message_post",
        "activity",
        "chatter",
    }
)


@dataclass(frozen=True)
class ProtectedViolation:
    reason: str
    model: str
    tier: str
    safe_alternative: str
    docs: str = PROTECTED_DOCS_LINK

    def http_detail(self) -> dict[str, Any]:
        return {
            "error": "protected_module_violation",
            "reason": self.reason,
            "model": self.model,
            "tier": self.tier,
            "safe_alternative": self.safe_alternative,
            "docs": self.docs,
        }

    def skip_reason(self) -> str:
        return (
            f"protected:{self.tier}:{self.model}: {self.reason} "
            f"(docs: {self.docs})"
        )


def is_custom_model(model_name: str) -> bool:
    return (model_name or "").strip().startswith("x_")


def is_custom_field(field_name: str) -> bool:
    return (field_name or "").strip().startswith("x_")


def manifest_for_connection(row: Any) -> dict[str, Any]:
    """Resolve cached connection manifest or offline community snapshot."""
    cached = manifest_from_json(getattr(row, "protected_manifest_json", None))
    if cached and cached.get("tier_1_never_generate_logic") is not None:
        return cached
    version = getattr(row, "server_version", None) or getattr(
        row, "protected_manifest_version", None
    )
    return community_manifest_for_version(version)


def _violation(model: str, tier: str, reason: str) -> ProtectedViolation:
    return ProtectedViolation(
        reason=reason,
        model=model,
        tier=tier,
        safe_alternative=safe_alternative_for(model),
    )


def check_field_create(
    manifest: dict[str, Any],
    *,
    model: str,
    ttype: str | None = None,
    relation: str | None = None,
    field_name: str | None = None,
) -> ProtectedViolation | None:
    """Gate creating a field on ``model``.

    Link-only: relational field ON a custom model (any relation target) is allowed.
    Creating any field ON a tier-1 model is blocked.
    Tier-2: additive custom fields allowed.
    """
    model = (model or "").strip()
    if not model:
        return None
    tier = protected_models_for(manifest, model)
    ttype_l = (ttype or "").strip().lower()
    rel = (relation or "").strip()

    # Link-only FROM custom models — even when relation points at tier-1
    if is_custom_model(model) and ttype_l in _RELATIONAL_TTYPES:
        return None
    if is_custom_model(model) and tier is None:
        return None

    if tier == "tier_1":
        return _violation(
            model,
            tier,
            "Cannot create or mutate fields on tier-1 protected models. "
            "Link from a custom (x_*) model via many2one/one2many/many2many instead.",
        )
    if tier == "tier_2":
        # Additive custom fields OK; refuse non-custom names as stock mutations
        if field_name and not is_custom_field(field_name):
            return _violation(
                model,
                tier,
                "Tier-2 models allow additive custom (x_*) fields only; "
                "cannot create or rename stock fields.",
            )
        return None
    return None


def check_field_delete_or_stock_mutate(
    manifest: dict[str, Any],
    *,
    model: str,
    field_name: str | None = None,
) -> ProtectedViolation | None:
    """Gate delete / stock-field mutation on protected models."""
    model = (model or "").strip()
    if not model:
        return None
    tier = protected_models_for(manifest, model)
    if tier == "tier_1":
        return _violation(
            model,
            tier,
            "Cannot delete or mutate fields on tier-1 protected models.",
        )
    if tier == "tier_2":
        if field_name and not is_custom_field(field_name):
            return _violation(
                model,
                tier,
                "Tier-2: cannot delete or rename stock (non-x_*) fields; "
                "additive custom fields only.",
            )
        return None
    return None


def check_model_delete(
    manifest: dict[str, Any],
    *,
    model: str,
) -> ProtectedViolation | None:
    model = (model or "").strip()
    if not model:
        return None
    tier = protected_models_for(manifest, model)
    if tier in {"tier_1", "tier_2"} and not is_custom_model(model):
        return _violation(
            model,
            tier,
            f"Cannot delete {tier.replace('_', '-')} protected stock models.",
        )
    return None


def check_relational_pair(
    manifest: dict[str, Any],
    *,
    parent_model: str,
    child_model: str,
) -> ProtectedViolation | None:
    """O2M is created ON parent; M2O ON child.

    Link-only allows M2O on custom child → protected parent, but creating O2M on a
    tier-1 parent is a mutation ON the protected model and is blocked.
    """
    parent = (parent_model or "").strip()
    child = (child_model or "").strip()
    # Creating O2M on parent
    v = check_field_create(
        manifest,
        model=parent,
        ttype="one2many",
        relation=child,
        field_name="x_pair",
    )
    if v:
        return v
    # Creating M2O on child (link-only from custom is fine; on tier-1 child blocked)
    return check_field_create(
        manifest,
        model=child,
        ttype="many2one",
        relation=parent,
        field_name="x_pair",
    )


def check_automation_create(
    manifest: dict[str, Any],
    *,
    model: str,
    action_kind: str,
    target_model: str | None = None,
    relation_model: str | None = None,
) -> ProtectedViolation | None:
    """Reject automations whose effect writes tier-1 records (chatter/activity OK)."""
    kind = (action_kind or "").strip().lower()
    model = (model or "").strip()
    if kind in _CHATTER_ACTION_KINDS:
        return None

    for candidate in (target_model, relation_model):
        if candidate and protected_models_for(manifest, candidate) == "tier_1":
            return _violation(
                candidate,
                "tier_1",
                f"Automation action {kind!r} targets tier-1 model {candidate}. "
                f"{safe_alternative_for(candidate)}",
            )

    tier = protected_models_for(manifest, model) if model else None
    if tier == "tier_1":
        return _violation(
            model,
            tier,
            f"Cannot create non-chatter automation on tier-1 model {model}. "
            "Allowed on tier-1: create_activity / mail_post / followers only. "
            f"{safe_alternative_for(model)}",
        )
    return None


def check_invoicing_draft_create(*, source_model: str) -> ProtectedViolation | None:
    """Allow draft account.move create only when triggered from a custom model."""
    if is_custom_model(source_model):
        return None
    return ProtectedViolation(
        reason=f"invoicing_from_protected:{source_model}",
        model=source_model,
        tier="tier_1",
        safe_alternative="Create draft invoices from a custom x_* model via link-only M2M.",
    )


def scrub_spec_for_protected_apply(
    spec: dict[str, Any],
    manifest: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Strip protected mutations from a ModuleSpec; return (cleaned, skip reasons).

    Violations become per-item skips — never a full-apply hard failure.
    """
    out = copy.deepcopy(spec)
    skips: list[str] = []

    models = out.get("models")
    if isinstance(models, list):
        kept_models: list[Any] = []
        for entry in models:
            if not isinstance(entry, dict):
                kept_models.append(entry)
                continue
            mid = str(entry.get("model") or "")
            tier = protected_models_for(manifest, mid) if mid else None
            mode = str(entry.get("mode") or "new")
            if tier == "tier_1" and not is_custom_model(mid):
                # Do not create/inherit behaviour on stock tier-1; keep entry only if
                # we will strip all fields (still allow empty for skip messaging).
                fields = entry.get("fields") or []
                kept_fields: list[Any] = []
                if isinstance(fields, list):
                    for f in fields:
                        if not isinstance(f, dict):
                            continue
                        fname = str(f.get("name") or "")
                        ttype = str(f.get("ttype") or f.get("type") or "")
                        rel = str(f.get("relation") or "") or None
                        viol = check_field_create(
                            manifest,
                            model=mid,
                            ttype=ttype,
                            relation=rel,
                            field_name=fname,
                        )
                        if viol:
                            skips.append(
                                f"field:{mid}.{fname or '?'}: {viol.skip_reason()}"
                            )
                            continue
                        kept_fields.append(f)
                if mode == "inherit" or kept_fields:
                    entry = {**entry, "fields": kept_fields}
                    if not kept_fields and mode == "inherit":
                        skips.append(f"model:{mid}: { _violation(mid, 'tier_1', 'tier-1 inherit/mutate blocked').skip_reason() }")
                        continue
                    kept_models.append(entry)
                else:
                    skips.append(
                        f"model:{mid}: "
                        f"{_violation(mid, 'tier_1', 'tier-1 model mutation blocked').skip_reason()}"
                    )
                continue

            fields = entry.get("fields") or []
            if isinstance(fields, list):
                kept_fields = []
                for f in fields:
                    if not isinstance(f, dict):
                        kept_fields.append(f)
                        continue
                    fname = str(f.get("name") or "")
                    ttype = str(f.get("ttype") or f.get("type") or "")
                    rel = str(f.get("relation") or "") or None
                    viol = check_field_create(
                        manifest,
                        model=mid,
                        ttype=ttype,
                        relation=rel,
                        field_name=fname,
                    )
                    if viol:
                        skips.append(
                            f"field:{mid}.{fname or '?'}: {viol.skip_reason()}"
                        )
                        continue
                    kept_fields.append(f)
                entry = {**entry, "fields": kept_fields}
            kept_models.append(entry)
        out["models"] = kept_models

    for key in ("automations",):
        items = out.get(key)
        if not isinstance(items, list):
            continue
        kept: list[Any] = []
        for auto in items:
            if not isinstance(auto, dict):
                kept.append(auto)
                continue
            auto_model = str(auto.get("model") or auto.get("res_model") or "")
            actions = auto.get("safe_actions") or auto.get("actions") or []
            kinds: list[str] = []
            target: str | None = None
            if isinstance(actions, list):
                for a in actions:
                    if not isinstance(a, dict):
                        continue
                    kinds.append(
                        str(a.get("kind") or a.get("type") or "").strip().lower()
                    )
                    for tk in ("target_model", "model", "res_model"):
                        if a.get(tk):
                            target = str(a.get(tk))
                            break
            # Infer primary kind
            kind = kinds[0] if len(kinds) == 1 else (
                "mail_post"
                if kinds and all(k in _CHATTER_ACTION_KINDS for k in kinds)
                else (kinds[0] if kinds else "update_field")
            )
            # Map AI draft kinds to API kinds
            kind_map = {
                "next_activity": "create_activity",
                "activity": "create_activity",
                "message_post": "mail_post",
                "object_write": "update_field",
                "object_create": "create_record",
                "create": "create_record",
            }
            kind = kind_map.get(kind, kind)
            viol = check_automation_create(
                manifest,
                model=auto_model,
                action_kind=kind,
                target_model=target,
            )
            if viol:
                skips.append(
                    f"automation:{auto.get('name') or auto_model}: {viol.skip_reason()}"
                )
                continue
            kept.append(auto)
        out[key] = kept

    # Smart buttons that would create fields ON tier-1
    buttons = out.get("smart_buttons")
    if isinstance(buttons, list):
        kept_btns: list[Any] = []
        for btn in buttons:
            if not isinstance(btn, dict):
                kept_btns.append(btn)
                continue
            on_model = str(btn.get("on_model") or btn.get("model") or "")
            related = str(btn.get("related_model") or "")
            # Creating O2M/count on on_model — block if tier-1
            if on_model and protected_models_for(manifest, on_model) == "tier_1":
                skips.append(
                    f"smart_button:{btn.get('name') or on_model}: "
                    f"{_violation(on_model, 'tier_1', 'smart button mutates tier-1').skip_reason()}"
                )
                continue
            if related and protected_models_for(manifest, related) == "tier_1":
                # M2O created ON related (target) — blocked if related is tier-1
                skips.append(
                    f"smart_button:{btn.get('name') or related}: "
                    f"{_violation(related, 'tier_1', 'smart button field on tier-1').skip_reason()}"
                )
                continue
            kept_btns.append(btn)
        out["smart_buttons"] = kept_btns

    return out, skips


__all__ = [
    "PROTECTED_DOCS_LINK",
    "ProtectedViolation",
    "check_automation_create",
    "check_field_create",
    "check_field_delete_or_stock_mutate",
    "check_invoicing_draft_create",
    "check_model_delete",
    "check_relational_pair",
    "is_custom_field",
    "is_custom_model",
    "manifest_for_connection",
    "protected_models_for",
    "scrub_spec_for_protected_apply",
]
