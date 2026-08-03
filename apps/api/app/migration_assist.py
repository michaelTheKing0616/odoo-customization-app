"""Odoo Online → Odoo.sh migration unlock panel (TIER-3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.tier_matrix import (
    TIER_CAPABILITY_LABELS,
    TierContext,
    TierCapabilityKey,
    build_tier_context,
    evaluate_tier_matrix,
)

ODOO_SH_DOCS_URL = "https://www.odoo.com/documentation/master/administration/odoo_sh.html"
ODOO_MIGRATION_DOCS_URL = "https://www.odoo.com/documentation/master/administration/on_premise.html"

# Capabilities most relevant when moving Online → Odoo.sh (Doc 6 gap 2).
MIGRATION_HIGHLIGHT_KEYS = (
    TierCapabilityKey.MODULE_DEPLOY,
    TierCapabilityKey.PYTHON_MODULE_INSTALL,
    TierCapabilityKey.SANDBOX_PARITY,
    TierCapabilityKey.BASE_AUTOMATION,
    TierCapabilityKey.REPORT_MERGE_PRINT,
    TierCapabilityKey.BULK_RPC_SUITE,
)


@dataclass(frozen=True)
class MigrationUnlockRow:
    key: str
    label: str
    online_status: str
    sh_status: str
    unlocks: bool
    reason: str


@dataclass
class MigrationAssistPanel:
    eligible: bool
    hosting: str
    title: str
    body: str
    unlocks: list[MigrationUnlockRow]
    docs_links: list[dict[str, str]]
    disclaimer: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "hosting": self.hosting,
            "title": self.title,
            "body": self.body,
            "unlocks": [
                {
                    "key": u.key,
                    "label": u.label,
                    "online_status": u.online_status,
                    "sh_status": u.sh_status,
                    "unlocks": u.unlocks,
                    "reason": u.reason,
                }
                for u in self.unlocks
            ],
            "docs_links": list(self.docs_links),
            "disclaimer": self.disclaimer,
            "message": self.message,
        }


def _sh_context_from(ctx: TierContext) -> TierContext:
    return TierContext(
        hosting="sh",
        edition=ctx.edition,
        installed=ctx.installed,
        major=ctx.major,
        server_version=ctx.server_version,
        url="https://staging.odoo.sh",
        hosting_hint="odoo_sh",
    )


def _improves(online_status: str, sh_status: str) -> bool:
    rank = {"yes": 3, "verify": 2, "plan_gated": 1, "no": 0}
    return rank.get(sh_status, 0) > rank.get(online_status, 0)


def migration_assist_panel(ctx: TierContext) -> MigrationAssistPanel:
    if ctx.hosting != "online":
        return MigrationAssistPanel(
            eligible=False,
            hosting=ctx.hosting,
            title="Migration assist applies to Odoo Online connections",
            body=(
                "This connection is not detected as Odoo Online — compare hosting tiers "
                "via the capability matrix instead."
            ),
            unlocks=[],
            docs_links=[
                {"label": "Odoo.sh documentation", "url": ODOO_SH_DOCS_URL},
            ],
            disclaimer="No legal or commercial promises — public docs only.",
            message="Not an Odoo Online target",
        )

    sh_ctx = _sh_context_from(ctx)
    online_rows = {r.key: r for r in evaluate_tier_matrix(ctx)}
    sh_rows = {r.key: r for r in evaluate_tier_matrix(sh_ctx)}
    unlocks: list[MigrationUnlockRow] = []

    for key in MIGRATION_HIGHLIGHT_KEYS:
        ok = online_rows.get(key.value)
        sk = sh_rows.get(key.value)
        if ok is None or sk is None:
            continue
        if _improves(ok.available, sk.available):
            unlocks.append(
                MigrationUnlockRow(
                    key=key.value,
                    label=TIER_CAPABILITY_LABELS.get(key.value, key.value),
                    online_status=ok.available,
                    sh_status=sk.available,
                    unlocks=True,
                    reason=sk.reason,
                )
            )

    return MigrationAssistPanel(
        eligible=True,
        hosting=ctx.hosting,
        title="What moving to Odoo.sh unlocks for this connection",
        body=(
            "Odoo Online limits filesystem module deploy and true staging parity. "
            "Odoo.sh adds Git-based module deploy, staging branches, and Option A Python paths."
        ),
        unlocks=unlocks,
        docs_links=[
            {"label": "Odoo.sh administration guide", "url": ODOO_SH_DOCS_URL},
            {"label": "Odoo hosting documentation", "url": ODOO_MIGRATION_DOCS_URL},
        ],
        disclaimer=(
            "Migration timing, pricing, and eligibility are Odoo's commercial process — "
            "we do not promise outcomes or approval."
        ),
        message=f"{len(unlocks)} capability improvement(s) Online → Odoo.sh",
    )


def migration_assist_for_connection(
    *,
    url: str | None,
    server_version: str | None,
    installed_modules: list[str] | None = None,
) -> MigrationAssistPanel:
    ctx = build_tier_context(
        url=url,
        server_version=server_version,
        installed_modules=installed_modules,
    )
    return migration_assist_panel(ctx)
