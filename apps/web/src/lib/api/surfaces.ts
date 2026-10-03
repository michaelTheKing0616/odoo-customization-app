import { request, fetchApi, requestForm } from "./client";
import type { ReportRenderProbeOut } from "./types-bulk";
import type { MenuNode, WindowActionRow } from "./types-catalog";

export const surfacesApi = {
  listWebsitePages: (id: string) =>
    request<{
      available: boolean;
      reason: string | null;
      pages: Array<{
        id: number;
        name: string | null;
        url: string | null;
        is_published: boolean | null;
      }> | null;
      menus: null;
    }>(`/api/connections/${id}/config/website/pages`),
  listWebsiteMenus: (id: string) =>
    request<{
      available: boolean;
      reason: string | null;
      pages: null;
      menus: Array<{
        id: number;
        name: string | null;
        url: string | null;
        sequence: number;
      }> | null;
    }>(`/api/connections/${id}/config/website/menus`),
  getWebsitePageBlocks: (id: string, pageId: number) =>
    request<{
      page_id: number;
      view_id: number;
      name: string;
      url: string | null;
      is_published: boolean;
      blocks: Array<Record<string, unknown>>;
    }>(`/api/connections/${id}/website/pages/${pageId}/blocks`),
  saveWebsitePageBlocks: (
    id: string,
    pageId: number,
    body: { page_id: number; view_id: number; blocks: Array<Record<string, unknown>> },
  ) =>
    request<{ ok: boolean; view_id: number; arch_len: number }>(
      `/api/connections/${id}/website/pages/${pageId}/blocks`,
      { method: "PUT", body: JSON.stringify(body) },
    ),
  publishWebsitePage: (id: string, pageId: number, publish: boolean) =>
    request<{ ok: boolean; page_id: number; is_published: boolean }>(
      `/api/connections/${id}/website/pages/${pageId}/publish`,
      { method: "POST", body: JSON.stringify({ page_id: pageId, publish }) },
    ),
  uploadWebsiteImage: (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return requestForm<{ attachment_id: number; src: string; name: string }>(
      `/api/connections/${id}/website/upload-image`,
      form,
    );
  },
  listMenuTree: (id: string, opts?: { rootsOnly?: boolean; parentId?: number }) => {
    const q = new URLSearchParams();
    if (opts?.rootsOnly) q.set("roots_only", "true");
    if (opts?.parentId != null) q.set("parent_id", String(opts.parentId));
    const qs = q.toString();
    return request<MenuNode[]>(
      `/api/connections/${id}/menus-builder/tree${qs ? `?${qs}` : ""}`,
    );
  },
  createBuilderMenu: (
    id: string,
    body: {
      name: string;
      parent_id?: number | null;
      action_id?: number | null;
      sequence?: number;
      web_icon?: string | null;
      group_ids?: number[];
    },
  ) =>
    request<MenuNode>(`/api/connections/${id}/menus-builder/menus`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateBuilderMenu: (
    id: string,
    menuId: number,
    body: Record<string, unknown>,
  ) =>
    request<MenuNode>(
      `/api/connections/${id}/menus-builder/menus/${menuId}`,
      { method: "PATCH", body: JSON.stringify(body) },
    ),
  deleteBuilderMenu: (
    id: string,
    menuId: number,
    body: { confirm_advanced?: boolean; confirm_phrase?: string | null },
  ) =>
    request<{ ok: boolean; menu_id?: number; snapshot_id?: string | null }>(
      `/api/connections/${id}/menus-builder/menus/${menuId}`,
      { method: "DELETE", body: JSON.stringify(body) },
    ),
  listWindowActions: (
    id: string,
    opts?: { model?: string; q?: string; standaloneOnly?: boolean },
  ) => {
    const q = new URLSearchParams();
    if (opts?.model) q.set("model", opts.model);
    if (opts?.q) q.set("q", opts.q);
    if (opts?.standaloneOnly) q.set("standalone_only", "true");
    const qs = q.toString();
    return request<WindowActionRow[]>(
      `/api/connections/${id}/menus-builder/actions${qs ? `?${qs}` : ""}`,
    );
  },
  createWindowAction: (
    id: string,
    body: {
      name: string;
      model: string;
      view_mode?: string;
      domain?: string | null;
      context?: string | null;
      target?: string;
    },
  ) =>
    request<{ id: number; name: string; res_model: string | null }>(
      `/api/connections/${id}/menus-builder/actions`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  updateWindowAction: (id: string, actionId: number, body: Record<string, unknown>) =>
    request<{ id: number; name: string }>(
      `/api/connections/${id}/menus-builder/actions/${actionId}`,
      { method: "PATCH", body: JSON.stringify(body) },
    ),
  listReports: (id: string, model?: string) =>
    request<
      Array<{
        id: number;
        name: string;
        model: string | null;
        report_type: string | null;
        report_name: string | null;
        paperformat_id: number | null;
        paperformat_name: string | null;
        arch: string | null;
        view_id: number | null;
      }>
    >(
      `/api/connections/${id}/reports${model ? `?model=${encodeURIComponent(model)}` : ""}`,
    ),
  listPaperformats: (id: string) =>
    request<
      Array<{
        id: number;
        name: string;
        format: string | null;
        orientation: string | null;
      }>
    >(`/api/connections/${id}/reports/paperformats`),
  createReport: (
    id: string,
    body: {
      name: string;
      model: string;
      report_key: string;
      arch?: string | null;
      paperformat_id?: number | null;
    },
  ) =>
    request<{ id: number; name: string; report_name: string | null }>(
      `/api/connections/${id}/reports`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  updateReport: (id: string, reportId: number, body: Record<string, unknown>) =>
    request<{ id: number; name: string }>(`/api/connections/${id}/reports/${reportId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteReport: (
    id: string,
    reportId: number,
    body: { confirm_advanced?: boolean; confirm_phrase?: string | null },
  ) =>
    request<{ ok: boolean }>(`/api/connections/${id}/reports/${reportId}`, {
      method: "DELETE",
      body: JSON.stringify(body),
    }),
  reportRenderProbe: (id: string, reportId?: number, resId?: number) => {
    const params = new URLSearchParams();
    if (reportId != null) params.set("report_id", String(reportId));
    if (resId != null) params.set("res_id", String(resId));
    const q = params.toString();
    return request<ReportRenderProbeOut>(
      `/api/connections/${id}/reports/render-probe${q ? `?${q}` : ""}`,
    );
  },
  getReportDesignPalette: (id: string) =>
    request<Array<{ type: string; label: string; hint: string }>>(
      `/api/connections/${id}/reports/design/palette`,
    ),
  compileReportDesign: (id: string, body: { spec: Record<string, unknown> }) =>
    request<{ ok: boolean; arch: string; body_html: string }>(
      `/api/connections/${id}/reports/design/compile`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  previewReportDesign: (
    id: string,
    body: { spec: Record<string, unknown>; report_id: number; record_id: number },
  ) =>
    request<{
      ok: boolean;
      content_base64: string;
      render_path: string;
      message: string;
    }>(`/api/connections/${id}/reports/design/preview`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  reportDesignToModuleSpec: (id: string, body: { spec: Record<string, unknown> }) =>
    request<{ ok: boolean; fragment: Record<string, unknown> }>(
      `/api/connections/${id}/reports/design/to-module-spec`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  mergePrintReports: async (
    id: string,
    body: {
      items: Array<{ report_id: number; record_ids: number[] }>;
      order?: number[];
      filename?: string;
    },
  ) => {
    const res = await fetchApi(`/api/connections/${id}/reports/merge-print`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      let detail: unknown = res.statusText;
      try {
        const parsed = await res.json();
        detail = parsed.detail !== undefined ? parsed.detail : parsed;
      } catch {
        /* ignore */
      }
      throw new Error(formatDetailMessage(detail) || `Merge print failed (${res.status})`);
    }
    return {
      blob: await res.blob(),
      totalPages: res.headers.get("X-Total-Pages"),
      renderPath: res.headers.get("X-Render-Path"),
    };
  },
  listPipelines: () =>
    request<
      Array<{
        id: string;
        name: string;
        staging_connection_id: string;
        prod_connection_id: string;
        sandbox_connection_id: string | null;
        created_at: string | null;
      }>
    >("/api/pipelines"),
  createPipeline: (body: {
    name: string;
    staging_connection_id: string;
    prod_connection_id: string;
    sandbox_connection_id?: string | null;
  }) =>
    request<{ id: string; name: string }>("/api/pipelines", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listPipelineHops: (pipelineId: string) =>
    request<
      Array<{
        id: string;
        hop: string;
        module_name: string;
        zip_sha256: string;
        status: string;
        message: string;
        validation_id: string | null;
        created_at: string | null;
      }>
    >(`/api/pipelines/${pipelineId}/hops`),
  pipelinePromote: (
    pipelineId: string,
    body: {
      hop: "sandbox" | "staging" | "prod";
      zip_base64: string;
      validation_id?: string | null;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<{
      ok: boolean;
      hop: string;
      module_name: string;
      zip_sha256: string;
      validation_id: string | null;
      message: string;
      hop_record_id: string | null;
      promote_method: string | null;
    }>(`/api/pipelines/${pipelineId}/promote`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listSeedPacks: (id: string) =>
    request<
      Array<{ id: string; name: string; description: string; models: string[] }>
    >(`/api/connections/${id}/data-import/seed-packs`),
  getSeedPack: (id: string, packId: string) =>
    request<{
      id: string;
      name: string;
      description: string;
      models: Array<{ model: string; filename: string; csv: string }>;
    }>(`/api/connections/${id}/data-import/seed-packs/${packId}`),
  listComponentGallery: () =>
    request<Array<{ id: string; name: string; description: string; host_slot: string }>>("/api/ai/component-gallery"),
};
