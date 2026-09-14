import type { JobRow } from "./api";

export const JOB_AUTOPILOT_STORAGE_PREFIX = "job-autopilot:";

export type JobAutopilotResumeKind = "running" | "succeeded" | "failed" | "stale";

export function jobAutopilotStorageKey(connectionId: string): string {
  return `${JOB_AUTOPILOT_STORAGE_PREFIX}${connectionId}`;
}

export function rememberJobAutopilot(connectionId: string, jobId: string): void {
  try {
    sessionStorage.setItem(jobAutopilotStorageKey(connectionId), jobId);
  } catch {
    /* private mode */
  }
}

export function readRememberedJobAutopilot(connectionId: string): string | null {
  try {
    const value = sessionStorage.getItem(jobAutopilotStorageKey(connectionId));
    return value && value.trim() ? value : null;
  } catch {
    return null;
  }
}

export function forgetJobAutopilot(connectionId: string): void {
  try {
    sessionStorage.removeItem(jobAutopilotStorageKey(connectionId));
  } catch {
    /* private mode */
  }
}

export function classifyJobAutopilotResume(
  row: Pick<JobRow, "status" | "connection_id">,
  connectionId: string,
): JobAutopilotResumeKind {
  if (row.connection_id && row.connection_id !== connectionId) return "stale";
  if (row.status === "queued" || row.status === "running") return "running";
  if (row.status === "succeeded") return "succeeded";
  if (["failed", "timeout", "cancelled", "interrupted"].includes(row.status)) return "failed";
  return "stale";
}

export function jobProgressHonestyLine(): string {
  return (
    "Completeness ≠ Cert ≠ Autopilot. Promote stays human. You can leave this page. " +
    "Returning here resumes this job if it is still running, or opens the last result."
  );
}

export function jobResumeNotice(kind: JobAutopilotResumeKind): string {
  switch (kind) {
    case "running":
      return "Resumed Autopilot job from this session.";
    case "succeeded":
      return "Opened last Autopilot result from this session.";
    case "failed":
      return "Last Autopilot job did not finish. Start a new run or keep this brief.";
    case "stale":
      return "Last Autopilot job was not found. Start a new run or keep this brief.";
  }
}
