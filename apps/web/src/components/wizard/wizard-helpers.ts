import { api, type AppTemplate, type JobRow } from "@/lib/api";
import { busyLabelFromJobResult } from "@/lib/draft-form-preview";
import { draftFromJobResult } from "@/lib/draft-job-outcome";
import { JobPollError, pollJob } from "@/lib/jobs";

export const CONFIRM_PHRASE = "I understand the risks";

export const BACKGROUND_JOB_POLL_MS = 2000;

export async function pollBackgroundJob(
  jobId: string,
  opts: {
    setBusyLabel: (label: string | null) => void;
    onPartial?: (partial: Record<string, unknown>) => void;
    maxMs?: number;
  },
): Promise<JobRow> {
  try {
    return await pollJob(jobId, {
      intervalMs: BACKGROUND_JOB_POLL_MS,
      maxAttempts: 2400,
      untilTerminal: true,
      fetchJob: (id) => api.getJob(id),
      onUpdate: (job) => {
        const phase = busyLabelFromJobResult(job.result);
        if (phase) opts.setBusyLabel(phase);
        const partial = draftFromJobResult(job);
        if (partial) opts.onPartial?.(partial);
      },
    });
  } catch (err) {
    if (err instanceof JobPollError && err.job) {
      return err.job;
    }
    throw err;
  }
}

export const FALLBACK_TEMPLATES: AppTemplate[] = [
  {
    id: "library",
    name: "Library",
    description: "Books, authors, categories, and loans with member tracking.",
  },
  {
    id: "car_rental",
    name: "Car Rental",
    description:
      "Fleet, Contacts, contracts, rates, damages, and maintenance. Invoices stay stock.",
  },
  {
    id: "crm_lite",
    name: "CRM Lite",
    description: "Lightweight leads with partner and stage.",
  },
  {
    id: "inventory_lite",
    name: "Inventory Lite",
    description: "Simple items with quantity and location.",
  },
];

export function dedupeTemplates(templates: AppTemplate[]): AppTemplate[] {
  const seen = new Set<string>();
  return templates.filter((tpl) => {
    if (seen.has(tpl.id)) return false;
    seen.add(tpl.id);
    return true;
  });
}

export function downloadEliteZipBase64(tech: string, zipBase64: string) {
  const bin = atob(zipBase64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const blob = new Blob([bytes], { type: "application/zip" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${tech}.zip`;
  a.click();
  URL.revokeObjectURL(url);
}

/** Library scaffold creates an object_write loan automation. */
export function templateScaffoldOpts(tplId: string) {
  return tplId === "library" ? { requireObjectWrite: true as const } : {};
}

export type DraftCacheEntry = {
  id: string;
  summary: string;
  prompt: string;
  updated_at: string | null;
};

export type OverlapFinding = {
  id: string;
  title: string;
  evidence: string;
  deep_link?: string | null;
  extend_host_model?: string | null;
};

export type HostCandidate = {
  model: string;
  label: string;
  score: number;
  reason?: string;
};

export type GalleryItem = {
  id: string;
  name: string;
  description: string;
  host_slot: string;
};

export type LiveApplyState = {
  ready?: boolean;
  findings?: Array<{ detail?: string }>;
  option_a?: string[];
  done_bar?: {
    mode?: string;
    next_step?: string;
    go_live_ready?: boolean;
  };
  go_live_ready?: boolean;
};

export type OperatorBriefState = {
  formatted?: string;
  capability_path?: string;
  ir_confidence?: string;
  unknowns?: string[];
};

export function mapDraftCacheEntries(
  cached: Array<{
    id: string;
    summary: string;
    prompt: string;
    updated_at: string | null;
  }> | null,
): DraftCacheEntry[] {
  return (cached || []).map((c) => ({
    id: c.id,
    summary: c.summary,
    prompt: c.prompt,
    updated_at: c.updated_at,
  }));
}
