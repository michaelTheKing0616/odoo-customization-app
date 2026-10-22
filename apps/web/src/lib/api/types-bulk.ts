export type PowerOpsRecipe = {
  id: string;
  name: string;
  description: string;
  model: string;
  destructive: boolean;
  risks: string[];
  requires_modules: string[];
  tags?: string[];
  min_major?: number;
  /** Money guard: refused server-side; never selectable. */
  locked?: boolean;
  locked_reason?: string | null;
  steps: Array<{ kind: string; method?: string | null; label: string }>;
};

export type PowerOpsCapabilities = {
  server_version?: string;
  philosophy?: string;
  custom_python_modules?: Record<string, unknown>;
  power_ops_recipes: Array<{
    id: string;
    name: string;
    available: boolean;
    reason: string;
    model: string;
  }>;
};

export type PowerOpsRunOut = {
  ok: boolean;
  dry_run: boolean;
  processed: number;
  succeeded: number;
  failed: number;
  message: string;
  available: boolean;
  unavailable_reason: string | null;
  logs: Array<{
    record_id: number;
    step: string;
    ok: boolean;
    error: string | null;
  }>;
};

export type BulkTransitionButton = {
  name: string;
  label: string;
  bulk_safe: boolean;
  reason: string;
  in_header: boolean;
};

export type BulkTransitionsOut = {
  model: string;
  buttons: BulkTransitionButton[];
};

export type DedupeScanOut = {
  model: string;
  mode: string;
  match_fields: string[];
  total_groups: number;
  partner_merge_available: boolean;
  groups: Array<{
    group_key: string;
    match_fields: string[];
    records: Array<{
      id: number;
      display_name: string;
      preview: Record<string, unknown>;
    }>;
  }>;
  message: string;
};

export type ReportRenderProbeOut = {
  major: number;
  rpc_methods: Record<string, string>;
  http_report_pdf: boolean;
  primary_path: string;
  message: string;
};


export type BulkRunOut = {
  run_id: string;
  operation: string;
  model: string;
  method: string | null;
  total: number;
  succeeded: number;
  failed: number;
  per_record: Array<{
    id: number;
    display_name: string;
    ok: boolean;
    error: string | null;
  }>;
  dry_run: boolean;
  message: string;
  values?: Record<string, unknown> | null;
  preview?: Array<{
    id: number;
    display_name: string;
    before: Record<string, unknown>;
    after: Record<string, unknown>;
  }> | null;
  winner_id?: number | null;
  loser_ids?: number[] | null;
  relinks?: Array<{
    model: string;
    field: string;
    ttype: string;
    count: number;
  }> | null;
  snapshot_id?: string | null;
  reversibility?: string | null;
  cron_ids?: number[] | null;
  run_via?: string | null;
  attachment_ids?: number[] | null;
  reclaimable_bytes?: number | null;
  kind?: string | null;
  mode?: string | null;
  preview_message?: string | null;
  action?: string | null;
  field?: string | null;
  dependencies?: string[] | null;
  probe?: {
    ok: boolean;
    field: string;
    model: string;
    dependencies: string[];
    probe_ids: number[];
    message: string;
    honesty_message?: string | null;
  } | null;
  receipt_token?: string | null;
  status?: string;
  pending_ids?: number[] | null;
  processed_count?: number | null;
  aborted?: boolean;
  can_continue?: boolean;
};

export type ActivityProbeOut = {
  major: number | null;
  mail_installed: boolean;
  supports_model: boolean;
  message: string;
};

export type SecurityPreviewOut = {
  mode: string;
  users: Array<{
    user_id: number;
    user_name: string;
    add_groups: Array<{ id: number; name: string }>;
    remove_groups: Array<{ id: number; name: string }>;
    implied_warnings: string[];
    deactivate: boolean;
  }>;
  message: string;
};

export type AttachmentRowOut = {
  id: number;
  name: string;
  res_model: string | null;
  res_id: number | null;
  res_field: string | null;
  checksum: string | null;
  file_size: number;
  create_date: string | null;
  mimetype: string | null;
  cleanable: boolean;
  exclusion_reason?: string | null;
};

export type OrphanScanOut = {
  orphans: AttachmentRowOut[];
  standalone: AttachmentRowOut[];
  excluded: AttachmentRowOut[];
  total_reclaimable_bytes: number;
  binary_field_hint: string;
  message: string;
};

export type DuplicateScanOut = {
  groups: Array<{
    checksum: string;
    keep_id: number;
    duplicate_ids: number[];
    reclaimable_bytes: number;
    members: AttachmentRowOut[];
  }>;
  total_reclaimable_bytes: number;
  binary_field_hint: string;
  message: string;
};

export type LargeOldScanOut = {
  attachments: AttachmentRowOut[];
  total_reclaimable_bytes: number;
  min_bytes: number;
  older_than_days: number;
  message: string;
};

export type CronRowOut = {
  id: number;
  name: string;
  model_name: string | null;
  interval_number: number | null;
  interval_type: string | null;
  active: boolean;
  nextcall: string | null;
  lastcall: string | null;
  description: string;
  state?: string | null;
  code_preview?: string | null;
};
