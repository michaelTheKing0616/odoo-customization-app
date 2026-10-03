import { request, fetchApi, requestForm } from "./client";
import type { JobRow, ProjectDiffOut, ReminderCreateBody, ReminderCreateOut, ScaffoldResult, SuggestDependsOut } from "./types-catalog";
import type { ConfigPacketApplyReport, ConfigPacketDiff, InstanceFingerprint, JobAutopilotContract, JobAutopilotPacketOut, JobAutopilotPromoteToResult, JobAutopilotQueued, JobAutopilotResult } from "./types-job";

export const jobAutopilotApi = {
  jobAutopilotContract: (connectionId: string) =>
    request<JobAutopilotContract>(`/api/connections/${connectionId}/job-autopilot/contract`),
  jobAutopilotPacket: (
    connectionId: string,
    body: {
      prompt: string;
      file_excerpts?: Array<{ filename: string; text: string }>;
      country_code?: string | null;
      company_name?: string | null;
      use_llm?: boolean | null;
    },
  ) =>
    request<JobAutopilotPacketOut>(`/api/connections/${connectionId}/job-autopilot/packet`, {
      method: "POST",
      body: JSON.stringify(body),
      timeoutMs: 120_000,
    }),
  jobAutopilotRun: (
    connectionId: string,
    body: {
      prompt: string;
      packet?: Record<string, unknown> | null;
      spec?: Record<string, unknown> | null;
      use_llm?: boolean | null;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<JobAutopilotResult | JobAutopilotQueued>(
      `/api/connections/${connectionId}/job-autopilot/run`,
      {
        method: "POST",
        body: JSON.stringify(body),
        timeoutMs: 120_000,
      },
    ),
  jobAutopilotRunFiles: async (
    connectionId: string,
    body: {
      prompt: string;
      files: File[];
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
      use_llm?: boolean | null;
    },
  ) => {
    const fd = new FormData();
    fd.append("prompt", body.prompt);
    fd.append("confirm_advanced", body.confirm_advanced ? "true" : "false");
    if (body.confirm_phrase) fd.append("confirm_phrase", body.confirm_phrase);
    if (body.use_llm != null) fd.append("use_llm", body.use_llm ? "true" : "false");
    for (const f of body.files) fd.append("files", f);
    return requestForm<JobAutopilotResult | JobAutopilotQueued>(
      `/api/connections/${connectionId}/job-autopilot/run-files`,
      fd,
      120_000,
    );
  },
    jobAutopilotPromoteTo: (
    connectionId: string,
    body: {
      target_connection_id: string;
      zip_base64?: string | null;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<JobAutopilotPromoteToResult>(
      `/api/connections/${connectionId}/job-autopilot/promote-to`,
      {
        method: "POST",
        body: JSON.stringify(body),
        timeoutMs: 660_000,
      },
    ),
  jobAutopilotFingerprint: (connectionId: string) =>
    request<{
      fingerprint: InstanceFingerprint;
      connection_kind: string;
      sandbox: boolean;
      message: string;
    }>(`/api/connections/${connectionId}/job-autopilot/fingerprint`),
  jobAutopilotCaptureSettings: (connectionId: string) =>
    request<{ settings: Record<string, unknown>; keys: string[]; message: string }>(
      `/api/connections/${connectionId}/job-autopilot/capture-settings`,
      { method: "POST" },
    ),
  jobAutopilotConfigDryRun: (connectionId: string, packet: Record<string, unknown>) =>
    request<{
      diff: ConfigPacketDiff;
      fingerprint: InstanceFingerprint;
      connection_kind: string;
      sandbox: boolean;
      warning: string;
      risks: string[];
      message: string;
    }>(`/api/connections/${connectionId}/job-autopilot/config-packet/dry-run`, {
      method: "POST",
      body: JSON.stringify({ packet }),
      timeoutMs: 120_000,
    }),
  jobAutopilotConfigApply: (
    connectionId: string,
    body: {
      packet: Record<string, unknown>;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<ConfigPacketApplyReport>(
      `/api/connections/${connectionId}/job-autopilot/config-packet/apply`,
      {
        method: "POST",
        body: JSON.stringify(body),
        timeoutMs: 180_000,
      },
    ),
  jobAutopilotReportPdf: async (connectionId: string, result: JobAutopilotResult) => {
    const res = await fetchApi(`/api/connections/${connectionId}/job-autopilot/report.pdf`, {
      method: "POST",
      body: JSON.stringify(result),
      timeoutMs: 120_000,
    });
    if (!res.ok) {
      throw new Error(`UAT PDF failed (${res.status})`);
    }
    return res.blob();
  },
  getScriptRunnerTemplates: (connectionId: string) =>
    request<{ templates: Array<{ id: string; label: string; description: string; code: string }> }>(
      `/api/connections/${connectionId}/script-runner/templates`,
    ),
  listScriptRuns: (connectionId: string) =>
    request<
      Array<{
        id: string;
        status: string;
        script_content: string;
        stdout: string | null;
        stderr: string | null;
        write_counts: Record<string, unknown>;
        error: string | null;
        created_at: string | null;
      }>
    >(`/api/connections/${connectionId}/script-runner/runs`),
  runScript: (
    connectionId: string,
    body: {
      script: string;
      async_job?: boolean;
      count_writes?: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<{ ok: boolean; async?: boolean; job_id?: string; run_id?: string }>(
      `/api/connections/${connectionId}/script-runner/run`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  listSavedScripts: (connectionId: string) =>
    request<
      Array<{ id: string; name: string; description: string | null; script_content: string; shared: boolean }>
    >(`/api/connections/${connectionId}/script-runner/library`),
  saveScript: (
    connectionId: string,
    body: { name: string; description?: string | null; script_content: string; shared?: boolean },
  ) =>
    request<{ id: string; name: string }>(`/api/connections/${connectionId}/script-runner/library`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  aiStatus: () =>
    request<{
      ai_assist: string;
      enabled: boolean;
      provider?: string;
      provider_label?: string;
      ollama_base_url: string;
      ollama_model: string;
      ollama_reachable?: boolean;
      ollama_detail?: string;
      provider_reachable?: boolean;
      provider_detail?: string;
      domain_packs?: string;
    }>("/api/ai/status"),
  scaffoldApp: (
    connectionId: string,
    body: {
      template_id: string;
      display_name?: string;
      technical_prefix?: string | null;
      multi_company?: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<ScaffoldResult>(`/api/connections/${connectionId}/apps/scaffold`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  cancelJob: (jobId: string) =>
    request<JobRow>(`/api/jobs/${jobId}/cancel`, { method: "POST" }),
  suggestDepends: (connectionId: string) =>
    request<SuggestDependsOut>(
      `/api/connections/${connectionId}/suggest-depends`,
    ),
  projectDiff: (connectionId: string, projectId: string) =>
    request<ProjectDiffOut>(
      `/api/connections/${connectionId}/projects/${projectId}/diff`,
    ),
  createReminder: (connectionId: string, body: ReminderCreateBody) =>
    request<ReminderCreateOut>(`/api/connections/${connectionId}/reminders`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  libraryStats: (connectionId: string) =>
    request<{
      available: boolean;
      book_model: string | null;
      loan_model: string | null;
      books: number | null;
      loans: number | null;
      active_loans: number | null;
      overdue_loans: number | null;
      message: string;
    }>(`/api/connections/${connectionId}/library/stats`),
};
