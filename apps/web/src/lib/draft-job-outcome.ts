import type { JobRow } from "./api";

export type JobDraftOutcome =
  | { kind: "succeeded"; draft: Record<string, unknown>; warnings?: string[]; note: string }
  | { kind: "partial"; draft: Record<string, unknown>; note: string }
  | { kind: "still_running"; note: string }
  | { kind: "failed"; error: string };

export type DraftCacheEntry = {
  id: string;
  prompt?: string | null;
  draft?: Record<string, unknown> | null;
  domain_pack?: string | null;
};

function asDraft(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const rec = value as Record<string, unknown>;
  return Object.keys(rec).length > 0 ? rec : null;
}

/** Skip a cached vertical pack when the prompt no longer names that pack. */
export function cachedDraftFitsPrompt(
  draft: Record<string, unknown> | null | undefined,
  prompt: string,
): boolean {
  if (!draft) return false;
  const pack = String(draft.domain_pack || "").trim().toLowerCase();
  if (!pack) return true;
  const text = prompt.toLowerCase();
  const parts = pack.split("_").filter((p) => p.length >= 3);
  if (!parts.length) return true;
  return parts.some((part) => new RegExp(`\\b${part}\\b`, "i").test(text));
}

export function draftFromJobResult(job: JobRow): Record<string, unknown> | null {
  const fromDraft = asDraft(job.result?.draft);
  if (fromDraft) return fromDraft;
  return asDraft(job.result?.partial_draft);
}

export function successNoteForDraft(draft: Record<string, unknown> | null): string {
  if (draft && draft._component) {
    const cp = draft.connect_points as
      | { host_label?: string; host_model?: string }
      | undefined;
    const host = cp?.host_label || cp?.host_model || "the stock app";
    return `Drafted on ${host}. Nothing writes to Odoo until you Apply.`;
  }
  const engine = draft?._generation_engine as
    | { capability?: string; gold_artifact_id?: string | null }
    | undefined;
  if (engine?.capability === "refuse_clone") {
    return "This request was not generated. Describe the residual process instead of cloning an Apps Store module.";
  }
  if (engine?.capability === "stock_reuse") {
    return "Stock Community apps cover this brief — no custom x_*. Run Job Autopilot for sandbox install and process smoke. Nothing to Apply in Draft Studio.";
  }
  if (draft && typeof draft.domain_pack === "string" && draft.domain_pack) {
    return "Draft Studio used the domain pack. Click Retry AI enrichment to tailor when a model is available.";
  }
  if (engine?.gold_artifact_id) {
    return "Gold Option A template selected. Review the settings, download the module zip, then sandbox-prove. Promote stays human.";
  }
  if (engine?.capability === "option_a_authored") {
    const auth = draft?._option_a_authoring as { status?: string } | undefined;
    if (auth?.status === "pass") {
      return "LLM-authored module passed the gate. Download zip and sandbox-prove. Promote stays human.";
    }
    return "LLM-authored module is blocked until the authoring gate passes. Zip and sandbox stay locked.";
  }
  return "Draft ready for review. Nothing writes to Odoo until you Apply.";
}

function operatorWarnings(warnings: unknown): string[] {
  return ((warnings as string[]) || []).filter((w) => {
    if (w.startsWith("senior: ")) return false;
    if (w.startsWith("live_apply:") && !w.toLowerCase().includes("gap")) return false;
    return true;
  });
}

export function resolveJobDraftOutcome(job: JobRow, successNote?: string): JobDraftOutcome {
  const draft = draftFromJobResult(job);
  if (job.status === "succeeded" && draft) {
    return {
      kind: "succeeded",
      draft,
      warnings: operatorWarnings(job.result?.warnings),
      note: successNote || successNoteForDraft(draft),
    };
  }
  if (
    (job.status === "timeout" || job.status === "failed" || job.status === "interrupted") &&
    draft
  ) {
    return {
      kind: "partial",
      draft,
      note:
        `Draft was saved before the job ${job.status}. ` +
        (job.error ? `${job.error} ` : "") +
        "Use this JSON or a row under Saved snapshots. Click Retry AI enrichment to wake AI, re-run missed steps, and complete residual fields from your brief if AI stays down.",
    };
  }
  if (job.status === "failed" || job.status === "timeout" || job.status === "interrupted") {
    return { kind: "failed", error: job.error || "Background job failed" };
  }
  if (job.status === "queued" || job.status === "running") {
    if (draft) {
      return {
        kind: "partial",
        draft,
        note:
          "Draft is still generating in the background — last saved JSON shown below. " +
          "Check Saved snapshots shortly or keep this page open.",
      };
    }
    return {
      kind: "still_running",
      note:
        "Draft is still generating in the background. Check Saved snapshots below or refresh in a few minutes.",
    };
  }
  return { kind: "failed", error: job.error || "Background job ended unexpectedly" };
}

export function pickCachedDraft(
  entries: DraftCacheEntry[],
  prompt: string,
): Record<string, unknown> | null {
  const needle = prompt.trim().replace(/\s+/g, " ");
  const viable = entries.filter((row) => {
    const draft = asDraft(row.draft);
    if (!draft) return false;
    if (!cachedDraftFitsPrompt(draft, prompt)) return false;
    return true;
  });
  const match = viable.find(
    (row) => (row.prompt || "").trim().replace(/\s+/g, " ") === needle,
  );
  return asDraft(match?.draft);
}

export function pickRecoverableDraft(
  recoveredPartial: Record<string, unknown> | null,
  entries: DraftCacheEntry[],
  prompt: string,
): Record<string, unknown> | null {
  if (recoveredPartial && cachedDraftFitsPrompt(recoveredPartial, prompt)) {
    return recoveredPartial;
  }
  return pickCachedDraft(entries, prompt);
}
