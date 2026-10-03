import { request } from "./client";
import type { ExpertAskResponse, ExpertDraftReviewResponse, ExpertNLSearchHit, ExpertSuggestedPrompt } from "./types-gating";

export type LiveDemoCopilotDisclosure = {
  version: string;
  title: string;
  summary: string;
  bullets: string[];
  opt_out: string;
  retention_default: string;
};

export type LiveDemoBotStatus = {
  raw: string;
  phase: string;
  label: string;
  hint: string;
  severity: "info" | "warning" | "danger" | "success" | "neutral" | string;
  needs_host_action: boolean;
  is_terminal: boolean;
};

export type LiveDemoCopilotSession = {
  id: string;
  workspace_id: string | null;
  connection_id: string | null;
  meeting_url: string;
  meeting_url_hash: string;
  bot_name: string;
  disclosure_accepted: boolean;
  disclosure_version: string;
  attendees_notified: boolean;
  retention_opt_in: boolean;
  declined: boolean;
  attendee_bot_id: string | null;
  bot_state: string;
  bot_status: LiveDemoBotStatus;
  mock_mode: boolean;
  attendee_configured: boolean;
  disclosure_required_version: string;
  transcript_count: number;
  leave_purge_status: string;
  last_ops_error: string | null;
  leave_purge_job_id: string | null;
  presenter_speakers: string[];
};

export type LiveDemoTranscriptLine = {
  speaker_name: string;
  speaker_uuid: string | null;
  text: string;
  timestamp_ms: number | null;
};

export type LiveDemoAnswer = {
  id: string;
  session_id: string;
  question: string;
  speaker_name: string | null;
  bullets: string[];
  confidence: string;
  confidence_flag: string | null;
  grounded: boolean;
  declined: boolean;
  citations: Array<Record<string, unknown>>;
  status: string;
  stage1_reason: string;
  stage1_score: string;
  model_used: string | null;
  created_at: string | null;
};

export const expertApi = {
  liveDemoCopilotDisclosure: () =>
    request<LiveDemoCopilotDisclosure>("/api/live-demo-copilot/disclosure"),
  liveDemoCopilotCreateSession: (body: {
    meeting_url: string;
    bot_name?: string;
    connection_id?: string;
    presenter_speakers?: string[];
  }) =>
    request<LiveDemoCopilotSession>("/api/live-demo-copilot/sessions", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  liveDemoCopilotGetSession: (sessionId: string) =>
    request<LiveDemoCopilotSession>(`/api/live-demo-copilot/sessions/${sessionId}`),
  liveDemoCopilotConsent: (
    sessionId: string,
    body: {
      disclosure_accepted: boolean;
      attendees_notified: boolean;
      retention_opt_in?: boolean;
      disclosure_version?: string;
    },
  ) =>
    request<LiveDemoCopilotSession>(`/api/live-demo-copilot/sessions/${sessionId}/consent`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  liveDemoCopilotLaunch: (sessionId: string) =>
    request<LiveDemoCopilotSession>(`/api/live-demo-copilot/sessions/${sessionId}/launch`, {
      method: "POST",
      body: "{}",
    }),
  liveDemoCopilotLeave: (sessionId: string) =>
    request<LiveDemoCopilotSession>(`/api/live-demo-copilot/sessions/${sessionId}/leave`, {
      method: "POST",
      body: "{}",
    }),
  liveDemoCopilotRefreshStatus: (sessionId: string) =>
    request<LiveDemoCopilotSession>(
      `/api/live-demo-copilot/sessions/${sessionId}/refresh-status`,
      { method: "POST", body: "{}" },
    ),
  liveDemoCopilotRetryLeavePurge: (sessionId: string) =>
    request<LiveDemoCopilotSession>(
      `/api/live-demo-copilot/sessions/${sessionId}/retry-leave-purge`,
      { method: "POST", body: "{}" },
    ),
  liveDemoCopilotTranscript: (sessionId: string) =>
    request<{ session_id: string; lines: LiveDemoTranscriptLine[] }>(
      `/api/live-demo-copilot/sessions/${sessionId}/transcript`,
    ),
  liveDemoCopilotAnswers: (sessionId: string) =>
    request<{ session_id: string; answers: LiveDemoAnswer[] }>(
      `/api/live-demo-copilot/sessions/${sessionId}/answers`,
    ),
  liveDemoCopilotSetPresenterSpeakers: (sessionId: string, presenter_speakers: string[]) =>
    request<LiveDemoCopilotSession>(
      `/api/live-demo-copilot/sessions/${sessionId}/presenter-speakers`,
      { method: "PATCH", body: JSON.stringify({ presenter_speakers }) },
    ),
  liveDemoCopilotMockUtterance: (
    sessionId: string,
    body: { speaker_name?: string; text: string; timestamp_ms?: number },
  ) =>
    request<LiveDemoCopilotSession>(
      `/api/live-demo-copilot/sessions/${sessionId}/mock-utterance`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  expertAsk: (body: {
    question: string;
    connection_id?: string;
    ui_context?: Record<string, unknown>;
    conversation?: Array<{ role: string; content: string }>;
  }) =>
    request<ExpertAskResponse>("/api/expert/ask", {
      method: "POST",
      body: JSON.stringify(body),
      timeoutMs: 660_000,
    }),
  expertReviewDraft: (body: {
    draft: Record<string, unknown>;
    user_prompt?: string;
    connection_id?: string;
    apply_fixes?: boolean;
  }) =>
    request<ExpertDraftReviewResponse>("/api/expert/review-draft", {
      method: "POST",
      body: JSON.stringify(body),
      timeoutMs: 660_000,
    }),
  expertExplainModel: (body: {
    model: string;
    field?: string;
    draft?: Record<string, unknown>;
    user_prompt?: string;
    connection_id?: string;
  }) =>
    request<ExpertAskResponse>("/api/expert/explain-model", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  expertPostToChatter: (body: {
    connection_id: string;
    model: string;
    res_id: number;
    body_markdown: string;
    subject?: string;
    confirmed: boolean;
  }) =>
    request<{ ok: boolean; posted: boolean; message: string }>("/api/expert/post-to-chatter", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  expertSuggestedPrompts: (params: {
    route?: string;
    model?: string;
    view_type?: string;
    draft_summary?: string;
  }) => {
    const q = new URLSearchParams();
    if (params.route) q.set("route", params.route);
    if (params.model) q.set("model", params.model);
    if (params.view_type) q.set("view_type", params.view_type);
    if (params.draft_summary) q.set("draft_summary", params.draft_summary);
    const qs = q.toString();
    return request<ExpertSuggestedPrompt[]>(
      `/api/expert/suggested-prompts${qs ? `?${qs}` : ""}`,
    );
  },
  expertNLSearch: (body: { query: string; connection_id: string }) =>
    request<{ query: string; hits: ExpertNLSearchHit[] }>("/api/expert/nl-search", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
