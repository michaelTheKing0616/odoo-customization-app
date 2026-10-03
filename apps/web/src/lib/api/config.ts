import { request, fetchApi } from "./client";
import type { CompanyRow, MenuRow, SequenceRow } from "./types-catalog";

export const configApi = {
  listCompanies: (id: string) =>
    request<CompanyRow[]>(`/api/connections/${id}/config/companies`),
  updateCompany: (
    id: string,
    companyId: number,
    body: Partial<{
      name: string;
      email: string;
      phone: string;
      website: string;
      street: string;
      street2: string;
      city: string;
      zip: string;
      vat: string;
      company_registry: string;
    }>,
  ) =>
    request<CompanyRow>(`/api/connections/${id}/config/companies/${companyId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  listSequences: (id: string, q?: string) =>
    request<SequenceRow[]>(
      `/api/connections/${id}/config/sequences${q ? `?q=${encodeURIComponent(q)}` : ""}`,
    ),
  updateSequence: (
    id: string,
    sequenceId: number,
    body: Partial<{
      name: string;
      prefix: string;
      suffix: string;
      padding: number;
      number_next: number;
      number_increment: number;
      active: boolean;
    }>,
  ) =>
    request<SequenceRow>(`/api/connections/${id}/config/sequences/${sequenceId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  exportFieldLabelsCsv: async (id: string, model: string) => {
    const res = await fetchApi(
      `/api/connections/${id}/config/field-labels.csv?model=${encodeURIComponent(model)}`,
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.text();
  },
  importFieldLabels: (
    id: string,
    body: {
      rows: Array<{ model: string; name: string; string: string }>;
      dry_run?: boolean;
    },
  ) =>
    request<{
      ok: boolean;
      updated: number;
      skipped: number;
      failed: number;
      message: string;
      errors: string[];
    }>(`/api/connections/${id}/config/field-labels`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listMenus: (id: string, rootsOnly = false) =>
    request<MenuRow[]>(
      `/api/connections/${id}/config/menus${rootsOnly ? "?roots_only=true" : ""}`,
    ),
  createAppMenu: (
    id: string,
    body: {
      root_name: string;
      model: string;
      child_label?: string | null;
      web_icon?: string;
    },
  ) =>
    request<{
      ok: boolean;
      root_menu_id: number;
      child_menu_id: number | null;
      action_id: number | null;
      message: string;
    }>(`/api/connections/${id}/config/menus/app`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createSequence: (
    id: string,
    body: {
      name: string;
      code?: string | null;
      prefix?: string | null;
      suffix?: string | null;
      padding?: number;
      number_next?: number;
      number_increment?: number;
    },
  ) =>
    request<SequenceRow>(`/api/connections/${id}/config/sequences`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listConfigMailTemplates: (id: string, model?: string) =>
    request<
      Array<{
        id: number;
        name: string;
        model: string | null;
        subject: string | null;
        body_html: string | null;
        email_to: string | null;
        description: string | null;
      }>
    >(
      `/api/connections/${id}/config/mail-templates${
        model ? `?model=${encodeURIComponent(model)}` : ""
      }`,
    ),
  createConfigMailTemplate: (
    id: string,
    body: {
      name: string;
      model: string;
      subject: string;
      body_html: string;
      email_to?: string;
      description?: string | null;
    },
  ) =>
    request<{
      id: number;
      name: string;
      model: string | null;
      subject: string | null;
      body_html: string | null;
      email_to: string | null;
      description: string | null;
    }>(`/api/connections/${id}/config/mail-templates`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateConfigMailTemplate: (
    id: string,
    templateId: number,
    body: Partial<{
      name: string;
      subject: string;
      body_html: string;
      email_to: string;
      description: string;
    }>,
  ) =>
    request<{ id: number; name: string }>(
      `/api/connections/${id}/config/mail-templates/${templateId}`,
      { method: "PATCH", body: JSON.stringify(body) },
    ),
  listConfigActivityTypes: (id: string) =>
    request<
      Array<{
        id: number;
        name: string;
        summary: string | null;
        icon: string | null;
        category: string | null;
        active: boolean;
      }>
    >(`/api/connections/${id}/config/activity-types`),
  createConfigActivityType: (
    id: string,
    body: { name: string; summary?: string; icon?: string; category?: string },
  ) =>
    request<{ id: number; name: string }>(
      `/api/connections/${id}/config/activity-types`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  listLanguages: (id: string) =>
    request<Array<{ id: number; code: string; name: string; active: boolean }>>(
      `/api/connections/${id}/config/languages`,
    ),
  exportTranslationsCsv: async (id: string, model: string, lang: string) => {
    const res = await fetchApi(
      `/api/connections/${id}/config/translations.csv?model=${encodeURIComponent(model)}&lang=${encodeURIComponent(lang)}`,
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.text();
  },
  importTranslations: (
    id: string,
    body: {
      rows: Array<{
        type: string;
        model: string;
        name: string;
        lang: string;
        value: string;
      }>;
      dry_run?: boolean;
    },
  ) =>
    request<{
      ok: boolean;
      updated: number;
      failed: number;
      skipped: number;
      message: string;
      errors: string[];
    }>(`/api/connections/${id}/config/translations`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  probeI18n: (id: string) =>
    request<{
      ok: boolean;
      major: number | null;
      method: string;
      context_lang_reads: boolean;
      ir_translation_model: boolean;
      message: string;
    }>(`/api/connections/${id}/config/i18n/probe`),
  exportSpecTranslationsCsv: async (
    id: string,
    spec: Record<string, unknown>,
    lang: string,
  ) => {
    const res = await fetchApi(`/api/connections/${id}/config/i18n/spec-export`, {
      method: "POST",
      body: JSON.stringify({ spec, lang }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.text();
  },
  importSpecTranslations: (
    id: string,
    body: { csv_text: string; dry_run?: boolean },
  ) =>
    request<{
      ok: boolean;
      dry_run: boolean;
      updated: number;
      skipped: number;
      preview: Array<{ model: string; name: string; lang: string; value: string }>;
    }>(`/api/connections/${id}/config/i18n/spec-import`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listConfigPaperformats: (id: string) =>
    request<
      Array<{
        id: number;
        name: string;
        format: string | null;
        orientation: string | null;
        margin_top: number | null;
        margin_bottom: number | null;
        margin_left: number | null;
        margin_right: number | null;
        header_line: boolean | null;
        dpi: number | null;
      }>
    >(`/api/connections/${id}/config/paperformats`),
  upsertConfigPaperformat: (
    id: string,
    body: {
      id?: number;
      name?: string;
      format?: string;
      orientation?: string;
      margin_top?: number;
      margin_bottom?: number;
      margin_left?: number;
      margin_right?: number;
      header_line?: boolean;
      dpi?: number;
    },
  ) =>
    request<{ id: number; name: string }>(`/api/connections/${id}/config/paperformats`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listIrDefaults: (id: string, model: string) =>
    request<
      Array<{
        id: number;
        field_id: number | null;
        field_name: string | null;
        model: string | null;
        json_value: string | null;
        user_id: number | null;
        company_id: number | null;
      }>
    >(`/api/connections/${id}/config/defaults?model=${encodeURIComponent(model)}`),
  upsertIrDefault: (
    id: string,
    body: {
      model?: string;
      model_id?: number;
      field_id?: number;
      field_name?: string;
      json_value?: string;
      value?: unknown;
      user_id?: number;
      company_id?: number;
    },
  ) =>
    request<{ id: number; json_value: string | null }>(
      `/api/connections/${id}/config/defaults`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  listIrProperties: (id: string, model?: string) => {
    const q = model ? `?model=${encodeURIComponent(model)}` : "";
    return request<
      Array<{
        id: number;
        name: string | null;
        fields_id: number | null;
        field_name: string | null;
        type: string | null;
        value_text: string | null;
      }>
    >(`/api/connections/${id}/config/properties${q}`);
  },
  listIrCrons: (id: string, opts?: { q?: string; active?: boolean }) => {
    const q = new URLSearchParams();
    if (opts?.q) q.set("q", opts.q);
    if (opts?.active != null) q.set("active", String(opts.active));
    const qs = q.toString();
    return request<
      Array<{
        id: number;
        name: string;
        model_id: number | null;
        model_name: string | null;
        interval_number: number | null;
        interval_type: string | null;
        active: boolean;
        nextcall: string | null;
      }>
    >(`/api/connections/${id}/config/crons${qs ? `?${qs}` : ""}`);
  },
  patchIrCronActive: (
    id: string,
    cronId: number,
    body: {
      active: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<{ id: number; name: string; active: boolean }>(
      `/api/connections/${id}/config/crons/${cronId}`,
      { method: "PATCH", body: JSON.stringify(body) },
    ),
};
