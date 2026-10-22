/**
 * FITGAP-01: fit-gap contract mirror (types and calls only, no UI).
 * Field names match apps/api/app/delivery/fit_gap_types.py and DELIVERY.md §FITGAP §6.
 */
import { request } from "./client";

export type FitGapErrorCode =
  | "ROLE_DENIED"
  | "VALIDATION"
  | "NOT_FOUND"
  | "CONFLICT"
  | "RATE_LIMITED";

export type LineClass = "standard" | "config" | "custom" | "impossible";

export type Evidence = {
  module: string | null;
  model: string | null;
  field: string | null;
  setting: string | null;
  not_in_community: string | null;
};

export type LineOverride = {
  cls: LineClass;
  reason: string;
};

export type FitGapLine = {
  id: string;
  quote: string;
  cls: LineClass | null;
  evidence: Evidence[];
  effort_h: [number, number];
  confidence: number;
  override: LineOverride | null;
};

export type FitGapDoc = {
  id: string;
  doc_sha256: string;
  catalog_version: string;
  lines: FitGapLine[];
};

/** Exactly one of upload_id or text. */
export type FitGapRequest =
  | { upload_id: string; text?: null }
  | { text: string; upload_id?: null };

export type FitGapErrorBody = {
  code: FitGapErrorCode;
  message: string;
  detail: Record<string, unknown> | null;
  retry_after_s: number | null;
};

const base = (connectionId: string) =>
  `/api/connections/${encodeURIComponent(connectionId)}/fitgap`;

export const fitGapApi = {
  createFitGap: (connectionId: string, body: FitGapRequest) =>
    request<FitGapDoc>(base(connectionId), {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getFitGap: (connectionId: string, docId: string) =>
    request<FitGapDoc>(`${base(connectionId)}/${encodeURIComponent(docId)}`),
  overrideLine: (connectionId: string, docId: string, lineId: string, body: LineOverride) =>
    request<FitGapLine>(
      `${base(connectionId)}/${encodeURIComponent(docId)}/lines/${encodeURIComponent(lineId)}`,
      { method: "PATCH", body: JSON.stringify(body) },
    ),
};
