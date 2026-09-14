"""Stock bootstrap: install modules, l10n/CoA probe, warehouse/company recipes."""

from __future__ import annotations

import time
from typing import Any

from odoo_client.client import OdooClientError

from app.invoicing_l10n import detect_l10n
from app.job_autopilot.packet import BootstrapReport, JobPacket, ProbeResult
from app.job_autopilot.recipes import RECIPE_VERSION, run_stock_recipes

_ALWAYS_SKIP = frozenset({"base", "web"})
_GENERIC_COA = "l10n_generic_coa"
_INSTALL_ATTEMPTS = 5
_BUSY_MARKERS = (
    "processing a scheduled action",
    "module operations are not possible",
)


def _refresh_module_list(client: Any) -> None:
    updater = getattr(client, "update_module_list", None)
    if callable(updater):
        try:
            updater()
        except Exception:  # noqa: BLE001
            return


def _module_state(client: Any, name: str) -> str | None:
    getter = getattr(client, "get_module_state", None)
    if callable(getter):
        row = getter(name)
        if isinstance(row, dict):
            return str(row.get("state") or "") or None
        return None
    try:
        rows = client.execute_kw(
            "ir.module.module",
            "search_read",
            [[("name", "=", name)]],
            {"fields": ["state"], "limit": 1},
        )
    except Exception:  # noqa: BLE001
        return None
    if not rows:
        return None
    return str(rows[0].get("state") or "") or None


