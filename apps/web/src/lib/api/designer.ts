import { request } from "./client";
import type { LocatorIssue, MailTemplateRow, ServerActionOut, SmartButtonBundleOut, WindowActionOut, XPathPreviewOut } from "./types-actions";
import type { ViewRow } from "./types-schema";

export const designerApi = {
  previewViewArch: (id: string, view_type: string, spec: unknown) =>
    request<{ arch: string }>(`/api/connections/${id}/views/preview`, {
      method: "POST",
      body: JSON.stringify({ view_type, spec }),
    }),
  parseViewArch: (id: string, view_type: string, arch: string) =>
    request<{ view_type: string; spec: Record<string, unknown> }>(
      `/api/connections/${id}/views/parse`,
      {
        method: "POST",
        body: JSON.stringify({ view_type, arch }),
      },
    ),
  listBindableActions: (id: string, model: string) =>
    request<
      Array<{
        id: number;
        name: string;
        action_type: "ir.actions.server" | "ir.actions.act_window";
        model: string;
        detail: string | null;
      }>
    >(`/api/connections/${id}/actions/bindable?model=${encodeURIComponent(model)}`),
  createUpdateFieldAction: (
    id: string,
    body: {
      name: string;
      model: string;
      field_name: string;
      value: string;
      bind_to_model?: boolean;
    },
  ) =>
    request<{
      id: number;
      name: string;
      model: string;
      model_id: number;
      state: string;
      binding_model_id: number | null;
      binding_type: string | null;
    }>(`/api/connections/${id}/actions/server/update-field`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createRelatedWindowAction: (
    id: string,
    body: {
      name: string;
      source_model: string;
      target_model: string;
      relation_field: string;
      view_mode?: string;
    },
  ) =>
    request<WindowActionOut>(`/api/connections/${id}/actions/window/related`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createNextActivityAction: (
    id: string,
    body: {
      name: string;
      model: string;
      activity_type_id: number;
      summary?: string;
      note?: string | null;
      user_type?: "specific" | "generic";
      user_id?: number | null;
      user_field_name?: string | null;
      bind_to_model?: boolean;
    },
  ) =>
    request<ServerActionOut>(`/api/connections/${id}/actions/server/next-activity`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createMailPostAction: (
    id: string,
    body: {
      name: string;
      model: string;
      template_id?: number | null;
      mail_post_method?: "email" | "comment" | "note";
      subject?: string | null;
      body_html?: string | null;
      email_to?: string | null;
      bind_to_model?: boolean;
    },
  ) =>
    request<ServerActionOut>(`/api/connections/${id}/actions/server/mail-post`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createSmartButtonBundle: (
    id: string,
    body: {
      name: string;
      source_model: string;
      target_model: string;
      relation_field: string;
      one2many_field?: string | null;
      count_field_name?: string | null;
      create_count_field?: boolean;
      icon?: string;
      view_mode?: string;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<SmartButtonBundleOut>(`/api/connections/${id}/actions/smart-button`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listMailTemplates: (id: string, model?: string) => {
    const qs = model ? `?model=${encodeURIComponent(model)}` : "";
    return request<MailTemplateRow[]>(
      `/api/connections/${id}/actions/mail-templates${qs}`,
    );
  },
  xpathPreview: (
    id: string,
    body: {
      expr: string;
      position?: "inside" | "after" | "before" | "replace" | "attributes";
      body_xml: string;
      parent_arch?: string | null;
      view_type?: string;
    },
  ) =>
    request<XPathPreviewOut>(`/api/connections/${id}/views/xpath/preview`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getPrimaryView: (id: string, model: string, view_type: string) =>
    request<ViewRow>(
      `/api/connections/${id}/views/primary?model=${encodeURIComponent(model)}&view_type=${encodeURIComponent(view_type)}`,
    ),
  resolveFieldNode: (
    id: string,
    body: { view_type: string; arch: string; field_name: string },
  ) =>
    request<{
      field_name: string;
      candidates: Array<{
        xpath: string;
        match?: string;
        from_spec?: boolean;
        score?: number;
        fragile?: boolean;
        match_count?: number | null;
      }>;
      ambiguous: boolean;
    }>(`/api/connections/${id}/views/resolve-field`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  resolveStructure: (
    id: string,
    body: { arch: string; tags?: string[] },
  ) =>
    request<{
      candidates: Array<{
        xpath: string;
        tag: string;
        label: string;
        score?: number;
        fragile?: boolean;
        match_count?: number | null;
      }>;
      ambiguous: boolean;
    }>(`/api/connections/${id}/views/resolve-structure`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  overlayPreview: (
    id: string,
    body: Record<string, unknown>,
  ) =>
    request<{
      xpath_arch: string;
      issues: string[];
      locator_issues?: LocatorIssue[];
      suggested_expr?: string | null;
    }>(
      `/api/connections/${id}/views/overlay/preview`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  applyOverlayOp: (
    id: string,
    body: Record<string, unknown>,
  ) =>
    request<{
      xpath_arch: string;
      issues: string[];
      locator_issues?: LocatorIssue[];
      suggested_expr?: string | null;
      view_id?: number | null;
      snapshot_id?: string | null;
      inherit_name?: string | null;
    }>(`/api/connections/${id}/views/overlay/apply`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  previewFrameUrl: (id: string, model: string, view_type: string) =>
    `/api/connections/${id}/preview/frame?model=${encodeURIComponent(model)}&view_type=${encodeURIComponent(view_type)}`,
  saveView: (
    id: string,
    body: {
      model: string;
      view_type: string;
      name?: string;
      view_id?: number;
      spec?: unknown;
      arch?: string;
      create_if_missing?: boolean;
      strategy?: "inherit" | "overwrite";
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<ViewRow>(`/api/connections/${id}/views/save`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  repairDesignerInherit: (
    id: string,
    body: { model: string; view_type?: string },
  ) =>
    request<{
      action: "repaired" | "already_additive" | "unlinked" | "missing";
      model: string;
      view_type: string;
      view_id?: number | null;
      view_name?: string | null;
      snapshot_id?: string | null;
      kept_custom_fields: string[];
      remaining_custom_injects: string[];
      detail: string;
    }>(`/api/connections/${id}/views/designer-inherit/repair`, {
      method: "POST",
      body: JSON.stringify({ view_type: "form", ...body }),
    }),
  unlinkDesignerInherit: (
    id: string,
    body: {
      model: string;
      view_type?: string;
      confirm_advanced: boolean;
      confirm_phrase: string;
    },
  ) =>
    request<{
      action: "repaired" | "already_additive" | "unlinked" | "missing";
      model: string;
      view_type: string;
      view_id?: number | null;
      view_name?: string | null;
      snapshot_id?: string | null;
      kept_custom_fields: string[];
      remaining_custom_injects: string[];
      detail: string;
    }>(`/api/connections/${id}/views/designer-inherit/unlink`, {
      method: "POST",
      body: JSON.stringify({ view_type: "form", ...body }),
    }),
  polishForm: (
    id: string,
    model: string,
    string?: string | null,
    confirm?: { confirm_advanced?: boolean; confirm_phrase?: string | null },
  ) =>
    request<{
      model: string;
      view_id: number | null;
      applied: boolean;
      detail: Record<string, unknown>;
    }>(`/api/connections/${id}/views/polish-form`, {
      method: "POST",
      body: JSON.stringify({
        model,
        string: string ?? null,
        ...(confirm || {}),
      }),
    }),
};
