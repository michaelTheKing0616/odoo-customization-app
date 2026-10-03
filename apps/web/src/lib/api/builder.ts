import { request } from "./client";
import type { BuilderWidgetOption, FieldCreateRow, FieldRow, InvoicingConnectOut, InvoicingDraftInvoiceOut, InvoicingMergeSpecOut, InvoicingModuleSpecOut, InvoicingPreflightOut, NicheWidgetsResponse, PreviewTheme, PropertyDefinitionWriteOut, PropertyFieldsProbeOut, PropertyFieldsSetupOut, RelatedPathOption, ScanFindOut } from "./types-schema";

export const builderApi = {
  createField: (
    id: string,
    body: {
      model: string;
      name: string;
      field_description: string;
      ttype: string;
      required?: boolean;
      readonly?: boolean;
      relation?: string | null;
      relation_field?: string | null;
      selection?: { value: string; label: string }[] | null;
      help?: string | null;
      related?: string | null;
      currency_field?: string | null;
      on_delete?: "set null" | "restrict" | "cascade" | null;
      inject_into_views?: boolean;
      inject_strategy?: "inherit" | "mutate";
      view_widget?: string | null;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<FieldCreateRow>(`/api/connections/${id}/fields`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listBuilderWidgets: (id: string, ttype: string) =>
    request<BuilderWidgetOption[]>(
      `/api/connections/${id}/builder/widgets?ttype=${encodeURIComponent(ttype)}`,
    ),
  listRelatedPaths: (id: string, model: string, depth = 2) =>
    request<RelatedPathOption[]>(
      `/api/connections/${id}/builder/related-paths?model=${encodeURIComponent(model)}&depth=${depth}`,
    ),
  listNicheWidgets: (id: string, viewType: string) =>
    request<NicheWidgetsResponse>(
      `/api/connections/${id}/builder/niche-widgets?view_type=${encodeURIComponent(viewType)}`,
    ),
  getPreviewTheme: (id: string) =>
    request<PreviewTheme>(`/api/connections/${id}/preview-theme`),
  getPropertyFieldsProbe: (id: string) =>
    request<PropertyFieldsProbeOut>(`/api/connections/${id}/builder/properties/probe`),
  setupPropertyFields: (
    id: string,
    body: {
      child_model: string;
      parent_m2o_field: string;
      properties_field?: string;
      definition_field?: string;
      properties_label?: string;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<PropertyFieldsSetupOut>(`/api/connections/${id}/builder/properties/setup`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  writePropertyDefinition: (
    id: string,
    body: {
      parent_model: string;
      parent_record_id: number;
      definition_field?: string;
      entries: Array<{
        name: string;
        string?: string;
        type?: string;
        default?: string | number | boolean | null;
        selection?: string[][];
        comodel?: string;
      }>;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<PropertyDefinitionWriteOut>(`/api/connections/${id}/builder/properties/definition`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getInvoicingPreflight: (id: string) =>
    request<InvoicingPreflightOut>(`/api/connections/${id}/builder/invoicing/preflight`),
  connectInvoicing: (
    id: string,
    body: {
      model: string;
      invoice_field?: string;
      smart_button_name?: string;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<InvoicingConnectOut>(`/api/connections/${id}/builder/invoicing/connect`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createDraftInvoice: (
    id: string,
    body: {
      source_model: string;
      record_id: number;
      invoice_field?: string;
      partner_field?: string;
      amount_field?: string;
      description_field?: string;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<InvoicingDraftInvoiceOut>(`/api/connections/${id}/builder/invoicing/draft-invoice`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getInvoicingModuleSpec: (
    id: string,
    body: {
      model: string;
      invoice_field?: string;
      origin_field_on_move?: string;
      partner_field?: string;
    },
  ) =>
    request<InvoicingModuleSpecOut>(`/api/connections/${id}/builder/invoicing/module-spec`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  mergeInvoicingIntoSpec: (
    id: string,
    body: {
      base_spec?: Record<string, unknown>;
      model: string;
      invoice_field?: string;
      origin_field_on_move?: string;
      partner_field?: string;
    },
  ) =>
    request<InvoicingMergeSpecOut>(`/api/connections/${id}/builder/invoicing/merge-into-spec`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getDocumentsGate: (id: string) =>
    request<{
      ok: boolean;
      available: boolean;
      verify_state?: string | null;
      folder_model?: string | null;
      message?: string | null;
      note?: string | null;
    }>(`/api/connections/${id}/builder/documents/gate`),
  getDocumentsFolderMap: (id: string) =>
    request<{ ok: boolean; mapping: Record<string, number> }>(
      `/api/connections/${id}/builder/documents/folder-map`,
    ),
  setDocumentsFolder: (
    id: string,
    body: { model: string; folder_id?: number | null },
  ) =>
    request<{ ok: boolean; mapping: Record<string, number> }>(
      `/api/connections/${id}/builder/documents/folder-map`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  mergeDocumentsIntoSpec: (
    id: string,
    body: {
      base_spec?: Record<string, unknown>;
      model: string;
      folder_id: number;
    },
  ) =>
    request<{ ok: boolean; merged: Record<string, unknown> }>(
      `/api/connections/${id}/builder/documents/merge-into-spec`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  bulkScanFind: (
    id: string,
    body: { model: string; field: string; value: string; limit?: number },
  ) =>
    request<ScanFindOut>(`/api/connections/${id}/bulk/scan-find`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateField: (
    id: string,
    fieldId: number,
    body: {
      string?: string;
      field_description?: string;
      help?: string | null;
      required?: boolean;
      readonly?: boolean;
      tracking?: boolean;
      selection?: string | null;
    },
  ) =>
    request<FieldRow>(`/api/connections/${id}/fields/${fieldId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteField: (
    id: string,
    fieldId: number,
    body: {
      mode?: "deprecate" | "hard_delete";
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<{
      ok: boolean;
      field_id: number;
      mode: "deprecate" | "hard_delete";
      snapshot_id: string | null;
      artifact_id?: string | null;
      artifact_url?: string | null;
      row_count?: number | null;
      truncated?: boolean | null;
      new_field_name?: string | null;
    }>(`/api/connections/${id}/fields/${fieldId}`, {
      method: "DELETE",
      body: JSON.stringify(body),
    }),
  deleteModel: (
    id: string,
    model: string,
    body: { confirm_advanced?: boolean; confirm_phrase?: string | null },
  ) =>
    request<{ ok: boolean; model: string; snapshot_id: string | null }>(
      `/api/connections/${id}/models/${encodeURIComponent(model)}`,
      { method: "DELETE", body: JSON.stringify(body) },
    ),
};
