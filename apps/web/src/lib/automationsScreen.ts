/**
 * UI-S-15 Automations studio-bar helpers. Pure, no React.
 */

export const PAGE_TITLE = "Automations";
export const PAGE_DESCRIPTION =
  "Model, trigger, apply-on, then a safe action. Python stays on the custom-code path: module, sandbox, promote.";

export type AutomationsGuide = { title: string; why: string; next: string };

export function sanitizeAutomationsCopy(text: string): string {
  return text.replace(/[\u2014\u2013]/g, "-");
}

export function automationsHonestyGuide(): AutomationsGuide {
  return {
    title: "Python needs custom code. Publishing to Odoo stays a step you confirm.",
    why: "Completeness is not Cert and not Autopilot. Form buttons live in View Designer; this screen is the model-level twin.",
    next: "Name the rule, pick a model and trigger, choose a safe action, then Create. Python exports a module zip only.",
  };
}

export function automationsSessionBadge(opts: { unsaved: boolean }): {
  label: string;
  variant: "default" | "warning" | "success" | "info" | "danger";
} {
  if (opts.unsaved) return { label: "Unsaved", variant: "warning" };
  return { label: "Ready", variant: "default" };
}
