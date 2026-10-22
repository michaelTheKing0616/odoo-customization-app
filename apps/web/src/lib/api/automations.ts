import { request } from "./client";
import type { AutomationActionKind } from "./types-actions";
import type { ActivityTypeRow, AutomationRow, CodeStudioBindResult, CodeStudioGateResponse, CodeStudioOptionAResult, CodeStudioTestRunResult, CodeStudioValidateResult, ModuleExport, SnapshotRow } from "./types-catalog";
import type { AutomationsGateResponse } from "./types-gating";
import type { ApprovalButton, ApprovalEntry, ApprovalRule, ApprovalStep, ApprovalsGateResponse, AutomationTriggersResponse, HealthCheckRun, HealthCheckTrigger, ProcessGateResponse, ProcessRequestRow, ProcessTypeRow } from "./types-schema";

export const automationsApi = {
  listAutomations: (id: string, model?: string) =>
    request<AutomationRow[]>(
      `/api/connections/${id}/automations${model ? `?model=${encodeURIComponent(model)}` : ""}`,
    ),
  listActivityTypes: (id: string) =>
    request<ActivityTypeRow[]>(`/api/connections/${id}/automations/activity-types`),
  getAutomationsGate: (id: string) =>
    request<AutomationsGateResponse>(`/api/connections/${id}/automations/gate`),
  getCodeStudioGate: (id: string) =>
    request<CodeStudioGateResponse>(`/api/connections/${id}/code-studio/gate`),
  probeCodeStudio: (id: string) =>
    request<Record<string, unknown>>(`/api/connections/${id}/code-studio/probe`, {
      method: "POST",
    }),
  getCodeStudioContext: (id: string) =>
    request<{ major: number | null; symbols: { name: string; description: string }[] }>(
      `/api/connections/${id}/code-studio/context`,
    ),
  getCodeStudioSnippets: (id: string) =>
    request<{ snippets: { id: string; label: string; code: string }[] }>(
      `/api/connections/${id}/code-studio/snippets`,
    ),
  validateCodeStudio: (id: string, code: string) =>
    request<CodeStudioValidateResult>(`/api/connections/${id}/code-studio/validate`, {
      method: "POST",
      body: JSON.stringify({ code }),
    }),
  testRunCodeStudio: (
    id: string,
    body: { model: string; record_id?: number | null; code: string },
  ) =>
    request<CodeStudioTestRunResult>(`/api/connections/${id}/code-studio/test-run`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  exportCodeStudioOptionA: (
    id: string,
    body: {
      name: string; model: string; code: string; technical_name?: string | null;
      /** Modules the built-in model comes from, so the extension installs after them. */
      depends?: string[] | null;
      /** Package as an imported models/ file (an _inherit extension of a built-in model). */
      as_extension?: boolean;
    },
  ) =>
    request<CodeStudioOptionAResult>(`/api/connections/${id}/code-studio/option-a`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getExtensionScaffold: (
    id: string,
    body: {
      model: string;
      kind: "selection_options" | "computed_field" | "behaviour";
      field_name?: string | null;
      label?: string | null;
      options?: { value: string; label: string }[] | null;
    },
  ) =>
    request<{ code: string; depends: string[]; technical_name: string }>(
      `/api/connections/${id}/code-studio/extension-scaffold`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  bindCodeStudio: (
    id: string,
    body: {
      name: string;
      model: string;
      code: string;
      bind_kind: "standalone" | "model_button" | "automation";
      bind_to_model?: boolean;
      trigger?: string | null;
      filter_domain?: string | null;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<CodeStudioBindResult>(`/api/connections/${id}/code-studio/bind`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getAutomationTriggers: (id: string) =>
    request<AutomationTriggersResponse>(`/api/connections/${id}/automations/triggers`),
  getApprovalsGate: (id: string) =>
    request<ApprovalsGateResponse>(`/api/connections/${id}/approvals/gate`),
  listApprovalRules: (id: string) =>
    request<ApprovalRule[]>(`/api/connections/${id}/approvals/rules`),
  listApprovalButtons: (id: string, model: string) =>
    request<ApprovalButton[]>(
      `/api/connections/${id}/approvals/buttons?model=${encodeURIComponent(model)}`,
    ),
  createApprovalRule: (
    id: string,
    body: {
      name: string;
      target_model: string;
      button_method: string;
      button_label?: string | null;
      steps: ApprovalStep[];
      engine?: string | null;
    },
  ) =>
    request<ApprovalRule>(`/api/connections/${id}/approvals/rules`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  checkApprovalAction: (id: string, ruleId: string, recordId: number, actorUserId?: number) =>
    request<{ allowed: boolean; message: string; pending_step?: number | null; entry_id?: string }>(
      `/api/connections/${id}/approvals/rules/${ruleId}/check`,
      {
        method: "POST",
        body: JSON.stringify({ record_id: recordId, actor_user_id: actorUserId }),
      },
    ),
  approveApprovalEntry: (
    id: string,
    entryId: string,
    body: { actor_user_id: number; approve?: boolean },
  ) =>
    request<ApprovalEntry>(`/api/connections/${id}/approvals/entries/${entryId}/approve`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listApprovalEntries: (id: string, ruleId?: string) =>
    request<ApprovalEntry[]>(
      `/api/connections/${id}/approvals/entries${ruleId ? `?rule_id=${encodeURIComponent(ruleId)}` : ""}`,
    ),
  getProcessGate: (id: string) =>
    request<ProcessGateResponse>(`/api/connections/${id}/approvals/processes/gate`),
  listProcessTypes: (id: string) =>
    request<ProcessTypeRow[]>(`/api/connections/${id}/approvals/processes/types`),
  listProcessRequests: (id: string) =>
    request<ProcessRequestRow[]>(`/api/connections/${id}/approvals/processes/requests`),
  createProcessRequest: (
    id: string,
    body: { type_id: number; subject: string; amount?: number; requester_id?: number },
  ) =>
    request<{ id: number; state: string }>(`/api/connections/${id}/approvals/processes/requests`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  submitProcessRequest: (id: string, requestId: number) =>
    request<{ id: number; state: string }>(
      `/api/connections/${id}/approvals/processes/requests/${requestId}/submit`,
      { method: "POST", body: JSON.stringify({}) },
    ),
  approveProcessRequest: (id: string, requestId: number, actorUserId: number) =>
    request<{ id: number; state: string }>(
      `/api/connections/${id}/approvals/processes/requests/${requestId}/approve`,
      {
        method: "POST",
        body: JSON.stringify({ actor_user_id: actorUserId }),
      },
    ),
  refuseProcessRequest: (id: string, requestId: number, actorUserId: number, reason?: string) =>
    request<{ id: number; state: string }>(
      `/api/connections/${id}/approvals/processes/requests/${requestId}/refuse`,
      {
        method: "POST",
        body: JSON.stringify({ actor_user_id: actorUserId, reason: reason ?? "" }),
      },
    ),
  scaffoldApprovalProcesses: (
    id: string,
    body: { confirm_advanced?: boolean; confirm_phrase?: string | null; display_name?: string },
  ) =>
    request<{ ok: boolean; message: string; warnings: string[] }>(
      `/api/connections/${id}/approvals/processes/scaffold`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  createAutomation: (
    id: string,
    body: {
      name: string;
      model: string;
      trigger: string;
      filter_domain?: string | null;
      filter_pre_domain?: string | null;
      trigger_field_names?: string[];
      trg_date_field_name?: string | null;
      trg_date_range?: number | null;
      trg_date_range_type?: "minutes" | "hour" | "day" | "month" | null;
      trg_date_range_mode?: "after" | "before" | null;
      active?: boolean;
      action_kind: AutomationActionKind;
      field_name?: string;
      value?: string;
      relation_field?: string;
      activity_type_id?: number;
      activity_summary?: string;
      activity_note?: string;
      activity_user_type?: "specific" | "generic";
      activity_user_id?: number;
      activity_user_field_name?: string;
      target_model?: string;
      field_values?: Record<string, string>;
      mail_template_id?: number | null;
      mail_post_method?: "email" | "comment" | "note";
      mail_subject?: string | null;
      mail_body_html?: string | null;
      mail_email_to?: string | null;
      webhook_url?: string | null;
      webhook_field_names?: string[];
      sms_template_id?: number | null;
      sms_body?: string | null;
      sms_method?: "sms" | "comment" | "note";
      partner_ids?: number[];
      followers_type?: "specific" | "generic";
      followers_partner_field_name?: string | null;
      python_code?: string;
      module_technical_name?: string;
      confirm_advanced?: boolean;
      confirm_phrase?: string;
    },
  ) =>
    request<AutomationRow | ModuleExport>(`/api/connections/${id}/automations`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  setAutomationActive: (id: string, automationId: number, active: boolean) =>
    request<AutomationRow>(`/api/connections/${id}/automations/${automationId}`, {
      method: "PATCH",
      body: JSON.stringify({ active }),
    }),
  updateAutomation: (
    id: string,
    automationId: number,
    body: {
      active?: boolean;
      name?: string;
      filter_domain?: string | null;
      model?: string;
    },
  ) =>
    request<AutomationRow>(`/api/connections/${id}/automations/${automationId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteAutomation: (
    id: string,
    automationId: number,
    body: { confirm_advanced?: boolean; confirm_phrase?: string | null },
  ) =>
    request<{ ok: boolean; automation_id: number; snapshot_id: string | null }>(
      `/api/connections/${id}/automations/${automationId}`,
      { method: "DELETE", body: JSON.stringify(body) },
    ),
  /** A4: one History — snapshots and real bulk runs, newest first, with filters. */
  history: (id: string, params: { page?: string; record_type?: string; q?: string } = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v) as [string, string][]).toString();
    return request<{ entries: HistoryEntry[]; pages: string[] }>(`/api/connections/${id}/history${qs ? `?${qs}` : ""}`);
  },
  listSnapshots: (id: string) =>
    request<SnapshotRow[]>(`/api/connections/${id}/snapshots`),
  getLatestHealthCheck: (id: string) =>
    request<HealthCheckRun | null>(`/api/connections/${id}/health-check/latest`),
  listHealthCheckRuns: (id: string, limit = 20) =>
    request<HealthCheckRun[]>(
      `/api/connections/${id}/health-check/runs?limit=${encodeURIComponent(String(limit))}`,
    ),
  runHealthCheck: (id: string, asyncJob = true) =>
    request<HealthCheckTrigger>(
      `/api/connections/${id}/health-check/run?async_job=${asyncJob ? "true" : "false"}`,
      { method: "POST" },
    ),
  rollbackSnapshot: (id: string, snapshotId: string) =>
    request<{ ok: boolean; restored: string; id: number }>(
      `/api/connections/${id}/snapshots/${snapshotId}/rollback`,
      { method: "POST" },
    ),
};

export type HistoryEntry = {
  id: string;
  kind: "snapshot" | "bulk_run";
  page: string;
  resource_type: string;
  record_type: string | null;
  label: string;
  at: string | null;
  undo: { snapshot_id: string; partial: boolean } | null;
  receipt: Record<string, unknown>;
};
