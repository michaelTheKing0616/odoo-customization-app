"""P4 Config Atlas elite — class-wide Stock/Config/Batch detection + handoff.

Resolves plain-language config/batch briefs onto Atlas class + recipe + risk
without Prefer-stealing Prefer field packs or Option A invent classes.

Completeness ≠ Cert ≠ Autopilot. Promote stays human. Preview ≠ posted/confirmed.
"""

from __future__ import annotations

import re
from typing import Any

# Explicit config/batch operator phrases (class-wide — not one client SOW).
_ATLAS_BATCH_RE = re.compile(
    r"(?i)\b("
    r"lock\s+(?:accounting\s+)?dates?|period\s+lock|fiscalyear\s+lock|tax\s+lock|"
    r"freeze\s+(?:the\s+)?books|close\s+period|"
    r"tax\s+pack|fiscal\s+year|"
    r"opening\s+balances?|trial\s+balance\s+upload|"
    r"journal\s+batch|upload\s+(?:journal|gl)\s+entr|"
    r"partners?\s+csv|products?\s+csv|"
    r"bulk\s+(?:create\s+)?(?:partners?|customers?|vendors?|products?)|"
    r"master\s+data\s+batch|"
    r"invoice\s+batch|upload\s+invoices?|bulk\s+invoices?|"
    r"vendor\s+bills?\s+batch|bills?\s+batch|"
    r"order\s+batch|sales?\s+order\s+batch|purchase\s+order\s+batch|"
    r"upload\s+(?:sales?\s+|purchase\s+)?orders?|"
    r"bulk\s+(?:sales?\s+|purchase\s+)?orders?|"
    r"settings\s+board|payment\s+terms\s+pack|"
    r"config\s+atlas|instance\s+config|"
    r"payment\s+matching\s+batch|payments?\s+batch"
    r")\b"
)

# Prefer / invent cues that must win over Atlas (do not steal).
_NOT_ATLAS_RE = re.compile(
    r"(?i)\b("
    r"prefer\s+for\s+delivery|add\s+(?:a\s+)?field\s+on|"
    r"build\s+(?:a\s+)?(?:new\s+)?app|visitor\s+log|"
    r"mark-?up|withh?olding\s+tax|\bwht\b|"
    r"cbn|central\s+bank|fx\s+rate|exchange\s+rate|"
    r"custom\s+python|owl\s+widget|option\s+a|"
    r"delivery\s+(?:note|slip)|qweb|report\s+layout"
    r")\b"
)

