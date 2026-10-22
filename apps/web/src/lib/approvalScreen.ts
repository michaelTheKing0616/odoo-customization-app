/**
 * UI-S-16 Odoo approval rules screen logic and copy.
 * Pure helpers. No React. Distinct from /approvals plan inbox (UI-S-50).
 */

import type { ApprovalEntry, ApprovalRule, ApprovalsGateResponse } from "@/lib/api";

export const PAGE_TITLE = "Odoo approval rules";
export const PAGE_DESCRIPTION =
  "Gate form buttons behind approvers on this Odoo connection. This is not the plan inbox.";
export const PRIMARY_CTA = "Deploy a rule";
export const INBOX_HINT =
  "Plan change cards live under Approval inbox. This screen only manages Odoo button rules and standalone processes.";

export type ApprovalsTab = "buttons" | "processes";

export type ApprovalRuleForm = {
  model: string;
  name: string;
  buttonMethod: string;
  approverUserId: string;
  testRecordId: string;
};

export type ApprovalsGuide = { title: string; why: string; next: string };

export function defaultApprovalRuleForm(): ApprovalRuleForm {
  return {
    model: "res.partner",
    name: "Button approval",
    buttonMethod: "",
    approverUserId: "2",
    testRecordId: "1",
  };
}

export function canDeployRule(form: ApprovalRuleForm): boolean {
  return Boolean(form.model.trim() && form.name.trim() && form.buttonMethod.trim());
}

export function parseUserId(raw: string, fallback = 2): number {
  const n = Number.parseInt(raw, 10);
  return Number.isFinite(n) && n > 0 ? n : fallback;
}

export function parseRecordId(raw: string, fallback = 1): number {
  const n = Number.parseInt(raw, 10);
  return Number.isFinite(n) && n > 0 ? n : fallback;
}

export function engineChipLabel(gate: ApprovalsGateResponse | null | undefined): string {
  if (!gate) return "Engine unknown";
  if (gate.engine === "studio") return "Enterprise Studio engine";
  return "Community rules engine";
}

export function engineHint(gate: ApprovalsGateResponse | null | undefined): string {
  if (!gate) return "Probe the connection to see which approval engine is available.";
  if (gate.engine === "studio" && gate.studio_available) {
    return "Studio approval rules are available on this database.";
  }
  if (gate.community_available) {
    return "Community button gating is available. Studio is not required.";
  }
  return gate.studio_note?.trim() || "Approval engines are limited on this instance.";
}

export function ruleMetaLine(rule: ApprovalRule): string {
  const button = rule.button_label?.trim() || rule.button_method;
  return `${rule.target_model}.${rule.button_method} · ${button} · ${rule.engine}`;
}

export function entryStatusVariant(
  status: string,
): "default" | "success" | "warning" | "danger" | "info" {
  const s = status.toLowerCase();
  if (s === "approved" || s === "done") return "success";
  if (s === "pending" || s === "waiting") return "warning";
  if (s === "rejected" || s === "refused" || s === "cancelled") return "danger";
  return "info";
}

export function filterApprovalRules(rules: ApprovalRule[], query: string): ApprovalRule[] {
  const q = query.trim().toLowerCase();
  if (!q) return rules;
  return rules.filter((r) => {
    const hay = `${r.name} ${r.target_model} ${r.button_method} ${r.button_label ?? ""} ${r.engine}`.toLowerCase();
    return hay.includes(q);
  });
}

export function rulesEmptyGuide(hasFilter: boolean, query: string): ApprovalsGuide {
  if (hasFilter) {
    return {
      title: `No rule matches "${query}"`,
      why: "The filter checks rule names, models, buttons, and engines only.",
      next: "Clear the filter, or deploy a new Odoo approval rule.",
    };
  }
  return {
    title: "No Odoo approval rules yet",
    why: "A rule gates one form button so the click waits for an approver before it runs.",
    next: "Discover buttons on a model, then deploy a rule.",
  };
}

export function entriesEmptyGuide(): ApprovalsGuide {
  return {
    title: "No approval entries yet",
    why: "Entries appear after someone triggers a gated button or an approver acts on a request.",
    next: "Simulate a click on a rule, or wait for a live gated action.",
  };
}

export function processesEmptyGuide(kinds: "types" | "requests"): ApprovalsGuide {
  if (kinds === "types") {
    return {
      title: "No approval types yet",
      why: "Standalone processes need x_approval_type rows (or Enterprise Approvals).",
      next: "Scaffold Approval Requests on a sandbox, then create a draft request.",
    };
  }
  return {
    title: "No process requests yet",
    why: "Requests are standalone approve/refuse workflows, separate from button gating.",
    next: "Pick a type and create a draft request.",
  };
}

export function approvalsErrorGuide(context: "load" | "deploy" | "check" | "resolve" | "scaffold"): ApprovalsGuide {
  switch (context) {
    case "deploy":
      return {
        title: "Could not deploy the rule",
        why: "The connection refused the create, or a field was incomplete.",
        next: "Check the model and button method, then try Deploy a rule again.",
      };
    case "check":
      return {
        title: "Simulate click failed",
        why: "The check call did not reach Odoo, or the rule id is stale.",
        next: "Refresh the rules list, confirm the record id, then simulate again.",
      };
    case "resolve":
      return {
        title: "Could not resolve the entry",
        why: "The approver action failed on the connection.",
        next: "Confirm the actor user id, then approve or reject again.",
      };
    case "scaffold":
      return {
        title: "Scaffold did not finish",
        why: "Live metadata writes need confirmation, or the database refused the models.",
        next: "Try a test copy, confirm the phrase, then scaffold again.",
      };
    default:
      return {
        title: "Could not load Odoo approval rules",
        why: "The connection did not return rules, entries, or the approvals gate.",
        next: "Retry. If it keeps failing, re-probe the connection on Overview.",
      };
  }
}

export function processEngineLabel(engine: string | null | undefined): string {
  if (engine === "enterprise") return "Enterprise approvals";
  return "Community x_approval_*";
}


export function sanitizeApprovalsCopy(text: string): string {
  return text.replace(/[\u2014\u2013]/g, "-");
}

/** Engine honesty folded into the studio bar (kills ap-honesty chip stack). */
export function approvalsHonestyGuide(gate: ApprovalsGateResponse | null | undefined): ApprovalsGuide {
  const chip = engineChipLabel(gate);
  const hint = engineHint(gate);
  return {
    title: chip,
    why: hint,
    next: "Deploy button rules here. Approvers act in the Approval inbox.",
  };
}

export function approvalsSessionBadge(gate: ApprovalsGateResponse | null | undefined): {
  label: string;
  variant: "default" | "warning" | "success" | "info" | "danger";
} {
  const engine = gate?.engine === "studio" ? "Studio" : "Community";
  return { label: engine, variant: gate?.engine === "studio" ? "info" : "default" };
}

