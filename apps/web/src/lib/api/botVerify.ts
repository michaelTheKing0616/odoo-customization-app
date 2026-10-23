/**
 * BV-01: verify-run contract mirror (types and calls only, no UI).
 * Field names match apps/api/app/bot_verify/contract.py and BOT_VERIFY.md §6.
 */
import { getApiBase, request } from "./client";

export type BVErrorCode =
  | "ROLE_DENIED"
  | "VALIDATION"
  | "NOT_FOUND"
  | "TARGET_NOT_ALLOWED"
  | "CHANGESET_NOT_APPLIED";

export type Layer = "live" | "walkthrough" | "flows";
export type VerifyTarget = "disposable_clone" | "approved_connection";
export type RunStatus = "queued" | "running" | "passed" | "failed" | "needs_human" | "rolled_back";
export type LayerStatus = "passed" | "failed" | "skipped";
export type StepAction = "open" | "click" | "fill" | "assert";

export type VerifyRunRequest = {
  changeset_id: string;
  layers: Layer[];
  target: VerifyTarget;
};

/** check: one of app/changeset/verify.py CHECKS. */
export type CheckResult = {
  check: string;
  op_index: number;
  passed: boolean;
  evidence: Record<string, string>;
};

export type WalkStep = {
  index: number;
  op_index: number | null;
  action: StepAction;
  target: string;
  passed: boolean;
  screenshot_id: string | null;
  dom_assertion: string | null;
};

export type LayerResult = {
  layer: Layer;
  status: LayerStatus;
  reason: string | null;
  checks: CheckResult[];
  steps: WalkStep[];
};

export type VerifyRun = {
  run_id: string;
  changeset_id: string;
  status: RunStatus;
  layers: LayerResult[];
  started_at: string;
  finished_at: string | null;
};

export type BVErrorBody = {
  code: BVErrorCode;
  message: string;
  detail: Record<string, unknown> | null;
  retry_after_s: number | null;
};

const base = (connectionId: string) =>
  `/api/connections/${encodeURIComponent(connectionId)}/verify-runs`;
const run = (connectionId: string, runId: string) =>
  `${base(connectionId)}/${encodeURIComponent(runId)}`;

export const botVerifyApi = {
  startVerifyRun: (connectionId: string, body: VerifyRunRequest) =>
    request<VerifyRun>(base(connectionId), { method: "POST", body: JSON.stringify(body) }),
  getVerifyRun: (connectionId: string, runId: string) =>
    request<VerifyRun>(run(connectionId, runId)),
  verifyArtifactUrl: (connectionId: string, runId: string, artifactId: string) =>
    `${getApiBase()}${run(connectionId, runId)}/artifacts/${encodeURIComponent(artifactId)}`,
};
