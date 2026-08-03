/** Connection capability helpers (shared by Automations, Designer, etc.). */

import type { CapabilityMatrix, Connection } from "@/lib/api";

/**
 * Fail-closed when capabilities are unknown.
 * API still refuses unsupported majors; UI must not enable risky controls while
 * probe data is missing (experimental / stale server_version).
 */
export function connectionSupports(
  connection: Connection | null | undefined,
  capabilityId: string,
): boolean {
  const caps = connection?.capabilities;
  if (!caps) return false;
  return caps.supported.includes(capabilityId);
}

export function connectionUnsupportedReason(
  connection: Connection | null | undefined,
  capabilityId: string,
): string | null {
  const caps = connection?.capabilities;
  if (!caps) {
    return "Version capabilities unknown — probe the connection on Connect / Browse";
  }
  if (caps.supported.includes(capabilityId)) return null;
  const hit = caps.unsupported.find((u) => u.id === capabilityId);
  return hit?.reason ?? `Unavailable on this Odoo version`;
}

export function isEnterpriseEdition(caps: CapabilityMatrix | null | undefined): boolean {
  return (caps?.edition ?? "").toLowerCase() === "enterprise";
}

/** Grid/planning views are EE-gated in product — arch helpers exist but UI locks without EE. */
export function gridViewAllowed(connection: Connection | null | undefined): boolean {
  return mutationAllowed(connection) && isEnterpriseEdition(connection?.capabilities);
}

export function isExperimentalMajor(caps: CapabilityMatrix | null | undefined): boolean {
  return Boolean(caps && !caps.ga);
}

export function connectionMajor(
  connection: Connection | null | undefined,
): number | null {
  const m = connection?.capabilities?.major;
  return typeof m === "number" ? m : null;
}

/** True when recipe/feature min_major exceeds the connected Odoo major. */
export function belowMinMajor(
  connection: Connection | null | undefined,
  minMajor: number | null | undefined,
): boolean {
  if (minMajor == null) return false;
  const major = connectionMajor(connection);
  if (major == null) return true; // fail-closed until probed
  return major < minMajor;
}

/**
 * Odoo 16 `ir.model.fields` has no `currency_field` column (client omits it).
 * Fail-closed when major unknown.
 */
export function currencyFieldSupported(
  connection: Connection | null | undefined,
): boolean {
  const major = connectionMajor(connection);
  if (major == null) return false;
  return major >= 17;
}

export function currencyFieldUnsupportedReason(
  connection: Connection | null | undefined,
): string | null {
  if (currencyFieldSupported(connection)) return null;
  const major = connectionMajor(connection);
  if (major == null) {
    return "Version capabilities unknown — monetary currency_field support cannot be verified";
  }
  return `Odoo ${major}: ir.model.fields has no currency_field column — monetary may omit currency_field`;
}

/**
 * Designer bind-mode → capability id when one exists in the registry.
 * Modes without an exact id are gated via {@link bindModeSupported} (GA only).
 */
export function bindModeCapabilityId(
  mode:
    | "create_update"
    | "create_related"
    | "create_activity"
    | "create_mail"
    | "create_smart"
    | "bind_existing"
    | string,
): string | null {
  switch (mode) {
    case "create_update":
      return "object_write_update_path";
    case "create_related":
      return "object_create_crud_model";
    case "create_smart":
      return "smart_button_inherit_box";
    // next_activity / mail / bind_existing: no dedicated CapabilityId
    default:
      return null;
  }
}

export function bindModeSupported(
  connection: Connection | null | undefined,
  mode: string,
): boolean {
  const cap = bindModeCapabilityId(mode);
  if (cap) return connectionSupports(connection, cap);
  const caps = connection?.capabilities;
  if (!caps) return false;
  // No exact cap id → allow on GA only (experimental gets reason text)
  return caps.ga === true;
}

export function bindModeUnsupportedReason(
  connection: Connection | null | undefined,
  mode: string,
): string | null {
  const cap = bindModeCapabilityId(mode);
  if (cap) return connectionUnsupportedReason(connection, cap);
  const caps = connection?.capabilities;
  if (!caps) {
    return "Version capabilities unknown — probe the connection on Connect / Browse";
  }
  if (caps.ga) return null;
  return `Unavailable on experimental Odoo ${caps.major} (no dedicated capability id)`;
}

/** Capability required for the chosen view inject strategy. */
export function injectStrategyCapabilityId(
  strategy: "inherit" | "mutate",
): "view_inject_inherit" | "view_inject_mutate" {
  return strategy === "mutate" ? "view_inject_mutate" : "view_inject_inherit";
}

