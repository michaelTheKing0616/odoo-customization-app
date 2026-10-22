import { request } from "./client";
import type { AppTemplate, JobRow, ModuleExport } from "./types-catalog";
import type { ProtectedModuleRefusal, StoreReadinessReport } from "./types-gating";

/** Python piece kept by `_option_a_batch` and returned from option-a-batch. */
export type StudioOptionAPiece = {
  label: string;
  key?: string;
  models?: string[];
  reason?: string;
  delivery_lane?: string;
  online_blocked?: boolean | "true" | "false";
  lane_note?: string;
};

/** Promote control the option-a-batch route returns with the pieces. */
export type StudioOptionAPromote = {
  mode: "single_button";
  label: "Promote";
  config_required: false;
};

/** Success body of `POST /api/ai/sessions/{id}/option-a-batch`. */
export type StudioOptionABatchResponse = {
  session_id: string;
  pieces: StudioOptionAPiece[];
  promote: StudioOptionAPromote;
};

export const studioDraftApi = {
  getJob: (jobId: string) =>
    request<JobRow>(`/api/jobs/${jobId}`, { timeoutMs: 25_000 }),
  getJobArtifact: (jobId: string) =>
    request<{ zip_base64?: string | null; elite_zip_base64?: string | null }>(
      `/api/jobs/${jobId}/artifact`,
      { timeoutMs: 120_000 },
    ),
  listAppTemplates: () => request<AppTemplate[]>("/api/apps/templates"),
  exportLibraryModule: (
    body: {
      technical_name?: string;
      display_name?: string;
      fines?: boolean;
      reminders?: boolean;
      multi_company?: boolean;
      store_ready?: boolean;
    },
    query?: { store_ready?: boolean },
  ) =>
    request<ModuleExport & { store_readiness?: StoreReadinessReport | null }>(
      `/api/apps/templates/library/export${query?.store_ready || body.store_ready ? "?store_ready=true" : ""}`,
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),
    draftModuleFromPrompt: (
    prompt: string,
    opts?: {
      connection_id?: string;
      reuse_models?: string[];
      rejected_reuse_models?: string[];
      reuse_view_ids?: number[];
      reuse_action_ids?: number[];
      expand?: boolean;
      grain?: string | null;
      gallery_id?: string | null;
      host_model?: string | null;
      connect_points?: Record<string, unknown> | null;
      overlap_choice?: string | null;
      overlap_finding_id?: string | null;
      async_job?: boolean;
    },
  ) =>
    request<{
      ok: boolean;
      draft: Record<string, unknown>;
      raw_response?: string | null;
      note?: string;
      warnings?: string[];
      refusals?: ProtectedModuleRefusal[];
      domain_pack?: string | null;
      grain?: string | null;
      grain_label?: string | null;
      connect_points?: Record<string, unknown> | null;
      host_candidates?: Array<{
        model: string;
        label: string;
        score: number;
        reason?: string;
      }>;
      job_id?: string | null;
    }>("/api/ai/draft-module", {
      method: "POST",
      timeoutMs: 660_000,
      body: JSON.stringify({
        prompt,
        connection_id: opts?.connection_id,
        reuse_models: opts?.reuse_models ?? [],
        rejected_reuse_models: opts?.rejected_reuse_models ?? [],
        reuse_view_ids: opts?.reuse_view_ids ?? [],
        reuse_action_ids: opts?.reuse_action_ids ?? [],
        expand: opts?.expand ?? true,
        grain: opts?.grain || undefined,
        gallery_id: opts?.gallery_id || undefined,
        host_model: opts?.host_model || undefined,
        connect_points: opts?.connect_points ?? undefined,
        overlap_choice: opts?.overlap_choice || undefined,
        overlap_finding_id: opts?.overlap_finding_id || undefined,
        async_job: opts?.async_job ?? false,
      }),
    }),
  createStudioSession: (body: {
    prompt: string;
    connection_id?: string;
    feature?: string;
    flash_ast_enrich?: boolean | null;
  }) =>
    request<import("@/lib/studio-session").StudioSession>("/api/ai/sessions", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getStudioPrefs: (connectionId: string) =>
    request<{
      flash_ast_enrich: boolean | null;
      flash_ast_enrich_label: string;
      flash_ast_enrich_help: string;
    }>(`/api/connections/${connectionId}/studio/prefs`),
  patchStudioPrefs: (
    connectionId: string,
    body: { flash_ast_enrich?: boolean | null },
  ) =>
    request<{
      flash_ast_enrich: boolean | null;
      flash_ast_enrich_label: string;
      flash_ast_enrich_help: string;
    }>(`/api/connections/${connectionId}/studio/prefs`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  getStudioSession: (sessionId: string) =>
    request<import("@/lib/studio-session").StudioSession>(`/api/ai/sessions/${sessionId}`),
  clarifyStudioSession: (
    sessionId: string,
    body: {
      merge_key: string;
      answer_id?: string;
      answer_text?: string;
      understanding?: import("@/lib/studio-session").StudioUnderstanding;
    },
  ) =>
    request<import("@/lib/studio-session").StudioSession>(
      `/api/ai/sessions/${sessionId}/clarify`,
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),
  /**
   * Install previews the body (dry run), then sends it.
   * Decline is one POST: that response already stops the session.
   */
  decideStudioStockApp: async (sessionId: string, decision: "install" | "decline") => {
    const url = `/api/ai/sessions/${sessionId}/stock-app`;
    type StockAppDecision = import("@/lib/studio-session").StudioSession & {
      stopped?: boolean;
      message?: string;
      installed?: { module: string; app_label: string; message: string };
    };
    if (decision === "decline") {
      return request<StockAppDecision>(url, {
        method: "POST",
        body: JSON.stringify({ decision, dry_run: false }),
        timeoutMs: 300_000,
      });
    }
    await request<unknown>(url, { method: "POST", body: JSON.stringify({ decision, dry_run: true }) });
    return request<StockAppDecision>(url, {
      method: "POST",
      body: JSON.stringify({ decision, dry_run: false }),
      timeoutMs: 300_000,
    });
  },
  /** Live installs need the same body previewed first (dry-run ledger), then sent for real. */
  installStudioApps: async (sessionId: string) => {
    const url = `/api/ai/sessions/${sessionId}/install-apps`;
    await request<unknown>(url, { method: "POST", body: JSON.stringify({ dry_run: true }) });
    return request<
      import("@/lib/studio-session").StudioSession & {
        install_step?: import("@/lib/studio-session").StudioInstallStep | null;
        installed?: string[];
        install_errors?: string[];
      }
    >(url, {
      method: "POST",
      body: JSON.stringify({ dry_run: false }),
      timeoutMs: 300_000,
    });
  },
  generateStudioSession: (sessionId: string, force = false) =>
    request<import("@/lib/studio-session").StudioSession & { job_id?: string }>(
      `/api/ai/sessions/${sessionId}/generate`,
      {
        method: "POST",
        body: JSON.stringify({ force }),
      },
    ),
  refineStudioSession: (sessionId: string, instruction: string) =>
    request<{
      ok: boolean;
      session: import("@/lib/studio-session").StudioSession;
      patch_summary?: string;
      highlighted_field_ids?: string[];
      needs_clarification?: import("@/lib/studio-session").StudioClarification;
      assistant_reply?: string;
      error?: string;
    }>(`/api/ai/sessions/${sessionId}/refine`, {
      method: "POST",
      body: JSON.stringify({ instruction }),
    }),
  syncStudioJob: (sessionId: string) =>
    request<import("@/lib/studio-session").StudioSession>(
      `/api/ai/sessions/${sessionId}/sync-job`,
      { method: "POST" },
    ),
  startOptionABatch: (sessionId: string) =>
    request<StudioOptionABatchResponse>(
      `/api/ai/sessions/${sessionId}/option-a-batch`,
      { method: "POST", timeoutMs: 180_000 },
    ),
  stampOptionAPromote: (sessionId: string) =>
    request<{
      session?: import("@/lib/studio-session").StudioSession;
      host_model?: string | null;
      open_action_id?: number | null;
      host_install?: Array<{ module: string; label: string; models: string[]; message?: string }>;
      message?: string;
      authoring_status?: string;
    } & import("@/lib/studio-session").StudioSession>(
      `/api/ai/sessions/${sessionId}/stamp-option-a-promote`,
      { method: "POST", timeoutMs: 60_000 },
    ),
  reverifyOptionAAuthoring: async (body: {
    connection_id?: string;
    session_id?: string;
    draft?: Record<string, unknown>;
  }) => {
    type Out = {
      ok: boolean;
      draft: Record<string, unknown>;
      status?: string;
      findings?: Array<{ code?: string; message?: string }>;
      host_install?: Array<{ module: string; label: string; models: string[]; message?: string }>;
      message?: string;
      session?: import("@/lib/studio-session").StudioSession;
    };
    if (body.session_id) {
      try {
        return await request<Out>(`/api/ai/sessions/${body.session_id}/reverify-authoring`, {
          method: "POST",
          timeoutMs: 120_000,
        });
      } catch (err) {
        const msg = err instanceof Error ? err.message : "";
        if (!/not found/i.test(msg)) throw err;
      }
    }
    return request<Out>("/api/ai/option-a/reverify", {
      method: "POST",
      body: JSON.stringify(body),
      timeoutMs: 120_000,
    });
  },
  applyStudioSession: (
    sessionId: string,
    body: {
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
      skip_validate_live?: boolean;
    },
  ) =>
    request<{
      ok: boolean;
      message: string;
      root_menu_id?: number | null;
      open_action_id?: number | null;
      warnings?: string[];
      session?: import("@/lib/studio-session").StudioSession;
    }>(`/api/ai/sessions/${sessionId}/apply`, {
      method: "POST",
      timeoutMs: 660_000,
      body: JSON.stringify(body),
    }),
  enrichDraft: (body: {
    prompt: string;
    draft: Record<string, unknown>;
    connection_id?: string;
    failed_steps?: string[];
    async_job?: boolean;
  }) =>
    request<{
      ok: boolean;
      draft: Record<string, unknown>;
      warnings?: string[];
      job_id?: string;
      note?: string;
    }>("/api/ai/enrich-draft", {
      method: "POST",
      timeoutMs: 660_000,
      body: JSON.stringify({ ...body, async_job: body.async_job ?? true }),
    }),
  reapplyReusePlan: (body: {
    prompt: string;
    draft: Record<string, unknown>;
    connection_id?: string;
    reuse_models?: string[];
    rejected_reuse_models?: string[];
  }) =>
    request<{
      ok: boolean;
      draft: Record<string, unknown>;
      warnings?: string[];
    }>("/api/ai/reapply-reuse", {
      method: "POST",
      body: JSON.stringify({
        prompt: body.prompt,
        draft: body.draft,
        connection_id: body.connection_id,
        reuse_models: body.reuse_models ?? [],
        rejected_reuse_models: body.rejected_reuse_models ?? [],
      }),
    }),
  proposeConnectPoints: (body: {
    prompt: string;
    connection_id?: string;
    grain?: string | null;
    gallery_id?: string | null;
    host_model?: string | null;
    connect_points?: Record<string, unknown> | null;
  }) =>
    request<{
      ok: boolean;
      grain: string;
      grain_label: string;
      connect_points?: Record<string, unknown> | null;
      host_candidates?: Array<{
        model: string;
        label: string;
        score: number;
        reason?: string;
      }>;
      requires_review: boolean;
      warnings?: string[];
      gallery_id?: string | null;
    }>("/api/ai/propose-connect-points", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  checkOverlap: (body: {
    prompt: string;
    connection_id?: string;
    grain?: string | null;
    host_model?: string | null;
  }) =>
    request<{
      ok: boolean;
      grain: string;
      grain_label: string;
      findings: Array<{
        id: string;
        source: string;
        title: string;
        evidence: string;
        confidence: number;
        artifact_type: string;
        artifact_ref: Record<string, unknown>;
        deep_link?: string | null;
        extend_host_model?: string | null;
        options: string[];
      }>;
      semantic_pass_ran: boolean;
      requires_review: boolean;
    }>("/api/ai/check-overlap", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  generalizeComponent: (body: {
    spec_json: Record<string, unknown>;
    consent_share_template: boolean;
    host_slot?: string | null;
    pack_slug?: string | null;
  }) =>
    request<{
      ok: boolean;
      filename: string;
      source: string;
      domain_pack: string;
      host_slot: string;
      connect_points_template?: Record<string, unknown>;
      note: string;
      warnings: string[];
    }>("/api/ai/generalize-component", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  generalizePack: (body: {
    spec_json?: Record<string, unknown>;
    project_id?: string;
    connection_id?: string;
    pack_slug?: string;
    consent_share_template: boolean;
  }) =>
    request<{
      ok: boolean;
      filename: string;
      source: string;
      domain_pack: string;
      suggested_tags: string[];
      anti_patterns: string[];
      model_count: number;
      warnings: string[];
      note: string;
    }>("/api/ai/generalize-pack", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
