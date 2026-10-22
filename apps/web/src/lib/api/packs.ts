import { request, requestForm } from "./client";
import type { AppsPackItem, AtlasClass, AtlasHit, BatchOsJob, BatchOsRecipeCard, IntentRouteResult, MasterPackItem, NumberingCatalogItem, RecipePlanOut, SettingsBoardOut } from "./types-batch";

export const packsApi = {
  runDay1Setup: (
    id: string,
    body: {
      name: string;
      currency_code?: string;
      country_code?: string | null;
      language_code?: string | null;
      email?: string | null;
      phone?: string | null;
      company_id?: number | null;
      dry_run?: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<RecipePlanOut>(`/api/connections/${id}/config/recipes/day1`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  numberingCatalog: (id: string) =>
    request<NumberingCatalogItem[]>(
      `/api/connections/${id}/config/recipes/numbering/catalog`,
    ),
  runNumberingPack: (
    id: string,
    body: {
      keys?: string[];
      prefix_year?: boolean;
      dry_run?: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<RecipePlanOut>(`/api/connections/${id}/config/recipes/numbering`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listAppsPacks: (id: string) =>
    request<AppsPackItem[]>(`/api/connections/${id}/config/recipes/apps-packs`),
  runAppsPack: (
    id: string,
    body: {
      pack_id: string;
      dry_run?: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<RecipePlanOut>(`/api/connections/${id}/config/recipes/apps-packs/run`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getSettingsBoard: (id: string) =>
    request<SettingsBoardOut>(`/api/connections/${id}/config/recipes/settings`),
  patchSettingsBoard: (
    id: string,
    body: {
      values: Record<string, unknown>;
      dry_run?: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<RecipePlanOut>(`/api/connections/${id}/config/recipes/settings`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  runMultiCompany: (
    id: string,
    body: {
      name: string;
      currency_code?: string;
      country_code?: string | null;
      dry_run?: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<RecipePlanOut>(`/api/connections/${id}/config/recipes/multi-company`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listMasterPacks: (id: string) =>
    request<MasterPackItem[]>(`/api/connections/${id}/config/recipes/master-packs`),
  runMasterPack: (
    id: string,
    body: {
      pack_id: string;
      dry_run?: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<RecipePlanOut>(`/api/connections/${id}/config/recipes/master-packs/run`, {
      method: "POST",
      body: JSON.stringify(body),
    }),



  batchOsAtlas: (id: string, classId?: string) =>
    request<{ classes: AtlasClass[]; honesty: string }>(
      `/api/connections/${id}/batch-os/atlas${classId ? `?class_id=${encodeURIComponent(classId)}` : ""}`,
    ),
  batchOsAtlasSearch: (
    id: string,
    opts?: { q?: string; class_id?: string; risk?: string },
  ) => {
    const qs = new URLSearchParams();
    if (opts?.q) qs.set("q", opts.q);
    if (opts?.class_id) qs.set("class_id", opts.class_id);
    if (opts?.risk) qs.set("risk", opts.risk);
    const q = qs.toString();
    return request<{ hits: AtlasHit[] }>(
      `/api/connections/${id}/batch-os/atlas/search${q ? `?${q}` : ""}`,
    );
  },
  batchOsRecipes: (id: string) =>
    request<BatchOsRecipeCard[]>(`/api/connections/${id}/batch-os/recipes`),
  /** Intent → feature router (Expert home + Batch OS alias). */
  expertIntentRoute: (
    id: string,
    body: { prompt: string; limit?: number; progress_run_id?: string },
  ) =>
    request<IntentRouteResult>(`/api/connections/${id}/expert/route`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  /** P2 Build spine — mode chips + handoff IR (brief + Diagnosis/Contract + stamps). */
  buildSpineResolve: (
    id: string,
    body: {
      prompt?: string;
      understanding?: Record<string, unknown>;
      contract?: Record<string, unknown>;
      generation_ir?: Record<string, unknown>;
    },
  ) =>
    request<import("@/lib/build-spine").BuildSpinePayload>(
      `/api/connections/${id}/build-spine/resolve`,
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),
  batchOsIntentRoute: (
    id: string,
    body: { prompt: string; limit?: number },
  ) =>
    request<IntentRouteResult>(`/api/connections/${id}/batch-os/intent-route`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  batchOsJournalIntake: async (id: string, file: File, recipeId = "accounting.journal_batch") => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("recipe_id", recipeId);
    return requestForm<BatchOsJob>(`/api/connections/${id}/batch-os/journal/intake`, fd);
  },
  batchOsJournalMap: (
    id: string,
    body: { job_id: string; column_map: Record<string, string> },
  ) =>
    request<BatchOsJob>(`/api/connections/${id}/batch-os/journal/map`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  batchOsJournalValidate: (id: string, body: { job_id: string }) =>
    request<BatchOsJob>(`/api/connections/${id}/batch-os/journal/validate`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  batchOsJournalDryRun: (id: string, body: { job_id: string }) =>
    request<BatchOsJob>(`/api/connections/${id}/batch-os/journal/dry-run`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  batchOsJournalApply: (
    id: string,
    body: {
      job_id: string;
      post_after_create?: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<BatchOsJob>(`/api/connections/${id}/batch-os/journal/apply`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  batchOsDocumentIntake: async (id: string, file: File, recipeId = "document_batch.invoices") => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("recipe_id", recipeId);
    return requestForm<BatchOsJob>(`/api/connections/${id}/batch-os/document/intake`, fd);
  },
  batchOsDocumentMap: (
    id: string,
    body: { job_id: string; column_map: Record<string, string> },
  ) =>
    request<BatchOsJob>(`/api/connections/${id}/batch-os/document/map`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  batchOsDocumentDryRun: (id: string, body: { job_id: string }) =>
    request<BatchOsJob>(`/api/connections/${id}/batch-os/document/dry-run`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  batchOsDocumentApply: (
    id: string,
    body: {
      job_id: string;
      post_after_create?: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<BatchOsJob>(`/api/connections/${id}/batch-os/document/apply`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  batchOsOrderIntake: async (id: string, file: File, recipeId = "document_batch.orders") => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("recipe_id", recipeId);
    return requestForm<BatchOsJob>(`/api/connections/${id}/batch-os/order/intake`, fd);
  },
  batchOsOrderMap: (
    id: string,
    body: { job_id: string; column_map: Record<string, string> },
  ) =>
    request<BatchOsJob>(`/api/connections/${id}/batch-os/order/map`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  batchOsOrderDryRun: (id: string, body: { job_id: string }) =>
    request<BatchOsJob>(`/api/connections/${id}/batch-os/order/dry-run`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  batchOsOrderApply: (
    id: string,
    body: {
      job_id: string;
      post_after_create?: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<BatchOsJob>(`/api/connections/${id}/batch-os/order/apply`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  batchOsPaymentIntake: async (id: string, file: File, recipeId = "document_batch.payments") => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("recipe_id", recipeId);
    return requestForm<BatchOsJob>(`/api/connections/${id}/batch-os/payment/intake`, fd);
  },
  batchOsPaymentMap: (
    id: string,
    body: { job_id: string; column_map: Record<string, string> },
  ) =>
    request<BatchOsJob>(`/api/connections/${id}/batch-os/payment/map`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  batchOsPaymentDryRun: (id: string, body: { job_id: string }) =>
    request<BatchOsJob>(`/api/connections/${id}/batch-os/payment/dry-run`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  batchOsPaymentApply: (
    id: string,
    body: {
      job_id: string;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<BatchOsJob>(`/api/connections/${id}/batch-os/payment/apply`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  
  batchOsMasterIntake: async (id: string, file: File, kind: "partners" | "products" = "partners") => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("kind", kind);
    return requestForm<BatchOsJob>(`/api/connections/${id}/batch-os/master/intake`, fd);
  },
  batchOsMasterMap: (
    id: string,
    body: { job_id: string; column_map: Record<string, string>; kind?: "partners" | "products" },
  ) => {
    const kind = body.kind || "partners";
    return request<BatchOsJob>(`/api/connections/${id}/batch-os/master/map?kind=${encodeURIComponent(kind)}`, {
      method: "POST",
      body: JSON.stringify({ job_id: body.job_id, column_map: body.column_map }),
    });
  },
  batchOsMasterDryRun: (
    id: string,
    body: { job_id: string; kind?: "partners" | "products" },
  ) => {
    const kind = body.kind || "partners";
    return request<BatchOsJob>(`/api/connections/${id}/batch-os/master/dry-run?kind=${encodeURIComponent(kind)}`, {
      method: "POST",
      body: JSON.stringify({ job_id: body.job_id }),
    });
  },
  batchOsMasterApply: (
    id: string,
    body: {
      job_id: string;
      kind?: "partners" | "products";
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) => {
    const kind = body.kind || "partners";
    return request<BatchOsJob>(`/api/connections/${id}/batch-os/master/apply?kind=${encodeURIComponent(kind)}`, {
      method: "POST",
      body: JSON.stringify({
        job_id: body.job_id,
        confirm_advanced: body.confirm_advanced,
        confirm_phrase: body.confirm_phrase,
      }),
    });
  },

batchOsJob: (id: string, jobId: string) =>
    request<BatchOsJob>(`/api/connections/${id}/batch-os/jobs/${jobId}`),
};