def _is_module_busy(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(marker in text for marker in _BUSY_MARKERS)


def _try_install(client: Any, name: str) -> None:
    installer = getattr(client, "install_module_by_name", None)
    if callable(installer):
        installer(name)
        return
    client.ensure_module_installed(name)


def _install(client: Any, name: str, report: BootstrapReport) -> None:
    if name in _ALWAYS_SKIP:
        return
    if name in report.installed or name in report.already_installed:
        return
    state = _module_state(client, name)
    if state is None:
        _refresh_module_list(client)
        state = _module_state(client, name)
    if state == "installed":
        report.already_installed.append(name)
        return
    if state is None:
        report.skipped.append(name)
        report.warnings.append(f"Module {name!r} not found on this instance — skipped.")
        return
    last_exc: BaseException | None = None
    for attempt in range(1, _INSTALL_ATTEMPTS + 1):
        if _module_state(client, name) == "installed":
            if name not in report.installed and name not in report.already_installed:
                report.already_installed.append(name)
            return
        try:
            _try_install(client, name)
            report.installed.append(name)
            return
        except (OdooClientError, Exception) as exc:  # noqa: BLE001
            last_exc = exc
            if not _is_module_busy(exc) or attempt >= _INSTALL_ATTEMPTS:
                break
            time.sleep(min(2 * attempt, 8))
    if _module_state(client, name) == "installed":
        if name not in report.installed and name not in report.already_installed:
            report.already_installed.append(name)
        return
    report.skipped.append(name)
    report.warnings.append(f"Could not install {name}: {last_exc}")


def _reconcile_skipped(client: Any, report: BootstrapReport) -> None:
    """Sale/l10n often pull contacts as a dependency after a busy-lock skip."""
    still: list[str] = []
    for name in report.skipped:
        if _module_state(client, name) == "installed":
            if name not in report.installed and name not in report.already_installed:
                report.already_installed.append(name)
            report.warnings = [w for w in report.warnings if f"Could not install {name}" not in w]
            continue
        still.append(name)
    report.skipped = still


def _l10n_candidates(packet: JobPacket) -> list[str]:
    names: list[str] = []
    if packet.l10n_module:
        names.append(packet.l10n_module)
    cc = (packet.country_code or "").strip().lower()
    if cc:
        names.append(f"l10n_{cc}")
    names.append(_GENERIC_COA)
    out: list[str] = []
    seen: set[str] = set()
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def _resolve_l10n_module(client: Any, packet: JobPacket) -> str | None:
    """Prefer the country pack on the addons path; fall back to generic CoA."""
    _refresh_module_list(client)
    for name in _l10n_candidates(packet):
        if _module_state(client, name) is not None:
            return name
    return packet.l10n_module


def _company_id(client: Any) -> int | None:
    try:
        rows = client.execute_kw(
            "res.company",
            "search_read",
            [[]],
            {"fields": ["id", "name"], "limit": 1},
        )
    except Exception:  # noqa: BLE001
        return None
    if not rows:
        return None
    return int(rows[0]["id"])


def _search_id(
    client: Any,
    model: str,
    domain: list[Any],
    *,
    context: dict[str, Any] | None = None,
) -> int | None:
    kw: dict[str, Any] = {"limit": 1}
    if context:
        kw["context"] = context
    try:
        ids = client.execute_kw(model, "search", [domain], kw)
    except Exception:  # noqa: BLE001
        return None
    if not ids:
        return None
    return int(ids[0])


def activate_currency(client: Any, code: str) -> tuple[int | None, str]:
    """Find ISO currency (including inactive), activate it, return (id, detail)."""
    iso = (code or "").strip().upper()
    if not iso:
        return None, "no currency code"
    cur_id = _search_id(
        client,
        "res.currency",
        [("name", "=", iso)],
        context={"active_test": False},
    )
    if cur_id is None:
        cur_id = _search_id(client, "res.currency", [("name", "=", iso)])
    if cur_id is None:
        return None, f"{iso} not in res.currency"
    try:
        client.execute_kw("res.currency", "write", [[cur_id], {"active": True}])
    except Exception as exc:  # noqa: BLE001
        return cur_id, f"{iso} id={cur_id} activate failed: {exc}"
    return cur_id, f"{iso} id={cur_id} active"


def _probe_company_currency(client: Any, packet: JobPacket, report: BootstrapReport) -> None:
    cid = _company_id(client)
    if cid is None:
        report.probes.append(ProbeResult(name="company", ok=False, detail="res.company missing"))
        return
    wrote: list[str] = []
    if packet.company_name:
        try:
            client.execute_kw("res.company", "write", [[cid], {"name": packet.company_name}])
            wrote.append("name")
        except Exception as exc:  # noqa: BLE001
            report.warnings.append(f"Company name write skipped: {exc}")
    if packet.country_code:
        country_id = _search_id(client, "res.country", [("code", "=", packet.country_code)])
        if country_id:
            try:
                client.execute_kw("res.company", "write", [[cid], {"country_id": country_id}])
                report.country_id = country_id
                wrote.append("country_id")
            except Exception as exc:  # noqa: BLE001
                report.warnings.append(f"Company country write skipped: {exc}")
        else:
            report.warnings.append(
                f"Country {packet.country_code} not found on res.country — country unchanged."
            )
    if packet.currency:
        cur_id, detail = activate_currency(client, packet.currency)
        report.probes.append(
            ProbeResult(name="currency", ok=cur_id is not None, detail=detail)
        )
        if cur_id:
            report.currency_id = cur_id
            try:
                client.execute_kw("res.company", "write", [[cid], {"currency_id": cur_id}])
                wrote.append("currency_id")
            except Exception as exc:  # noqa: BLE001
                report.warnings.append(
                    f"Company currency {packet.currency} activated but not written: {exc}. "
                    "Odoo blocks currency change once journals/moves exist. Recreate the "
                    "sandbox DB without Accounting preinstalled "
                    "(SKIP_GATE_MODULES=1 ./docker/init-db.sh) so country/currency land "
                    "before sale/account."
                )
        else:
            report.warnings.append(
                f"Currency {packet.currency} not found — company currency unchanged."
            )
    report.probes.append(
        ProbeResult(
            name="company",
            ok=bool(wrote) or not (packet.country_code or packet.currency or packet.company_name),
            detail=f"company_id={cid} wrote={wrote}",
        )
    )


def _probe_warehouse(client: Any, report: BootstrapReport) -> None:
    exists = getattr(client, "model_exists", None)
    if callable(exists) and not exists("stock.warehouse"):
        report.probes.append(
            ProbeResult(name="warehouse", ok=False, detail="stock.warehouse model missing")
        )
        return
    try:
        rows = client.execute_kw(
            "stock.warehouse",
            "search_read",
            [[]],
            {"fields": ["id", "code", "name"], "limit": 1},
        )
    except Exception as exc:  # noqa: BLE001
        report.probes.append(ProbeResult(name="warehouse", ok=False, detail=str(exc)))
        return
    if rows:
        row = rows[0]
        report.probes.append(
            ProbeResult(
                name="warehouse",
                ok=True,
                detail=f"exists id={row.get('id')} code={row.get('code')}",
            )
        )
        return
    cid = _company_id(client)
    payload: dict[str, Any] = {"name": "Main Warehouse", "code": "MAIN"}
    if cid:
        payload["company_id"] = cid
    try:
        wid = client.execute_kw("stock.warehouse", "create", [payload])
    except Exception as exc:  # noqa: BLE001
        report.probes.append(ProbeResult(name="warehouse", ok=False, detail=str(exc)))
        report.warnings.append(f"Warehouse create failed: {exc}")
        return
    report.probes.append(
        ProbeResult(name="warehouse", ok=True, detail=f"created id={wid} code=MAIN")
    )


def _reconcile_named_apps(client: Any, packet: JobPacket, report: BootstrapReport) -> None:
    """Sale/POS often install account as a dependency — count it, don't leave it invisible."""
    for name in packet.stock_apps:
        if name in _ALWAYS_SKIP:
            continue
        if name in report.installed or name in report.already_installed:
            continue
        if _module_state(client, name) == "installed":
            report.already_installed.append(name)


def _install_l10n_pack(client: Any, packet: JobPacket, report: BootstrapReport) -> str | None:
    """Install the country pack (or generic CoA) before/after Accounting as needed."""
    resolved = _resolve_l10n_module(client, packet)
    if resolved:
        _install(client, resolved, report)
    return resolved


def _stamp_l10n_probe(client: Any, packet: JobPacket, report: BootstrapReport) -> None:
    """Stamp l10n after stock apps exist. Missing account *before* install is not a warning."""
    try:
        detected = detect_l10n(client)
    except Exception as exc:  # noqa: BLE001
        report.probes.append(ProbeResult(name="l10n", ok=False, detail=str(exc)))
        return
    account_on = _module_state(client, "account") == "installed"
    if not account_on:
        exists = getattr(client, "model_exists", None)
        account_on = bool(callable(exists) and exists("account.move"))
    country_unknown = not (packet.country_code or packet.l10n_module)
    if detected.get("ok"):
        ok = True
        detail = str(detected.get("message") or detected)
    elif account_on and country_unknown:
        ok = True
        detail = (
            "Accounting installed; country unset (unknowns — do not assume). "
            "Instance CoA in use."
        )
    else:
        ok = False
        detail = str(detected.get("message") or "l10n not detected")
        report.warnings.append(detail)
    report.probes.append(ProbeResult(name="l10n", ok=ok, detail=detail))


def _probe_coa(client: Any, report: BootstrapReport) -> None:
    try:
        exists = getattr(client, "model_exists", None)
        if callable(exists) and not exists("account.account"):
            report.probes.append(
                ProbeResult(name="coa", ok=False, detail="account.account model missing")
            )
            return
        ids = client.execute_kw("account.account", "search", [[]], {"limit": 1})
        report.probes.append(
            ProbeResult(
                name="coa",
                ok=bool(ids),
                detail="account.account present" if ids else "chart of accounts empty",
            )
        )
    except Exception as exc:  # noqa: BLE001
        report.warnings.append(f"CoA probe skipped: {exc}")


def bootstrap_stock(client: Any, packet: JobPacket) -> BootstrapReport:
    """Install inferred stock apps and run config recipes with probes. RPC only.

    Country and currency are written *before* Accounting so Odoo loads the matching
    l10n CoA. Installing sale/account first on a US-default company creates journal
    items and permanently blocks a later NGN/KES currency write.
    """
    report = BootstrapReport(recipe_version=RECIPE_VERSION)
    _refresh_module_list(client)
    _probe_company_currency(client, packet, report)
    has_fiscal_target = bool(packet.country_code or packet.l10n_module)
    wants_account = "account" in packet.stock_apps or has_fiscal_target
    if has_fiscal_target:
        # Named country / l10n pack only. Unknown country must not assume l10n_generic_coa.
        _install_l10n_pack(client, packet, report)
    already = set(report.installed) | set(report.already_installed)
    for name in packet.stock_apps:
        if name in already:
            continue
        _install(client, name, report)
    _reconcile_skipped(client, report)
    _reconcile_named_apps(client, packet, report)
    if wants_account:
        if has_fiscal_target:
            _install_l10n_pack(client, packet, report)
        _stamp_l10n_probe(client, packet, report)
        _probe_coa(client, report)
    if packet.warehouse_needed or "stock" in packet.stock_apps:
        _probe_warehouse(client, report)
    run_stock_recipes(client, packet, report)
    try:
        from app.job_autopilot.demo_seed import (
            probe_leftover_stock_form_fields,
            probe_leftover_verticals,
        )

        report.probes.extend(probe_leftover_verticals(client))
        report.probes.extend(probe_leftover_stock_form_fields(client))
    except Exception as exc:  # noqa: BLE001
        report.warnings.append(f"Sandbox identity probe skipped: {exc}")
    report.message = (
        f"Installed {len(report.installed)}, already {len(report.already_installed)}, "
        f"skipped {len(report.skipped)}; {sum(1 for p in report.probes if p.ok)} probes ok "
        f"(recipe v{report.recipe_version})."
    )
    return report


def install_named_modules(client: Any, names: list[str]) -> BootstrapReport:
    """Install a module list (Config Packet delta). Same busy retries as Autopilot."""
    report = BootstrapReport(recipe_version=RECIPE_VERSION)
    _refresh_module_list(client)
    for name in names:
        _install(client, name, report)
    _reconcile_skipped(client, report)
    report.message = (
        f"Installed {len(report.installed)}, already {len(report.already_installed)}, "
        f"skipped {len(report.skipped)}."
    )
    return report


__all__ = ["bootstrap_stock", "activate_currency", "install_named_modules"]
