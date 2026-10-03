import { request } from "./client";
import type { ValidateLiveResult } from "./types-gating";

export const studioSpecApi = {
  validateModuleSpecLive: (connectionId: string, body: { spec: Record<string, unknown> }) =>
    request<ValidateLiveResult>(
      `/api/connections/${connectionId}/module-spec/validate-live`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  applyModuleSpec: (
    connectionId: string,
    body: {
      spec: Record<string, unknown>;
      apply_views?: boolean;
      apply_menus?: boolean;
      apply_smart_buttons?: boolean;
      apply_automations?: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
      skip_validate_live?: boolean;
    },
  ) =>
    request<{
      ok: boolean;
      models_created: string[];
      fields_created: number;
      views_created: number;
      views_updated: number;
      menus_created: number;
      smart_buttons: number;
      automations_created?: number;
      root_menu_id?: number | null;
      open_action_id?: number | null;
      skipped: string[];
      warnings: string[];
      message: string;
    }>(`/api/connections/${connectionId}/module-spec/apply`, {
      method: "POST",
      body: JSON.stringify(body),
      timeoutMs: 660_000,
    }),
  seedModuleSpecWalkthrough: (
    connectionId: string,
    body: {
      spec: Record<string, unknown>;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<{
      ok: boolean;
      created: Record<string, number>;
      open_model: string | null;
      open_record_id: number | null;
      warnings: string[];
      message: string;
    }>(`/api/connections/${connectionId}/module-spec/seed-walkthrough`, {
      method: "POST",
      body: JSON.stringify(body),
      timeoutMs: 120_000,
    }),
  lintModuleSpecBlocks: (connectionId: string, spec: Record<string, unknown>) =>
    request<{ ok: boolean; blocks: Array<{ source_file?: string; issues?: { message: string }[] }> }>(
      `/api/connections/${connectionId}/module-spec/lint-blocks`,
      { method: "POST", body: JSON.stringify({ spec }) },
    ),
  exportModuleSpecZip: (
    connectionId: string,
    body: { spec: Record<string, unknown>; odoo_major?: number | null },
  ) =>
    request<{
      ok: boolean;
      module?: string;
      zip_base64?: string;
      structural_zip?: { ok?: boolean; findings?: string[] };
      odoo_major?: number;
    }>(`/api/connections/${connectionId}/module-spec/export-zip`, {
      method: "POST",
      body: JSON.stringify(body),
      timeoutMs: 120_000,
    }),
  exportModuleSpecSandbox: (
    connectionId: string,
    body: { spec: Record<string, unknown>; async_job?: boolean; odoo_major?: number | null },
  ) =>
    request<{ ok: boolean; job_id?: string; validation_id?: string; message?: string }>(
      `/api/connections/${connectionId}/module-spec/export-sandbox`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  proveOptionA: (
    connectionId: string,
    body: {
      spec: Record<string, unknown>;
      odoo_major?: number | null;
      structural_only?: boolean;
    },
  ) =>
    request<{
      ok: boolean;
      draft?: Record<string, unknown>;
      smoke?: Record<string, unknown>;
      sandbox?: { ok?: boolean; message?: string; log_tail?: string };
      score_0_10?: number;
      go_live_ready?: boolean;
      grain_label?: string;
      done_bar?: Record<string, unknown>;
      structural_only?: boolean;
      message?: string;
      validation_id?: string;
      zip_base64?: string;
      promote_ready?: boolean;
      module?: string;
      feedback_repair?: {
        ok?: boolean;
        applied?: boolean;
        files?: string[];
        deterministic?: boolean;
        llm?: boolean;
        gate_status?: string;
        message?: string;
        reason?: string;
      };
    }>(`/api/connections/${connectionId}/module-spec/option-a-prove`, {
      method: "POST",
      body: JSON.stringify(body),
      timeoutMs: 660_000,
    }),
  repairOptionAFeedback: (
    connectionId: string,
    body: {
      spec: Record<string, unknown>;
      error_text?: string;
      operator_notes?: string;
      retry_sandbox?: boolean;
      odoo_major?: number | null;
    },
  ) =>
    request<{
      ok: boolean;
      draft?: Record<string, unknown>;
      message?: string;
      feedback_repair?: {
        ok?: boolean;
        applied?: boolean;
        files?: string[];
        deterministic?: boolean;
        llm?: boolean;
        gate_status?: string;
        message?: string;
        reason?: string;
      };
      sandbox?: { ok?: boolean; message?: string; log_tail?: string };
      smoke?: Record<string, unknown>;
      validation_id?: string;
      zip_base64?: string;
      promote_ready?: boolean;
    }>(`/api/connections/${connectionId}/module-spec/option-a-repair-feedback`, {
      method: "POST",
      body: JSON.stringify(body),
      timeoutMs: 660_000,
    }),
  goldInspect: (connectionId: string, goldId: string) =>
    request<{
      gold_id: string;
      host_ready: boolean;
      missing_depends: string[];
      install_module?: string | null;
      install_label?: string | null;
      action_id?: number | null;
      href?: string | null;
      label?: string;
      message?: string;
    }>(
      `/api/connections/${connectionId}/module-spec/gold-inspect?gold_id=${encodeURIComponent(goldId)}`,
    ),
  eliteModuleGate: (connectionId: string, spec: Record<string, unknown>) =>
    request<{
      gate_passed: boolean;
      gate_reasons: string[];
      score_0_10?: number;
      dimensions?: Record<string, number>;
    }>(`/api/connections/${connectionId}/module-spec/elite-gate`, {
      method: "POST",
      body: JSON.stringify({ spec }),
    }),
  eliteModuleAutopilot: (
    connectionId: string,
    body: { spec: Record<string, unknown>; odoo_major?: number | null; skip_gate?: boolean },
  ) =>
    request<{
      ok: boolean;
      gate_passed?: boolean;
      gate_reasons?: string[];
      validation_id?: string;
      zip_base64?: string;
      score_0_10?: number;
      message?: string;
    }>(`/api/connections/${connectionId}/module-spec/elite-autopilot`, {
      method: "POST",
      body: JSON.stringify(body),
      timeoutMs: 660_000,
    }),
};
