/** Carry a Draft Studio brief into Job Autopilot without a second paste. */

export function jobAutopilotBriefStorageKey(connectionId: string): string {
  return `job-autopilot-brief:${connectionId}`;
}

export function briefTextForJobAutopilot(
  draft: Record<string, unknown> | null | undefined,
  fallbackPrompt = "",
): string {
  const ob = draft?._operator_brief;
  if (ob && typeof ob === "object" && !Array.isArray(ob)) {
    const formatted = (ob as { formatted?: unknown }).formatted;
    if (typeof formatted === "string" && formatted.trim()) {
      return formatted.trim();
    }
  }
  const user = draft?._user_prompt;
  if (typeof user === "string" && user.trim()) {
    return user.trim();
  }
  return fallbackPrompt.trim();
}

export function stashJobAutopilotBrief(connectionId: string, brief: string): void {
  const text = brief.trim();
  if (!connectionId || !text) return;
  try {
    sessionStorage.setItem(jobAutopilotBriefStorageKey(connectionId), text);
  } catch {
    /* private mode */
  }
}

export function readJobAutopilotBrief(connectionId: string): string | null {
  if (!connectionId) return null;
  try {
    const text = (sessionStorage.getItem(jobAutopilotBriefStorageKey(connectionId)) || "").trim();
    return text || null;
  } catch {
    return null;
  }
}