/**
 * Fail-closed gate for primary mutate controls (create / apply / live write).
 * True only when connection capabilities have been probed — pages must not
 * invent per-major encode logic; use this + {@link connectionSupports}.
 */
export function mutationAllowed(
  connection: Connection | null | undefined,
): boolean {
  return Boolean(connection?.capabilities);
}

export function mutationBlockedReason(
  connection: Connection | null | undefined,
): string | null {
  if (mutationAllowed(connection)) return null;
  return "Version capabilities unknown — probe the connection on Connect / Browse";
}

/**
 * Advanced / destructive mutate gate: missing caps OR experimental major → false.
 * Use for deletes, cron reminders, and other confirm-gated ERP-risk actions.
 */
export function advancedMutationAllowed(
  connection: Connection | null | undefined,
): boolean {
  const caps = connection?.capabilities;
  if (!caps) return false;
  return caps.ga === true;
}

export function advancedMutationBlockedReason(
  connection: Connection | null | undefined,
): string | null {
  if (advancedMutationAllowed(connection)) return null;
  const caps = connection?.capabilities;
  if (!caps) {
    return "Version capabilities unknown — probe the connection on Connect / Browse";
  }
  return `Unavailable on experimental Odoo ${caps.major} — advanced actions require a GA major`;
}

/**
 * Wizard / ModuleSpec scaffold+apply: needs create + inherit inject.
 * Pass requireObjectWrite / requireRelatedWrite when the path uses those caps
 * (e.g. library loan automation, ModuleSpec update_field / related_write).
 */
export function scaffoldApplyAllowed(
  connection: Connection | null | undefined,
  opts?: { requireObjectWrite?: boolean; requireRelatedWrite?: boolean },
): boolean {
  if (!mutationAllowed(connection)) return false;
  if (!connectionSupports(connection, "object_create_crud_model")) return false;
  if (!connectionSupports(connection, "view_inject_inherit")) return false;
  if (
    opts?.requireObjectWrite &&
    !connectionSupports(connection, "object_write_update_path")
  ) {
    return false;
  }
  if (
    opts?.requireRelatedWrite &&
    !connectionSupports(connection, "related_write_dotted_path")
  ) {
    return false;
  }
  return true;
}

export function scaffoldApplyBlockedReason(
  connection: Connection | null | undefined,
  opts?: { requireObjectWrite?: boolean; requireRelatedWrite?: boolean },
): string | null {
  if (scaffoldApplyAllowed(connection, opts)) return null;
  const base = mutationBlockedReason(connection);
  if (base) return base;
  if (!connectionSupports(connection, "object_create_crud_model")) {
    return connectionUnsupportedReason(connection, "object_create_crud_model");
  }
  if (!connectionSupports(connection, "view_inject_inherit")) {
    return connectionUnsupportedReason(connection, "view_inject_inherit");
  }
  if (
    opts?.requireObjectWrite &&
    !connectionSupports(connection, "object_write_update_path")
  ) {
    return connectionUnsupportedReason(connection, "object_write_update_path");
  }
  if (
    opts?.requireRelatedWrite &&
    !connectionSupports(connection, "related_write_dotted_path")
  ) {
    return connectionUnsupportedReason(connection, "related_write_dotted_path");
  }
  return "Unavailable on this Odoo version";
}

/**
 * Default act_window view_mode from capability registry (no major ifs).
 * Prefer list on majors with list_as_list_type; otherwise tree.
 */
export function defaultWindowViewMode(
  connection: Connection | null | undefined,
): string {
  if (connectionSupports(connection, "list_as_list_type")) return "list,form";
  return "tree,form";
}

/** Inspect ModuleSpec / AI draft automations for update_path-era requirements. */
export function scaffoldOptsFromSpec(
  spec: Record<string, unknown> | null | undefined,
): { requireObjectWrite?: boolean; requireRelatedWrite?: boolean } {
  const autos = Array.isArray(spec?.automations) ? spec.automations : [];
  let requireObjectWrite = false;
  let requireRelatedWrite = false;
  for (const raw of autos) {
    if (!raw || typeof raw !== "object") continue;
    const kind = String((raw as { kind?: unknown }).kind ?? "");
    if (kind === "related_write") requireRelatedWrite = true;
    if (kind === "update_field" || kind === "object_write") requireObjectWrite = true;
    const field = String((raw as { field?: unknown }).field ?? "");
    if (field.includes(".")) requireRelatedWrite = true;
  }
  return { requireObjectWrite, requireRelatedWrite };
}
