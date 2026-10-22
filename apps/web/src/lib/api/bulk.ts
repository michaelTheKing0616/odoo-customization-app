import { request } from "./client";
import type { CronListOut, RecipeCard } from "./types-batch";
import type { ActivityProbeOut, BulkRunOut, BulkTransitionsOut, CronRowOut, DedupeScanOut, DuplicateScanOut, LargeOldScanOut, OrphanScanOut, PowerOpsCapabilities, PowerOpsRecipe, PowerOpsRunOut, SecurityPreviewOut } from "./types-bulk";
import type { AccessMatrixOut, DomainPlaybook, EePlaybook, StudioFeatureRecipe } from "./types-catalog";

export const bulkApi = {
  powerOpsRecipes: (id: string) =>
    request<{ recipes: PowerOpsRecipe[] }>(`/api/connections/${id}/power-ops/recipes`),
  powerOpsCapabilities: (id: string) =>
    request<PowerOpsCapabilities>(`/api/connections/${id}/power-ops/capabilities`),
  listEePlaybooks: (id: string) =>
    request<EePlaybook[]>(`/api/connections/${id}/ee-playbooks`),
  listDocumentsFolders: (id: string) =>
    request<Array<{ id: number; name: string | null }>>(
      `/api/connections/${id}/ee-playbooks/documents/folders`,
    ),
  listDomainPlaybooks: (id: string) =>
    request<DomainPlaybook[]>(`/api/connections/${id}/domain-playbooks`),
  listStudioFeatureRecipes: () =>
    request<StudioFeatureRecipe[]>(`/api/studio-feature-recipes`),
  powerOpsRun: (
    id: string,
    body: {
      recipe_id: string;
      model?: string | null;
      domain?: unknown[];
      ids?: number[];
      dry_run?: boolean;
      batch_size?: number;
      continue_on_error?: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<PowerOpsRunOut>(`/api/connections/${id}/power-ops/run`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  bulkTransitions: (id: string, model: string) =>
    request<BulkTransitionsOut>(
      `/api/connections/${id}/bulk/transitions?model=${encodeURIComponent(model)}`,
    ),
  bulkTransitionRun: (
    id: string,
    body: {
      model: string;
      method: string;
      domain?: unknown[] | string | null;
      ids?: number[];
      dry_run?: boolean;
      cap?: number;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
      receipt_token?: string | null;
      continue_run_id?: string | null;
      disable_sample_first?: boolean;
      progress_run_id?: string | null;
    },
  ) =>
    request<BulkRunOut>(`/api/connections/${id}/bulk/transitions/run`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  bulkRunContinue: (id: string, runId: string) =>
    request<BulkRunOut>(`/api/connections/${id}/bulk/runs/${runId}/continue`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  bulkRunAbort: (id: string, runId: string) =>
    request<BulkRunOut>(`/api/connections/${id}/bulk/runs/${runId}/abort`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  bulkMassEdit: (
    id: string,
    body: {
      model: string;
      values: Record<string, unknown>;
      domain?: unknown[] | string | null;
      ids?: number[];
      dry_run?: boolean;
      cap?: number;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<BulkRunOut>(`/api/connections/${id}/bulk/mass-edit`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  bulkDedupeScan: (
    id: string,
    body: {
      model: string;
      match_fields: string[];
      mode?: "exact" | "fuzzy";
      limit?: number;
      domain?: unknown[] | null;
    },
  ) =>
    request<DedupeScanOut>(`/api/connections/${id}/bulk/dedupe/scan`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  bulkDedupeMerge: (
    id: string,
    body: {
      model: string;
      winner_id: number;
      loser_ids: number[];
      dry_run?: boolean;
      archive_or_delete?: "archive" | "unlink";
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<BulkRunOut>(`/api/connections/${id}/bulk/dedupe/merge`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  bulkCrons: (
    id: string,
    params?: { q?: string; active?: boolean; limit?: number },
  ) => {
    const qs = new URLSearchParams();
    if (params?.q) qs.set("q", params.q);
    if (params?.active != null) qs.set("active", String(params.active));
    if (params?.limit != null) qs.set("limit", String(params.limit));
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return request<CronListOut>(`/api/connections/${id}/bulk/crons${suffix}`);
  },
  bulkCronRunNow: (
    id: string,
    body: {
      cron_ids: number[];
      dry_run?: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<BulkRunOut>(`/api/connections/${id}/bulk/crons/run-now`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  bulkCronCreate: (
    id: string,
    body: {
      name: string;
      model: string;
      method: string;
      interval_number?: number;
      interval_type?: "minutes" | "hours" | "days" | "weeks" | "months";
      active?: boolean;
      nextcall?: string | null;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<CronRowOut>(`/api/connections/${id}/bulk/crons`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  bulkCronPatch: (
    id: string,
    cronId: number,
    body: {
      interval_number?: number;
      interval_type?: "minutes" | "hours" | "days" | "weeks" | "months";
      active?: boolean;
      nextcall?: string | null;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<CronRowOut>(`/api/connections/${id}/bulk/crons/${cronId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  bulkAttachmentOrphanScan: (id: string, body?: { limit?: number }) =>
    request<OrphanScanOut>(`/api/connections/${id}/bulk/attachments/orphans/scan`, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  bulkAttachmentDuplicateScan: (id: string, body?: { limit?: number }) =>
    request<DuplicateScanOut>(`/api/connections/${id}/bulk/attachments/duplicates/scan`, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  bulkAttachmentLargeOldScan: (
    id: string,
    body?: { min_bytes?: number; older_than_days?: number; limit?: number },
  ) =>
    request<LargeOldScanOut>(`/api/connections/${id}/bulk/attachments/large-old/scan`, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  bulkAttachmentClean: (
    id: string,
    body: {
      attachment_ids: number[];
      dry_run?: boolean;
      kind?: "orphan" | "duplicate" | "large_old" | "manual";
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<BulkRunOut>(`/api/connections/${id}/bulk/attachments/clean`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  bulkActivitiesProbe: (id: string, model: string) =>
    request<ActivityProbeOut>(
      `/api/connections/${id}/bulk/activities/probe?model=${encodeURIComponent(model)}`,
    ),
  bulkActivities: (
    id: string,
    body: {
      model: string;
      ids?: number[];
      domain?: unknown;
      activity_type_id: number;
      summary: string;
      date_deadline: string;
      user_id?: number | null;
      dry_run?: boolean;
      cap?: number;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<BulkRunOut>(`/api/connections/${id}/bulk/activities`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  bulkSecurityPreview: (
    id: string,
    body: {
      user_ids: number[];
      group_ids?: number[];
      mode?: "add" | "remove" | "offboard";
      deactivate?: boolean;
    },
  ) =>
    request<SecurityPreviewOut>(`/api/connections/${id}/bulk/security/preview`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  bulkSecurityApply: (
    id: string,
    body: {
      user_ids: number[];
      group_ids?: number[];
      mode?: "add" | "remove" | "offboard";
      deactivate?: boolean;
      dry_run?: boolean;
      preview_acknowledged?: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<BulkRunOut>(`/api/connections/${id}/bulk/security/apply`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  bulkPortal: (
    id: string,
    body: {
      partner_ids: number[];
      action?: "grant" | "revoke";
      dry_run?: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<BulkRunOut>(`/api/connections/${id}/bulk/portal`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  bulkRecompute: (
    id: string,
    body: {
      model: string;
      field: string;
      ids?: number[];
      domain?: string | unknown[];
      dry_run?: boolean;
      cap?: number;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<BulkRunOut>(`/api/connections/${id}/bulk/recompute`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  bulkSendMessage: (
    id: string,
    body: {
      model: string;
      ids?: number[];
      domain?: string | unknown[];
      body?: string | null;
      subject?: string | null;
      mail_template_id?: number | null;
      dry_run?: boolean;
      cap?: number;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<BulkRunOut>(`/api/connections/${id}/bulk/send-message`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  accessMatrix: (id: string, models: string[]) =>
    request<AccessMatrixOut>(
      `/api/connections/${id}/access/matrix?models=${encodeURIComponent(models.join(","))}`,
    ),

listConfigRecipes: (id: string) =>
    request<RecipeCard[]>(`/api/connections/${id}/config/recipes`),
};
