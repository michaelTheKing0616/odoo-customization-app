"""Residual full_app session/IR identity gates — Contract wins over pack bleed.

When Diagnosis locks a residual full_app (Visitor Log) but the draft still carries
prior Restaurant/pack IR (domain_pack, foreign x_* models, field-type display
names), rebuild the draft from the residual brief. Never rewrite a
Diagnosis-confirmed Contract to match contaminated pack IR.
"""

from __future__ import annotations

import copy
import re
from typing import Any

_FIELD_TYPE_TITLE_RE = re.compile(
    r"(?i)^\s*`?(char|text|integer|boolean|float|monetary|selection|many2one|"
    r"many2many|one2many|date|datetime|html|binary)`?\s+field\b"
)
_FIELD_FOR_TITLE_RE = re.compile(
    r"(?i)\bfield\s+for\s+['\"]?\w+['\"]?"
)


def is_field_type_display_name(title: str) -> bool:
    """True when display_name was mangled from a field ttype/label (never an app noun)."""
    text = str(title or "").strip()
    if not text:
        return False
    if _FIELD_TYPE_TITLE_RE.match(text):
        return True
    if _FIELD_FOR_TITLE_RE.search(text) and len(text) < 64:
        return True
    return False


def _residual_slug_and_title(
    prompt: str,
    locked: dict[str, Any] | None = None,
    *,
    prefer_locked: bool = False,
) -> tuple[str, str]:
    """Return (slug, title). Prompt residual noun wins unless prefer_locked."""
    if isinstance(locked, dict):
        if locked.get("inherit_existing") or str(locked.get("grain") or "") in {
            "field_pack",
            "feature_slice",
        }:
            return "", ""
    locked_title = (
        str(locked.get("title") or "").strip() if isinstance(locked, dict) else ""
    )
    display = ""
    tech = ""
    try:
        from app.ai_document_shape import naming_from_residual

        display, tech = naming_from_residual(prompt or "")
    except Exception:  # noqa: BLE001
        pass
    if prefer_locked and locked_title:
        title = locked_title
        slug = tech or re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:40]
    else:
        title = display or locked_title
        slug = tech or (
            re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:40] if title else ""
        )
    return slug, title


def _pack_title(draft: dict[str, Any]) -> str:
    pack_id = str(draft.get("domain_pack") or "")
    if not pack_id:
        return ""
    try:
        from app.ai_domain_packs import load_domain_pack

        pack = load_domain_pack(pack_id) or {}
        return str(pack.get("display_name") or pack_id)
    except Exception:  # noqa: BLE001
        return pack_id


def _titles_diverge(a: str, b: str) -> bool:
    left = (a or "").strip().lower()
    right = (b or "").strip().lower()
    if not left or not right:
        return False
    if left == right:
        return False
    if left in right or right in left:
        return False
    return True


