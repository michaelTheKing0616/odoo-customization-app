"""Protected Core Modules — pattern-based tier classification (Document 5).

Classifies Odoo **module names** (not Studio SKUs) into protection tiers. Tier-1 modules
must never receive generated business logic (automations, writes, computed fields that alter
behaviour). Tier-2 modules may be extended via documented inheritance only.

Model→tier mapping uses the first segment of the technical model name as the owning module
hint (``account.move`` → ``account``). Chatter/activity on protected records stays allowed;
the restriction is on the **effect** (writing to or altering behaviour of a protected
model), not the mechanism.

Model→module mapping table (representative):
- ``account.move``, ``account.move.line``, ``account.tax``, ``account.payment`` → ``account``
- ``payment.transaction``, ``payment.token`` → ``payment``
- ``hr.payslip``, ``hr.payroll.*`` → ``hr_payroll``
- ``sign.request``, ``sign.template`` → ``sign``
- ``sale.subscription``, ``sale.subscription.line`` → ``sale_subscription``
- ``mail.message``, ``mail.followers`` → ``mail`` (tier-2 extend; posting allowed)
- ``res.users``, ``res.partner`` → unclassified (safe to link from custom models)
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

PROTECTED_PATTERNS: dict[str, re.Pattern[str]] = {
    "accounting_core": re.compile(r"^account($|_)"),
    "fiscal_localization": re.compile(r"^l10n_"),
    "stock_valuation": re.compile(
        r"^(stock_account|stock_landed_costs|mrp_account|mrp_landed_costs|"
        r"mrp_subcontracting_account|mrp_subcontracting_landed_costs)$"
    ),
    "payment_processing": re.compile(r"^payment($|_)"),
    "pos_financial": re.compile(
        r"^pos_(account_tax_python|online_payment.*|stripe|adyen|razorpay|paytm|pine_labs|six|"
        r".*_(stripe|adyen|razorpay|paytm|pine_labs|six))"
    ),
    "payroll": re.compile(r"^hr_payroll"),
    "esign": re.compile(r"^sign"),
    "subscriptions": re.compile(r"^sale_subscription"),
    "iap_billing": re.compile(r"^iap($|_)"),
    "framework_core": re.compile(r"^(base|web)$"),
    "auth_security": re.compile(r"^auth_"),
    "messaging_audit": re.compile(r"^mail$"),
}

TIER_1_KEYS: frozenset[str] = frozenset(
    {
        "accounting_core",
        "payment_processing",
        "pos_financial",
        "payroll",
        "esign",
        "subscriptions",
        "iap_billing",
        "stock_valuation",
    }
)

TIER_2_KEYS: frozenset[str] = frozenset(
    {
        "fiscal_localization",
        "framework_core",
        "auth_security",
        "messaging_audit",
    }
)

_GUARDAIL_EFFECT_CLOSING = (
    "The restriction is on the EFFECT (writing to or altering the behaviour of a protected "
    "model), not the mechanism. Link-only relations from custom models into protected models "
    "are allowed; generating logic that mutates protected records is not."
)


def classify(module_name: str) -> str | None:
    """Return ``tier_1``, ``tier_2``, or ``None`` for an Odoo module technical name."""
    name = (module_name or "").strip()
    if not name:
        return None
    for key, pattern in PROTECTED_PATTERNS.items():
        if pattern.search(name):
            if key in TIER_1_KEYS:
                return "tier_1"
            if key in TIER_2_KEYS:
                return "tier_2"
    return None


def build_manifest(
    module_names: list[str],
    source_label: str,
) -> dict[str, Any]:
    """Classify a module list into tier buckets for caching / API responses."""
    tier_1: dict[str, list[str]] = {k: [] for k in sorted(TIER_1_KEYS)}
    tier_2: dict[str, list[str]] = {k: [] for k in sorted(TIER_2_KEYS)}
    unclassified: list[str] = []
    seen: set[str] = set()

    for raw in module_names:
        mod = (raw or "").strip()
        if not mod or mod in seen:
            continue
        seen.add(mod)
        matched_key: str | None = None
        for key, pattern in PROTECTED_PATTERNS.items():
            if pattern.search(mod):
                matched_key = key
                break
        if matched_key is None:
            unclassified.append(mod)
            continue
        if matched_key in TIER_1_KEYS:
            tier_1[matched_key].append(mod)
        elif matched_key in TIER_2_KEYS:
            tier_2[matched_key].append(mod)
        else:
            unclassified.append(mod)

    for bucket in (*tier_1.values(), *tier_2.values(), [unclassified]):
        bucket.sort()

    return {
        "source": source_label,
        "tier_1_never_generate_logic": tier_1,
        "tier_2_extend_only": tier_2,
        "unclassified_count": len(unclassified),
        "unclassified_sample": unclassified[:50],
    }


def _module_hint_for_model(model_name: str) -> str | None:
    """Best-effort module owner from a model technical name."""
    name = (model_name or "").strip()
    if not name or "." not in name:
        return None
    head = name.split(".", 1)[0]
    # Payroll models often live under hr_payroll* modules but use hr.* prefix
    if head == "hr" and "payroll" in name:
        return "hr_payroll"
    if head == "sale" and name.startswith("sale.subscription"):
        return "sale_subscription"
    if head == "sign":
        return "sign"
    if head == "payment":
        return "payment"
    if head == "account":
        return "account"
    if head == "mail":
        return "mail"
    return head


def protected_models_for(manifest: dict[str, Any], model_name: str) -> str | None:
    """Map a model technical name to ``tier_1`` / ``tier_2`` using the manifest buckets."""
    hint = _module_hint_for_model(model_name)
    if not hint:
        return None
    tier = classify(hint)
    if tier:
        return tier
    # Also scan manifest lists (handles Enterprise module names not matching model prefix)
    t1 = manifest.get("tier_1_never_generate_logic") or {}
    t2 = manifest.get("tier_2_extend_only") or {}
    for mods in t1.values():
        if isinstance(mods, list) and any(hint == m or hint in m for m in mods):
            return "tier_1"
    for mods in t2.values():
        if isinstance(mods, list) and any(hint == m or hint in m for m in mods):
            return "tier_2"
    return None


def category_for_model(model_name: str) -> str | None:
    """Return the PROTECTED_PATTERNS key for a model, if any."""
    hint = _module_hint_for_model(model_name)
    if not hint:
        return None
    for key, pattern in PROTECTED_PATTERNS.items():
        if pattern.search(hint):
            return key
    return None


def safe_alternative_for(model_or_module: str) -> str:
    """Human-readable safe alternative for a refused tier-1 capability."""
    cat = category_for_model(model_or_module)
    if cat is None:
        for key, pattern in PROTECTED_PATTERNS.items():
            if pattern.search((model_or_module or "").strip()):
                cat = key
                break
    alternatives = {
        "accounting_core": (
            "Link custom models to account.move / account.payment via many2one; "
            "use Odoo's standard invoicing or Power Ops recipes that call Odoo methods — "
            "do not generate posting, tax, or state-mutation logic."
        ),
        "payment_processing": (
            "Link to payment.transaction for display/reference only; complete payments "
            "through Odoo's installed payment providers."
        ),
        "pos_financial": (
            "Do not generate POS payment/tax logic; configure providers in Odoo POS settings."
        ),
        "payroll": (
            "Link hr.employee / custom staff models; do not generate payslip or payroll rules."
        ),
        "esign": (
            "Link to sign.request for reference only; use Odoo Sign flows for signatures."
        ),
        "subscriptions": (
            "Model renewals on a custom workflow and link to sale.order / account.move; "
            "do not recreate sale_subscription billing logic."
        ),
        "iap_billing": (
            "Do not generate IAP credit/billing logic; use Odoo's IAP services as-is."
        ),
        "stock_valuation": (
            "Link stock.picking / product; do not generate valuation or landed-cost logic."
        ),
    }
    return alternatives.get(
        cat or "",
        "Link to the protected model via many2one/one2many only; do not generate write/"
        "automation logic that mutates protected records.",
    )


def guardrail_prompt(manifest: dict[str, Any]) -> str:
    """Render Doc 5 §4-style guardrail text with tier-1 category names (token-efficient)."""
    t1 = manifest.get("tier_1_never_generate_logic") or {}
    active_cats = [k for k, mods in t1.items() if isinstance(mods, list) and mods]
    cats = ", ".join(active_cats) if active_cats else ", ".join(sorted(TIER_1_KEYS))
    return (
        "PROTECTED MODULES (mandatory — do not violate):\n"
        f"Tier-1 categories present: {cats}.\n"
        "Never generate business logic against tier-1 modules/models: no automations, "
        "server actions, related_write, or field mutations that change protected records. "
        "Do not recreate accounting, payroll, payments, subscriptions, e-sign, or IAP flows.\n"
        "Tier-2 modules (localization, framework, auth, mail) — extend via inheritance only; "
        "do not replace core behaviour.\n"
        f"{_GUARDAIL_EFFECT_CLOSING}"
    )


_DATA_DIR = Path(__file__).resolve().parent / "data"
_ODOO_GIT_URL = "https://github.com/odoo/odoo.git"
_SUPPORTED_VERSIONS = ("16.0", "17.0", "18.0", "19.0")


def _normalize_odoo_version(server_version: str | None) -> str:
    """Map ``19.0+e-20250802`` → ``19.0`` with GA major fallback."""
    if not server_version:
        return "19.0"
    m = re.match(r"^(\d+)\.(\d+)", server_version.strip())
    if not m:
        return "19.0"
    ver = f"{m.group(1)}.{m.group(2)}"
    return ver if ver in _SUPPORTED_VERSIONS else "19.0"


def _snapshot_path(version: str) -> Path:
    key = version.replace(".", "_")
    return _DATA_DIR / f"community_modules_{key}.json"


def load_vendored_community_modules(version: str) -> list[str]:
    """Offline fallback: vendored community module name list for a major."""
    path = _snapshot_path(_normalize_odoo_version(version))
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    mods = data.get("modules") or []
    return sorted({str(m).strip() for m in mods if str(m).strip()})


def fetch_community_modules_from_source(
    version: str,
    *,
    timeout: int = 120,
) -> tuple[list[str], str]:
    """Path A: sparse-checkout of ``odoo/odoo`` community addons for ``version``.

    Returns ``(module_names, source_label)``. Falls back to vendored snapshot on failure.
    """
    ver = _normalize_odoo_version(version)
    tmp = Path(tempfile.mkdtemp(prefix=f"odoo-src-{ver.replace('.', '')}-"))
    try:
        subprocess.run(
            [
                "git",
                "clone",
                "--filter=blob:none",
                "--no-checkout",
                "--depth",
                "1",
                "-b",
                ver,
                _ODOO_GIT_URL,
                str(tmp),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        subprocess.run(
            ["git", "sparse-checkout", "init", "--cone"],
            cwd=tmp,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        subprocess.run(
            ["git", "sparse-checkout", "set", "addons", "odoo/addons"],
            cwd=tmp,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        subprocess.run(
            ["git", "checkout"],
            cwd=tmp,
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        names: set[str] = set()
        for rel in ("addons", "odoo/addons"):
            root = tmp / rel
            if root.is_dir():
                names.update(
                    p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")
                )
        modules = sorted(names)
        if not modules:
            raise ValueError("no community modules discovered")
        return modules, f"community_source:git:{ver}"
    except (subprocess.SubprocessError, OSError, ValueError, FileNotFoundError) as exc:
        fallback = load_vendored_community_modules(ver)
        if fallback:
            return fallback, f"vendored_snapshot:{ver} ({exc.__class__.__name__})"
        raise RuntimeError(
            f"community module fetch failed for {ver} and no vendored snapshot exists"
        ) from exc
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def fetch_live_installed_module_names(client: Any) -> list[str]:
    """Path B: installed module technical names from a live Odoo connection."""
    rows = client.list_modules(installed_only=True, applications_only=False)
    return sorted({str(m.name).strip() for m in rows if getattr(m, "name", None)})


def merge_connection_manifest(
    *,
    version: str,
    community_modules: list[str],
    live_modules: list[str],
    community_source_label: str,
    live_source_label: str = "live_instance",
) -> dict[str, Any]:
    """Merge Path A + Path B manifests per Doc 5 §3."""
    ver = _normalize_odoo_version(version)
    community = build_manifest(community_modules, community_source_label)
    live = build_manifest(live_modules, live_source_label)
    union = sorted(set(community_modules) | set(live_modules))
    merged = build_manifest(union, f"merged:{ver}")
    merged["version"] = ver
    merged["community_source"] = community
    merged["live_instance"] = live
    merged["module_counts"] = {
        "community_source": len(community_modules),
        "live_instance": len(live_modules),
        "union": len(union),
    }
    merged["tier_summary"] = tier_summary(merged)
    return merged


def tier_summary(manifest: dict[str, Any]) -> dict[str, int]:
    """Count modules per tier bucket for API responses."""
    t1 = manifest.get("tier_1_never_generate_logic") or {}
    t2 = manifest.get("tier_2_extend_only") or {}
    t1_count = sum(len(v) for v in t1.values() if isinstance(v, list))
    t2_count = sum(len(v) for v in t2.values() if isinstance(v, list))
    return {
        "tier_1_modules": t1_count,
        "tier_2_modules": t2_count,
        "unclassified": int(manifest.get("unclassified_count") or 0),
    }


def manifest_from_json(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def manifest_to_json(manifest: dict[str, Any]) -> str:
    return json.dumps(manifest, separators=(",", ":"))


def community_manifest_for_version(version: str) -> dict[str, Any]:
    """Offline manifest for tests/gates (vendored snapshot with source fallback)."""
    ver = _normalize_odoo_version(version)
    community = load_vendored_community_modules(ver)
    label = f"vendored_snapshot:{ver}"
    if not community:
        community, label = fetch_community_modules_from_source(ver)
    return merge_connection_manifest(
        version=ver,
        community_modules=community,
        live_modules=[],
        community_source_label=label,
    )


def refresh_connection_protected_manifest(
    *,
    server_version: str | None,
    client: Any | None = None,
    force_source_fetch: bool = False,
) -> dict[str, Any]:
    """Build + return merged manifest; uses live modules when ``client`` is provided."""
    ver = _normalize_odoo_version(server_version)
    if force_source_fetch:
        community, label = fetch_community_modules_from_source(ver)
    else:
        community = load_vendored_community_modules(ver)
        label = f"vendored_snapshot:{ver}"
        if not community:
            community, label = fetch_community_modules_from_source(ver)
    live: list[str] = []
    if client is not None:
        try:
            live = fetch_live_installed_module_names(client)
        except Exception:  # noqa: BLE001 — probe must not fail connections
            live = []
    return merge_connection_manifest(
        version=ver,
        community_modules=community,
        live_modules=live,
        community_source_label=label,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI parity stub for PCM-2 (`python -m app.protected_modules`)."""
    parser = argparse.ArgumentParser(description="Classify Odoo modules by protection tier")
    parser.add_argument("--version", default="19.0", help="Odoo version label for output")
    parser.add_argument(
        "--modules",
        nargs="*",
        default=["account", "crm", "l10n_ng", "payment_stripe"],
        help="Module names to classify",
    )
    parser.add_argument(
        "--fetch-source",
        action="store_true",
        help="Fetch community module list from odoo/odoo git (Path A)",
    )
    parser.add_argument("--output", help="Write manifest JSON to path")
    args = parser.parse_args(argv)
    if args.fetch_source:
        modules, label = fetch_community_modules_from_source(args.version)
        manifest = merge_connection_manifest(
            version=args.version,
            community_modules=modules,
            live_modules=list(args.modules or []),
            community_source_label=label,
        )
    else:
        manifest = build_manifest(list(args.modules), source_label=f"cli:{args.version}")
    payload = json.dumps(manifest, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(payload)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
