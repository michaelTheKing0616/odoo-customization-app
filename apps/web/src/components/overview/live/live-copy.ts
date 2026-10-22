import type { LiveSnapshot } from "@/lib/api";

/** Plain-language labels for the "What you can change here" summary. */
export const CHANGE_COPY: Record<string, string> = {
  custom_fields: "Add fields to any record",
  custom_models: "Create new kinds of records",
  views_community: "Change forms, lists and kanban boards",
  views_enterprise_types: "Gantt, map and cohort views",
  menus_actions: "Add menus and screens",
  security_acl_rules: "Control who can see and edit what",
  base_automation: "Standard automations and reminders",
  python_module_install: "Custom code modules",
  module_deploy: "Install your own modules",
  code_server_actions: "Code-based server actions",
};

export const HOSTING_COPY: Record<LiveSnapshot["hosting"], string> = {
  online: "Odoo Online",
  sh: "Odoo.sh",
  onprem: "Self-hosted",
  unknown: "Hosting not detected",
};

export const EDITION_COPY: Record<LiveSnapshot["edition"], string> = {
  community: "Community",
  enterprise: "Enterprise",
  unknown: "Edition not detected",
};

export function availabilityLabel(a: string): string {
  if (a === "yes") return "Yes";
  if (a === "no") return "Not on this plan";
  if (a === "plan_gated") return "Needs a plan upgrade";
  return "Check first";
}
