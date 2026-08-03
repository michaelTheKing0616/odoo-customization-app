"""COPY_GUIDE three-options gating built from TIER-1 matrix (TIER-2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.tier_matrix import (
    TierCapabilityKey,
    TierContext,
    build_tier_context,
    evaluate_tier_matrix,
)

GatingChoiceId = Literal[
    "upgrade_plan",
    "export_module",
    "install_module",
    "leave_out",
    "use_staging",
]

SANDBOX_APPROXIMATION_TEMPLATE = (
    "Approximate validation — this sandbox is a clean Odoo {major}, not a copy of your "
    "instance. Differences in installed apps or data can still cause conflicts."
)


@dataclass(frozen=True)
class GatingOption:
    id: GatingChoiceId
    label: str


@dataclass(frozen=True)
class GatingCallout:
    feature: str
    title: str
    why: str
    options: tuple[str, ...]
    available: bool
    capability_key: str
    choices: tuple[GatingOption, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature": self.feature,
            "title": self.title,
            "why": self.why,
            "options": list(self.options),
            "available": self.available,
            "capability_key": self.capability_key,
            "gating_choices": [{"id": c.id, "label": c.label} for c in self.choices],
        }


def _capability_row(ctx: TierContext, key: TierCapabilityKey) -> str:
    for row in evaluate_tier_matrix(ctx):
        if row.key == key.value:
            return row.available
    return "no"


def automations_gating(ctx: TierContext) -> GatingCallout:
    available = _capability_row(ctx, TierCapabilityKey.BASE_AUTOMATION) == "yes"
    if available:
        return GatingCallout(
            feature="automations",
            title="Automations are available on this connection",
            why="The base_automation module is installed.",
            options=(),
            available=True,
            capability_key=TierCapabilityKey.BASE_AUTOMATION.value,
        )

    if ctx.hosting == "online":
        why = (
            "Automation rules need the base_automation module, which isn't installed on this "
            "Odoo Online instance (it ships with Odoo's Custom plan)."
        )
        options = (
            "Upgrade the Odoo subscription to the Custom plan to unlock live automations.",
            "Deploying to Odoo.sh or self-hosted? Export this as a module with scheduled actions instead.",
            "Or leave automations out — everything else here works fully.",
        )
        choices = (
            GatingOption(
                id="upgrade_plan",
                label="Upgrade the Odoo subscription to the Custom plan",
            ),
            GatingOption(
                id="export_module",
                label="Export as a module with scheduled actions instead",
            ),
            GatingOption(id="leave_out", label="Leave automations out"),
        )
    else:
        why = (
            "Automation rules need the base_automation module, which isn't installed on this database."
        )
        options = (
            "Install the Automations app (base_automation) on this database.",
            "Export this as a module with scheduled actions (ir.cron) instead.",
            "Or leave automations out — everything else here works fully.",
        )
        choices = (
            GatingOption(
                id="install_module",
                label="Install the Automations app (base_automation)",
            ),
            GatingOption(
                id="export_module",
                label="Export as a module with scheduled actions (ir.cron)",
            ),
            GatingOption(id="leave_out", label="Leave automations out"),
        )

    return GatingCallout(
        feature="automations",
        title="Automations aren't available on this connection",
        why=why,
        options=options,
        available=False,
        capability_key=TierCapabilityKey.BASE_AUTOMATION.value,
        choices=choices,
    )


def approvals_gating(ctx: TierContext) -> GatingCallout:
    status = _capability_row(ctx, TierCapabilityKey.APPROVAL_RULES_STUDIO)
    if status == "yes":
        return GatingCallout(
            feature="approval_rules",
            title="Approval rules are available on this connection",
            why="Enterprise approval modules are detected and verified.",
            options=(),
            available=True,
            capability_key=TierCapabilityKey.APPROVAL_RULES_STUDIO.value,
        )
    if status == "verify":
        return GatingCallout(
            feature="approval_rules",
            title="Approval rules need live verification on this connection",
            why=(
                "Enterprise or Studio modules were detected — approval rule RPC must be "
                "verified on this Odoo major before writes."
            ),
            options=(
                "Run a live probe on an Enterprise instance with web_studio installed.",
                "Use safe automations (base_automation) instead of Studio approval rules.",
                "Or leave approval rules out — everything else here works fully.",
            ),
            available=False,
            capability_key=TierCapabilityKey.APPROVAL_RULES_STUDIO.value,
            choices=(
                GatingOption(id="leave_out", label="Leave approval rules out"),
                GatingOption(
                    id="export_module",
                    label="Export metadata without Studio approval rules",
                ),
            ),
        )
    return GatingCallout(
        feature="approval_rules",
        title="Approval rules aren't available on this connection",
        why="Approval rules are Enterprise-only and were not detected on this database.",
        options=(
            "Upgrade to Odoo Enterprise with Studio on a self-hosted or Odoo.sh instance.",
            "Use safe automations (base_automation) for simpler workflows instead.",
            "Or leave approval rules out — everything else here works fully.",
        ),
        available=False,
        capability_key=TierCapabilityKey.APPROVAL_RULES_STUDIO.value,
        choices=(
            GatingOption(id="upgrade_plan", label="Upgrade to Odoo Enterprise with Studio"),
            GatingOption(id="leave_out", label="Leave approval rules out"),
        ),
    )


def online_python_promote_gating() -> GatingCallout:
    return GatingCallout(
        feature="promote_python",
        title="Python module promote isn't available on Odoo Online",
        why=(
            "Odoo Online cannot install custom Python modules on the filesystem — only "
            "metadata/data import paths are supported."
        ),
        options=(
            "Re-export with install_mode=data for metadata-only modules.",
            "Move to Odoo.sh or self-hosted for Option A Python module deploy.",
            "Or keep the validated zip for a non-Online target connection.",
        ),
        available=False,
        capability_key=TierCapabilityKey.PYTHON_MODULE_INSTALL.value,
        choices=(
            GatingOption(id="export_module", label="Re-export with install_mode=data"),
            GatingOption(id="leave_out", label="Cancel promote"),
        ),
    )


def deployment_panel(ctx: TierContext, *, technical_name: str = "custom_module") -> dict[str, Any]:
    if ctx.hosting == "sh":
        return {
            "tier": "sh",
            "title": "Deploy via Odoo.sh Git push",
            "body": (
                f"Export includes DEPLOY_ODOO_SH.md with branch naming, module placement under "
                f"your repo's addons path, and staging → production steps for {technical_name}."
            ),
            "options": [
                "Push to a staging branch and run the matching-major sandbox gate first.",
                "Merge to production only after validation passes.",
            ],
            "include_deploy_doc": True,
        }
    if ctx.hosting == "online":
        return {
            "tier": "online",
            "title": "Portable ownership on Odoo Online",
            "body": (
                "Odoo Online accepts metadata/data module import — not custom Python on the "
                "filesystem. Export install_mode=data for safe customizations, or plan a move "
                "to Odoo.sh / self-hosted for full module deploy."
            ),
            "options": [
                "Use install_mode=data for metadata-only exports.",
                "See migration assist (TIER-3) for what Odoo.sh unlocks.",
                "Promote Python zips only on self-hosted or Odoo.sh connections.",
            ],
            "include_deploy_doc": False,
        }
    return {
        "tier": "onprem",
        "title": "Self-hosted promote path",
        "body": (
            "Validate in sandbox, then promote to this connection's filesystem or use the "
            "existing hub promote flow."
        ),
        "options": [
            "Run sandbox validation before promote.",
            "Prefer a matching-major sandbox (same Odoo major as this connection).",
        ],
        "include_deploy_doc": False,
    }


def sandbox_approximation_label(major: int | None) -> str:
    return SANDBOX_APPROXIMATION_TEMPLATE.format(major=major or "?")


def sh_staging_suggestion(*, has_other_sh: bool, other_sh_name: str | None = None) -> str | None:
    if not has_other_sh:
        return None
    label = other_sh_name or "your Odoo.sh staging connection"
    return (
        f"For real parity, run sandbox validation against {label} "
        "(Odoo.sh staging branch) instead of approximate validation on Odoo Online."
    )


def gating_context_for_connection(
    *,
    url: str | None,
    server_version: str | None,
    installed_modules: list[str] | None = None,
    web_base_url: str | None = None,
) -> TierContext:
    return build_tier_context(
        url=url,
        server_version=server_version,
        installed_modules=installed_modules,
        web_base_url=web_base_url,
    )
