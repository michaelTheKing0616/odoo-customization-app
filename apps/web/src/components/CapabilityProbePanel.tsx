"use client";

import { useState } from "react";
import type { CapabilityMatrix } from "@/lib/api";

const LABELS: Record<string, string> = {
  related_write_dotted_path: "Related write (dotted update_path)",
  object_write_update_path: "Update field (object_write)",
  object_create_crud_model: "Create record (object_create)",
  base_automation_safe_triggers: "Safe automation triggers",
  view_inject_inherit: "View inject via inherit",
  view_inject_mutate: "View inject via mutate (advanced)",
  smart_button_inherit_box: "Smart buttons (button_box inherit)",
  list_as_list_type: "List views as type=list",
  list_tree_fallback: "List↔tree view type fallback",
};

type Props = {
  capabilities: CapabilityMatrix | null | undefined;
  /** Compact badge-only until expanded */
  defaultOpen?: boolean;
  className?: string;
  onRefresh?: () => void;
  refreshing?: boolean;
};

export function CapabilityProbePanel({
  capabilities,
  defaultOpen = false,
  className = "",
  onRefresh,
  refreshing = false,
}: Props) {
  const [open, setOpen] = useState(defaultOpen);

  if (!capabilities) {
    return (
      <p className={`text-xs text-muted ${className}`}>
        Version capabilities unknown — probe the connection after save.
      </p>
    );
  }

  const badge = capabilities.ga
    ? `Odoo ${capabilities.major ?? "?"} ${capabilities.edition}`
    : `Odoo ${capabilities.major ?? "?"} (limited)`;

  const hosting =
    capabilities.hosting_hint === "online"
      ? "Online"
      : capabilities.hosting_hint === "odoo_sh"
        ? "Odoo.sh"
        : capabilities.hosting_hint === "self_hosted"
          ? "Self-hosted"
          : null;

  return (
    <div className={`text-sm ${className}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={
            capabilities.ga
              ? "border border-[#3d6b5a] bg-[#143029] px-2 py-0.5 text-xs font-medium text-muted"
              : "border border-[#6b5a3d] bg-[#2a2414] px-2 py-0.5 text-xs font-medium text-[#e8d09f]"
          }
        >
          {badge}
        </span>
        {hosting && (
          <span className="border border-border-subtle bg-[#120e14] px-2 py-0.5 text-xs text-muted">
            {hosting}
          </span>
        )}
        {capabilities.python_module_install === false && (
          <span className="border border-[#6b3d3d] bg-[#2a1414] px-2 py-0.5 text-xs text-[#e8a0a0]">
            No Python module install
          </span>
        )}
        <span className="text-xs text-muted">
          {capabilities.supported.length} capabilities
          {capabilities.unsupported.length > 0
            ? ` · ${capabilities.unsupported.length} unavailable`
            : ""}
        </span>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="text-xs text-muted underline-offset-2 hover:underline"
        >
          {open ? "Hide details" : "Show details"}
        </button>
        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            disabled={refreshing}
            className="text-xs text-muted underline-offset-2 hover:underline disabled:opacity-50"
          >
            {refreshing ? "Probing…" : "Re-probe"}
          </button>
        )}
      </div>
      {capabilities.warnings && capabilities.warnings.length > 0 && (
        <ul className="mt-2 space-y-1 border border-[#6b5a3d] bg-[#2a2414] px-3 py-2 text-xs text-[#e8d09f]">
          {capabilities.warnings.map((w) => (
            <li key={w.slice(0, 48)}>{w}</li>
          ))}
        </ul>
      )}
      {open && (
        <div className="mt-2 space-y-2 border border-border-subtle bg-[#120e14] px-3 py-2">
          <p className="text-xs text-muted">{capabilities.message}</p>
          {capabilities.installed_modules_sample &&
            capabilities.installed_modules_sample.length > 0 && (
              <p className="text-[11px] text-[#6b5a66]">
                Modules sample:{" "}
                {capabilities.installed_modules_sample.slice(0, 12).join(", ")}
                {capabilities.installed_modules_sample.length > 12 ? "…" : ""}
              </p>
            )}
          <ul className="space-y-1">
            {capabilities.supported.map((id) => (
              <li key={id} className="flex gap-2 text-xs text-muted">
                <span aria-hidden>✓</span>
                <span>{LABELS[id] ?? id}</span>
              </li>
            ))}
            {capabilities.unsupported.map((u) => (
              <li key={u.id} className="flex gap-2 text-xs text-muted">
                <span aria-hidden className="text-[#6b5a66]">
                  –
                </span>
                <span>
                  <span className="text-[#a8909e]">{u.label}</span>
                  <span className="block text-[#6b5a66]">{u.reason}</span>
                </span>
              </li>
            ))}
          </ul>
          <p className="text-[11px] text-[#6b5a66]">
            Community 19, 18, and 17 are GA; 16 is experimental (lacks related
            write / update_path). Enterprise editions are allowed for public-ORM
            metadata only — Studio source is never used. Unsupported majors are
            refused at connect. Odoo Online: data/XML modules only (no custom
            Python).
          </p>
        </div>
      )}
    </div>
  );
}
