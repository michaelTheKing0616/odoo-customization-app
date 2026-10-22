import { request, fetchApi, ODOO_RPC_READ_TIMEOUT_MS } from "./client";
import { api } from "../api";
import type { ProtectedTier } from "./types-gating";
import type { FieldRow, ModelRow, ModuleRow, ReuseModelRow, ViewRow } from "./types-schema";

export const schemaApi = {
  listModules: (
    id: string,
    applicationsOnlyOrOpts:
      | boolean
      | { applicationsOnly?: boolean; installedOnly?: boolean } = false,
  ) => {
    const opts =
      typeof applicationsOnlyOrOpts === "boolean"
        ? { applicationsOnly: applicationsOnlyOrOpts, installedOnly: true }
        : {
            applicationsOnly: applicationsOnlyOrOpts.applicationsOnly ?? false,
            installedOnly: applicationsOnlyOrOpts.installedOnly ?? true,
          };
    const params = new URLSearchParams({
      applications_only: String(opts.applicationsOnly),
      installed_only: String(opts.installedOnly),
    });
    return request<ModuleRow[]>(`/api/connections/${id}/modules?${params}`);
  },
  listInstalledModules: (id: string, q?: string) => {
    const params = new URLSearchParams();
    if (q?.trim()) params.set("q", q.trim());
    const qs = params.toString();
    return request<ModuleRow[]>(
      `/api/connections/${id}/modules/installed${qs ? `?${qs}` : ""}`,
    );
  },
  /** Live installs need the same body previewed first (dry-run ledger), then sent for real. */
  installCommunityModule: async (id: string, moduleName: string) => {
    const url = `/api/connections/${id}/modules/install-community`;
    await request<unknown>(url, {
      method: "POST",
      body: JSON.stringify({ module_name: moduleName, dry_run: true }),
      timeoutMs: 60_000,
    });
    return request<{
      ok: boolean;
      module: string;
      module_state?: string | null;
      message: string;
    }>(url, {
      method: "POST",
      body: JSON.stringify({ module_name: moduleName, dry_run: false }),
      timeoutMs: 300_000,
    });
  },
  listModels: (id: string, customOnly = false, limit = 2000) =>
    request<ModelRow[]>(
      `/api/connections/${id}/models?custom_only=${customOnly}&limit=${limit}`,
      { timeoutMs: ODOO_RPC_READ_TIMEOUT_MS },
    ),
  listReuseCatalog: async (id: string, q?: string, limit = 2000) => {
    const params = new URLSearchParams({ limit: String(limit), stock_only: "true" });
    if (q?.trim()) params.set("q", q.trim());
    try {
      return await request<ReuseModelRow[]>(
        `/api/connections/${id}/reuse-catalog?${params.toString()}`,
        { timeoutMs: ODOO_RPC_READ_TIMEOUT_MS },
      );
    } catch {
      const models = await api.listModels(id, false, limit);
      const needle = (q || "").trim().toLowerCase();
      return models
        .filter((m) => m.model && !m.model.startsWith("x_"))
        .filter((m) => {
          if (!needle) return true;
          const hay = `${m.model} ${m.name}`.toLowerCase();
          return hay.includes(needle);
        })
        .map((m) => ({
          model: m.model,
          name: m.name || m.model,
          app: m.model.split(".")[0] || m.model,
          link_only: false,
        }));
    }
  },
  listDraftCache: (connectionId?: string, limit = 20) => {
    const qs = connectionId
      ? `?connection_id=${encodeURIComponent(connectionId)}&limit=${limit}`
      : `?limit=${limit}`;
    return request<
      Array<{
        id: string;
        connection_id: string | null;
        prompt: string;
        summary: string;
        domain_pack: string | null;
        draft: Record<string, unknown>;
        updated_at: string | null;
      }>
    >(`/api/ai/draft-cache${qs}`);
  },
  getDraftCache: (cacheId: string) =>
    request<{
      id: string;
      prompt: string;
      summary: string;
      draft: Record<string, unknown>;
    }>(`/api/ai/draft-cache/${cacheId}`),
  modelTier: (connectionId: string, model: string) =>
    request<{ model: string; tier: ProtectedTier | null }>(
      `/api/connections/${connectionId}/model-tier?model=${encodeURIComponent(model)}`,
    ),
  listFields: (id: string, model: string) =>
    request<FieldRow[]>(`/api/connections/${id}/models/${encodeURIComponent(model)}/fields`),
  /** Q2 touch 56: share of records with each field filled (counts only). */
  fieldFill: (id: string, model: string, fields: string[]) =>
    request<{ model: string; total: number; fill: Record<string, number | null> }>(
      `/api/connections/${id}/models/${encodeURIComponent(model)}/fill?fields=${encodeURIComponent(fields.slice(0, 40).join(","))}`,
    ),
  listViews: (id: string, model: string) =>
    request<ViewRow[]>(`/api/connections/${id}/models/${encodeURIComponent(model)}/views`),
  createModel: (
    id: string,
    body: {
      name: string;
      model: string;
      transient?: boolean;
      with_defaults?: boolean;
      enable_mail_thread?: boolean;
    },
  ) =>
    request<
      ModelRow & { warnings?: string[]; mail_thread_enabled?: boolean }
    >(`/api/connections/${id}/models`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createRelationalPair: (
    id: string,
    body: {
      parent_model: string;
      child_model: string;
      parent_o2m_name: string;
      child_m2o_name: string;
      parent_o2m_string: string;
      child_m2o_string: string;
      inject_into_views?: boolean;
    },
  ) =>
    request<{
      ok: boolean;
      parent_model: string;
      child_model: string;
      parent_o2m_name: string;
      child_m2o_name: string;
      m2o_created: boolean;
      o2m_created: boolean;
      injected_view_ids: number[];
      warnings: string[];
    }>(`/api/connections/${id}/fields/relational_pair`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listProjects: (id: string) =>
    request<
      {
        id: string;
        connection_id: string;
        name: string;
        template_id: string | null;
        spec_json: Record<string, unknown>;
        status: string;
        lifecycle_status?: string;
        created_at?: string | null;
        updated_at?: string | null;
      }[]
    >(`/api/connections/${id}/projects`),
  archiveProject: (id: string, projectId: string) =>
    request<{ lifecycle_status: string }>(`/api/connections/${id}/projects/${projectId}/archive`, {
      method: "POST",
    }),
  unarchiveProject: (id: string, projectId: string) =>
    request<{ lifecycle_status: string }>(`/api/connections/${id}/projects/${projectId}/unarchive`, {
      method: "POST",
    }),
  createProject: (
    id: string,
    body: {
      name: string;
      template_id?: string | null;
      spec_json?: Record<string, unknown>;
    },
  ) =>
    request<{
      id: string;
      connection_id: string;
      name: string;
      template_id: string | null;
      spec_json: Record<string, unknown>;
      status: string;
    }>(`/api/connections/${id}/projects`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getProject: (id: string, projectId: string) =>
    request<{
      id: string;
      connection_id: string;
      name: string;
      template_id: string | null;
      spec_json: Record<string, unknown>;
      status: string;
    }>(`/api/connections/${id}/projects/${projectId}`),
  updateProject: (
    id: string,
    projectId: string,
    body: {
      name?: string;
      template_id?: string | null;
      spec_json?: Record<string, unknown>;
      status?: string;
    },
  ) =>
    request<{
      id: string;
      connection_id: string;
      name: string;
      template_id: string | null;
      spec_json: Record<string, unknown>;
      status: string;
    }>(`/api/connections/${id}/projects/${projectId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  importModuleSpec: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetchApi("/api/module-spec/import", {
      method: "POST",
      body: form,
    });
    if (!res.ok) {
      let detail: unknown = res.statusText;
      try {
        const body = await res.json();
        detail = body.detail !== undefined ? body.detail : body;
      } catch {
        /* ignore */
      }
      throw new Error(
        typeof detail === "string" ? detail : JSON.stringify(detail),
      );
    }
    return res.json() as Promise<{
      ok: boolean;
      spec: Record<string, unknown>;
      warnings: string[];
      unmapped: Record<string, unknown>[];
      source: string;
      note?: string;
    }>;
  },
  importModuleSpecJson: (body: { spec: Record<string, unknown>; prepare?: boolean }) =>
    request<{
      ok: boolean;
      spec: Record<string, unknown>;
      warnings: string[];
      unmapped: Record<string, unknown>[];
      custom_code_blocks: Record<string, unknown>[];
      source: string;
      note?: string;
    }>("/api/module-spec/import-json", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  applyProject: (
    id: string,
    projectId: string,
    body: { confirm_advanced?: boolean; confirm_phrase?: string | null },
  ) =>
    request<{
      ok: boolean;
      project_id: string;
      models_created: string[];
      fields_created: number;
      skipped: string[];
      warnings: string[];
      message: string;
    }>(`/api/connections/${id}/projects/${projectId}/apply`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  deleteProject: (id: string, projectId: string) =>
    request<void>(`/api/connections/${id}/projects/${projectId}`, {
      method: "DELETE",
    }),
};