def _custom_x_models(draft: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if mid.startswith("x_") and str(model.get("mode") or "new") != "inherit":
            if not mid.endswith("_line") and not mid.endswith("_party"):
                out.append(mid)
    return out


def draft_mismatches_residual_identity(
    draft: dict[str, Any],
    *,
    prompt: str = "",
    locked: dict[str, Any] | None = None,
    prefer_locked: bool = False,
) -> bool:
    """True when draft IR is foreign pack / field-title noise under a residual brief."""
    text = prompt or str(draft.get("_user_prompt") or "")
    slug, title = _residual_slug_and_title(text, locked, prefer_locked=prefer_locked)
    if not slug and not title:
        return False
    display = str(draft.get("display_name") or "").strip()
    if is_field_type_display_name(display):
        return True
    pack_title = _pack_title(draft)
    if pack_title and title and _titles_diverge(pack_title, title):
        return True
    want = f"x_{slug}" if slug and not slug.startswith("x_") else slug
    customs = _custom_x_models(draft)
    if want and customs:
        # Class: foreign pack surface replaced residual primary (even a single
        # header) — Vehicle brief must not render as only x_purchase_request.
        if want not in customs:
            return True
        # Residual primary present but a foreign pack header remains
        # (Vehicle Request + x_purchase_request bleed is the dual-header class).
        # Same-stem satellites (x_vehicle_request + x_vehicle_assignment) stay.
        if want in customs:
            stem = want.replace("x_", "", 1).split("_")[0]
            foreign = [
                m
                for m in customs
                if m != want
                and m.replace("x_", "", 1).split("_")[0] != stem
            ]
            if foreign:
                return True
    if title and display and _titles_diverge(title, display) and pack_title:
        return True
    return False


def enforce_residual_draft_identity(
    draft: dict[str, Any],
    *,
    prompt: str = "",
    locked: dict[str, Any] | None = None,
    prefer_locked: bool = False,
) -> list[str]:
    """Purge foreign pack IR and rebuild residual register when identity diverges.

    Structural: any residual full_app whose Contract/brief noun diverges from
    domain_pack or carries field-type display_name — not Visitor-only.
    """
    notes: list[str] = []
    text = prompt or str(draft.get("_user_prompt") or "")
    if isinstance(locked, dict):
        if locked.get("inherit_existing") or str(locked.get("grain") or "") in {
            "field_pack",
            "feature_slice",
        }:
            return notes
        if locked.get("needs_module"):
            return notes
    if not draft_mismatches_residual_identity(
        draft, prompt=text, locked=locked, prefer_locked=prefer_locked
    ):
        # Still scrub field-type titles even when model set looks fine.
        display = str(draft.get("display_name") or "").strip()
        if is_field_type_display_name(display):
            slug, title = _residual_slug_and_title(
                text, locked, prefer_locked=prefer_locked
            )
            if title:
                draft["display_name"] = title
                notes.append(f"identity: display_name {display!r} → {title}")
            if slug:
                draft["technical_name"] = slug
        return notes

    slug, title = _residual_slug_and_title(text, locked, prefer_locked=prefer_locked)
    pack_id = str(draft.get("domain_pack") or "")
    notes.append(
        f"identity: residual «{title or slug}» diverges from pack/IR "
        f"({pack_id or display_preview(draft)}) — rebuilding register"
    )

    # Drop pack authority so register shape + honor can purge satellites.
    draft.pop("domain_pack", None)
    draft.pop("_pack_model_ids", None)
    draft.pop("_pack_reuse_stock", None)
    draft["_document_shape"] = "register"
    draft["_ambition"] = "thin"
    draft["grain"] = "full_app"
    draft.pop("_component", None)

    want = f"x_{slug}" if slug and not slug.startswith("x_") else (slug or "")
    customs = _custom_x_models(draft)
    keep = {want} if want else set()
    removed = {m for m in customs if m not in keep}
    # Also drop stock inherits invented by pack merge (calendar.event, etc.) unless Prefer.
    for model in list(draft.get("models") or []):
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        mode = str(model.get("mode") or "new")
        if mid.startswith("x_"):
            continue
        if mode == "inherit" and mid not in {
            "res.partner",
            "hr.employee",
            "res.users",
            "res.company",
            "res.currency",
        }:
            # calendar.event etc. from restaurant pack — purge.
            removed.add(mid)

    if removed:
        try:
            from app.ai_domain_packs import _purge_draft_artifacts_for_models

            _purge_draft_artifacts_for_models(draft, removed)
            notes.append(f"identity: purged {len(removed)} foreign models")
        except Exception:  # noqa: BLE001
            draft["models"] = [
                m
                for m in (draft.get("models") or [])
                if isinstance(m, dict) and str(m.get("model") or "") not in removed
            ]

    # Rebuild primary residual if missing / hollow.
    try:
        from app.ai_document_shape import (
            ensure_residual_must_do_fields,
            seed_register_from_brief,
        )

        models = [
            m
            for m in (draft.get("models") or [])
            if isinstance(m, dict) and str(m.get("model") or "") == want
        ]
        if not models or len((models[0].get("fields") or [])) <= 1:
            # Full register reseed — keeps Must-do columns.
            seed = {"_user_prompt": text}
            seed_notes = seed_register_from_brief(seed, prompt=text)
            notes.extend(seed_notes)
            for key in (
                "models",
                "views",
                "menus",
                "actions",
                "depends",
                "technical_name",
                "display_name",
                "smart_buttons",
                "automations",
                "_document_shape",
                "_ambition",
            ):
                if key in seed:
                    draft[key] = copy.deepcopy(seed[key])
            draft["grain"] = "full_app"
        else:
            notes.extend(ensure_residual_must_do_fields(draft, prompt=text))
            if title:
                draft["display_name"] = title
            if slug:
                draft["technical_name"] = slug
    except Exception as exc:  # noqa: BLE001
        notes.append(f"identity: rebuild skipped ({exc})")
        if title:
            draft["display_name"] = title
        if slug:
            draft["technical_name"] = slug

    # Clear menus/actions that pointed at purged models — reseed will add app menu later.
    if removed:
        draft["menus"] = [
            m
            for m in (draft.get("menus") or [])
            if isinstance(m, dict)
            and not any(
                doomed in str(m.get("action_xml_id") or "")
                or doomed in str(m.get("technical_name") or "")
                for doomed in removed
            )
        ]
        draft["actions"] = [
            a
            for a in (draft.get("actions") or [])
            if isinstance(a, dict) and str(a.get("model") or "") not in removed
        ]
        draft["smart_buttons"] = [
            b
            for b in (draft.get("smart_buttons") or [])
            if isinstance(b, dict)
            and str(b.get("on_model") or "") not in removed
            and str(b.get("related_model") or "") not in removed
        ]
        draft["views"] = [
            v
            for v in (draft.get("views") or [])
            if isinstance(v, dict) and str(v.get("model") or "") not in removed
        ]

    if title:
        draft["display_name"] = title
    if is_field_type_display_name(str(draft.get("display_name") or "")):
        draft["display_name"] = title or slug.replace("_", " ").title()
    return notes


def display_preview(draft: dict[str, Any]) -> str:
    return str(draft.get("display_name") or draft.get("technical_name") or "draft")[:48]


def locked_contract_should_win(locked: dict[str, Any] | None) -> bool:
    """Diagnosis-confirmed residual Contract is authoritative for Generate."""
    if not isinstance(locked, dict):
        return False
    if locked.get("inherit_existing"):
        return False
    if str(locked.get("grain") or "full_app") != "full_app":
        return False
    if locked.get("needs_module"):
        return False
    source = str(locked.get("source") or "")
    # Session dump / diagnosis / locked block — never reconciled_draft.
    if source in {"reconciled_draft"}:
        return False
    title = str(locked.get("title") or "").strip()
    return bool(title)


__all__ = [
    "draft_mismatches_residual_identity",
    "enforce_residual_draft_identity",
    "is_field_type_display_name",
    "locked_contract_should_win",
]
