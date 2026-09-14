/** App Studio journey stages and busy-label helpers — chrome only, not the generator. */

import type { JobRow } from "./api";
import { busyLabelFromJobResult } from "./draft-form-preview";
import type { StudioPhase } from "./studio-session";

export const STUDIO_STAGES = [
  { id: "brief", label: "Brief" },
  { id: "clarify", label: "Clarify" },
  { id: "generate", label: "Generate" },
  { id: "review", label: "Review" },
  { id: "apply", label: "Apply" },
] as const;

export type StudioJourneyId = (typeof STUDIO_STAGES)[number]["id"];

export type StudioJourneyState = {
  id: StudioJourneyId;
  failed?: boolean;
  applied?: boolean;
};

export function studioJourneyFromPhase(opts: {
  phase: StudioPhase;
  applied?: boolean;
}): StudioJourneyState {
  const applied = Boolean(opts.applied);
  if (opts.phase === "prompt") return { id: "brief" };
  if (opts.phase === "clarify") return { id: "clarify" };
  if (opts.phase === "generating") return { id: "generate" };
  if (opts.phase === "failed") return { id: "generate", failed: true };
  if (opts.phase === "review") {
    return applied ? { id: "apply", applied: true } : { id: "review" };
  }
  return { id: "brief" };
}

export function studioJourneyHint(state: StudioJourneyState): string {
  if (state.failed) {
    return "Generation did not finish. Retry, or start a new app. Promote stays human.";
  }
  switch (state.id) {
    case "brief":
      return "Describe the work in everyday words. Nothing is installed until you apply.";
    case "clarify":
      return "Lock the diagnosis before generate. Yes — build this commits the IR.";
    case "generate":
      return "Building a draft. Completeness is not Cert. Promote stays human.";
    case "review":
      return "Preview and refine. Apply writes live metadata. Option A stays zip, sandbox, then Promote.";
    case "apply":
      return "Live on this connection. Open in Odoo, or View Designer for the primary form.";
  }
}

export function progressLabelFromJob(job: JobRow | null): string {
  const result = (job?.result ?? {}) as Record<string, unknown>;
  const fromBusy = busyLabelFromJobResult(result);
  const raw =
    fromBusy ||
    (typeof result.progress_label === "string" && result.progress_label) ||
    null;
  if (raw) {
    return raw.replace(/^Stage [A-Z]\s*·?\s*/i, "").trim() || "Building your draft";
  }
  if (job?.status === "queued") return "Queued";
  return "Building your draft";
}

export function draftFromJobResult(job: JobRow | null): Record<string, unknown> | null {
  const draft = job?.result?.draft;
  if (draft && typeof draft === "object" && !Array.isArray(draft)) {
    return draft as Record<string, unknown>;
  }
  return null;
}

export function sandboxInstallFailed(
  draft: Record<string, unknown> | null | undefined,
): boolean {
  const row = draft?._sandbox_install;
  return Boolean(row && typeof row === "object" && (row as { ok?: boolean }).ok === false);
}

export function feedbackRepairFromDraft(
  draft: Record<string, unknown> | null | undefined,
): {
  applied?: boolean;
  message?: string;
} | null {
  const row = draft?._option_a_feedback_repair;
  if (!row || typeof row !== "object") return null;
  return row as { applied?: boolean; message?: string };
}

export const STUDIO_STARTER_CHIP_LABELS: Record<string, string> = {
  "Car rental with deposits and return checklist": "Car rental",
  "Clinic booking with walk-in appointments": "Clinic booking",
  "Helpdesk tickets with requester and status workflow": "Helpdesk tickets",
  "Retail inventory and stock moves": "Retail inventory",
};

export function studioErrorTitle(message: string | null | undefined): string {
  const text = (message || "").trim();
  if (!text) return "App Studio request failed";
  if (/author/i.test(text)) return "Authoring failed";
  if (/generat/i.test(text)) return "Generation failed";
  if (/clarif/i.test(text)) return "Clarification failed";
  if (/refine|map|apply that change/i.test(text)) return "Refine did not apply";
  if (/zip|export/i.test(text)) return "Zip export failed";
  if (/sandbox|prove/i.test(text)) return "Sandbox prove failed";
  if (/promote/i.test(text)) return "Promote failed";
  if (/install/i.test(text)) return "Install failed";
  if (/session|load/i.test(text)) return "Could not load session";
  return "App Studio request failed";
}
