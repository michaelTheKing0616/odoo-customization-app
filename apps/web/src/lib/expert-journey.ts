import type { ShellUiContext } from "@/context/ShellContext";
import type { ExpertAskResponse } from "@/lib/api";

/** Completeness / Cert / Autopilot stay independent. Expert never writes or promotes. */
export const EXPERT_HONESTY_LINE =
  "Completeness ≠ Cert ≠ Autopilot. Expert never auto-promotes.";

export const EXPERT_HONESTY_LEGEND = [
  "Completeness is hygiene on drafts — not a shippable score.",
  "Certification is a separate bar. Expert does not certify an instance.",
  "Autopilot is Job Autopilot. Expert is a copilot: it answers, it does not apply or promote.",
] as const;

export function expertHonestyLegend(): string[] {
  return [...EXPERT_HONESTY_LEGEND];
}

export function expertHeaderDescription(connectionName?: string | null): string {
  const base =
    "Grounded answers with citations. Expert does not apply, certify, or auto-promote.";
  const name = (connectionName || "").trim();
  return name ? `${name} · ${base}` : base;
}

export function expertEmptyTitle(): string {
  return "Ask about Odoo or this connection";
}

export function expertEmptyBody(): string {
  return "Expert cites docs and instance metadata when it can, and says so when it cannot. It is a copilot — not Job Autopilot, and not promote.";
}

export function expertComposerPlaceholder(): string {
  return "Ask about this model, a view inherit, ACL, or paste an error…";
}

export function expertSessionHint(opts: {
  contextEnabled: boolean;
  contextLabel: string | null;
}): string {
  if (!opts.contextEnabled) return "Page context off";
  if (opts.contextLabel) return `Using ${opts.contextLabel}`;
  return "Page context on";
}

export function formatExpertContextLabel(
  uiContext: ShellUiContext,
  contextEnabled: boolean,
): string | null {
  if (!contextEnabled) return null;
  const parts: string[] = [];
  if (uiContext.model) parts.push(uiContext.model);
  if (uiContext.field) parts.push(uiContext.field);
  if (uiContext.draftSummary) parts.push("draft");
  if (uiContext.route) parts.push(uiContext.route.split("/").pop() ?? "");
  const unique = [...new Set(parts.filter(Boolean))];
  return unique.length ? unique.join(" · ") : null;
}

export function expertGroundingLabel(
  response: Pick<ExpertAskResponse, "declined" | "grounded" | "uncited_warning">,
): { label: string; variant: "warning" | "success" | "info" } | null {
  if (response.declined) return { label: "Declined", variant: "warning" };
  if (response.grounded) {
    if (response.uncited_warning) {
      return { label: "Grounded · some claims uncited", variant: "info" };
    }
    return { label: "Grounded", variant: "success" };
  }
  return { label: "Ungrounded", variant: "warning" };
}

export function expertOverviewKicker(): string {
  return "Global assistant";
}

export function expertOverviewTitle(): string {
  return "Odoo Expert";
}

export function expertOverviewBody(): string {
  return "A grounded copilot for this connection. It cites sources, diagnoses errors, and explains models — it never applies ModuleSpec, certifies, or auto-promotes.";
}

export const EXPERT_STARTER_PROMPTS: ReadonlyArray<{ id: string; label: string; question: string }> = [
  {
    id: "xpath",
    label: "XPath inherit",
    question: "How does xpath inherit extend a form without replacing the primary arch?",
  },
  {
    id: "acl",
    label: "AccessError",
    question: "What usually causes an AccessError when writing a custom x_ model?",
  },
  {
    id: "stack",
    label: "Module stack",
    question: "Which Community modules do I typically need before customizing Sales and Contacts?",
  },
];

/** Turn inline [n] markers into markdown links the answer renderer converts to chips. */
export function linkifyCitationMarkers(markdown: string): string {
  return markdown.replace(/\[(\d+)\](?!\()/g, "[$1](#cite-$1)");
}

export function splitUserTurnForDisplay(content: string): {
  question: string;
  errorLog: string | null;
} {
  const match = content.split(/\n\nError log:\n/i);
  if (match.length < 2) return { question: content, errorLog: null };
  return { question: match[0] ?? content, errorLog: match.slice(1).join("\n\nError log:\n") };
}

/** Dedicated Expert destination route (not the overview ?expert=1 shim). */
export function expertDestinationHref(connectionId: string): string {
  return `/connections/${connectionId}/expert`;
}

