"use client";

import { useState } from "react";
import { api, type AttentionItem } from "@/lib/api";
import { PreviewApply, errorText, type Phase } from "./PreviewApply";

export type FixKind = "access" | "menu";

export function fixKindFor(item: AttentionItem): FixKind | null {
  if (item.key === "custom_no_access") return "access";
  if (item.key === "custom_no_menu") return "menu";
  return null;
}

/** The ModuleSpec Apply receives for a one-model fix (existing models are left as they are). */
export function fixSpec(kind: FixKind, model: string, label: string): Record<string, unknown> {
  const base = {
    technical_name: `overview_fix_${model}`,
    display_name: label,
    models: [{ model, description: label, mode: "new", fields: [] }],
  };
  if (kind === "access") {
    return {
      ...base,
      access_rules: [
        { name: `access_${model}_user`, model, group: "base.group_user",
          perm_read: true, perm_write: true, perm_create: true, perm_unlink: false },
      ],
    };
  }
  return {
    ...base,
    actions: [{ xml_id: `action_${model}`, name: label, res_model: model, view_mode: "list,form" }],
    menus: [
      { xml_id: `menu_${model}_root`, name: label, sequence: 50 },
      { xml_id: `menu_${model}`, name: label, parent_xml_id: `menu_${model}_root`, action_xml_id: `action_${model}`, sequence: 10 },
    ],
  };
}

export function AttentionFix({ connectionId, kind, model, label, onDone, onCancel }: {
  connectionId: string; kind: FixKind; model: string; label: string; onDone: () => void; onCancel: () => void;
}) {
  const [phase, setPhase] = useState<Phase>({ kind: "preview" });
  const changes = kind === "access"
    ? [`Let internal users read, create and edit ${label} records`, "Deleting stays with administrators"]
    : [`Add a “${label}” app to the Odoo menu`, `Open ${label} as a list, with a form for each record`];
  async function apply() {
    setPhase({ kind: "applying" });
    try {
      await api.applyModuleSpec(connectionId, {
        spec: fixSpec(kind, model, label),
        apply_views: false,
        apply_menus: kind === "menu",
        apply_smart_buttons: false,
        apply_automations: false,
      });
      onDone();
    } catch (err) {
      setPhase({ kind: "error", message: errorText(err) });
    }
  }
  return (
    <PreviewApply
      title={kind === "access" ? `Add access rules to ${label}` : `Add a menu for ${label}`}
      changes={changes}
      phase={phase}
      onBack={onCancel}
      onApply={() => void apply()}
    />
  );
}
