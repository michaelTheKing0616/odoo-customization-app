/**
 * NG-01: Nigeria pack contract mirror (types and calls only, no UI).
 * Field names match apps/api/app/l10n_ng/contract.py and LOCALIZATION.md §NG §6.
 * Money (Decimal on the server) arrives as a string to keep exact figures.
 */
import { request } from "./client";
import type { Finding } from "./scans";

export type NgErrorCode = "ROLE_DENIED" | "VALIDATION" | "NOT_FOUND";

export type NgTax = {
  id: number;
  name: string;
  amount: string;
  type_tax_use: string;
};

export type NgDetect = {
  country: string | null;
  l10n_ng_installed: boolean;
  l10n_ng_available: boolean;
  taxes: NgTax[];
};

export type NgPlanResponse = {
  plan_id: string;
};

export type EinvoiceReadiness = {
  items: Finding[];
  sample_payload: Record<string, unknown> | null;
};

/** Exactly one source: upload_id, or from_hr: true. period is YYYY-MM. */
export type PayrollComputeRequest = {
  upload_id?: string | null;
  from_hr?: boolean;
  period: string;
};

export type PayrollRow = {
  employee_ref: string;
  gross: string;
  paye: string;
  pension_employee: string;
  pension_employer: string;
};

export type PayrollCompute = {
  rows: PayrollRow[];
  rules_version: string;
};

export type BankConvertRequest = {
  upload_id: string;
  bank?: string | null;
};

export type TryLoading = {
  ok: boolean;
  messages: string[];
};

export type BankConvert = {
  bank: string | null;
  rows: Record<string, unknown>[];
  csv_id: string | null;
  try_loading: TryLoading;
};

export type NgErrorBody = {
  code: NgErrorCode;
  message: string;
  detail: Record<string, unknown> | null;
  retry_after_s: number | null;
};

const base = (connectionId: string) =>
  `/api/connections/${encodeURIComponent(connectionId)}/l10n-ng`;

export const nigeriaApi = {
  detect: (connectionId: string) => request<NgDetect>(`${base(connectionId)}/detect`),
  plan: (connectionId: string) =>
    request<NgPlanResponse>(`${base(connectionId)}/plan`, { method: "POST" }),
  einvoiceReadiness: (connectionId: string) =>
    request<EinvoiceReadiness>(`${base(connectionId)}/einvoice-readiness`),
  payrollCompute: (connectionId: string, body: PayrollComputeRequest) =>
    request<PayrollCompute>(`${base(connectionId)}/payroll-compute`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  bankConvert: (connectionId: string, body: BankConvertRequest) =>
    request<BankConvert>(`${base(connectionId)}/bank/convert`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
