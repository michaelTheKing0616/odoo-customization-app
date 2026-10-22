import { request, requestForm } from "./client";
import type { StudioClarification } from "@/lib/studio-session";
import type { PreviewFormView } from "@/lib/draft-form-preview";

export type WireframeStatus = {
  provider: string;
  connected: boolean;
  message: string;
  default_provider: string;
};

export type WireframeOutcome = {
  status: "not_connected" | "error" | "clarify" | "review";
  connected: boolean;
  provider?: string;
  message?: string;
  clarification: StudioClarification | null;
  spec: Record<string, unknown> | null;
  form_preview?: PreviewFormView | null;
  apply_ready: boolean;
  sketch: Record<string, unknown> | null;
};

export type WireframeMapRow = {
  region: string;
  /** Where the box sits on the sketch: [x, y, w, h] fractions; null when the reader could not tell. */
  box?: [number, number, number, number] | null;
  label: string;
  hint: string;
  action: "reuse" | "new";
  field: string | null;
  field_label?: string;
  type?: string;
  unclear?: boolean;
};
export type WireframeMap = {
  target: { action: "extend" | "new"; model: string; name: string; score: number; maybe?: { model: string; name: string } };
  rows: WireframeMapRow[];
  questions: Array<{ id: string; text: string; options: Array<{ id: string; label: string }> }>;
  summary: string;
  install: { mode: "data" | "module"; why: string };
  hosting: string;
  guards: { redacted: Record<string, number>; flagged_regions: string[] };
};

export const wireframeApi = {
  wireframeMap: (connectionId: string, sketch: Record<string, unknown>) =>
    request<WireframeMap>(`/api/connections/${connectionId}/wireframe/map`, {
      method: "POST",
      body: JSON.stringify({ sketch }),
    }),
  wireframeStatus: (connectionId: string) =>
    request<WireframeStatus>(`/api/connections/${connectionId}/wireframe/status`),
  wireframeRead: async (connectionId: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return requestForm<WireframeOutcome>(
      `/api/connections/${connectionId}/wireframe/read`,
      fd,
    );
  },
  wireframeClarify: (
    connectionId: string,
    body: {
      sketch: Record<string, unknown>;
      merge_key: string;
      answer_id: string;
      answer_text?: string;
    },
  ) =>
    request<WireframeOutcome>(`/api/connections/${connectionId}/wireframe/clarify`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
