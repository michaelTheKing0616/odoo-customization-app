export type JobAutopilotContract = {
  stock_first: boolean;
  sandbox_only: boolean;
  promote_stays_human: boolean;
  scorecard_is_not_golive: boolean;
  refuse_production: boolean;
  implementation_job_scorecard?: boolean;
  promote_to_other_connection?: boolean;
  no_prod_db_clone?: boolean;
  note: string;
  confirm_phrase: string;
  smoke_done_bar?: string;
};

export type JobCustomResidual = {
  key: string;
  model: string;
  reason: string;
};

export type JobDataFileClass = {
  filename: string;
  doc_type: string;
  confidence: number;
  excerpt?: string;
};

export type JobPacket = {
  prompt: string;
  domain_label: string;
  actors: string[];
  processes: string[];
  documents: string[];
  stock_apps: string[];
  custom_residuals: JobCustomResidual[];
  data_files: JobDataFileClass[];
  country_code: string | null;
  l10n_module: string | null;
  company_name: string | null;
  currency: string | null;
  warehouse_needed: boolean;
  roles: string[];
  org_emails?: string[];
  grounding?: string[];
  risks: string[];
  decision_record: string[];
  warnings: string[];
  planner: string;
  scorecard_note: string;
  connectors?: string[];
  structured_brief?: string;
  operator_brief?: {
    formatted?: string;
    capability_path?: string;
    unknowns?: string[];
  };
};

export type JobAutopilotPacketOut = {
  packet: JobPacket;
  connection_kind: string;
  sandbox: boolean;
  scorecard_note: string;
  message: string;
};

export type JobProbeResult = {
  name: string;
  ok: boolean;
  detail: string;
};

export type JobScorecard = {
  stack_fit: number;
  stock_coverage: number;
  data_load: number;
  process_smoke: number;
  overall: number;
  findings: string[];
  modulespec_completeness_note: string;
};

export type JobAutopilotQueued = {
  job_id: string;
  queued: true;
  status: string;
  message: string;
};

export type JobAutopilotResult = {
  ok: boolean;
  refused: boolean;
  refuse_reason: string | null;
  connection_kind: string;
  sandbox: boolean;
  packet: JobPacket;
  bootstrap: {
    installed: string[];
    already_installed: string[];
    skipped: string[];
    probes: JobProbeResult[];
    warnings: string[];
    recipe_version?: number;
    message: string;
  } | null;
  connectors?: {
    ok: boolean;
    skipped: boolean;
    ran: string[];
    failed: string[];
    skipped_ids?: string[];
    steps: JobProbeResult[];
    warnings: string[];
    message: string;
  } | null;
  custom: {
    skipped: boolean;
    reason: string | null;
    apply_message: string | null;
    models_created: string[];
    fields_created: number;
    fields_relaxed: number;
    root_menu_id: number | null;
    open_action_id: number | null;
    elite: Record<string, unknown> | null;
    zip_base64?: string | null;
    zip_omitted?: boolean;
    expert_score_before?: number | null;
    expert_score_after?: number | null;
    warnings: string[];
    spec: Record<string, unknown> | null;
  } | null;
  ingest: {
    skipped: boolean;
    reason: string | null;
    ingest_job_id: string | null;
    status: string | null;
    committed: boolean;
    dry_run_only: boolean;
    source_rows?: number;
    loaded_rows?: number;
    unmatched_m2o?: string[];
    gaps: string[];
    warnings: string[];
    message: string;
  } | null;
  smoke: {
    ok: boolean;
    steps: JobProbeResult[];
    named_process?: string | null;
    ingest_source_rows?: number;
    ingest_loaded_rows?: number;
    unmatched_m2o?: string[];
    partner_id?: number | null;
    sale_order_id?: number | null;
    invoice_id?: number | null;
    open_model?: string | null;
    open_id?: number | null;
    open_action_id?: number | null;
    message: string;
  } | null;
  job_scorecard?: JobScorecard | null;
  promote_ready: boolean;
  stages: string[];
  retry_count?: number;
  walkthrough_seeded?: boolean;
  report_markdown?: string | null;
  message: string;
  scorecard_note: string;
  clone_required?: boolean;
  config_packet?: ConfigPacket | null;
};

