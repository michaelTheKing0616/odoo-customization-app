import type { CapabilityMatrix, GatingCallout } from "./types-gating";

export type Connection = {
  id: string;
  name: string;
  url: string;
  db_name: string;
  username: string;
  server_version: string | null;
  last_seen_version?: string | null;
  upgrade_detected?: boolean;
  upgrade_detected_at?: string | null;
  write_mode: "observer" | "standard" | "production";
  writes_paused?: boolean;
  /** odoo.sh / online vs self-hosted — used for Online capability callouts. */
  hosting?: string | null;
  group_label?: string | null;
  /** Saved "This is a test copy" flag; null/undefined = never set (older connections). */
  is_test_copy?: boolean | null;
  created_at: string | null;
  updated_at: string | null;
  capabilities?: CapabilityMatrix | null;
};

export type ProductionReadinessItem = {
  key: string;
  label: string;
  status: "pass" | "fail" | "warn" | "todo";
  detail: string;
};

export type ProductionReadinessReport = {
  passed: boolean;
  items: ProductionReadinessItem[];
  drill_snapshot_id?: string | null;
  updated_at?: string | null;
  first_write_acknowledged?: boolean;
};

export type HealthCheckItem = {
  artifact_id: string;
  artifact_type: string;
  label: string;
  status: "ok" | "broken" | "skipped" | string;
  reason: string;
  deep_link: string;
  resource_type?: string | null;
  resource_key?: string | null;
};

export type HealthCheckRun = {
  id: string;
  connection_id: string;
  job_id?: string | null;
  trigger: string;
  status: string;
  previous_version?: string | null;
  current_version?: string | null;
  ok_count: number;
  broken_count: number;
  message: string;
  items: HealthCheckItem[];
  created_at?: string | null;
  finished_at?: string | null;
};

export type HealthCheckTrigger = {
  job_id?: string | null;
  run_id?: string | null;
  async_job: boolean;
  message: string;
  report?: HealthCheckRun | null;
};

export type ApprovalStep = {
  order: number;
  approver_user_ids?: number[];
  approver_group_id?: number | null;
  exclusive?: boolean;
  domain?: string | null;
};

export type ApprovalRule = {
  id: string;
  connection_id: string;
  engine: "community" | "studio" | string;
  name: string;
  target_model: string;
  button_method: string;
  button_label?: string | null;
  steps: ApprovalStep[];
  active: boolean;
  deployed: boolean;
  odoo_wrapper_action_id?: number | null;
  odoo_studio_rule_id?: number | null;
  created_at?: string | null;
};

export type ApprovalEntry = {
  id: string;
  rule_id: string;
  record_model: string;
  record_id: number;
  step_order: number;
  status: string;
  approver_user_id?: number | null;
  message: string;
  created_at?: string | null;
  resolved_at?: string | null;
};

export type ApprovalsGateResponse = {
  engine: string;
  studio_available: boolean;
  studio_verify_state: string;
  community_available: boolean;
  studio_note?: string | null;
  gating: GatingCallout;
};

export type ApprovalButton = {
  name: string;
  label: string;
  bulk_safe: boolean;
  reason: string;
  in_header: boolean;
};






export type ProcessGateResponse = {
  engine: string;
  enterprise_available: boolean;
  verify_state: string;
  enterprise_note?: string | null;
  community_models_ready: boolean;
};

export type ProcessTypeRow = {
  id: number;
  name?: string | null;
  active: boolean;
  levels: number;
  chain: Array<{
    level: number;
    min_approvals: number;
    approver_user_ids: number[];
    approver_group_id?: number | null;
    domain?: string | null;
  }>;
};

export type ProcessRequestRow = {
  id: number;
  name?: string | null;
  subject?: string | null;
  amount?: number | null;
  state?: string | null;
  current_level?: number | null;
  type_id?: number | null;
  requester_id?: number | null;
};

