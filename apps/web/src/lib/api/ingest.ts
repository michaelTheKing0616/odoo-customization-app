import { request, fetchApi, requestForm, formatDetailMessage } from "./client";
import type { DataImportCommitOut, DataImportPreviewOut, IdGeneratorAssignmentOut, IdGeneratorPreviewOut, IdGeneratorRunOut, ImageImportCommitOut, ImageImportPreviewOut, IngestJobOut } from "./types-ingest";

export const ingestApi = {
  dataImportTemplate: (id: string, model: string) =>
    request<{ model: string; filename: string; csv: string }>(
      `/api/connections/${id}/data-import/template?model=${encodeURIComponent(model)}`,
    ),
  usersCsvTemplate: (id: string) =>
    request<{ model: string; filename: string; csv: string }>(
      `/api/connections/${id}/data-import/users-template`,
    ),
  dataImportPreview: async (id: string, file: File, model?: string) => {
    const fd = new FormData();
    fd.append("file", file);
    if (model) fd.append("model", model);
    return requestForm<DataImportPreviewOut>(
      `/api/connections/${id}/data-import/parse-rows`,
      fd,
    );
  },
  dataImportCommit: (
    id: string,
    body: {
      model: string;
      mapping: Record<string, string>;
      mode?: "create" | "upsert";
      match_fields?: string[];
      dry_run?: boolean;
      batch_size?: number;
      rows: Record<string, string>[];
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<DataImportCommitOut>(`/api/connections/${id}/data-import/commit`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  ingestCreateJob: async (id: string, files: File[]) => {
    const fd = new FormData();
    for (const f of files) fd.append("files", f);
    return requestForm<IngestJobOut>(`/api/connections/${id}/ingest/jobs`, fd);
  },
  ingestGetJob: (id: string, jobId: string) =>
    request<IngestJobOut>(`/api/connections/${id}/ingest/jobs/${jobId}`),
  ingestDryRun: (
    id: string,
    jobId: string,
    body?: {
      batch_size?: number;
      notify_mode?: "batch_summary" | "individual";
      allow_coa_as_is?: boolean;
    },
  ) =>
    request<IngestJobOut>(`/api/connections/${id}/ingest/jobs/${jobId}/dry-run`, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  ingestCommit: (
    id: string,
    jobId: string,
    body?: {
      batch_size?: number;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
      notify_mode?: "batch_summary" | "individual";
      allow_coa_as_is?: boolean;
    },
  ) =>
    request<IngestJobOut>(`/api/connections/${id}/ingest/jobs/${jobId}/commit`, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  ingestOverride: (
    id: string,
    jobId: string,
    body: { force_doc_types: Record<string, string> },
  ) =>
    request<IngestJobOut>(`/api/connections/${id}/ingest/jobs/${jobId}/override`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  ingestCoaRemap: (
    id: string,
    jobId: string,
    body: { remap?: Record<string, string>; auto?: boolean; min_score?: number },
  ) =>
    request<IngestJobOut>(`/api/connections/${id}/ingest/jobs/${jobId}/coa-remap`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  ingestGetPrefs: (id: string) =>
    request<{
      notify_mode: "batch_summary" | "individual";
      allow_coa_as_is_default: boolean;
      coa_auto_remap_default: boolean;
    }>(`/api/connections/${id}/ingest/prefs`),
  ingestPatchPrefs: (
    id: string,
    body: {
      notify_mode?: "batch_summary" | "individual";
      allow_coa_as_is_default?: boolean;
      coa_auto_remap_default?: boolean;
    },
  ) =>
    request<{
      notify_mode: "batch_summary" | "individual";
      allow_coa_as_is_default: boolean;
      coa_auto_remap_default: boolean;
    }>(`/api/connections/${id}/ingest/prefs`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  ingestVisionStatus: (id: string) =>
    request<{ enabled: boolean; ready: boolean; message: string; model: string }>(
      `/api/connections/${id}/ingest/vision/status`,
    ),
  ingestInterviewQuestions: (id: string) =>
    request<
      Array<{ id: string; prompt: string; kind: string; choices: string[] }>
    >(`/api/connections/${id}/ingest/interview/questions`),
  ingestCreateInterviewJob: (
    id: string,
    body: {
      business_name?: string;
      product_type?: "product" | "service" | "mixed";
      product_lines?: string[];
      starter_contacts?: string[];
      expense_categories?: string[];
    },
  ) =>
    request<IngestJobOut>(`/api/connections/${id}/ingest/interview/jobs`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  imageImportPreview: async (id: string, manifest: File, imagesZip: File) => {
    const fd = new FormData();
    fd.append("manifest", manifest);
    fd.append("images_zip", imagesZip);
    return requestForm<ImageImportPreviewOut>(
      `/api/connections/${id}/data-import/images/preview`,
      fd,
    );
  },
  imageImportCommit: async (
    id: string,
    body: {
      model: string;
      manifest: File;
      imagesZip: File;
      match_field?: string;
      image_field?: string;
      dry_run?: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) => {
    const fd = new FormData();
    fd.append("manifest", body.manifest);
    fd.append("images_zip", body.imagesZip);
    fd.append("model", body.model);
    fd.append("match_field", body.match_field ?? "x_name");
    if (body.image_field) fd.append("image_field", body.image_field);
    fd.append("dry_run", String(body.dry_run ?? true));
    if (body.confirm_advanced) fd.append("confirm_advanced", "true");
    if (body.confirm_phrase) fd.append("confirm_phrase", body.confirm_phrase);
    return requestForm<ImageImportCommitOut>(
      `/api/connections/${id}/data-import/images/commit`,
      fd,
    );
  },
  idGeneratorCsvPreview: async (
    id: string,
    file: File,
    body: {
      name_column: string;
      code_column?: string;
      id_column?: string;
      prefix: string;
      separator?: string;
      padding?: number;
      initials_length?: number;
      skip_if_present?: boolean;
      changed_only?: boolean;
    },
  ) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("name_column", body.name_column);
    if (body.code_column) fd.append("code_column", body.code_column);
    if (body.id_column) fd.append("id_column", body.id_column);
    fd.append("prefix", body.prefix);
    fd.append("separator", body.separator ?? "-");
    fd.append("padding", String(body.padding ?? 4));
    fd.append("initials_length", String(body.initials_length ?? 3));
    fd.append("skip_if_present", String(body.skip_if_present ?? true));
    fd.append("changed_only", String(body.changed_only ?? false));
    return requestForm<IdGeneratorPreviewOut>(`/api/connections/${id}/id-generator/csv/preview`, fd);
  },
  idGeneratorCsvDownload: async (
    id: string,
    body: {
      headers: string[];
      rows: Record<string, string>[];
      assignments: IdGeneratorAssignmentOut[];
      code_column: string;
      changed_only?: boolean;
    },
  ) => {
    const res = await fetchApi(`/api/connections/${id}/id-generator/csv/download`, {
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
      throw new Error(formatDetailMessage(detail) || `CSV download failed (${res.status})`);
    }
    return res.blob();
  },
  idGeneratorLive: (
    id: string,
    body: {
      model: string;
      name_field: string;
      code_field: string;
      config: {
        prefix: string;
        separator?: string;
        padding?: number;
        initials_length?: number;
        skip_if_present?: boolean;
      };
      ids?: number[];
      domain?: string | unknown[];
      dry_run?: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<IdGeneratorRunOut>(`/api/connections/${id}/id-generator/live`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  idGeneratorCreateSequence: (
    id: string,
    body: {
      model: string;
      config: {
        prefix: string;
        separator?: string;
        padding?: number;
        initials_length?: number;
        skip_if_present?: boolean;
      };
      sequence_name?: string;
    },
  ) =>
    request<{ ok: boolean; sequence: Record<string, unknown> }>(
      `/api/connections/${id}/id-generator/sequence`,
      { method: "POST", body: JSON.stringify(body) },
    ),
};
