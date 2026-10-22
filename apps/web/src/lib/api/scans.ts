/**
 * SCAN-01: scan contract mirror (types and calls only, no UI).
 * Field names match apps/api/app/scans/contract.py and 00_BASELINE.md B5.
 */
import { request } from "./client";

export type ScanErrorCode =
  | "ODOO_UNREACHABLE"
  | "ODOO_ACCESS_MISSING"
  | "ROLE_DENIED"
  | "RATE_LIMITED"
  | "VALIDATION"
  | "NOT_FOUND"
  | "CONFLICT";

export type ScanRunStatus = "queued" | "running" | "partial" | "done" | "failed" | "cancelled";
export type AreaStatus = "done" | "partial" | "skipped" | "failed";
export type FindingSeverity = "info" | "low" | "medium" | "high" | "critical";
export type FixKind = "plan" | "link" | "manual";

export type AreaResult = {
  area: string;
  status: AreaStatus;
  rows_read: number;
  sampled: boolean;
  duration_ms: number;
  findings_count: number;
  error_code: ScanErrorCode | null;
};

export type ScanRun = {
  id: string;
  connection_id: string;
  scan_id: string;
  status: ScanRunStatus;
  started_at: string | null;
  finished_at: string | null;
  areas: AreaResult[];
  budget_ms: number;
  odoo_version: string | null;
  schema_fingerprint: string | null;
};

export type FixRef = {
  kind: FixKind;
  plan_template: string | null;
  params: Record<string, unknown>;
};

export type Finding = {
  id: string;
  scan_id: string;
  area: string;
  severity: FindingSeverity;
  title: string;
  plain_why: string;
  count: number;
  sample_ids: number[];
  model: string | null;
  evidence: Record<string, unknown>;
  fix: FixRef | null;
  docs_url: string | null;
};

export type StartScanRequest = {
  scan_id: string;
  params?: Record<string, unknown>;
};

export type FindingsPage = {
  items: Finding[];
  next_cursor: string | null;
};

export type PlanDraftRef = {
  draft_id: string;
};

export type ScanErrorBody = {
  code: ScanErrorCode;
  message: string;
  detail: Record<string, unknown> | null;
  retry_after_s: number | null;
};

export type FindingsFilter = {
  severity?: FindingSeverity;
  area?: string;
  cursor?: string;
  limit?: number;
};

const base = (connectionId: string) =>
  `/api/connections/${encodeURIComponent(connectionId)}`;

export const scansApi = {
  startScan: (connectionId: string, body: StartScanRequest) =>
    request<ScanRun>(`${base(connectionId)}/scans`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getScan: (connectionId: string, runId: string) =>
    request<ScanRun>(`${base(connectionId)}/scans/${encodeURIComponent(runId)}`),
  listFindings: (connectionId: string, runId: string, filter: FindingsFilter = {}) => {
    const q = new URLSearchParams();
    if (filter.severity) q.set("severity", filter.severity);
    if (filter.area) q.set("area", filter.area);
    if (filter.cursor) q.set("cursor", filter.cursor);
    if (filter.limit) q.set("limit", String(filter.limit));
    const qs = q.toString();
    return request<FindingsPage>(
      `${base(connectionId)}/scans/${encodeURIComponent(runId)}/findings${qs ? `?${qs}` : ""}`,
    );
  },
  cancelScan: (connectionId: string, runId: string) =>
    request<ScanRun>(`${base(connectionId)}/scans/${encodeURIComponent(runId)}/cancel`, {
      method: "POST",
    }),
  planFinding: (connectionId: string, findingId: string) =>
    request<PlanDraftRef>(
      `${base(connectionId)}/findings/${encodeURIComponent(findingId)}/plan`,
      { method: "POST" },
    ),
};
