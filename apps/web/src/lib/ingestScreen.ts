/**
 * UI-S-28 Universal ingest screen logic and copy.
 * Pure helpers. No React. Test run honesty for the studio bar.
 */

import type { IngestStepId } from "@/components/ingest/IngestStepRail";

export const PAGE_TITLE = "Universal ingest";
export const PAGE_DESCRIPTION =
  "Classify uploaded sheets and images, order the commit, test run with no writes, then commit to the connected Odoo.";
export const PRIMARY_CTA = "Commit";

export type IngestGuide = { title: string; why: string; next: string };

/** Strip em / en dashes from UI copy (playbook law 9). */
export function sanitizeIngestCopy(text: string): string {
  return text.replace(/[\u2014\u2013]/g, "-");
}

/** Test run honesty folded into the studio bar (kills always-on Callout stack). */
export function ingestHonestyGuide(): IngestGuide {
  return {
    title: "Test run writes nothing. Commit writes for real.",
    why: "Test run surfaces gaps and remap risk before any create or update on this connection.",
    next: "Resolve gaps, test run, then Commit. Financial files need the confirm phrase.",
  };
}

export function emptyIngestGuide(): IngestGuide {
  return {
    title: "No ingest job yet",
    why: "A classified batch with a commit order lets test run prove creates and updates before any write.",
    next: "Upload files or build from interview, then Analyze and plan.",
  };
}

export function ingestSessionBadge(step: IngestStepId): {
  label: string;
  variant: "default" | "warning" | "success" | "info" | "danger";
} {
  if (step === "commit") return { label: "Commit", variant: "success" };
  if (step === "dry-run") return { label: "Test run", variant: "info" };
  if (step === "plan") return { label: "Plan", variant: "warning" };
  if (step === "classify") return { label: "Classify", variant: "warning" };
  return { label: "Upload", variant: "default" };
}

export function ingestSessionHint(opts: {
  hasCommitLog: boolean;
  hasDryRunLog: boolean;
}): string {
  if (opts.hasCommitLog) return "Commit applied. Writes are on this live connection.";
  if (opts.hasDryRunLog) return "Test run complete. No rows written. Review the log, then Commit.";
  return "Ready on this connection.";
}