# Ordered golden → atlas handoff (first match wins).
_GOLDEN_ROUTES: tuple[tuple[re.Pattern[str], dict[str, str]], ...] = (
    (
        re.compile(r"(?i)\block\s+(?:accounting\s+)?dates?|period\s+lock|freeze\s+books"),
        {
            "atlas_class": "accounting",
            "recipe_id": "accounting.lock_dates",
            "risk": "L3",
            "route": "config",
            "intent_id": "accounting.lock_dates",
        },
    ),
    (
        re.compile(r"(?i)\btax\s+pack\b"),
        {
            "atlas_class": "accounting",
            "recipe_id": "accounting.tax_pack",
            "risk": "L2",
            "route": "config",
            "intent_id": "accounting.taxes",
        },
    ),
    (
        re.compile(r"(?i)\bfiscal\s+year\b"),
        {
            "atlas_class": "accounting",
            "recipe_id": "accounting.fiscal_year",
            "risk": "L2",
            "route": "config",
            "intent_id": "accounting.fy",
        },
    ),
    (
        re.compile(r"(?i)\b(?:partners?\s+csv|bulk\s+(?:create\s+)?(?:partners?|customers?|vendors?)|master\s+data\s+batch)\b"),
        {
            "atlas_class": "master_data",
            "recipe_id": "master_data.partners_batch",
            "risk": "L1",
            "route": "journal?tab=master",
            "intent_id": "master.partners",
        },
    ),
    (
        re.compile(r"(?i)\b(?:products?\s+csv|bulk\s+(?:create\s+)?products?)\b"),
        {
            "atlas_class": "master_data",
            "recipe_id": "master_data.products_batch",
            "risk": "L1",
            "route": "journal?tab=master",
            "intent_id": "master.products",
        },
    ),
    (
        re.compile(r"(?i)\b(?:invoice\s+batch|upload\s+invoices?|bulk\s+invoices?|vendor\s+bills?\s+batch)\b"),
        {
            "atlas_class": "document_batch",
            "recipe_id": "document_batch.invoices",
            "risk": "L1",
            "route": "journal?tab=invoices",
            "intent_id": "docs.invoices",
        },
    ),
    (
        re.compile(
            r"(?i)\b("
            r"order\s+batch|sales?\s+order\s+batch|purchase\s+order\s+batch|"
            r"upload\s+(?:sales?\s+|purchase\s+)?orders?|"
            r"bulk\s+(?:sales?\s+|purchase\s+)?orders?"
            r")\b"
        ),
        {
            "atlas_class": "document_batch",
            "recipe_id": "document_batch.orders",
            "risk": "L1",
            "route": "journal?tab=orders",
            "intent_id": "docs.orders",
        },
    ),
    (
        re.compile(r"(?i)\b(?:settings\s+board|payment\s+terms\s+pack)\b"),
        {
            "atlas_class": "settings",
            "recipe_id": "settings.board_apply",
            "risk": "L2",
            "route": "config",
            "intent_id": "settings.board",
        },
    ),
    (
        re.compile(r"(?i)\b(?:journal\s+batch|upload\s+(?:journal|gl)\s+entr|opening\s+balances?)\b"),
        {
            "atlas_class": "accounting",
            "recipe_id": "accounting.journal_batch",
            "risk": "L1",
            "route": "journal?tab=batch",
            "intent_id": "accounting.journal_batch",
        },
    ),
    (
        re.compile(r"(?i)\b(?:config\s+atlas|instance\s+config)\b"),
        {
            "atlas_class": "settings",
            "recipe_id": "settings.board_apply",
            "risk": "L2",
            "route": "config",
            "intent_id": "settings.board",
        },
    ),
)


def is_atlas_config_batch_brief(prompt: str) -> bool:
    """True when the brief is Stock/Config/Batch Atlas grain (not Prefer/Option A)."""
    text = prompt or ""
    if not text.strip():
        return False
    if _NOT_ATLAS_RE.search(text) and not _ATLAS_BATCH_RE.search(text):
        return False
    # Prefer field packs mention Sales Orders but are Prefer, not order batch.
    if re.search(r"(?i)\badd\s+(?:a\s+)?field\s+on\b", text):
        return False
    if re.search(r"(?i)\bprefer\s+for\s+delivery\b", text):
        return False
    return bool(_ATLAS_BATCH_RE.search(text))


def resolve_atlas_handoff(prompt: str) -> dict[str, Any] | None:
    """Map a config/batch brief → atlas_class / recipe_id / risk / route."""
    if not is_atlas_config_batch_brief(prompt):
        return None
    text = prompt or ""
    for pattern, handoff in _GOLDEN_ROUTES:
        if pattern.search(text):
            out = dict(handoff)
            out["delivery_lane"] = "online_metadata"
            out["artifact_kind"] = "stock_config"
            out["prove_status"] = "not_required"
            out["honesty"] = (
                "Preview ≠ posted/confirmed. L3 lock dates require confirm. "
                "Completeness ≠ Cert ≠ Autopilot. Promote stays human."
            )
            return out
    # Generic Atlas hub
    return {
        "atlas_class": "settings",
        "recipe_id": None,
        "risk": "L1",
        "route": "config",
        "intent_id": None,
        "delivery_lane": "online_metadata",
        "artifact_kind": "stock_config",
        "prove_status": "not_required",
        "honesty": (
            "Preview ≠ posted/confirmed. Completeness ≠ Cert ≠ Autopilot. "
            "Promote stays human."
        ),
    }


def atlas_zero_stub_intents() -> bool:
    """Elite gate: no Atlas intent remains stub once recipes are complete."""
    from app.batch_os.atlas.loader import load_atlas

    for cls in load_atlas():
        for intent in cls.intents:
            if intent.status == "stub":
                return False
    return True


__all__ = [
    "atlas_zero_stub_intents",
    "is_atlas_config_batch_brief",
    "resolve_atlas_handoff",
]
