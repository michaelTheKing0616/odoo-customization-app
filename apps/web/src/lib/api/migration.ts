/**
 * MIG-01: data migration studio contract mirror (types and calls only, no UI).
 * Field names match apps/api/app/migration_studio/contract.py and INTEGRATE.md §MIG §6.
 * Reconcile sums are decimal strings to keep exact figures.
 */
import { request } from "./client";

export type MigErrorCode = "ROLE_DENIED" | "VALIDATION" | "NOT_FOUND" | "CONFLICT";

export type MigrationSource =
  | "QuickBooks Online export"
  | "Sage 50 CSV"
  | "Zoho Books export"
  | "Excel workbook"
  | "Other ERP CSV";

export type MigrationCreate = {
  source: MigrationSource;
};

export type MigrationJob = {
  id: string;
  connection_id: string;
  source: MigrationSource;
  created_at: string;
};

export type MigrationFile = {
  filename: string;
};

/** column_map: source column -> Odoo field name. transforms: source column -> transform name. */
export type EntityMapping = {
  source: MigrationSource;
  entity: string;
  column_map: Record<string, string>;
  transforms: Record<string, string>;
};

export type MappingSet = {
  mappings: EntityMapping[];
};

/** row is the 1-based data row. */
export type RowError = {
  row: number;
  column: string;
  message: string;
};

export type DryRunEntity = {
  entity: string;
  rows: number;
  errors: RowError[];
};

export type DryRunResult = {
  entities: DryRunEntity[];
};

/** A Live target with confirm false returns 409 CONFLICT. */
export type ImportRequest = {
  target_connection_id: string;
  confirm: boolean;
};

export type ImportResult = {
  target_connection_id: string;
  failed: RowError[];
};

export type ReconcileLine = {
  entity: string;
  file_count: number;
  odoo_count: number;
  file_sum: string;
  odoo_sum: string;
  equal: boolean;
};

export type ReconcileReport = {
  lines: ReconcileLine[];
};

export type MigErrorBody = {
  code: MigErrorCode;
  message: string;
  detail: Record<string, unknown> | null;
  retry_after_s: number | null;
};

const base = (connectionId: string) =>
  `/api/connections/${encodeURIComponent(connectionId)}/migrations`;
const job = (connectionId: string, mid: string) =>
  `${base(connectionId)}/${encodeURIComponent(mid)}`;

export const migrationApi = {
  createMigration: (connectionId: string, body: MigrationCreate) =>
    request<MigrationJob>(base(connectionId), { method: "POST", body: JSON.stringify(body) }),
  uploadMigrationFile: (connectionId: string, mid: string, file: File) => {
    const form = new FormData();
    form.append("file", file, file.name);
    return request<MigrationFile>(`${job(connectionId, mid)}/files`, {
      method: "POST",
      body: form,
    });
  },
  getMigrationMapping: (connectionId: string, mid: string) =>
    request<MappingSet>(`${job(connectionId, mid)}/mapping`),
  putMigrationMapping: (connectionId: string, mid: string, body: MappingSet) =>
    request<MappingSet>(`${job(connectionId, mid)}/mapping`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  dryRunMigration: (connectionId: string, mid: string) =>
    request<DryRunResult>(`${job(connectionId, mid)}/dry-run`, { method: "POST" }),
  importMigration: (connectionId: string, mid: string, body: ImportRequest) =>
    request<ImportResult>(`${job(connectionId, mid)}/import`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  reconcileMigration: (connectionId: string, mid: string) =>
    request<ReconcileReport>(`${job(connectionId, mid)}/reconcile`),
};
