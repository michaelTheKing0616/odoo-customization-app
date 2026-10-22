import { request } from "./client";

export type StageEvent = {
  run_id: string;
  stage: string;
  detail: string;
};

export type StageEventsResponse = {
  run_id: string;
  events: StageEvent[];
  total: number;
};

export const progressApi = {
  stageEvents: (runId: string, after = 0) =>
    request<StageEventsResponse>(
      `/api/progress/runs/${encodeURIComponent(runId)}/events?after=${after}`,
    ),
  dashboardPreview: (body: { prompt: string; progress_run_id?: string }) =>
    request<{ run_id: string; status: string; message: string }>(
      "/api/dashboard-studio/preview",
      { method: "POST", body: JSON.stringify(body) },
    ),
};
