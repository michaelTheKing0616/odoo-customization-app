export type DataImportPreviewOut = {
  headers: string[];
  sample_rows: Record<string, string>[];
  row_count: number;
  suggested_model: string | null;
  field_hints: Array<Record<string, unknown>>;
  suggested_mapping: Record<string, string>;
  warnings: string[];
};

export type IngestGapOut = {
  model: string;
  field: string;
  value: string;
  message: string;
};

export type IngestPlanStepOut = {
  step_index: number;
  table_ids: string[];
  models: string[];
  parallel_ok: boolean;
};

export type IngestPlanOut = {
  steps: IngestPlanStepOut[];
  gaps: IngestGapOut[];
};

export type IngestFileOut = {
  id: string;
  filename: string;
  mime?: string | null;
  doc_type: string;
  confidence: number;
  needs_user_confirm: boolean;
  warnings: string[];
  table_ids: string[];
};

export type IngestTableOut = {
  id: string;
  model: string;
  doc_type: string;
  row_count?: number;
  natural_key_fields: string[];
  warnings: string[];
};

export type IngestCommitLogOut = {
  dry_run: boolean;
  created: number;
  updated: number;
  failed: number;
  skipped: number;
  messages: string[];
  step_results: Array<Record<string, unknown>>;
};

export type IngestBatchOut = {
  connection_id?: string | null;
  files: IngestFileOut[];
  tables: Array<IngestTableOut & { rows?: Array<Record<string, unknown>> }>;
  refs: Array<Record<string, unknown>>;
  gaps: IngestGapOut[];
  plan: IngestPlanOut | null;
  commit_log: IngestCommitLogOut | null;
  warnings: string[];
  notify_mode?: "batch_summary" | "individual";
  allow_coa_as_is?: boolean;
  meta?: Record<string, unknown>;
};
export type IngestJobOut = {
  id: string;
  connection_id: string;
  status: string;
  batch: IngestBatchOut;
  error?: string | null;
};

export type IdGeneratorAssignmentOut = {
  row_id: string | number;
  name: string;
  existing_code: string | null;
  new_code: string | null;
  changed: boolean;
  initials?: string | null;
};

export type IdGeneratorPreviewOut = {
  total: number;
  changed: number;
  skipped: number;
  assignments: IdGeneratorAssignmentOut[];
  headers?: string[] | null;
  message: string;
};

export type IdGeneratorRunOut = {
  run_id: string;
  operation: string;
  model: string;
  total: number;
  succeeded: number;
  failed: number;
  changed: number;
  skipped: number;
  dry_run: boolean;
  message: string;
  assignments: IdGeneratorAssignmentOut[];
};




export type DataImportCommitOut = {
  ok: boolean;
  dry_run: boolean;
  created: number;
  updated: number;
  failed: number;
  skipped: number;
  message: string;
  results: Array<{
    row_index: number;
    ok: boolean;
    record_id: number | null;
    action: string | null;
    error: string | null;
  }>;
  error_csv: string | null;
};

export type ImageImportPreviewOut = {
  row_count: number;
  sample_rows: Array<Record<string, string>>;
  image_field: string;
  match_field: string;
  match_mode: string;
  warnings: string[];
};

export type ImageImportCommitOut = {
  ok: boolean;
  dry_run: boolean;
  updated: number;
  failed: number;
  skipped: number;
  message: string;
  results: Array<{
    row_index: number;
    match_value: string;
    filename: string;
    ok: boolean;
    record_id: number | null;
    action: string | null;
    error: string | null;
    bytes_in: number;
    bytes_out: number;
  }>;
};
