import { request } from "./client";
import type { AccessRightRow, GroupRow, ModuleExport, PromoteResult, PromotedModuleRow, RecordRuleRow, SandboxRunResult, UninstallResult } from "./types-catalog";
import type { MigrationAssist, StoreReadinessReport } from "./types-gating";
import type { ViewRow } from "./types-schema";

export const modulesSecurityApi = {
  getView: (id: string, viewId: number) =>
    request<ViewRow>(`/api/connections/${id}/views/${viewId}`),
  exportModule: (
    id: string,
    body: {
      technical_name: string;
      display_name: string;
      include_custom_models?: boolean;
      include_extensions?: boolean;
      include_views?: boolean;
      include_reports?: boolean;
      install_mode?: string;
      model_filter?: string[] | null;
      extend_models?: string[] | null;
      depends?: string[] | null;
      store_ready?: boolean;
    },
    query?: { store_ready?: boolean },
  ) =>
    request<
      ModuleExport & {
        model_count: number;
        view_count: number;
        report_count?: number;
        target_major?: number | null;
        manifest_version?: string | null;
        warnings?: string[];
        store_readiness?: StoreReadinessReport | null;
      }
    >(
      `/api/connections/${id}/export-module${query?.store_ready ? "?store_ready=true" : body.store_ready ? "?store_ready=true" : ""}`,
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),
  getMigrationAssist: (id: string) =>
    request<MigrationAssist>(`/api/connections/${id}/migration-assist`),
  runSandbox: (
    id: string,
    body: {
      technical_name?: string;
      display_name?: string;
      include_custom_models?: boolean;
      include_extensions?: boolean;
      include_views?: boolean;
      model_filter?: string[] | null;
      extend_models?: string[] | null;
      depends?: string[] | null;
      extra_modules?: string[] | null;
      zip_base64?: string | null;
      keep_alive?: boolean;
      async_job?: boolean;
    },
  ) =>
    request<SandboxRunResult>(`/api/connections/${id}/sandbox/run`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  promoteModule: (
    id: string,
    body: {
      technical_name?: string;
      display_name?: string;
      include_custom_models?: boolean;
      include_views?: boolean;
      model_filter?: string[] | null;
      install_mode?: string;
      zip_base64?: string | null;
      validation_id?: string | null;
      run_sandbox?: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<PromoteResult>(`/api/connections/${id}/modules/promote`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listPromotedModules: (id: string) =>
    request<PromotedModuleRow[]>(`/api/connections/${id}/modules/promoted`),
  uninstallModule: (
    id: string,
    body: {
      module_name: string;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<UninstallResult>(`/api/connections/${id}/modules/uninstall`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listGroups: (id: string) =>
    request<GroupRow[]>(`/api/connections/${id}/access/groups`),
  listAccessRights: (id: string, model?: string) =>
    request<AccessRightRow[]>(
      `/api/connections/${id}/access/rights${model ? `?model=${encodeURIComponent(model)}` : ""}`,
    ),
  createAccessRight: (
    id: string,
    body: {
      model: string;
      name: string;
      group_id?: number | null;
      perm_read?: boolean;
      perm_write?: boolean;
      perm_create?: boolean;
      perm_unlink?: boolean;
      active?: boolean;
    },
  ) =>
    request<AccessRightRow>(`/api/connections/${id}/access/rights`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateAccessRight: (
    id: string,
    accessId: number,
    body: {
      name?: string;
      group_id?: number | null;
      clear_group?: boolean;
      perm_read?: boolean;
      perm_write?: boolean;
      perm_create?: boolean;
      perm_unlink?: boolean;
      active?: boolean;
    },
  ) =>
    request<AccessRightRow>(`/api/connections/${id}/access/rights/${accessId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteAccessRight: (
    id: string,
    accessId: number,
    body: { confirm_advanced?: boolean; confirm_phrase?: string | null },
  ) =>
    request<{ ok: boolean; access_id: number; snapshot_id: string | null }>(
      `/api/connections/${id}/access/rights/${accessId}`,
      { method: "DELETE", body: JSON.stringify(body) },
    ),
  listRecordRules: (id: string, model?: string) =>
    request<RecordRuleRow[]>(
      `/api/connections/${id}/access/rules${model ? `?model=${encodeURIComponent(model)}` : ""}`,
    ),
  createRecordRule: (
    id: string,
    body: {
      model: string;
      name: string;
      domain_force: string;
      group_ids?: number[];
      perm_read?: boolean;
      perm_write?: boolean;
      perm_create?: boolean;
      perm_unlink?: boolean;
      active?: boolean;
    },
  ) =>
    request<RecordRuleRow>(`/api/connections/${id}/access/rules`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateRecordRule: (
    id: string,
    ruleId: number,
    body: {
      name?: string;
      domain_force?: string;
      group_ids?: number[];
      perm_read?: boolean;
      perm_write?: boolean;
      perm_create?: boolean;
      perm_unlink?: boolean;
      active?: boolean;
    },
  ) =>
    request<RecordRuleRow>(`/api/connections/${id}/access/rules/${ruleId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteRecordRule: (
    id: string,
    ruleId: number,
    body: { confirm_advanced?: boolean; confirm_phrase?: string | null },
  ) =>
    request<{ ok: boolean; rule_id: number; snapshot_id: string | null }>(
      `/api/connections/${id}/access/rules/${ruleId}`,
      { method: "DELETE", body: JSON.stringify(body) },
    ),
  getMultiCompanyGuidance: (id: string) =>
    request<{ title: string; body: string }>(
      `/api/connections/${id}/access/multi-company/guidance`,
    ),
  applyMultiCompanyDraft: (id: string, draft: Record<string, unknown>) =>
    request<{ ok: boolean; draft: Record<string, unknown> }>(
      `/api/connections/${id}/access/multi-company/apply-draft`,
      { method: "POST", body: JSON.stringify({ draft }) },
    ),
  applyMultiCompanyLive: (
    id: string,
    models: string[],
    confirm?: { confirm_advanced?: boolean; confirm_phrase?: string | null },
  ) =>
    request<{
      ok: boolean;
      models: string[];
      fields_created: number;
      rules_created: number;
      warnings: string[];
    }>(`/api/connections/${id}/access/multi-company/apply-live`, {
      method: "POST",
      body: JSON.stringify({
        models,
        confirm_advanced: confirm?.confirm_advanced ?? false,
        confirm_phrase: confirm?.confirm_phrase ?? null,
      }),
    }),
};