export type ConfigChecklistItem = {
  id: string;
  label: string;
  status: "done" | "todo" | "blocked" | "secret";
  surface: string;
  href_hint?: string;
  action_id?: number | null;
  odoo_model?: string;
};

export type ConfigPacket = {
  packet_version: number;
  recipe_version: number;
  source_kind: string;
  modules: string[];
  company: { name?: string | null; currency?: string | null; country_code?: string | null };
  accounting: {
    journals: Array<{ name: string; type: string; code: string }>;
    tax_xmlids: string[];
    fiscal_position_names: string[];
    account_code_count: number;
    taxes_invented?: boolean;
  };
  stock: {
    warehouse_code?: string | null;
    delivery_steps?: string | null;
    reception_steps?: string | null;
    lot_tracking?: boolean;
    mto?: boolean;
    dropship?: boolean;
  };
  users: Array<{ login: string; name?: string | null; email?: string | null; group_xmlids: string[] }>;
  connectors: Array<{
    id: string;
    title: string;
    needs_secret: boolean;
    odoo_model: string;
    brands: string[];
    open_hint?: string;
    action_id?: number | null;
    action_xmlid?: string | null;
  }>;
  mail: {
    smtp_servers: number;
    alias_domains: number;
    ok: boolean;
    warnings: string[];
    action_id?: number | null;
    odoo_model?: string;
  };
  settings?: { values: Record<string, unknown> };
  smoke: { processes: string[]; passed: string[]; failed: string[] };
  opening: {
    tb_present: boolean;
    tb_allowed: boolean;
    coa_threshold: number;
    account_code_count: number;
    message: string;
    lock_date_blocked?: boolean;
    period_lock_date?: string | null;
    fiscalyear_lock_date?: string | null;
    tax_lock_date?: string | null;
  };
  checklist: ConfigChecklistItem[];
  sha256: string;
  secrets_excluded: boolean;
  custom_zip_present?: boolean;
  residual_models?: string[];
  documents?: {
    paperformat_name?: string | null;
    option_a_qweb_needed?: boolean;
    logo_upload_needed?: boolean;
    font?: string | null;
    layout_background?: string | null;
    external_report_layout_xmlid?: string | null;
    report_header?: string | null;
    report_footer?: string | null;
  };
};

export type InstanceFingerprint = {
  major?: number | null;
  modules_installed: string[];
  journal_types: string[];
  journal_names: string[];
  warehouse_codes: string[];
  tax_xmlids: string[];
  user_logins: string[];
  account_code_count: number;
  company_name?: string | null;
  currency?: string | null;
  country_code?: string | null;
  sha256: string;
  warnings: string[];
  mail?: { smtp_servers: number; alias_domains: number; ok: boolean; warnings: string[]; action_id?: number | null };
  period_lock_date?: string | null;
  fiscalyear_lock_date?: string | null;
  tax_lock_date?: string | null;
  fiscal_position_names?: string[];
};

export type ConfigPacketDiff = {
  ops: Array<{ op: string; target: string; detail: string; risky: boolean }>;
  skipped: string[];
  blocked: string[];
  checklist: ConfigChecklistItem[];
  message: string;
};

export type ConfigPacketApplyReport = {
  ok: boolean;
  refused: boolean;
  refuse_reason: string | null;
  snapshot_id?: string | null;
  applied: string[];
  skipped: string[];
  warnings: string[];
  checklist: ConfigChecklistItem[];
  message: string;
  target_kind: string;
};

export type JobAutopilotPromoteToResult = {
  ok: boolean;
  refused: boolean;
  refuse_reason: string | null;
  source_connection_id: string;
  target_connection_id: string;
  target_kind: string;
  module: string | null;
  method: string | null;
  message: string;
  confirm_phrase: string;
};
