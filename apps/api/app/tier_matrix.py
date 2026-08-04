"""Four-tier capability matrix — hosting × edition × modules (TIER-1 / Doc 6 §2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Literal
from urllib.parse import urlparse

from odoo_client.compat import CapabilityId, UnsupportedOdooMajorError, for_major, parse_major

from app.hosting import LOCAL_HOSTS, hosting_hint_from_url

Availability = Literal["yes", "no", "verify", "plan_gated"]
HostingTier = Literal["online", "sh", "onprem", "unknown"]
EditionTier = Literal["community", "enterprise", "unknown"]

# In-process cache: (connection_id, server_version, hosting, edition, modules_hash)
_MATRIX_CACHE: dict[tuple[str, ...], dict[str, Any]] = {}


class TierCapabilityKey(str, Enum):
    CUSTOM_MODELS = "custom_models"
    CUSTOM_FIELDS = "custom_fields"
    VIEWS_COMMUNITY = "views_community"
    VIEWS_ENTERPRISE_TYPES = "views_enterprise_types"
    MENUS_ACTIONS = "menus_actions"
    SECURITY_ACL_RULES = "security_acl_rules"
    QWEB_REPORTS = "qweb_reports"
    XPATH_INHERIT = "xpath_inherit"
    IMAGES_MEDIA = "images_media"
    BASE_AUTOMATION = "base_automation"
    APPROVAL_RULES_STUDIO = "approval_rules_studio"
    PROPERTY_FIELDS = "property_fields"
    MODULE_DEPLOY = "module_deploy"
    CODE_SERVER_ACTIONS = "code_server_actions"
    SANDBOX_PARITY = "sandbox_parity"
    DIRECT_SQL = "direct_sql"
    FINANCIAL_LINK_ONLY = "financial_link_only"
    BULK_RPC_SUITE = "bulk_rpc_suite"
    REPORT_MERGE_PRINT = "report_merge_print"
    PYTHON_MODULE_INSTALL = "python_module_install"
    BARCODE_SCAN_MODULE = "barcode_scan_module"
    EE_PLAYBOOK_SIGN = "ee_playbook_sign"
    EE_PLAYBOOK_DOCUMENTS = "ee_playbook_documents"
    EE_PLAYBOOK_SPREADSHEET = "ee_playbook_spreadsheet"


TIER_CAPABILITY_LABELS: dict[str, str] = {
    TierCapabilityKey.CUSTOM_MODELS.value: "Custom models (ir.model)",
    TierCapabilityKey.CUSTOM_FIELDS.value: "Custom fields (ir.model.fields)",
    TierCapabilityKey.VIEWS_COMMUNITY.value: "Community view types via inherit",
    TierCapabilityKey.VIEWS_ENTERPRISE_TYPES.value: "Enterprise view types (gantt/map/cohort)",
    TierCapabilityKey.MENUS_ACTIONS.value: "Menus & window actions",
    TierCapabilityKey.SECURITY_ACL_RULES.value: "Access rules & record rules",
    TierCapabilityKey.QWEB_REPORTS.value: "QWeb PDF reports",
    TierCapabilityKey.XPATH_INHERIT.value: "XPath view inheritance",
    TierCapabilityKey.IMAGES_MEDIA.value: "Images & attachments",
    TierCapabilityKey.BASE_AUTOMATION.value: "Automations (base_automation)",
    TierCapabilityKey.APPROVAL_RULES_STUDIO.value: "Approval rules (Enterprise)",
    TierCapabilityKey.PROPERTY_FIELDS.value: "Property fields",
    TierCapabilityKey.MODULE_DEPLOY.value: "Installable module deploy",
    TierCapabilityKey.SANDBOX_PARITY.value: "Sandbox parity vs production",
    TierCapabilityKey.DIRECT_SQL.value: "Direct SQL / shell access",
    TierCapabilityKey.FINANCIAL_LINK_ONLY.value: "Financial link-only customization",
    TierCapabilityKey.BULK_RPC_SUITE.value: "Bulk RPC suite (transitions, mass edit, dedupe)",
    TierCapabilityKey.REPORT_MERGE_PRINT.value: "Cross-report merged PDF print",
    TierCapabilityKey.PYTHON_MODULE_INSTALL.value: "Custom Python module install (Option A)",
    TierCapabilityKey.CODE_SERVER_ACTIONS.value: "Live code server actions (Code Studio)",
    TierCapabilityKey.BARCODE_SCAN_MODULE.value: "Exported barcode scan OWL widget module",
    TierCapabilityKey.EE_PLAYBOOK_SIGN.value: "Sign — templates & requests (EE module)",
    TierCapabilityKey.EE_PLAYBOOK_DOCUMENTS.value: "Documents — folders & attach (EE module)",
    TierCapabilityKey.EE_PLAYBOOK_SPREADSHEET.value: "Spreadsheet dashboards (read-only EE)",
}


@dataclass(frozen=True)
class TierContext:
    hosting: HostingTier
    edition: EditionTier
    installed: frozenset[str]
    major: int | None
    server_version: str | None = None
    url: str | None = None
    hosting_hint: str = "unknown"

    @property
    def is_online(self) -> bool:
        return self.hosting == "online"

    @property
    def is_enterprise(self) -> bool:
        return self.edition == "enterprise"


@dataclass(frozen=True)
class TierCapabilityResult:
    key: str
    label: str
    available: Availability
    reason: str
    options: tuple[str, ...] = ()


@dataclass
class EvaluatedTierMatrix:
    hosting: HostingTier
    hosting_hint: str
    edition: EditionTier
    major: int | None
    server_version: str | None
    installed_modules_sample: list[str]
    capabilities: list[TierCapabilityResult] = field(default_factory=list)
    legacy_supported: list[str] = field(default_factory=list)
    legacy_unsupported: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "hosting": self.hosting,
            "hosting_hint": self.hosting_hint,
            "edition": self.edition,
            "major": self.major,
            "server_version": self.server_version,
            "installed_modules_sample": list(self.installed_modules_sample),
            "capabilities": [
                {
                    "key": c.key,
                    "label": c.label,
                    "available": c.available,
                    "reason": c.reason,
                    "options": list(c.options),
                }
                for c in self.capabilities
            ],
            "legacy_supported": list(self.legacy_supported),
            "legacy_unsupported": list(self.legacy_unsupported),
            "warnings": list(self.warnings),
            "message": self.message,
        }


def normalize_hosting_hint(hint: str | None) -> HostingTier:
    mapping = {
        "online": "online",
        "odoo_sh": "sh",
        "self_hosted": "onprem",
        "unknown": "unknown",
    }
    return mapping.get(str(hint or "unknown"), "unknown")  # type: ignore[return-value]


def detect_edition(
    server_version: str | None,
    installed_modules: set[str] | frozenset[str] | None = None,
) -> EditionTier:
    mods = set(installed_modules or [])
    if "web_enterprise" in mods or "enterprise" in mods:
        return "enterprise"
    if server_version:
        low = server_version.lower()
        if "+e" in low or "enterprise" in low:
            return "enterprise"
    if server_version:
        return "community"
    return "unknown"


def detect_hosting(url: str | None, *, web_base_url: str | None = None) -> tuple[HostingTier, str]:
    hint = hosting_hint_from_url(url)
    tier = normalize_hosting_hint(hint)
    if web_base_url:
        extra_hint = hosting_hint_from_url(web_base_url)
        extra_tier = normalize_hosting_hint(extra_hint)
        if tier == "unknown" and extra_tier != "unknown":
            tier = extra_tier
            hint = extra_hint
    if tier == "unknown" and url:
        parsed = urlparse(url if "://" in url else f"http://{url}")
        host = (parsed.hostname or "").lower()
        if host in LOCAL_HOSTS or host.endswith(".local"):
            tier = "onprem"
            hint = "self_hosted"
    return tier, hint


def build_tier_context(
    *,
    url: str | None,
    server_version: str | None,
    installed_modules: list[str] | None = None,
    web_base_url: str | None = None,
) -> TierContext:
    mods = frozenset(installed_modules or [])
    hosting, hint = detect_hosting(url, web_base_url=web_base_url)
    edition = detect_edition(server_version, mods)
    major: int | None = None
    if server_version:
        try:
            major = parse_major(server_version)
        except UnsupportedOdooMajorError:
            major = None
    return TierContext(
        hosting=hosting,
        edition=edition,
        installed=mods,
        major=major,
        server_version=server_version,
        url=url,
        hosting_hint=hint,
    )


def _always_yes(key: TierCapabilityKey, reason: str) -> Callable[[TierContext], TierCapabilityResult]:
    def _rule(ctx: TierContext) -> TierCapabilityResult:
        _ = ctx
        return TierCapabilityResult(
            key=key.value,
            label=TIER_CAPABILITY_LABELS[key.value],
            available="yes",
            reason=reason,
        )

    return _rule


def evaluate_tier_matrix(ctx: TierContext) -> list[TierCapabilityResult]:
    return [rule(ctx) for _, rule in TIER_RULES]


def _rule_module_deploy(ctx: TierContext) -> TierCapabilityResult:
    if ctx.hosting == "online":
        return TierCapabilityResult(
            key=TierCapabilityKey.MODULE_DEPLOY.value,
            label=TIER_CAPABILITY_LABELS[TierCapabilityKey.MODULE_DEPLOY.value],
            available="no",
            reason="Odoo Online cannot install custom Python/modules on the filesystem.",
            options=(
                "Use metadata/XML data import for safe customizations",
                "Move to Odoo.sh or self-host for Option A module deploy",
            ),
        )
    if ctx.hosting == "sh":
        return TierCapabilityResult(
            key=TierCapabilityKey.MODULE_DEPLOY.value,
            label=TIER_CAPABILITY_LABELS[TierCapabilityKey.MODULE_DEPLOY.value],
            available="yes",
            reason="Odoo.sh deploys modules via Git branch push to the build.",
            options=("Use staging branch + matching-major sandbox gate",),
        )
    return TierCapabilityResult(
        key=TierCapabilityKey.MODULE_DEPLOY.value,
        label=TIER_CAPABILITY_LABELS[TierCapabilityKey.MODULE_DEPLOY.value],
        available="yes",
        reason="Self-hosted instances can install modules via filesystem or app promote path.",
    )


def _rule_python_module(ctx: TierContext) -> TierCapabilityResult:
    base = _rule_module_deploy(ctx)
    return TierCapabilityResult(
        key=TierCapabilityKey.PYTHON_MODULE_INSTALL.value,
        label=TIER_CAPABILITY_LABELS[TierCapabilityKey.PYTHON_MODULE_INSTALL.value],
        available=base.available,
        reason=base.reason,
        options=base.options,
    )


def _rule_direct_sql(ctx: TierContext) -> TierCapabilityResult:
    _ = ctx
    return TierCapabilityResult(
        key=TierCapabilityKey.DIRECT_SQL.value,
        label=TIER_CAPABILITY_LABELS[TierCapabilityKey.DIRECT_SQL.value],
        available="no",
        reason="Direct SQL / shell access is never available via public ORM/RPC.",
        options=("Use supported RPC metadata paths only",),
    )


def _rule_sandbox_parity(ctx: TierContext) -> TierCapabilityResult:
    if ctx.hosting == "online":
        return TierCapabilityResult(
            key=TierCapabilityKey.SANDBOX_PARITY.value,
            label=TIER_CAPABILITY_LABELS[TierCapabilityKey.SANDBOX_PARITY.value],
            available="verify",
            reason="Odoo Online has no customer shell — sandbox runs are approximate only.",
            options=("Treat dry-runs as best-effort", "Use Odoo.sh staging for real parity"),
        )
    if ctx.hosting == "sh":
        return TierCapabilityResult(
            key=TierCapabilityKey.SANDBOX_PARITY.value,
            label=TIER_CAPABILITY_LABELS[TierCapabilityKey.SANDBOX_PARITY.value],
            available="yes",
            reason="Odoo.sh staging branches provide real parity before production.",
        )
    return TierCapabilityResult(
        key=TierCapabilityKey.SANDBOX_PARITY.value,
        label=TIER_CAPABILITY_LABELS[TierCapabilityKey.SANDBOX_PARITY.value],
        available="yes",
        reason="Self-hosted Docker/local sandboxes mirror production RPC behavior.",
    )


def _rule_base_automation(ctx: TierContext) -> TierCapabilityResult:
    if "base_automation" in ctx.installed:
        return TierCapabilityResult(
            key=TierCapabilityKey.BASE_AUTOMATION.value,
            label=TIER_CAPABILITY_LABELS[TierCapabilityKey.BASE_AUTOMATION.value],
            available="yes",
            reason="base_automation module is installed on this database.",
        )
    return TierCapabilityResult(
        key=TierCapabilityKey.BASE_AUTOMATION.value,
        label=TIER_CAPABILITY_LABELS[TierCapabilityKey.BASE_AUTOMATION.value],
        available="no",
        reason="base_automation is not installed — install the Automations app/module first.",
        options=("Install base_automation on this database",),
    )


def _rule_approval_rules(ctx: TierContext) -> TierCapabilityResult:
    mods = ctx.installed
    if "studio_customization" in mods or "web_studio" in mods:
        return TierCapabilityResult(
            key=TierCapabilityKey.APPROVAL_RULES_STUDIO.value,
            label=TIER_CAPABILITY_LABELS[TierCapabilityKey.APPROVAL_RULES_STUDIO.value],
            available="verify",
            reason="Studio/approval modules detected — verify approval_rules RPC on this major.",
            options=("Use public approval RPC only — never Studio source",),
        )
    if ctx.is_enterprise:
        return TierCapabilityResult(
            key=TierCapabilityKey.APPROVAL_RULES_STUDIO.value,
            label=TIER_CAPABILITY_LABELS[TierCapabilityKey.APPROVAL_RULES_STUDIO.value],
            available="verify",
            reason="Enterprise edition — approval rules require live probe per major.",
        )
    return TierCapabilityResult(
        key=TierCapabilityKey.APPROVAL_RULES_STUDIO.value,
        label=TIER_CAPABILITY_LABELS[TierCapabilityKey.APPROVAL_RULES_STUDIO.value],
        available="no",
        reason="Approval rules are Enterprise-only and not detected on this database.",
    )


def _rule_property_fields(ctx: TierContext) -> TierCapabilityResult:
    from app.property_fields_probe import PROPERTY_PROBE_FALLBACK

    major = ctx.major
    if major is None:
        return TierCapabilityResult(
            key=TierCapabilityKey.PROPERTY_FIELDS.value,
            label=TIER_CAPABILITY_LABELS[TierCapabilityKey.PROPERTY_FIELDS.value],
            available="verify",
            reason="Property fields require live probe per Odoo major (CMP-7 hook).",
        )
    fb = PROPERTY_PROBE_FALLBACK.get(int(major), PROPERTY_PROBE_FALLBACK[19])
    if fb.get("supported"):
        return TierCapabilityResult(
            key=TierCapabilityKey.PROPERTY_FIELDS.value,
            label=TIER_CAPABILITY_LABELS[TierCapabilityKey.PROPERTY_FIELDS.value],
            available="yes",
            reason=f"Odoo {major}: Properties + PropertiesDefinition supported (probe matrix).",
        )
    if int(major) <= 16:
        return TierCapabilityResult(
            key=TierCapabilityKey.PROPERTY_FIELDS.value,
            label=TIER_CAPABILITY_LABELS[TierCapabilityKey.PROPERTY_FIELDS.value],
            available="no",
            reason=(
                f"Odoo {major}: Properties fields not available via public RPC "
                "(experimental major — use regular fields)."
            ),
        )
    return TierCapabilityResult(
        key=TierCapabilityKey.PROPERTY_FIELDS.value,
        label=TIER_CAPABILITY_LABELS[TierCapabilityKey.PROPERTY_FIELDS.value],
        available="verify",
        reason="Property fields require live probe on this connection.",
    )


def _rule_views_enterprise(ctx: TierContext) -> TierCapabilityResult:
    if ctx.is_enterprise:
        return TierCapabilityResult(
            key=TierCapabilityKey.VIEWS_ENTERPRISE_TYPES.value,
            label=TIER_CAPABILITY_LABELS[TierCapabilityKey.VIEWS_ENTERPRISE_TYPES.value],
            available="yes",
            reason="Enterprise edition — gantt/map/cohort views may be available when modules are installed.",
        )
    return TierCapabilityResult(
        key=TierCapabilityKey.VIEWS_ENTERPRISE_TYPES.value,
        label=TIER_CAPABILITY_LABELS[TierCapabilityKey.VIEWS_ENTERPRISE_TYPES.value],
        available="no",
        reason="Enterprise-only view types are not available on Community edition.",
    )


def _rule_financial_link(ctx: TierContext) -> TierCapabilityResult:
    if ctx.hosting == "online":
        return TierCapabilityResult(
            key=TierCapabilityKey.FINANCIAL_LINK_ONLY.value,
            label=TIER_CAPABILITY_LABELS[TierCapabilityKey.FINANCIAL_LINK_ONLY.value],
            available="plan_gated",
            reason="Odoo Online financial integrations may be link-only — verify on this database.",
        )
    return TierCapabilityResult(
        key=TierCapabilityKey.FINANCIAL_LINK_ONLY.value,
        label=TIER_CAPABILITY_LABELS[TierCapabilityKey.FINANCIAL_LINK_ONLY.value],
        available="yes",
        reason="Financial customizations via public metadata are allowed within tier-1 guardrails.",
    )


def _rule_report_merge(ctx: TierContext) -> TierCapabilityResult:
    if ctx.major is not None and ctx.major >= 17:
        return TierCapabilityResult(
            key=TierCapabilityKey.REPORT_MERGE_PRINT.value,
            label=TIER_CAPABILITY_LABELS[TierCapabilityKey.REPORT_MERGE_PRINT.value],
            available="yes",
            reason="Merged PDF uses HTTP /report/pdf session render on GA majors (17–19).",
        )
    return TierCapabilityResult(
        key=TierCapabilityKey.REPORT_MERGE_PRINT.value,
        label=TIER_CAPABILITY_LABELS[TierCapabilityKey.REPORT_MERGE_PRINT.value],
        available="verify",
        reason="Report merge render path must be probed on this Odoo major.",
    )


def _rule_ee_module(ctx: TierContext, *, key: TierCapabilityKey, modules: list[str], label: str) -> TierCapabilityResult:
    if any(m in ctx.installed for m in modules):
        return TierCapabilityResult(
            key=key.value,
            label=label,
            available="yes",
            reason=f"Module installed: {', '.join(m for m in modules if m in ctx.installed)}.",
        )
    return TierCapabilityResult(
        key=key.value,
        label=label,
        available="no",
        reason=f"Requires installed module(s): {', '.join(modules)}.",
        options=(f"Install {modules[0]} on this database",),
    )


def _rule_ee_playbook_sign(ctx: TierContext) -> TierCapabilityResult:
    return _rule_ee_module(
        ctx,
        key=TierCapabilityKey.EE_PLAYBOOK_SIGN,
        modules=["sign"],
        label=TIER_CAPABILITY_LABELS[TierCapabilityKey.EE_PLAYBOOK_SIGN.value],
    )


def _rule_ee_playbook_documents(ctx: TierContext) -> TierCapabilityResult:
    return _rule_ee_module(
        ctx,
        key=TierCapabilityKey.EE_PLAYBOOK_DOCUMENTS,
        modules=["documents"],
        label=TIER_CAPABILITY_LABELS[TierCapabilityKey.EE_PLAYBOOK_DOCUMENTS.value],
    )


def _rule_ee_playbook_spreadsheet(ctx: TierContext) -> TierCapabilityResult:
    mods = ["spreadsheet_dashboard", "spreadsheet"]
    if any(m in ctx.installed for m in mods):
        hit = next(m for m in mods if m in ctx.installed)
        return TierCapabilityResult(
            key=TierCapabilityKey.EE_PLAYBOOK_SPREADSHEET.value,
            label=TIER_CAPABILITY_LABELS[TierCapabilityKey.EE_PLAYBOOK_SPREADSHEET.value],
            available="yes",
            reason=f"Spreadsheet module installed: {hit}.",
        )
    return TierCapabilityResult(
        key=TierCapabilityKey.EE_PLAYBOOK_SPREADSHEET.value,
        label=TIER_CAPABILITY_LABELS[TierCapabilityKey.EE_PLAYBOOK_SPREADSHEET.value],
        available="no",
        reason="Requires spreadsheet_dashboard or spreadsheet module.",
        options=("Install spreadsheet_dashboard on this database",),
    )


def _rule_ee_module(ctx: TierContext, *, key: TierCapabilityKey, modules: list[str], label: str) -> TierCapabilityResult:
    if any(m in ctx.installed for m in modules):
        return TierCapabilityResult(
            key=key.value,
            label=label,
            available="yes",
            reason=f"Module installed: {', '.join(m for m in modules if m in ctx.installed)}.",
        )
    return TierCapabilityResult(
        key=key.value,
        label=label,
        available="no",
        reason=f"Requires installed module(s): {', '.join(modules)}.",
        options=(f"Install {modules[0]} on this database",),
    )


def _rule_ee_playbook_sign(ctx: TierContext) -> TierCapabilityResult:
    return _rule_ee_module(
        ctx,
        key=TierCapabilityKey.EE_PLAYBOOK_SIGN,
        modules=["sign"],
        label=TIER_CAPABILITY_LABELS[TierCapabilityKey.EE_PLAYBOOK_SIGN.value],
    )


def _rule_ee_playbook_documents(ctx: TierContext) -> TierCapabilityResult:
    return _rule_ee_module(
        ctx,
        key=TierCapabilityKey.EE_PLAYBOOK_DOCUMENTS,
        modules=["documents"],
        label=TIER_CAPABILITY_LABELS[TierCapabilityKey.EE_PLAYBOOK_DOCUMENTS.value],
    )


def _rule_ee_playbook_spreadsheet(ctx: TierContext) -> TierCapabilityResult:
    mods = ["spreadsheet_dashboard", "spreadsheet"]
    if any(m in ctx.installed for m in mods):
        hit = next(m for m in mods if m in ctx.installed)
        return TierCapabilityResult(
            key=TierCapabilityKey.EE_PLAYBOOK_SPREADSHEET.value,
            label=TIER_CAPABILITY_LABELS[TierCapabilityKey.EE_PLAYBOOK_SPREADSHEET.value],
            available="yes",
            reason=f"Spreadsheet module installed: {hit}.",
        )
    return TierCapabilityResult(
        key=TierCapabilityKey.EE_PLAYBOOK_SPREADSHEET.value,
        label=TIER_CAPABILITY_LABELS[TierCapabilityKey.EE_PLAYBOOK_SPREADSHEET.value],
        available="no",
        reason="Requires spreadsheet_dashboard or spreadsheet module.",
        options=("Install spreadsheet_dashboard on this database",),
    )


def _rule_code_server_actions(ctx: TierContext) -> TierCapabilityResult:
    from app.code_studio_gating import MODULE_PATH_OPTIONS

    return TierCapabilityResult(
        key=TierCapabilityKey.CODE_SERVER_ACTIONS.value,
        label=TIER_CAPABILITY_LABELS[TierCapabilityKey.CODE_SERVER_ACTIONS.value],
        available="verify",
        reason="Live state=code is probed per connection on first Code Studio open — never assumed by hosting tier.",
        options=tuple(MODULE_PATH_OPTIONS),
    )


TIER_RULES: tuple[tuple[TierCapabilityKey, Callable[[TierContext], TierCapabilityResult]], ...] = (
    (TierCapabilityKey.CUSTOM_MODELS, _always_yes(TierCapabilityKey.CUSTOM_MODELS, "Public ORM supports ir.model on all tiers.")),
    (TierCapabilityKey.CUSTOM_FIELDS, _always_yes(TierCapabilityKey.CUSTOM_FIELDS, "Public ORM supports ir.model.fields on all tiers.")),
    (TierCapabilityKey.VIEWS_COMMUNITY, _always_yes(TierCapabilityKey.VIEWS_COMMUNITY, "Community view inherit/mutate via public RPC.")),
    (TierCapabilityKey.VIEWS_ENTERPRISE_TYPES, _rule_views_enterprise),
    (TierCapabilityKey.MENUS_ACTIONS, _always_yes(TierCapabilityKey.MENUS_ACTIONS, "Menus and ir.actions.* via public RPC.")),
    (TierCapabilityKey.SECURITY_ACL_RULES, _always_yes(TierCapabilityKey.SECURITY_ACL_RULES, "Access rules via res.groups / ir.model.access.")),
    (TierCapabilityKey.QWEB_REPORTS, _always_yes(TierCapabilityKey.QWEB_REPORTS, "QWeb reports via ir.actions.report + ir.ui.view.")),
    (TierCapabilityKey.XPATH_INHERIT, _always_yes(TierCapabilityKey.XPATH_INHERIT, "XPath inherit on ir.ui.view.")),
    (TierCapabilityKey.IMAGES_MEDIA, _always_yes(TierCapabilityKey.IMAGES_MEDIA, "Attachments/binary fields via public RPC.")),
    (TierCapabilityKey.BASE_AUTOMATION, _rule_base_automation),
    (TierCapabilityKey.APPROVAL_RULES_STUDIO, _rule_approval_rules),
    (TierCapabilityKey.PROPERTY_FIELDS, _rule_property_fields),
    (TierCapabilityKey.MODULE_DEPLOY, _rule_module_deploy),
    (TierCapabilityKey.PYTHON_MODULE_INSTALL, _rule_python_module),
    (TierCapabilityKey.CODE_SERVER_ACTIONS, _rule_code_server_actions),
    (TierCapabilityKey.BARCODE_SCAN_MODULE, _rule_module_deploy),
    (TierCapabilityKey.SANDBOX_PARITY, _rule_sandbox_parity),
    (TierCapabilityKey.DIRECT_SQL, _rule_direct_sql),
    (TierCapabilityKey.FINANCIAL_LINK_ONLY, _rule_financial_link),
    (TierCapabilityKey.BULK_RPC_SUITE, _always_yes(TierCapabilityKey.BULK_RPC_SUITE, "Bulk suite uses public ORM/RPC only.")),
    (TierCapabilityKey.REPORT_MERGE_PRINT, _rule_report_merge),
    (TierCapabilityKey.EE_PLAYBOOK_SIGN, _rule_ee_playbook_sign),
    (TierCapabilityKey.EE_PLAYBOOK_DOCUMENTS, _rule_ee_playbook_documents),
    (TierCapabilityKey.EE_PLAYBOOK_SPREADSHEET, _rule_ee_playbook_spreadsheet),
)


def _legacy_matrix(ctx: TierContext) -> tuple[list[str], list[dict[str, str]], bool, list[str]]:
    from app.capabilities import CAPABILITY_LABELS

    warnings: list[str] = []
    if ctx.hosting == "online":
        warnings.append(
            "Custom Python module install is not available on Odoo Online — "
            "use data/XML export or move to Odoo.sh / self-host for Option A."
        )
    if any(m in ctx.installed for m in ("web_studio", "studio_customization")):
        warnings.append(
            "Studio-related modules detected — public ORM/RPC only; Studio source is never used."
        )
    if ctx.major is None:
        unsupported = [
            {
                "id": cid.value,
                "label": CAPABILITY_LABELS.get(cid.value, cid.value),
                "reason": "Unsupported or unknown Odoo major.",
            }
            for cid in CapabilityId
        ]
        return [], unsupported, False, warnings
    try:
        caps = for_major(ctx.major, edition=ctx.edition if ctx.edition != "unknown" else "community")
    except UnsupportedOdooMajorError:
        return [], [], False, warnings
    supported = sorted(c.value for c in caps.enabled)
    unsupported = [
        {
            "id": cid.value,
            "label": CAPABILITY_LABELS.get(cid.value, cid.value),
            "reason": f"Not available on Odoo {ctx.major} ({ctx.edition})",
        }
        for cid in CapabilityId
        if cid not in caps.enabled
    ]
    return supported, unsupported, bool(getattr(caps, "ga", ctx.major in {17, 18, 19})), warnings


def evaluate_full_matrix(
    *,
    url: str | None,
    server_version: str | None,
    installed_modules: list[str] | None = None,
    web_base_url: str | None = None,
    connection_id: str | None = None,
    use_cache: bool = True,
) -> EvaluatedTierMatrix:
    ctx = build_tier_context(
        url=url,
        server_version=server_version,
        installed_modules=installed_modules,
        web_base_url=web_base_url,
    )
    cache_key = (
        connection_id or "",
        server_version or "",
        ctx.hosting,
        ctx.edition,
        ",".join(sorted(ctx.installed)[:60]),
    )
    if use_cache and cache_key in _MATRIX_CACHE:
        return _MATRIX_CACHE[cache_key]

    caps = evaluate_tier_matrix(ctx)
    supported, unsupported, ga, warnings = _legacy_matrix(ctx)
    py_row = next((c for c in caps if c.key == TierCapabilityKey.PYTHON_MODULE_INSTALL.value), None)
    message_parts = [
        f"Odoo {ctx.major or '?'} {ctx.edition} on {ctx.hosting} hosting",
        f"{sum(1 for c in caps if c.available == 'yes')} capabilities yes",
    ]
    if ctx.hosting == "online":
        message_parts.append("Odoo Online constraints apply")
    if ctx.is_enterprise:
        message_parts.append("Enterprise edition detected")
    result = EvaluatedTierMatrix(
        hosting=ctx.hosting,
        hosting_hint=ctx.hosting_hint,
        edition=ctx.edition,
        major=ctx.major,
        server_version=server_version,
        installed_modules_sample=sorted(ctx.installed)[:40],
        capabilities=caps,
        legacy_supported=supported,
        legacy_unsupported=unsupported,
        warnings=warnings,
        message=". ".join(message_parts) + (" (GA)" if ga else ""),
    )
    if use_cache:
        _MATRIX_CACHE[cache_key] = result
    return result


def invalidate_matrix_cache(connection_id: str | None = None) -> None:
    global _MATRIX_CACHE
    if connection_id is None:
        _MATRIX_CACHE.clear()
        return
    drop = [k for k in _MATRIX_CACHE if k[0] == connection_id]
    for k in drop:
        _MATRIX_CACHE.pop(k, None)


def python_modules_allowed_from_matrix(ctx: TierContext) -> bool:
    row = _rule_python_module(ctx)
    return row.available == "yes"


def python_modules_allowed(hosting_hint: str) -> bool:
    """Backward-compatible shim used by hosting.py and promote."""
    ctx = TierContext(
        hosting=normalize_hosting_hint(hosting_hint),
        edition="unknown",
        installed=frozenset(),
        major=None,
        hosting_hint=hosting_hint or "unknown",
    )
    return python_modules_allowed_from_matrix(ctx)
