import type { DeploymentPanel, GatingCallout } from "./types-gating";

export type SandboxRunResult = {
  ok: boolean;
  module: string;
  message: string;
  log_tail: string;
  sandbox_url: string | null;
  validation_id?: string | null;
  zip_sha256?: string | null;
  zip_base64?: string | null;
  job_id?: string | null;
  approximation?: boolean;
  approximation_label?: string | null;
  sh_staging_suggestion?: string | null;
};

export type JobRow = {
  id: string;
  kind: string;
  connection_id: string | null;
  status: string;
  result: Record<string, unknown> | null;
  error: string | null;
  created_at: string | null;
  finished_at: string | null;
};

export type PromoteResult = {
  ok: boolean;
  module: string;
  method: string;
  message: string;
  module_state: string | null;
  validation_id: string | null;
  promotion_id?: string | null;
};

export type PromotedModuleRow = {
  id: string;
  module_name: string;
  method: string;
  status: string;
  zip_sha256: string | null;
  created_at: string | null;
  uninstalled_at: string | null;
};

export type UninstallResult = {
  ok: boolean;
  module: string;
  module_state: string | null;
  message: string;
  residual_models?: string[];
  residual_note?: string | null;
};

export type GroupRow = {
  id: number;
  name: string;
  full_name: string | null;
  share: boolean;
};

export type AccessRightRow = {
  id: number;
  name: string;
  model: string;
  model_id: number;
  group_id: number | null;
  group_name: string | null;
  perm_read: boolean;
  perm_write: boolean;
  perm_create: boolean;
  perm_unlink: boolean;
  active: boolean;
};

export type RecordRuleRow = {
  id: number;
  name: string;
  model: string;
  model_id: number;
  domain_force: string | null;
  group_ids: number[];
  perm_read: boolean;
  perm_write: boolean;
  perm_create: boolean;
  perm_unlink: boolean;
  active: boolean;
  global?: boolean;
};

export type AutomationRow = {
  id: number;
  name: string;
  model: string;
  model_id: number;
  trigger: string;
  active: boolean;
  filter_domain: string | null;
  action_server_ids: number[];
  snapshot_id?: string | null;
};

export type ActivityTypeRow = {
  id: number;
  name: string;
};

export type ModuleExport = {
  technical_name: string;
  filename: string;
  content_base64: string;
  note: string;
  deployment_panel?: DeploymentPanel | null;
};

export type SnapshotRow = {
  id: string;
  resource_type: string;
  resource_key: string;
  label: string;
  reversible: string;
  created_at: string | null;
};

export type MenuNode = {
  id: number;
  name: string;
  parent_id: number | null;
  parent_name?: string | null;
  action: string | null;
  action_id: number | null;
  action_type?: string | null;
  sequence: number;
  web_icon: string | null;
  child_count: number;
  group_ids?: number[];
};

export type WindowActionRow = {
  id: number;
  name: string;
  res_model: string | null;
  view_mode: string | null;
  domain?: string | null;
  context?: string | null;
  target?: string | null;
  requires_active_id?: boolean;
};

export type AccessMatrixOut = {
  models: string[];
  groups: GroupRow[];
  cells: Array<{
    model: string;
    group_id: number | null;
    access_id: number | null;
    name: string | null;
    perm_read: boolean;
    perm_write: boolean;
    perm_create: boolean;
    perm_unlink: boolean;
    active: boolean;
  }>;
};

export type CompanyRow = {
  id: number;
  name: string;
  email: string | null;
  phone: string | null;
  website: string | null;
  street: string | null;
  street2: string | null;
  city: string | null;
  zip: string | null;
  vat: string | null;
  company_registry: string | null;
  currency_id: number | null;
  currency_name: string | null;
};

export type EePlaybook = {
  id: string;
  name: string;
  description: string;
  requires_modules: string[];
  available: boolean;
  reason: string;
  warn_only: boolean;
};

export type DomainPlaybook = {
  id: string;
  name: string;
  description: string;
  requires_modules: string[];
  available: boolean;
  reason: string;
};

export type StudioFeatureRecipe = {
  id: string;
  name: string;
  status: string;
  how: string;
  app_surfaces: string[];
};

export type SequenceRow = {
  id: number;
  name: string;
  code: string | null;
  prefix: string | null;
  suffix: string | null;
  padding: number;
  number_next: number;
  number_increment: number;
  active: boolean;
};

export type MenuRow = {
  id: number;
  name: string;
  parent_id: number | null;
  parent_name: string | null;
  action: string | null;
  sequence: number;
  web_icon: string | null;
};

export type AuditLogRow = {
  id: string;
  method: string;
  path: string;
  status_code: number;
  client_ip: string | null;
  api_key_prefix: string | null;
  duration_ms: number | null;
  detail_json?: string | null;
  created_at: string | null;
};

export type CodeStudioGateResponse = {
  probe: Record<string, unknown>;
  gating: GatingCallout;
  developer_role_required: boolean;
  entitlement_key: string;
};

export type CodeStudioValidateResult = {
  ok: boolean;
  syntax_ok: boolean;
  warnings: { code: string; message: string }[];
  error?: string | null;
};

export type CodeStudioTestRunResult = {
  ok: boolean;
  validation: CodeStudioValidateResult;
  ran_for_real: boolean;
  record: { model: string; id: number | null };
  exception?: string | null;
  field_diff: { field: string; before: unknown; after: unknown }[];
  before?: Record<string, unknown> | null;
  after?: Record<string, unknown> | null;
};

export type CodeStudioBindResult = {
  ok: boolean;
  bind_kind: string;
  code: string;
  snapshot_id?: string | null;
  server_action_id?: number | null;
  automation_id?: number | null;
};

export type AppTemplate = {
  id: string;
  name: string;
  description: string;
};

export type ScaffoldResult = {
  ok: boolean;
  template_id: string;
  models: string[];
  models_created?: string[];
  models_skipped?: string[];
  fields_created: number;
  menus_created?: number;
  view_injects?: number;
  message: string;
  warnings?: string[];
};

export type ProjectDiffOut = {
  ok: boolean;
  message: string;
  to_create_models: string[];
  existing_models: string[];
  to_create_fields: string[];
  existing_fields: string[];
  conflicts: string[];
};

export type SuggestDependsOut = {
  suggested: string[];
  from_relations: string[];
  message: string;
};

export type ReminderCreateBody = {
  name: string;
  model: string;
  date_field: string;
  mode?: "overdue" | "due_soon";
  due_soon_days?: number;
  interval_number?: number;
  interval_type?: string;
  email_to?: string;
  subject?: string | null;
  body_html?: string | null;
  create_cron?: boolean;
  confirm_advanced?: boolean;
  confirm_phrase?: string | null;
};

export type ReminderCreateOut = {
  ok: boolean;
  mail_template_id: number | null;
  cron_id: number | null;
  message: string;
  warnings?: string[];
};
