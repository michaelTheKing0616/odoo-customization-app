import { request } from "./client";
import type { StudioAppDesign } from "@/lib/studio-session";

export type AgentRedesignAssumption = { id?: string; text?: string; chosen?: string };

/** Agent mode: send playback answers / assumption edits; the server re-designs in the same
 * agent conversation, stores the new design on the session, and returns it. */
export const studioAgentApi = {
  agentRedesign: (sessionId: string, answers: Record<string, string>, assumptions: AgentRedesignAssumption[]) =>
    request<{ design: StudioAppDesign; outcome: Record<string, unknown> }>(
      `/api/ai/sessions/${encodeURIComponent(sessionId)}/agent-redesign`,
      { method: "POST", body: JSON.stringify({ answers, assumptions }), timeoutMs: 600_000 },
    ),
};