export type ModuleRow = {
  id: number;
  name: string;
  shortdesc: string | null;
  state: string;
  application: boolean;
};

export type ModelRow = {
  id: number;
  model: string;
  name: string;
  state: string | null;
  transient: boolean;
};

export type ReuseModelRow = {
  model: string;
  name: string;
  app: string;
  link_only: boolean;
};

export type FieldRow = {
  id: number;
  name: string;
  field_description: string;
  ttype: string;
  required: boolean;
  readonly: boolean;
  relation: string | null;
  state: string | null;
  help?: string | null;
  selection?: string | null;
  related?: string | null;
  currency_field?: string | null;
  relation_field?: string | null;
  tracking?: boolean;
};

export type ViewRow = {
  id: number;
  name: string;
  model: string;
  type: string;
  arch: string | null;
  priority?: number | null;
  snapshot_id?: string | null;
};

export type FieldCreateRow = FieldRow & {
  injected_view_ids: number[];
  currency_field_created?: string | null;
};

export type BuilderWidgetOption = {
  id: string;
  label: string;
  hint?: string;
};

export type RelatedPathOption = {
  path: string;
  label: string;
  ttype: string;
  relation?: string | null;
};

export type PreviewTheme = {
  ok: boolean;
  theme: Record<string, string>;
  preview_vars: Record<string, string>;
  error?: string | null;
};

export type AutomationTriggersResponse = {
  major: number;
  source: string;
  supported_triggers: string[];
  probe_table: Array<{
    major: number;
    source: string;
    on_webhook: boolean;
    on_change: boolean;
    on_change_field_ids?: boolean;
    trigger_count?: number | null;
  }>;
};

export type NicheWidgetEntry = {
  id: string;
  label: string;
  recommended_ttypes: string[];
  view_types?: string[];
  hint?: string;
  supporting_field?: {
    name: string;
    ttype: string;
    string?: string;
    relation?: string;
  } | null;
};


export type NicheWidgetsResponse = {
  widgets: NicheWidgetEntry[];
  color_palette: Array<{ index: number; name: string }>;
};


export type PropertyFieldsProbeOut = {
  major: number;
  source: string;
  supported: boolean;
  probe_table: Array<{
    major: number;
    source: string;
    ttype_properties: boolean;
    ttype_properties_definition: boolean;
    definition_record_column: boolean;
    definition_record_field_column?: boolean;
    definition_write: boolean;
    rpc_create: boolean;
    supported: boolean;
  }>;
};

export type PropertyFieldsSetupOut = {
  ok: boolean;
  properties_field: string;
  definition_field: string;
  parent_model: string;
  created: boolean;
  definition_field_created?: boolean | null;
};

export type PropertyDefinitionWriteOut = {
  ok: boolean;
  parent_model: string;
  record_id: number;
  definition_field: string;
  property_count: number;
};

export type InvoicingPreflightOut = {
  ok: boolean;
  account_installed: boolean;
  l10n_installed: boolean;
  company_country?: string | null;
  l10n_modules: string[];
  message: string;
};

export type InvoicingConnectOut = {
  ok: boolean;
  path: string;
  invoice_field: string;
  field_created: boolean;
  count_field?: string | null;
  count_field_created?: boolean | null;
  window_action_id: number;
  button_spec: Record<string, unknown>;
  form_view_id?: number | null;
  form_view_name?: string | null;
};

export type InvoicingMergeSpecOut = {
  ok: boolean;
  merged: Record<string, unknown>;
};

export type ScanFindOut = {
  ok: boolean;
  model: string;
  field: string;
  value: string;
  count: number;
  records: Array<{ id: number; display_name?: string | null }>;
};

export type InvoicingDraftInvoiceOut = {
  ok: boolean;
  move_id: number;
  move_name?: string | null;
  state?: string | null;
  source_model: string;
  record_id: number;
};

export type InvoicingModuleSpecOut = {
  ok: boolean;
  fragment: Record<string, unknown>;
};
