const DEFAULT_API_ORIGIN = "http://127.0.0.1:8001";

/** Absolute API origin (SSR, downloads, explicit NEXT_PUBLIC_API_URL). */
export const API_BASE = (process.env.NEXT_PUBLIC_API_URL ?? DEFAULT_API_ORIGIN).replace(
  /\/$/,
  "",
);

function isLoopbackOrigin(origin: string): boolean {
  try {
    const { hostname } = new URL(origin);
    return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "[::1]";
  } catch {
    return false;
  }
}

/**
 * Base URL for browser fetch calls. Loopback API URLs route through same-origin `/api/*`
 * so Next.js rewrites proxy to FastAPI (avoids CORS and extension fetch interception).
 * Remote/production NEXT_PUBLIC_API_URL still calls the API directly.
 */
export function getApiBase(): string {
  if (typeof window !== "undefined") {
    if (!process.env.NEXT_PUBLIC_API_URL || isLoopbackOrigin(API_BASE)) {
      return "";
    }
    return API_BASE;
  }
  return API_BASE;
}

export type CapabilityMatrix = {
  major: number | null;
  edition: string;
  server_version: string | null;
  supported: string[];
  unsupported: { id: string; label: string; reason: string }[];
  ga: boolean;
  message: string;
  hosting_hint?: string;
  python_module_install?: boolean;
  installed_modules_sample?: string[];
  warnings?: string[];
};

export type GatingChoiceId =
  | "upgrade_plan"
  | "export_module"
  | "install_module"
  | "leave_out"
  | "use_staging";

export type GatingCallout = {
  feature: string;
  title: string;
  why: string;
  options: string[];
  available: boolean;
  capability_key: string;
  gating_choices: { id: GatingChoiceId; label: string }[];
};

export type AutomationsGateResponse = {
  automations: GatingCallout;
  approvals: GatingCallout;
};

export type ProtectedTier = "tier_1" | "tier_2";

export type ProtectedModuleRefusal = {
  protected_module_conflict: boolean;
  requested_capability: string;
  protected_module: string;
  safe_alternative: string;
  kind?: string;
  model?: string | null;
  reason?: string;
};

export type ExpertCitation = {
  source: string;
  version: string;
  breadcrumb: string;
  chunk_id: string;
  source_index: number;
};

export type ExpertAskResponse = {
  answer_markdown: string;
  citations: ExpertCitation[];
  grounded: boolean;
  declined: boolean;
  suggested_tools: Array<{ id?: string; label?: string; deep_link?: string }>;
  caution_flags: string[];
  retrieval_version?: string | null;
  model_used?: string | null;
  reasoning: boolean;
  uncited_warning: boolean;
};

export type DeploymentPanel = {
  tier: "onprem" | "sh" | "online" | "unknown";
  title: string;
  body: string;
  options: string[];
  include_deploy_doc: boolean;
};

export type ValidateLiveItem = {
  item_id: string;
  category: string;
  status: "pass" | "warn" | "fail";
  message: string;
};

export type ValidateLiveResult = {
  ok: boolean;
  items: ValidateLiveItem[];
  fail_count: number;
  warn_count: number;
  message: string;
};

export type StoreReadinessItem = {
  key: string;
  label: string;
  status: "pass" | "warn" | "fail";
  message: string;
};

export type StoreReadinessReport = {
  ok: boolean;
  items: StoreReadinessItem[];
  fail_count: number;
  warn_count: number;
  disclaimer: string;
  message: string;
};

export type MigrationUnlock = {
  key: string;
  label: string;
  online_status: string;
  sh_status: string;
  unlocks: boolean;
  reason: string;
};

export type MigrationAssist = {
  eligible: boolean;
  hosting: string;
  title: string;
  body: string;
  unlocks: MigrationUnlock[];
  docs_links: { label: string; url: string }[];
  disclaimer: string;
  message: string;
};











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
  created_at: string | null;
  updated_at: string | null;
  capabilities?: CapabilityMatrix | null;
};

export type ProductionReadinessItem = {
  key: string;
  label: string;
  status: "pass" | "fail" | "warn";
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

export type ConfirmationRequiredDetail = {
  requires_confirmation: true;
  warning: string;
  risks: string[];
  confirm_phrase: string;
};

export class ConfirmationRequiredError extends Error {
  readonly requires_confirmation = true as const;
  readonly warning: string;
  readonly risks: string[];
  readonly confirm_phrase: string;
  readonly status: number;

  constructor(
    detail: {
      warning?: string;
      risks?: string[];
      confirm_phrase?: string;
      message?: string;
    },
    status = 403,
  ) {
    const warning =
      detail.warning ||
      detail.message ||
      "This action requires explicit confirmation.";
    super(warning);
    this.name = "ConfirmationRequiredError";
    this.warning = warning;
    this.risks = Array.isArray(detail.risks) ? detail.risks.map(String) : [];
    this.confirm_phrase = detail.confirm_phrase || "I understand the risks";
    this.status = status;
  }
}

function isConfirmationDetail(detail: unknown): detail is ConfirmationRequiredDetail {
  return (
    typeof detail === "object" &&
    detail !== null &&
    (detail as { requires_confirmation?: unknown }).requires_confirmation === true
  );
}

export class FeatureGatedError extends Error {
  featureKey: string;
  planId?: string;

  constructor(detail: { message?: string; feature_key?: string; plan_id?: string }) {
    super(detail.message ?? "Feature not available on your plan");
    this.name = "FeatureGatedError";
    this.featureKey = detail.feature_key ?? "";
    this.planId = detail.plan_id;
  }
}

function formatDetailMessage(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (detail == null) return "";
  if (typeof detail === "object") {
    const obj = detail as Record<string, unknown>;
    if (typeof obj.message === "string") return obj.message;
    if (typeof obj.warning === "string") return obj.warning;
    if (typeof obj.detail === "string") return obj.detail;
    try {
      return JSON.stringify(detail);
    } catch {
      return String(detail);
    }
  }
  return String(detail);
}

const API_KEY_STORAGE = "odoo_custom_api_key";

export function getStoredApiKey(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(API_KEY_STORAGE);
}

export function setStoredApiKey(key: string | null) {
  if (typeof window === "undefined") return;
  if (!key) {
    window.localStorage.removeItem(API_KEY_STORAGE);
    return;
  }
  window.localStorage.setItem(API_KEY_STORAGE, key);
}

export type AuthStatus = {
  auth_mode: string;
  auth_enabled: boolean;
  active_keys: number;
  env_key_configured: boolean;
  bootstrap_available: boolean;
};

export type EntitlementsOut = {
  workspace_id: string;
  plan_id: string;
  subscription_status: string;
  features: Record<string, string>;
  extra_project_slots: number;
  active_projects: number;
  active_project_limit: number | null;
  trial_ends_at: string | null;
  current_period_end: string | null;
};

export type BillingPlanRow = {
  id: string;
  display_name: string;
  features: Record<string, string>;
  monthly_usd: number | null;
  extra_slot_monthly_usd: number | null;
};

export type BillingPlansCatalog = {
  tier_order: string[];
  display_features: Array<{ key: string; label: string }>;
  project_pass: { display_name: string; one_time_usd: number };
  plans: BillingPlanRow[];
};

export type AccountSession = {
  user: {
    id: string;
    email: string;
    email_verified: boolean;
    totp_enabled: boolean;
    is_superadmin: boolean;
  };
  workspace: {
    id: string;
    name: string;
    slug: string;
    plan: string;
    role: string;
  };
};

export type ApiKeyRow = {
  id: string;
  name: string;
  key_prefix: string;
  created_at: string | null;
  revoked_at: string | null;
  last_used_at: string | null;
};

export type AutomationActionKind =
  | "update_field"
  | "related_write"
  | "create_activity"
  | "create_record"
  | "mail_post"
  | "python_module"
  | "code_live"
  | "webhook"
  | "sms"
  | "followers"
  | "remove_followers";

export type MailTemplateRow = {
  id: number;
  name: string;
  model: string | null;
  subject: string | null;
};

export type ServerActionOut = {
  id: number;
  name: string;
  model: string;
  model_id: number;
  state: string;
  binding_model_id: number | null;
  binding_type: string | null;
};

export type WindowActionOut = {
  id: number;
  name: string;
  res_model: string;
  view_mode: string;
  domain: string | null;
  context: string | null;
};

export type SmartButtonBundleOut = {
  window_action: WindowActionOut;
  count_field: string | null;
  count_field_id: number | null;
  button_spec: Record<string, unknown>;
};

export type XPathPreviewOut = {
  arch: string;
  issues: string[];
};

async function fetchApi(path: string, init?: RequestInit): Promise<Response> {
  const base = getApiBase();
  const url = `${base}${path}`;
  const storedKey = getStoredApiKey();
  const headers: Record<string, string> = {
    ...(storedKey ? { Authorization: `Bearer ${storedKey}` } : {}),
  };
  if (init?.body && !(init.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  try {
    return await fetch(url, {
      credentials: "include",
      ...init,
      headers: {
        ...headers,
        ...(init?.headers ?? {}),
      },
    });
  } catch (err) {
    if (err instanceof TypeError) {
      const target =
        base || (typeof window !== "undefined" ? window.location.origin : DEFAULT_API_ORIGIN);
      throw new Error(
        `Cannot reach the API${base ? ` at ${target}` : ""}. ` +
          `Start the API (uvicorn on port 8001) and restart the web dev server ` +
          `(Next /api proxy → API_PROXY_TARGET, default http://127.0.0.1:8001).`,
      );
    }
    throw err;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetchApi(path, init);
  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail !== undefined ? body.detail : body;
    } catch {
      /* ignore */
    }
    if (isConfirmationDetail(detail)) {
      throw new ConfirmationRequiredError(detail, res.status);
    }
    if (
      typeof detail === "object" &&
      detail !== null &&
      (detail as { error?: string }).error === "feature_gated"
    ) {
      throw new FeatureGatedError(detail as { message?: string; feature_key?: string; plan_id?: string });
    }
    throw new Error(formatDetailMessage(detail) || `Request failed (${res.status})`);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

export const api = {
  authStatus: () => request<AuthStatus>("/api/auth/status"),
  accountSignup: (body: { email: string; password: string; workspace_name?: string }) =>
    request<{ message: string; user_id: string; workspace_id: string }>("/api/accounts/signup", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  accountLogin: (body: { email: string; password: string; totp_code?: string }) =>
    request<AccountSession>("/api/accounts/login", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  accountLogout: () => request<void>("/api/accounts/logout", { method: "POST" }),
  accountMe: () => request<AccountSession>("/api/accounts/me"),
  accountVerifyEmail: (token: string) =>
    request<{ message: string }>("/api/accounts/verify-email", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),
  accountRequestPasswordReset: (email: string) =>
    request<void>("/api/accounts/request-password-reset", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  accountResetPassword: (token: string, password: string) =>
    request<{ message: string }>("/api/accounts/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, password }),
    }),
  accountOAuthProviders: () => request<{ providers: string[] }>("/api/accounts/oauth/providers"),
  accountOAuthComplete2FA: (body: { token: string; totp_code: string }) =>
    request<AccountSession>("/api/accounts/oauth/complete-2fa", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  accountOAuthIdentities: () =>
    request<Array<{ provider: string; email: string | null; created_at: string }>>(
      "/api/accounts/oauth/identities",
    ),
  accountOAuthUnlink: (provider: string) =>
    request<void>(`/api/accounts/oauth/${encodeURIComponent(provider)}`, { method: "DELETE" }),
  billingEntitlements: () => request<EntitlementsOut>("/api/billing/entitlements"),
  billingPlans: () => request<BillingPlansCatalog>("/api/billing/plans"),
  billingPlanDiff: (fromPlan: string, toPlan = "free_solo") =>
    request<{ from_plan: string; to_plan: string; lost_features: Array<{ feature_key: string; from: string; to: string }> }>(
      `/api/billing/plan-diff?from_plan=${encodeURIComponent(fromPlan)}&to_plan=${encodeURIComponent(toPlan)}`,
    ),
  stripeCheckout: (body: {
    plan_id: string;
    seat_quantity: number;
    success_url: string;
    cancel_url: string;
  }) =>
    request<{ checkout_url: string; session_id: string; mode: string }>("/api/billing/checkout/stripe", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  stripeExtraSlotsCheckout: (body: {
    slot_quantity: number;
    success_url: string;
    cancel_url: string;
  }) =>
    request<{ checkout_url: string; session_id: string; mode: string }>(
      "/api/billing/checkout/stripe/extra-slots",
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),
  stripePortal: () => request<{ portal_url: string }>("/api/billing/portal/stripe", { method: "POST" }),
  bootstrapApiKey: () =>
    request<{ api_key: string; key_id: string; name: string; note: string }>(
      "/api/auth/bootstrap",
      { method: "POST" },
    ),
  listApiKeys: () => request<ApiKeyRow[]>("/api/auth/keys"),
  createApiKey: (name: string) =>
    request<{ id: string; name: string; key_prefix: string; api_key: string; note: string }>(
      "/api/auth/keys",
      { method: "POST", body: JSON.stringify({ name }) },
    ),
  revokeApiKey: (keyId: string) =>
    request<void>(`/api/auth/keys/${keyId}`, { method: "DELETE" }),
  listAuditLogs: (limit = 100) =>
    request<AuditLogRow[]>(`/api/audit/logs?limit=${limit}`),
  getJob: (jobId: string) => request<JobRow>(`/api/jobs/${jobId}`),
  listAppTemplates: () => request<AppTemplate[]>("/api/apps/templates"),
  exportLibraryModule: (
    body: {
      technical_name?: string;
      display_name?: string;
      fines?: boolean;
      reminders?: boolean;
      multi_company?: boolean;
      store_ready?: boolean;
    },
    query?: { store_ready?: boolean },
  ) =>
    request<ModuleExport & { store_readiness?: StoreReadinessReport | null }>(
      `/api/apps/templates/library/export${query?.store_ready || body.store_ready ? "?store_ready=true" : ""}`,
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),
    draftModuleFromPrompt: (
    prompt: string,
    opts?: {
      connection_id?: string;
      reuse_models?: string[];
      rejected_reuse_models?: string[];
      reuse_view_ids?: number[];
      reuse_action_ids?: number[];
      expand?: boolean;
      grain?: string | null;
      gallery_id?: string | null;
      host_model?: string | null;
      connect_points?: Record<string, unknown> | null;
      overlap_choice?: string | null;
      overlap_finding_id?: string | null;
      async_job?: boolean;
    },
  ) =>
    request<{
      ok: boolean;
      draft: Record<string, unknown>;
      raw_response?: string | null;
      note?: string;
      warnings?: string[];
      refusals?: ProtectedModuleRefusal[];
      domain_pack?: string | null;
      grain?: string | null;
      grain_label?: string | null;
      connect_points?: Record<string, unknown> | null;
      host_candidates?: Array<{
        model: string;
        label: string;
        score: number;
        reason?: string;
      }>;
      job_id?: string | null;
    }>("/api/ai/draft-module", {
      method: "POST",
      body: JSON.stringify({
        prompt,
        connection_id: opts?.connection_id,
        reuse_models: opts?.reuse_models ?? [],
        rejected_reuse_models: opts?.rejected_reuse_models ?? [],
        reuse_view_ids: opts?.reuse_view_ids ?? [],
        reuse_action_ids: opts?.reuse_action_ids ?? [],
        expand: opts?.expand ?? true,
        grain: opts?.grain || undefined,
        gallery_id: opts?.gallery_id || undefined,
        host_model: opts?.host_model || undefined,
        connect_points: opts?.connect_points ?? undefined,
        overlap_choice: opts?.overlap_choice || undefined,
        overlap_finding_id: opts?.overlap_finding_id || undefined,
        async_job: opts?.async_job ?? false,
      }),
    }),
  enrichDraft: (body: {
    prompt: string;
    draft: Record<string, unknown>;
    connection_id?: string;
    failed_steps?: string[];
    async_job?: boolean;
  }) =>
    request<{
      ok: boolean;
      draft: Record<string, unknown>;
      warnings?: string[];
      job_id?: string;
      note?: string;
    }>("/api/ai/enrich-draft", {
      method: "POST",
      body: JSON.stringify({ ...body, async_job: body.async_job ?? true }),
    }),
  reapplyReusePlan: (body: {
    prompt: string;
    draft: Record<string, unknown>;
    connection_id?: string;
    reuse_models?: string[];
    rejected_reuse_models?: string[];
  }) =>
    request<{
      ok: boolean;
      draft: Record<string, unknown>;
      warnings?: string[];
    }>("/api/ai/reapply-reuse", {
      method: "POST",
      body: JSON.stringify({
        prompt: body.prompt,
        draft: body.draft,
        connection_id: body.connection_id,
        reuse_models: body.reuse_models ?? [],
        rejected_reuse_models: body.rejected_reuse_models ?? [],
      }),
    }),
  proposeConnectPoints: (body: {
    prompt: string;
    connection_id?: string;
    grain?: string | null;
    gallery_id?: string | null;
    host_model?: string | null;
    connect_points?: Record<string, unknown> | null;
  }) =>
    request<{
      ok: boolean;
      grain: string;
      grain_label: string;
      connect_points?: Record<string, unknown> | null;
      host_candidates?: Array<{
        model: string;
        label: string;
        score: number;
        reason?: string;
      }>;
      requires_review: boolean;
      warnings?: string[];
      gallery_id?: string | null;
    }>("/api/ai/propose-connect-points", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  checkOverlap: (body: {
    prompt: string;
    connection_id?: string;
    grain?: string | null;
    host_model?: string | null;
  }) =>
    request<{
      ok: boolean;
      grain: string;
      grain_label: string;
      findings: Array<{
        id: string;
        source: string;
        title: string;
        evidence: string;
        confidence: number;
        artifact_type: string;
        artifact_ref: Record<string, unknown>;
        deep_link?: string | null;
        extend_host_model?: string | null;
        options: string[];
      }>;
      semantic_pass_ran: boolean;
      requires_review: boolean;
    }>("/api/ai/check-overlap", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  generalizeComponent: (body: {
    spec_json: Record<string, unknown>;
    consent_share_template: boolean;
    host_slot?: string | null;
    pack_slug?: string | null;
  }) =>
    request<{
      ok: boolean;
      filename: string;
      source: string;
      domain_pack: string;
      host_slot: string;
      connect_points_template?: Record<string, unknown>;
      note: string;
      warnings: string[];
    }>("/api/ai/generalize-component", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  generalizePack: (body: {
    spec_json?: Record<string, unknown>;
    project_id?: string;
    connection_id?: string;
    pack_slug?: string;
    consent_share_template: boolean;
  }) =>
    request<{
      ok: boolean;
      filename: string;
      source: string;
      domain_pack: string;
      suggested_tags: string[];
      anti_patterns: string[];
      model_count: number;
      warnings: string[];
      note: string;
    }>("/api/ai/generalize-pack", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  validateModuleSpecLive: (connectionId: string, body: { spec: Record<string, unknown> }) =>
    request<ValidateLiveResult>(
      `/api/connections/${connectionId}/module-spec/validate-live`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  applyModuleSpec: (
    connectionId: string,
    body: {
      spec: Record<string, unknown>;
      apply_views?: boolean;
      apply_menus?: boolean;
      apply_smart_buttons?: boolean;
      apply_automations?: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
      skip_validate_live?: boolean;
    },
  ) =>
    request<{
      ok: boolean;
      models_created: string[];
      fields_created: number;
      views_created: number;
      views_updated: number;
      menus_created: number;
      smart_buttons: number;
      automations_created?: number;
      skipped: string[];
      warnings: string[];
      message: string;
    }>(`/api/connections/${connectionId}/module-spec/apply`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  lintModuleSpecBlocks: (connectionId: string, spec: Record<string, unknown>) =>
    request<{ ok: boolean; blocks: Array<{ source_file?: string; issues?: { message: string }[] }> }>(
      `/api/connections/${connectionId}/module-spec/lint-blocks`,
      { method: "POST", body: JSON.stringify({ spec }) },
    ),
  exportModuleSpecSandbox: (
    connectionId: string,
    body: { spec: Record<string, unknown>; async_job?: boolean; odoo_major?: number | null },
  ) =>
    request<{ ok: boolean; job_id?: string; validation_id?: string; message?: string }>(
      `/api/connections/${connectionId}/module-spec/export-sandbox`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  getScriptRunnerTemplates: (connectionId: string) =>
    request<{ templates: Array<{ id: string; label: string; description: string; code: string }> }>(
      `/api/connections/${connectionId}/script-runner/templates`,
    ),
  listScriptRuns: (connectionId: string) =>
    request<
      Array<{
        id: string;
        status: string;
        script_content: string;
        stdout: string | null;
        stderr: string | null;
        write_counts: Record<string, unknown>;
        error: string | null;
        created_at: string | null;
      }>
    >(`/api/connections/${connectionId}/script-runner/runs`),
  runScript: (
    connectionId: string,
    body: {
      script: string;
      async_job?: boolean;
      count_writes?: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<{ ok: boolean; async?: boolean; job_id?: string; run_id?: string }>(
      `/api/connections/${connectionId}/script-runner/run`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  listSavedScripts: (connectionId: string) =>
    request<
      Array<{ id: string; name: string; description: string | null; script_content: string; shared: boolean }>
    >(`/api/connections/${connectionId}/script-runner/library`),
  saveScript: (
    connectionId: string,
    body: { name: string; description?: string | null; script_content: string; shared?: boolean },
  ) =>
    request<{ id: string; name: string }>(`/api/connections/${connectionId}/script-runner/library`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  aiStatus: () =>
    request<{
      ai_assist: string;
      enabled: boolean;
      ollama_base_url: string;
      ollama_model: string;
      ollama_reachable?: boolean;
      ollama_detail?: string;
      domain_packs?: string;
    }>("/api/ai/status"),
  scaffoldApp: (
    connectionId: string,
    body: {
      template_id: string;
      display_name?: string;
      technical_prefix?: string | null;
      multi_company?: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<ScaffoldResult>(`/api/connections/${connectionId}/apps/scaffold`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  cancelJob: (jobId: string) =>
    request<JobRow>(`/api/jobs/${jobId}/cancel`, { method: "POST" }),
  suggestDepends: (connectionId: string) =>
    request<SuggestDependsOut>(
      `/api/connections/${connectionId}/suggest-depends`,
    ),
  projectDiff: (connectionId: string, projectId: string) =>
    request<ProjectDiffOut>(
      `/api/connections/${connectionId}/projects/${projectId}/diff`,
    ),
  createReminder: (connectionId: string, body: ReminderCreateBody) =>
    request<ReminderCreateOut>(`/api/connections/${connectionId}/reminders`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  libraryStats: (connectionId: string) =>
    request<{
      available: boolean;
      book_model: string | null;
      loan_model: string | null;
      books: number | null;
      loans: number | null;
      active_loans: number | null;
      overdue_loans: number | null;
      message: string;
    }>(`/api/connections/${connectionId}/library/stats`),
  listConnections: () => request<Connection[]>("/api/connections"),
  getConnection: (id: string) =>
    request<Connection>(`/api/connections/${id}`),
  createConnection: (body: {
    name: string;
    url: string;
    db_name: string;
    username: string;
    password: string;
    verify?: boolean;
  }) =>
    request<Connection>("/api/connections", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateConnection: (
    id: string,
    body: {
      name?: string;
      url?: string;
      db_name?: string;
      username?: string;
      password?: string;
      verify?: boolean;
    },
  ) =>
    request<Connection>(`/api/connections/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  updateConnectionWriteMode: (id: string, write_mode: Connection["write_mode"]) =>
    request<Connection>(`/api/connections/${id}/write-mode`, {
      method: "PATCH",
      body: JSON.stringify({ write_mode }),
    }),
  getProductionReadiness: (id: string) =>
    request<ProductionReadinessReport>(`/api/connections/${id}/production-readiness`),
  runProductionSnapshotDrill: (id: string) =>
    request<{ ok: boolean; snapshot_id: string; report: ProductionReadinessReport }>(
      `/api/connections/${id}/production-readiness/snapshot-drill`,
      { method: "POST" },
    ),
  confirmProductionLeastPrivilege: (id: string, acknowledge_admin: boolean) =>
    request<ProductionReadinessReport>(
      `/api/connections/${id}/production-readiness/confirm-least-privilege`,
      { method: "POST", body: JSON.stringify({ acknowledge_admin }) },
    ),
  verifyProductionBackupArtifact: (id: string) =>
    request<ProductionReadinessReport>(
      `/api/connections/${id}/production-readiness/verify-backup-artifact`,
      { method: "POST" },
    ),
  ackProductionFirstWrite: (id: string) =>
    request<ProductionReadinessReport>(
      `/api/connections/${id}/production-readiness/ack-first-write`,
      { method: "POST" },
    ),
  getSafetyContract: () => request<{ markdown: string; source: string }>("/api/trust/safety"),
  deleteConnection: (id: string) =>
    request<void>(`/api/connections/${id}`, { method: "DELETE" }),
  probeConnection: (id: string) =>
    request<{
      ok: boolean;
      uid: number | null;
      server_version: string | null;
      capabilities: CapabilityMatrix | null;
    }>(`/api/connections/${id}/probe`, { method: "POST" }),
  listModules: (
    id: string,
    applicationsOnlyOrOpts:
      | boolean
      | { applicationsOnly?: boolean; installedOnly?: boolean } = false,
  ) => {
    const opts =
      typeof applicationsOnlyOrOpts === "boolean"
        ? { applicationsOnly: applicationsOnlyOrOpts, installedOnly: true }
        : {
            applicationsOnly: applicationsOnlyOrOpts.applicationsOnly ?? false,
            installedOnly: applicationsOnlyOrOpts.installedOnly ?? true,
          };
    const params = new URLSearchParams({
      applications_only: String(opts.applicationsOnly),
      installed_only: String(opts.installedOnly),
    });
    return request<ModuleRow[]>(`/api/connections/${id}/modules?${params}`);
  },
  listInstalledModules: (id: string, q?: string) => {
    const params = new URLSearchParams();
    if (q?.trim()) params.set("q", q.trim());
    const qs = params.toString();
    return request<ModuleRow[]>(
      `/api/connections/${id}/modules/installed${qs ? `?${qs}` : ""}`,
    );
  },
  listModels: (id: string, customOnly = false, limit = 2000) =>
    request<ModelRow[]>(
      `/api/connections/${id}/models?custom_only=${customOnly}&limit=${limit}`,
    ),
  listReuseCatalog: (id: string, q?: string, limit = 2000) => {
    const params = new URLSearchParams({ limit: String(limit), stock_only: "true" });
    if (q?.trim()) params.set("q", q.trim());
    return request<ReuseModelRow[]>(
      `/api/connections/${id}/reuse-catalog?${params.toString()}`,
    );
  },
  listDraftCache: (connectionId?: string, limit = 20) => {
    const qs = connectionId
      ? `?connection_id=${encodeURIComponent(connectionId)}&limit=${limit}`
      : `?limit=${limit}`;
    return request<
      Array<{
        id: string;
        connection_id: string | null;
        prompt: string;
        summary: string;
        domain_pack: string | null;
        draft: Record<string, unknown>;
        updated_at: string | null;
      }>
    >(`/api/ai/draft-cache${qs}`);
  },
  getDraftCache: (cacheId: string) =>
    request<{
      id: string;
      prompt: string;
      summary: string;
      draft: Record<string, unknown>;
    }>(`/api/ai/draft-cache/${cacheId}`),
  modelTier: (connectionId: string, model: string) =>
    request<{ model: string; tier: ProtectedTier | null }>(
      `/api/connections/${connectionId}/model-tier?model=${encodeURIComponent(model)}`,
    ),
  listFields: (id: string, model: string) =>
    request<FieldRow[]>(`/api/connections/${id}/models/${encodeURIComponent(model)}/fields`),
  listViews: (id: string, model: string) =>
    request<ViewRow[]>(`/api/connections/${id}/models/${encodeURIComponent(model)}/views`),
  createModel: (
    id: string,
    body: {
      name: string;
      model: string;
      transient?: boolean;
      with_defaults?: boolean;
      enable_mail_thread?: boolean;
    },
  ) =>
    request<
      ModelRow & { warnings?: string[]; mail_thread_enabled?: boolean }
    >(`/api/connections/${id}/models`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createRelationalPair: (
    id: string,
    body: {
      parent_model: string;
      child_model: string;
      parent_o2m_name: string;
      child_m2o_name: string;
      parent_o2m_string: string;
      child_m2o_string: string;
      inject_into_views?: boolean;
    },
  ) =>
    request<{
      ok: boolean;
      parent_model: string;
      child_model: string;
      parent_o2m_name: string;
      child_m2o_name: string;
      m2o_created: boolean;
      o2m_created: boolean;
      injected_view_ids: number[];
      warnings: string[];
    }>(`/api/connections/${id}/fields/relational_pair`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listProjects: (id: string) =>
    request<
      {
        id: string;
        connection_id: string;
        name: string;
        template_id: string | null;
        spec_json: Record<string, unknown>;
        status: string;
        lifecycle_status?: string;
        created_at?: string | null;
        updated_at?: string | null;
      }[]
    >(`/api/connections/${id}/projects`),
  archiveProject: (id: string, projectId: string) =>
    request<{ lifecycle_status: string }>(`/api/connections/${id}/projects/${projectId}/archive`, {
      method: "POST",
    }),
  unarchiveProject: (id: string, projectId: string) =>
    request<{ lifecycle_status: string }>(`/api/connections/${id}/projects/${projectId}/unarchive`, {
      method: "POST",
    }),
  createProject: (
    id: string,
    body: {
      name: string;
      template_id?: string | null;
      spec_json?: Record<string, unknown>;
    },
  ) =>
    request<{
      id: string;
      connection_id: string;
      name: string;
      template_id: string | null;
      spec_json: Record<string, unknown>;
      status: string;
    }>(`/api/connections/${id}/projects`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getProject: (id: string, projectId: string) =>
    request<{
      id: string;
      connection_id: string;
      name: string;
      template_id: string | null;
      spec_json: Record<string, unknown>;
      status: string;
    }>(`/api/connections/${id}/projects/${projectId}`),
  updateProject: (
    id: string,
    projectId: string,
    body: {
      name?: string;
      template_id?: string | null;
      spec_json?: Record<string, unknown>;
      status?: string;
    },
  ) =>
    request<{
      id: string;
      connection_id: string;
      name: string;
      template_id: string | null;
      spec_json: Record<string, unknown>;
      status: string;
    }>(`/api/connections/${id}/projects/${projectId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  importModuleSpec: async (file: File) => {
    const res = await fetchApi("/api/module-spec/import", {
      method: "POST",
      body: form,
    });
    if (!res.ok) {
      let detail: unknown = res.statusText;
      try {
        const body = await res.json();
        detail = body.detail !== undefined ? body.detail : body;
      } catch {
        /* ignore */
      }
      throw new Error(
        typeof detail === "string" ? detail : JSON.stringify(detail),
      );
    }
    return res.json() as Promise<{
      ok: boolean;
      spec: Record<string, unknown>;
      warnings: string[];
      unmapped: Record<string, unknown>[];
      source: string;
      note?: string;
    }>;
  },
  applyProject: (
    id: string,
    projectId: string,
    body: { confirm_advanced?: boolean; confirm_phrase?: string | null },
  ) =>
    request<{
      ok: boolean;
      project_id: string;
      models_created: string[];
      fields_created: number;
      skipped: string[];
      warnings: string[];
      message: string;
    }>(`/api/connections/${id}/projects/${projectId}/apply`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  deleteProject: (id: string, projectId: string) =>
    request<void>(`/api/connections/${id}/projects/${projectId}`, {
      method: "DELETE",
    }),
  createField: (
    id: string,
    body: {
      model: string;
      name: string;
      field_description: string;
      ttype: string;
      required?: boolean;
      readonly?: boolean;
      relation?: string | null;
      relation_field?: string | null;
      selection?: { value: string; label: string }[] | null;
      help?: string | null;
      related?: string | null;
      currency_field?: string | null;
      on_delete?: "set null" | "restrict" | "cascade" | null;
      inject_into_views?: boolean;
      inject_strategy?: "inherit" | "mutate";
      view_widget?: string | null;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<FieldCreateRow>(`/api/connections/${id}/fields`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listBuilderWidgets: (id: string, ttype: string) =>
    request<BuilderWidgetOption[]>(
      `/api/connections/${id}/builder/widgets?ttype=${encodeURIComponent(ttype)}`,
    ),
  listRelatedPaths: (id: string, model: string, depth = 2) =>
    request<RelatedPathOption[]>(
      `/api/connections/${id}/builder/related-paths?model=${encodeURIComponent(model)}&depth=${depth}`,
    ),
  listNicheWidgets: (id: string, viewType: string) =>
    request<NicheWidgetsResponse>(
      `/api/connections/${id}/builder/niche-widgets?view_type=${encodeURIComponent(viewType)}`,
    ),
  getPreviewTheme: (id: string) =>
    request<PreviewTheme>(`/api/connections/${id}/preview-theme`),
  getPropertyFieldsProbe: (id: string) =>
    request<PropertyFieldsProbeOut>(`/api/connections/${id}/builder/properties/probe`),
  setupPropertyFields: (
    id: string,
    body: {
      child_model: string;
      parent_m2o_field: string;
      properties_field?: string;
      definition_field?: string;
      properties_label?: string;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<PropertyFieldsSetupOut>(`/api/connections/${id}/builder/properties/setup`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  writePropertyDefinition: (
    id: string,
    body: {
      parent_model: string;
      parent_record_id: number;
      definition_field?: string;
      entries: Array<{
        name: string;
        string?: string;
        type?: string;
        default?: string | number | boolean | null;
        selection?: string[][];
        comodel?: string;
      }>;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<PropertyDefinitionWriteOut>(`/api/connections/${id}/builder/properties/definition`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getInvoicingPreflight: (id: string) =>
    request<InvoicingPreflightOut>(`/api/connections/${id}/builder/invoicing/preflight`),
  connectInvoicing: (
    id: string,
    body: {
      model: string;
      invoice_field?: string;
      smart_button_name?: string;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<InvoicingConnectOut>(`/api/connections/${id}/builder/invoicing/connect`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createDraftInvoice: (
    id: string,
    body: {
      source_model: string;
      record_id: number;
      invoice_field?: string;
      partner_field?: string;
      amount_field?: string;
      description_field?: string;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<InvoicingDraftInvoiceOut>(`/api/connections/${id}/builder/invoicing/draft-invoice`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getInvoicingModuleSpec: (
    id: string,
    body: {
      model: string;
      invoice_field?: string;
      origin_field_on_move?: string;
      partner_field?: string;
    },
  ) =>
    request<InvoicingModuleSpecOut>(`/api/connections/${id}/builder/invoicing/module-spec`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  mergeInvoicingIntoSpec: (
    id: string,
    body: {
      base_spec?: Record<string, unknown>;
      model: string;
      invoice_field?: string;
      origin_field_on_move?: string;
      partner_field?: string;
    },
  ) =>
    request<InvoicingMergeSpecOut>(`/api/connections/${id}/builder/invoicing/merge-into-spec`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getDocumentsGate: (id: string) =>
    request<{
      ok: boolean;
      available: boolean;
      verify_state?: string | null;
      folder_model?: string | null;
      message?: string | null;
      note?: string | null;
    }>(`/api/connections/${id}/builder/documents/gate`),
  getDocumentsFolderMap: (id: string) =>
    request<{ ok: boolean; mapping: Record<string, number> }>(
      `/api/connections/${id}/builder/documents/folder-map`,
    ),
  setDocumentsFolder: (
    id: string,
    body: { model: string; folder_id?: number | null },
  ) =>
    request<{ ok: boolean; mapping: Record<string, number> }>(
      `/api/connections/${id}/builder/documents/folder-map`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  mergeDocumentsIntoSpec: (
    id: string,
    body: {
      base_spec?: Record<string, unknown>;
      model: string;
      folder_id: number;
    },
  ) =>
    request<{ ok: boolean; merged: Record<string, unknown> }>(
      `/api/connections/${id}/builder/documents/merge-into-spec`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  bulkScanFind: (
    id: string,
    body: { model: string; field: string; value: string; limit?: number },
  ) =>
    request<ScanFindOut>(`/api/connections/${id}/bulk/scan-find`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateField: (
    id: string,
    fieldId: number,
    body: {
      string?: string;
      field_description?: string;
      help?: string | null;
      required?: boolean;
      readonly?: boolean;
      tracking?: boolean;
      selection?: string | null;
    },
  ) =>
    request<FieldRow>(`/api/connections/${id}/fields/${fieldId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteField: (
    id: string,
    fieldId: number,
    body: {
      mode?: "deprecate" | "hard_delete";
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<{
      ok: boolean;
      field_id: number;
      mode: "deprecate" | "hard_delete";
      snapshot_id: string | null;
      artifact_id?: string | null;
      artifact_url?: string | null;
      row_count?: number | null;
      truncated?: boolean | null;
      new_field_name?: string | null;
    }>(`/api/connections/${id}/fields/${fieldId}`, {
      method: "DELETE",
      body: JSON.stringify(body),
    }),
  deleteModel: (
    id: string,
    model: string,
    body: { confirm_advanced?: boolean; confirm_phrase?: string | null },
  ) =>
    request<{ ok: boolean; model: string; snapshot_id: string | null }>(
      `/api/connections/${id}/models/${encodeURIComponent(model)}`,
      { method: "DELETE", body: JSON.stringify(body) },
    ),
  getView: (id: string, viewId: number) =>
    request<ViewRow>(`/api/connections/${id}/views/${viewId}`),
  exportModule: (
    id: string,
    body: {
      technical_name: string;
      display_name: string;
      include_custom_models?: boolean;
      include_extensions?: boolean;
      include_views?: boolean;
      include_reports?: boolean;
      install_mode?: string;
      model_filter?: string[] | null;
      extend_models?: string[] | null;
      depends?: string[] | null;
      store_ready?: boolean;
    },
    query?: { store_ready?: boolean },
  ) =>
    request<
      ModuleExport & {
        model_count: number;
        view_count: number;
        report_count?: number;
        target_major?: number | null;
        manifest_version?: string | null;
        warnings?: string[];
        store_readiness?: StoreReadinessReport | null;
      }
    >(
      `/api/connections/${id}/export-module${query?.store_ready ? "?store_ready=true" : body.store_ready ? "?store_ready=true" : ""}`,
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),
  getMigrationAssist: (id: string) =>
    request<MigrationAssist>(`/api/connections/${id}/migration-assist`),
  runSandbox: (
    id: string,
    body: {
      technical_name?: string;
      display_name?: string;
      include_custom_models?: boolean;
      include_extensions?: boolean;
      include_views?: boolean;
      model_filter?: string[] | null;
      extend_models?: string[] | null;
      depends?: string[] | null;
      extra_modules?: string[] | null;
      zip_base64?: string | null;
      keep_alive?: boolean;
      async_job?: boolean;
    },
  ) =>
    request<SandboxRunResult>(`/api/connections/${id}/sandbox/run`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  promoteModule: (
    id: string,
    body: {
      technical_name?: string;
      display_name?: string;
      include_custom_models?: boolean;
      include_views?: boolean;
      model_filter?: string[] | null;
      install_mode?: string;
      zip_base64?: string | null;
      validation_id?: string | null;
      run_sandbox?: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<PromoteResult>(`/api/connections/${id}/modules/promote`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listPromotedModules: (id: string) =>
    request<PromotedModuleRow[]>(`/api/connections/${id}/modules/promoted`),
  uninstallModule: (
    id: string,
    body: {
      module_name: string;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<UninstallResult>(`/api/connections/${id}/modules/uninstall`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listGroups: (id: string) =>
    request<GroupRow[]>(`/api/connections/${id}/access/groups`),
  listAccessRights: (id: string, model?: string) =>
    request<AccessRightRow[]>(
      `/api/connections/${id}/access/rights${model ? `?model=${encodeURIComponent(model)}` : ""}`,
    ),
  createAccessRight: (
    id: string,
    body: {
      model: string;
      name: string;
      group_id?: number | null;
      perm_read?: boolean;
      perm_write?: boolean;
      perm_create?: boolean;
      perm_unlink?: boolean;
      active?: boolean;
    },
  ) =>
    request<AccessRightRow>(`/api/connections/${id}/access/rights`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateAccessRight: (
    id: string,
    accessId: number,
    body: {
      name?: string;
      group_id?: number | null;
      clear_group?: boolean;
      perm_read?: boolean;
      perm_write?: boolean;
      perm_create?: boolean;
      perm_unlink?: boolean;
      active?: boolean;
    },
  ) =>
    request<AccessRightRow>(`/api/connections/${id}/access/rights/${accessId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteAccessRight: (
    id: string,
    accessId: number,
    body: { confirm_advanced?: boolean; confirm_phrase?: string | null },
  ) =>
    request<{ ok: boolean; access_id: number; snapshot_id: string | null }>(
      `/api/connections/${id}/access/rights/${accessId}`,
      { method: "DELETE", body: JSON.stringify(body) },
    ),
  listRecordRules: (id: string, model?: string) =>
    request<RecordRuleRow[]>(
      `/api/connections/${id}/access/rules${model ? `?model=${encodeURIComponent(model)}` : ""}`,
    ),
  createRecordRule: (
    id: string,
    body: {
      model: string;
      name: string;
      domain_force: string;
      group_ids?: number[];
      perm_read?: boolean;
      perm_write?: boolean;
      perm_create?: boolean;
      perm_unlink?: boolean;
      active?: boolean;
    },
  ) =>
    request<RecordRuleRow>(`/api/connections/${id}/access/rules`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateRecordRule: (
    id: string,
    ruleId: number,
    body: {
      name?: string;
      domain_force?: string;
      group_ids?: number[];
      perm_read?: boolean;
      perm_write?: boolean;
      perm_create?: boolean;
      perm_unlink?: boolean;
      active?: boolean;
    },
  ) =>
    request<RecordRuleRow>(`/api/connections/${id}/access/rules/${ruleId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteRecordRule: (
    id: string,
    ruleId: number,
    body: { confirm_advanced?: boolean; confirm_phrase?: string | null },
  ) =>
    request<{ ok: boolean; rule_id: number; snapshot_id: string | null }>(
      `/api/connections/${id}/access/rules/${ruleId}`,
      { method: "DELETE", body: JSON.stringify(body) },
    ),
  getMultiCompanyGuidance: (id: string) =>
    request<{ title: string; body: string }>(
      `/api/connections/${id}/access/multi-company/guidance`,
    ),
  applyMultiCompanyDraft: (id: string, draft: Record<string, unknown>) =>
    request<{ ok: boolean; draft: Record<string, unknown> }>(
      `/api/connections/${id}/access/multi-company/apply-draft`,
      { method: "POST", body: JSON.stringify({ draft }) },
    ),
  applyMultiCompanyLive: (id: string, models: string[]) =>
    request<{
      ok: boolean;
      models: string[];
      fields_created: number;
      rules_created: number;
      warnings: string[];
    }>(`/api/connections/${id}/access/multi-company/apply-live`, {
      method: "POST",
      body: JSON.stringify({ models }),
    }),
  previewViewArch: (id: string, view_type: string, spec: unknown) =>
    request<{ arch: string }>(`/api/connections/${id}/views/preview`, {
      method: "POST",
      body: JSON.stringify({ view_type, spec }),
    }),
  parseViewArch: (id: string, view_type: string, arch: string) =>
    request<{ view_type: string; spec: Record<string, unknown> }>(
      `/api/connections/${id}/views/parse`,
      {
        method: "POST",
        body: JSON.stringify({ view_type, arch }),
      },
    ),
  listBindableActions: (id: string, model: string) =>
    request<
      Array<{
        id: number;
        name: string;
        action_type: "ir.actions.server" | "ir.actions.act_window";
        model: string;
        detail: string | null;
      }>
    >(`/api/connections/${id}/actions/bindable?model=${encodeURIComponent(model)}`),
  createUpdateFieldAction: (
    id: string,
    body: {
      name: string;
      model: string;
      field_name: string;
      value: string;
      bind_to_model?: boolean;
    },
  ) =>
    request<{
      id: number;
      name: string;
      model: string;
      model_id: number;
      state: string;
      binding_model_id: number | null;
      binding_type: string | null;
    }>(`/api/connections/${id}/actions/server/update-field`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createRelatedWindowAction: (
    id: string,
    body: {
      name: string;
      source_model: string;
      target_model: string;
      relation_field: string;
      view_mode?: string;
    },
  ) =>
    request<WindowActionOut>(`/api/connections/${id}/actions/window/related`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createNextActivityAction: (
    id: string,
    body: {
      name: string;
      model: string;
      activity_type_id: number;
      summary?: string;
      note?: string | null;
      user_type?: "specific" | "generic";
      user_id?: number | null;
      user_field_name?: string | null;
      bind_to_model?: boolean;
    },
  ) =>
    request<ServerActionOut>(`/api/connections/${id}/actions/server/next-activity`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createMailPostAction: (
    id: string,
    body: {
      name: string;
      model: string;
      template_id?: number | null;
      mail_post_method?: "email" | "comment" | "note";
      subject?: string | null;
      body_html?: string | null;
      email_to?: string | null;
      bind_to_model?: boolean;
    },
  ) =>
    request<ServerActionOut>(`/api/connections/${id}/actions/server/mail-post`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createSmartButtonBundle: (
    id: string,
    body: {
      name: string;
      source_model: string;
      target_model: string;
      relation_field: string;
      one2many_field?: string | null;
      count_field_name?: string | null;
      create_count_field?: boolean;
      icon?: string;
      view_mode?: string;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<SmartButtonBundleOut>(`/api/connections/${id}/actions/smart-button`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listMailTemplates: (id: string, model?: string) => {
    const qs = model ? `?model=${encodeURIComponent(model)}` : "";
    return request<MailTemplateRow[]>(
      `/api/connections/${id}/actions/mail-templates${qs}`,
    );
  },
  xpathPreview: (
    id: string,
    body: {
      expr: string;
      position?: "inside" | "after" | "before" | "replace" | "attributes";
      body_xml: string;
    },
  ) =>
    request<XPathPreviewOut>(`/api/connections/${id}/views/xpath/preview`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getPrimaryView: (id: string, model: string, view_type: string) =>
    request<ViewRow>(
      `/api/connections/${id}/views/primary?model=${encodeURIComponent(model)}&view_type=${encodeURIComponent(view_type)}`,
    ),
  resolveFieldNode: (
    id: string,
    body: { view_type: string; arch: string; field_name: string },
  ) =>
    request<{
      field_name: string;
      candidates: Array<{ xpath: string; match?: string; from_spec?: boolean }>;
      ambiguous: boolean;
    }>(`/api/connections/${id}/views/resolve-field`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  overlayPreview: (
    id: string,
    body: Record<string, unknown>,
  ) =>
    request<{ xpath_arch: string; issues: string[] }>(
      `/api/connections/${id}/views/overlay/preview`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  applyOverlayOp: (
    id: string,
    body: Record<string, unknown>,
  ) =>
    request<{
      xpath_arch: string;
      issues: string[];
      view_id?: number | null;
      snapshot_id?: string | null;
      inherit_name?: string | null;
    }>(`/api/connections/${id}/views/overlay/apply`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  previewFrameUrl: (id: string, model: string, view_type: string) =>
    `/api/connections/${id}/preview/frame?model=${encodeURIComponent(model)}&view_type=${encodeURIComponent(view_type)}`,
  saveView: (
    id: string,
    body: {
      model: string;
      view_type: string;
      name?: string;
      view_id?: number;
      spec?: unknown;
      arch?: string;
      create_if_missing?: boolean;
      strategy?: "inherit" | "overwrite";
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<ViewRow>(`/api/connections/${id}/views/save`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  polishForm: (
    id: string,
    model: string,
    string?: string | null,
    confirm?: { confirm_advanced?: boolean; confirm_phrase?: string | null },
  ) =>
    request<{
      model: string;
      view_id: number | null;
      applied: boolean;
      detail: Record<string, unknown>;
    }>(`/api/connections/${id}/views/polish-form`, {
      method: "POST",
      body: JSON.stringify({
        model,
        string: string ?? null,
        ...(confirm || {}),
      }),
    }),
  listAutomations: (id: string, model?: string) =>
    request<AutomationRow[]>(
      `/api/connections/${id}/automations${model ? `?model=${encodeURIComponent(model)}` : ""}`,
    ),
  listActivityTypes: (id: string) =>
    request<ActivityTypeRow[]>(`/api/connections/${id}/automations/activity-types`),
  getAutomationsGate: (id: string) =>
    request<AutomationsGateResponse>(`/api/connections/${id}/automations/gate`),
  getCodeStudioGate: (id: string) =>
    request<CodeStudioGateResponse>(`/api/connections/${id}/code-studio/gate`),
  probeCodeStudio: (id: string) =>
    request<Record<string, unknown>>(`/api/connections/${id}/code-studio/probe`, {
      method: "POST",
    }),
  getCodeStudioContext: (id: string) =>
    request<{ major: number | null; symbols: { name: string; description: string }[] }>(
      `/api/connections/${id}/code-studio/context`,
    ),
  getCodeStudioSnippets: (id: string) =>
    request<{ snippets: { id: string; label: string; code: string }[] }>(
      `/api/connections/${id}/code-studio/snippets`,
    ),
  validateCodeStudio: (id: string, code: string) =>
    request<CodeStudioValidateResult>(`/api/connections/${id}/code-studio/validate`, {
      method: "POST",
      body: JSON.stringify({ code }),
    }),
  testRunCodeStudio: (
    id: string,
    body: { model: string; record_id?: number | null; code: string },
  ) =>
    request<CodeStudioTestRunResult>(`/api/connections/${id}/code-studio/test-run`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  bindCodeStudio: (
    id: string,
    body: {
      name: string;
      model: string;
      code: string;
      bind_kind: "standalone" | "model_button" | "automation";
      bind_to_model?: boolean;
      trigger?: string | null;
      filter_domain?: string | null;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<CodeStudioBindResult>(`/api/connections/${id}/code-studio/bind`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getAutomationTriggers: (id: string) =>
    request<AutomationTriggersResponse>(`/api/connections/${id}/automations/triggers`),
  getApprovalsGate: (id: string) =>
    request<ApprovalsGateResponse>(`/api/connections/${id}/approvals/gate`),
  listApprovalRules: (id: string) =>
    request<ApprovalRule[]>(`/api/connections/${id}/approvals/rules`),
  listApprovalButtons: (id: string, model: string) =>
    request<ApprovalButton[]>(
      `/api/connections/${id}/approvals/buttons?model=${encodeURIComponent(model)}`,
    ),
  createApprovalRule: (
    id: string,
    body: {
      name: string;
      target_model: string;
      button_method: string;
      button_label?: string | null;
      steps: ApprovalStep[];
      engine?: string | null;
    },
  ) =>
    request<ApprovalRule>(`/api/connections/${id}/approvals/rules`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  checkApprovalAction: (id: string, ruleId: string, recordId: number, actorUserId?: number) =>
    request<{ allowed: boolean; message: string; pending_step?: number | null; entry_id?: string }>(
      `/api/connections/${id}/approvals/rules/${ruleId}/check`,
      {
        method: "POST",
        body: JSON.stringify({ record_id: recordId, actor_user_id: actorUserId }),
      },
    ),
  approveApprovalEntry: (
    id: string,
    entryId: string,
    body: { actor_user_id: number; approve?: boolean },
  ) =>
    request<ApprovalEntry>(`/api/connections/${id}/approvals/entries/${entryId}/approve`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listApprovalEntries: (id: string, ruleId?: string) =>
    request<ApprovalEntry[]>(
      `/api/connections/${id}/approvals/entries${ruleId ? `?rule_id=${encodeURIComponent(ruleId)}` : ""}`,
    ),
  getProcessGate: (id: string) =>
    request<ProcessGateResponse>(`/api/connections/${id}/approvals/processes/gate`),
  listProcessTypes: (id: string) =>
    request<ProcessTypeRow[]>(`/api/connections/${id}/approvals/processes/types`),
  listProcessRequests: (id: string) =>
    request<ProcessRequestRow[]>(`/api/connections/${id}/approvals/processes/requests`),
  createProcessRequest: (
    id: string,
    body: { type_id: number; subject: string; amount?: number; requester_id?: number },
  ) =>
    request<{ id: number; state: string }>(`/api/connections/${id}/approvals/processes/requests`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  submitProcessRequest: (id: string, requestId: number) =>
    request<{ id: number; state: string }>(
      `/api/connections/${id}/approvals/processes/requests/${requestId}/submit`,
      { method: "POST", body: JSON.stringify({}) },
    ),
  approveProcessRequest: (id: string, requestId: number, actorUserId: number) =>
    request<{ id: number; state: string }>(
      `/api/connections/${id}/approvals/processes/requests/${requestId}/approve`,
      {
        method: "POST",
        body: JSON.stringify({ actor_user_id: actorUserId }),
      },
    ),
  refuseProcessRequest: (id: string, requestId: number, actorUserId: number, reason?: string) =>
    request<{ id: number; state: string }>(
      `/api/connections/${id}/approvals/processes/requests/${requestId}/refuse`,
      {
        method: "POST",
        body: JSON.stringify({ actor_user_id: actorUserId, reason: reason ?? "" }),
      },
    ),
  scaffoldApprovalProcesses: (
    id: string,
    body: { confirm_advanced?: boolean; confirm_phrase?: string | null; display_name?: string },
  ) =>
    request<{ ok: boolean; message: string; warnings: string[] }>(
      `/api/connections/${id}/approvals/processes/scaffold`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  createAutomation: (
    id: string,
    body: {
      name: string;
      model: string;
      trigger: string;
      filter_domain?: string | null;
      filter_pre_domain?: string | null;
      trigger_field_names?: string[];
      trg_date_field_name?: string | null;
      active?: boolean;
      action_kind: AutomationActionKind;
      field_name?: string;
      value?: string;
      relation_field?: string;
      activity_type_id?: number;
      activity_summary?: string;
      activity_note?: string;
      activity_user_type?: "specific" | "generic";
      activity_user_id?: number;
      activity_user_field_name?: string;
      target_model?: string;
      field_values?: Record<string, string>;
      mail_template_id?: number | null;
      mail_post_method?: "email" | "comment" | "note";
      mail_subject?: string | null;
      mail_body_html?: string | null;
      mail_email_to?: string | null;
      webhook_url?: string | null;
      webhook_field_names?: string[];
      sms_template_id?: number | null;
      sms_body?: string | null;
      sms_method?: "sms" | "comment" | "note";
      partner_ids?: number[];
      followers_type?: "specific" | "generic";
      followers_partner_field_name?: string | null;
      python_code?: string;
      module_technical_name?: string;
      confirm_advanced?: boolean;
      confirm_phrase?: string;
    },
  ) =>
    request<AutomationRow | ModuleExport>(`/api/connections/${id}/automations`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  setAutomationActive: (id: string, automationId: number, active: boolean) =>
    request<AutomationRow>(`/api/connections/${id}/automations/${automationId}`, {
      method: "PATCH",
      body: JSON.stringify({ active }),
    }),
  deleteAutomation: (
    id: string,
    automationId: number,
    body: { confirm_advanced?: boolean; confirm_phrase?: string | null },
  ) =>
    request<{ ok: boolean; automation_id: number; snapshot_id: string | null }>(
      `/api/connections/${id}/automations/${automationId}`,
      { method: "DELETE", body: JSON.stringify(body) },
    ),
  listSnapshots: (id: string) =>
    request<SnapshotRow[]>(`/api/connections/${id}/snapshots`),
  getLatestHealthCheck: (id: string) =>
    request<HealthCheckRun | null>(`/api/connections/${id}/health-check/latest`),
  listHealthCheckRuns: (id: string, limit = 20) =>
    request<HealthCheckRun[]>(
      `/api/connections/${id}/health-check/runs?limit=${encodeURIComponent(String(limit))}`,
    ),
  runHealthCheck: (id: string, asyncJob = true) =>
    request<HealthCheckTrigger>(
      `/api/connections/${id}/health-check/run?async_job=${asyncJob ? "true" : "false"}`,
      { method: "POST" },
    ),
  rollbackSnapshot: (id: string, snapshotId: string) =>
    request<{ ok: boolean; restored: string; id: number }>(
      `/api/connections/${id}/snapshots/${snapshotId}/rollback`,
      { method: "POST" },
    ),
  dataImportTemplate: (id: string, model: string) =>
    request<{ model: string; filename: string; csv: string }>(
      `/api/connections/${id}/data-import/template?model=${encodeURIComponent(model)}`,
    ),
  dataImportPreview: async (id: string, file: File, model?: string) => {
    const fd = new FormData();
    fd.append("file", file);
    if (model) fd.append("model", model);
    return requestForm<DataImportPreviewOut>(
      `/api/connections/${id}/data-import/parse-rows`,
      fd,
    );
  },
  dataImportCommit: (
    id: string,
    body: {
      model: string;
      mapping: Record<string, string>;
      mode?: "create" | "upsert";
      match_fields?: string[];
      dry_run?: boolean;
      batch_size?: number;
      rows: Record<string, string>[];
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<DataImportCommitOut>(`/api/connections/${id}/data-import/commit`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  ingestCreateJob: async (id: string, files: File[]) => {
    const fd = new FormData();
    for (const f of files) fd.append("files", f);
    return requestForm<IngestJobOut>(`/api/connections/${id}/ingest/jobs`, fd);
  },
  ingestGetJob: (id: string, jobId: string) =>
    request<IngestJobOut>(`/api/connections/${id}/ingest/jobs/${jobId}`),
  ingestDryRun: (
    id: string,
    jobId: string,
    body?: {
      batch_size?: number;
      notify_mode?: "batch_summary" | "individual";
      allow_coa_as_is?: boolean;
    },
  ) =>
    request<IngestJobOut>(`/api/connections/${id}/ingest/jobs/${jobId}/dry-run`, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  ingestCommit: (
    id: string,
    jobId: string,
    body?: {
      batch_size?: number;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
      notify_mode?: "batch_summary" | "individual";
      allow_coa_as_is?: boolean;
    },
  ) =>
    request<IngestJobOut>(`/api/connections/${id}/ingest/jobs/${jobId}/commit`, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  ingestOverride: (
    id: string,
    jobId: string,
    body: { force_doc_types: Record<string, string> },
  ) =>
    request<IngestJobOut>(`/api/connections/${id}/ingest/jobs/${jobId}/override`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  ingestCoaRemap: (
    id: string,
    jobId: string,
    body: { remap?: Record<string, string>; auto?: boolean; min_score?: number },
  ) =>
    request<IngestJobOut>(`/api/connections/${id}/ingest/jobs/${jobId}/coa-remap`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  ingestGetPrefs: (id: string) =>
    request<{
      notify_mode: "batch_summary" | "individual";
      allow_coa_as_is_default: boolean;
      coa_auto_remap_default: boolean;
    }>(`/api/connections/${id}/ingest/prefs`),
  ingestPatchPrefs: (
    id: string,
    body: {
      notify_mode?: "batch_summary" | "individual";
      allow_coa_as_is_default?: boolean;
      coa_auto_remap_default?: boolean;
    },
  ) =>
    request<{
      notify_mode: "batch_summary" | "individual";
      allow_coa_as_is_default: boolean;
      coa_auto_remap_default: boolean;
    }>(`/api/connections/${id}/ingest/prefs`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  ingestVisionStatus: (id: string) =>
    request<{ enabled: boolean; ready: boolean; message: string; model: string }>(
      `/api/connections/${id}/ingest/vision/status`,
    ),
  ingestInterviewQuestions: (id: string) =>
    request<
      Array<{ id: string; prompt: string; kind: string; choices: string[] }>
    >(`/api/connections/${id}/ingest/interview/questions`),
  ingestCreateInterviewJob: (
    id: string,
    body: {
      business_name?: string;
      product_type?: "product" | "service" | "mixed";
      product_lines?: string[];
      starter_contacts?: string[];
      expense_categories?: string[];
    },
  ) =>
    request<IngestJobOut>(`/api/connections/${id}/ingest/interview/jobs`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  imageImportPreview: async (id: string, manifest: File, imagesZip: File) => {
    const fd = new FormData();
    fd.append("manifest", manifest);
    fd.append("images_zip", imagesZip);
    return requestForm<ImageImportPreviewOut>(
      `/api/connections/${id}/data-import/images/preview`,
      fd,
    );
  },
  imageImportCommit: async (
    id: string,
    body: {
      model: string;
      manifest: File;
      imagesZip: File;
      match_field?: string;
      image_field?: string;
      dry_run?: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) => {
    const fd = new FormData();
    fd.append("manifest", body.manifest);
    fd.append("images_zip", body.imagesZip);
    fd.append("model", body.model);
    fd.append("match_field", body.match_field ?? "x_name");
    if (body.image_field) fd.append("image_field", body.image_field);
    fd.append("dry_run", String(body.dry_run ?? true));
    if (body.confirm_advanced) fd.append("confirm_advanced", "true");
    if (body.confirm_phrase) fd.append("confirm_phrase", body.confirm_phrase);
    return requestForm<ImageImportCommitOut>(
      `/api/connections/${id}/data-import/images/commit`,
      fd,
    );
  },
  idGeneratorCsvPreview: async (
    id: string,
    file: File,
    body: {
      name_column: string;
      code_column?: string;
      id_column?: string;
      prefix: string;
      separator?: string;
      padding?: number;
      initials_length?: number;
      skip_if_present?: boolean;
      changed_only?: boolean;
    },
  ) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("name_column", body.name_column);
    if (body.code_column) fd.append("code_column", body.code_column);
    if (body.id_column) fd.append("id_column", body.id_column);
    fd.append("prefix", body.prefix);
    fd.append("separator", body.separator ?? "-");
    fd.append("padding", String(body.padding ?? 4));
    fd.append("initials_length", String(body.initials_length ?? 3));
    fd.append("skip_if_present", String(body.skip_if_present ?? true));
    fd.append("changed_only", String(body.changed_only ?? false));
    return requestForm<IdGeneratorPreviewOut>(`/api/connections/${id}/id-generator/csv/preview`, fd);
  },
  idGeneratorCsvDownload: async (
    id: string,
    body: {
      headers: string[];
      rows: Record<string, string>[];
      assignments: IdGeneratorAssignmentOut[];
      code_column: string;
      changed_only?: boolean;
    },
  ) => {
    const res = await fetchApi(`/api/connections/${id}/id-generator/csv/download`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      let detail: unknown = res.statusText;
      try {
        const parsed = await res.json();
        detail = parsed.detail !== undefined ? parsed.detail : parsed;
      } catch {
        /* ignore */
      }
      throw new Error(formatDetailMessage(detail) || `CSV download failed (${res.status})`);
    }
    return res.blob();
  },
  idGeneratorLive: (
    id: string,
    body: {
      model: string;
      name_field: string;
      code_field: string;
      config: {
        prefix: string;
        separator?: string;
        padding?: number;
        initials_length?: number;
        skip_if_present?: boolean;
      };
      ids?: number[];
      domain?: string | unknown[];
      dry_run?: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<IdGeneratorRunOut>(`/api/connections/${id}/id-generator/live`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  idGeneratorCreateSequence: (
    id: string,
    body: {
      model: string;
      config: {
        prefix: string;
        separator?: string;
        padding?: number;
        initials_length?: number;
        skip_if_present?: boolean;
      };
      sequence_name?: string;
    },
  ) =>
    request<{ ok: boolean; sequence: Record<string, unknown> }>(
      `/api/connections/${id}/id-generator/sequence`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  powerOpsRecipes: (id: string) =>
    request<{ recipes: PowerOpsRecipe[] }>(`/api/connections/${id}/power-ops/recipes`),
  powerOpsCapabilities: (id: string) =>
    request<PowerOpsCapabilities>(`/api/connections/${id}/power-ops/capabilities`),
  listEePlaybooks: (id: string) =>
    request<EePlaybook[]>(`/api/connections/${id}/ee-playbooks`),
  listDocumentsFolders: (id: string) =>
    request<Array<{ id: number; name: string | null }>>(
      `/api/connections/${id}/ee-playbooks/documents/folders`,
    ),
  listDomainPlaybooks: (id: string) =>
    request<DomainPlaybook[]>(`/api/connections/${id}/domain-playbooks`),
  listStudioFeatureRecipes: () =>
    request<StudioFeatureRecipe[]>(`/api/studio-feature-recipes`),
  powerOpsRun: (
    id: string,
    body: {
      recipe_id: string;
      model?: string | null;
      domain?: unknown[];
      ids?: number[];
      dry_run?: boolean;
      batch_size?: number;
      continue_on_error?: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<PowerOpsRunOut>(`/api/connections/${id}/power-ops/run`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  bulkTransitions: (id: string, model: string) =>
    request<BulkTransitionsOut>(
      `/api/connections/${id}/bulk/transitions?model=${encodeURIComponent(model)}`,
    ),
  bulkTransitionRun: (
    id: string,
    body: {
      model: string;
      method: string;
      domain?: unknown[] | string | null;
      ids?: number[];
      dry_run?: boolean;
      cap?: number;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
      receipt_token?: string | null;
      continue_run_id?: string | null;
      disable_sample_first?: boolean;
    },
  ) =>
    request<BulkRunOut>(`/api/connections/${id}/bulk/transitions/run`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  bulkRunContinue: (id: string, runId: string) =>
    request<BulkRunOut>(`/api/connections/${id}/bulk/runs/${runId}/continue`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  bulkRunAbort: (id: string, runId: string) =>
    request<BulkRunOut>(`/api/connections/${id}/bulk/runs/${runId}/abort`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  bulkMassEdit: (
    id: string,
    body: {
      model: string;
      values: Record<string, unknown>;
      domain?: unknown[] | string | null;
      ids?: number[];
      dry_run?: boolean;
      cap?: number;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<BulkRunOut>(`/api/connections/${id}/bulk/mass-edit`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  bulkDedupeScan: (
    id: string,
    body: {
      model: string;
      match_fields: string[];
      mode?: "exact" | "fuzzy";
      limit?: number;
      domain?: unknown[] | null;
    },
  ) =>
    request<DedupeScanOut>(`/api/connections/${id}/bulk/dedupe/scan`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  bulkDedupeMerge: (
    id: string,
    body: {
      model: string;
      winner_id: number;
      loser_ids: number[];
      dry_run?: boolean;
      archive_or_delete?: "archive" | "unlink";
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<BulkRunOut>(`/api/connections/${id}/bulk/dedupe/merge`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  bulkCrons: (
    id: string,
    params?: { q?: string; active?: boolean; limit?: number },
  ) => {
    const qs = new URLSearchParams();
    if (params?.q) qs.set("q", params.q);
    if (params?.active != null) qs.set("active", String(params.active));
    if (params?.limit != null) qs.set("limit", String(params.limit));
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return request<CronListOut>(`/api/connections/${id}/bulk/crons${suffix}`);
  },
  bulkCronRunNow: (
    id: string,
    body: {
      cron_ids: number[];
      dry_run?: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<BulkRunOut>(`/api/connections/${id}/bulk/crons/run-now`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  bulkCronCreate: (
    id: string,
    body: {
      name: string;
      model: string;
      method: string;
      interval_number?: number;
      interval_type?: "minutes" | "hours" | "days" | "weeks" | "months";
      active?: boolean;
      nextcall?: string | null;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<CronRowOut>(`/api/connections/${id}/bulk/crons`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  bulkCronPatch: (
    id: string,
    cronId: number,
    body: {
      interval_number?: number;
      interval_type?: "minutes" | "hours" | "days" | "weeks" | "months";
      active?: boolean;
      nextcall?: string | null;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<CronRowOut>(`/api/connections/${id}/bulk/crons/${cronId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  bulkAttachmentOrphanScan: (id: string, body?: { limit?: number }) =>
    request<OrphanScanOut>(`/api/connections/${id}/bulk/attachments/orphans/scan`, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  bulkAttachmentDuplicateScan: (id: string, body?: { limit?: number }) =>
    request<DuplicateScanOut>(`/api/connections/${id}/bulk/attachments/duplicates/scan`, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  bulkAttachmentLargeOldScan: (
    id: string,
    body?: { min_bytes?: number; older_than_days?: number; limit?: number },
  ) =>
    request<LargeOldScanOut>(`/api/connections/${id}/bulk/attachments/large-old/scan`, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  bulkAttachmentClean: (
    id: string,
    body: {
      attachment_ids: number[];
      dry_run?: boolean;
      kind?: "orphan" | "duplicate" | "large_old" | "manual";
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<BulkRunOut>(`/api/connections/${id}/bulk/attachments/clean`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  bulkActivitiesProbe: (id: string, model: string) =>
    request<ActivityProbeOut>(
      `/api/connections/${id}/bulk/activities/probe?model=${encodeURIComponent(model)}`,
    ),
  bulkActivities: (
    id: string,
    body: {
      model: string;
      ids?: number[];
      domain?: unknown;
      activity_type_id: number;
      summary: string;
      date_deadline: string;
      user_id?: number | null;
      dry_run?: boolean;
      cap?: number;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<BulkRunOut>(`/api/connections/${id}/bulk/activities`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  bulkSecurityPreview: (
    id: string,
    body: {
      user_ids: number[];
      group_ids?: number[];
      mode?: "add" | "remove" | "offboard";
      deactivate?: boolean;
    },
  ) =>
    request<SecurityPreviewOut>(`/api/connections/${id}/bulk/security/preview`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  bulkSecurityApply: (
    id: string,
    body: {
      user_ids: number[];
      group_ids?: number[];
      mode?: "add" | "remove" | "offboard";
      deactivate?: boolean;
      dry_run?: boolean;
      preview_acknowledged?: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<BulkRunOut>(`/api/connections/${id}/bulk/security/apply`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  bulkPortal: (
    id: string,
    body: {
      partner_ids: number[];
      action?: "grant" | "revoke";
      dry_run?: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<BulkRunOut>(`/api/connections/${id}/bulk/portal`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  bulkRecompute: (
    id: string,
    body: {
      model: string;
      field: string;
      ids?: number[];
      domain?: string | unknown[];
      dry_run?: boolean;
      cap?: number;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<BulkRunOut>(`/api/connections/${id}/bulk/recompute`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  bulkSendMessage: (
    id: string,
    body: {
      model: string;
      ids?: number[];
      domain?: string | unknown[];
      body?: string | null;
      subject?: string | null;
      mail_template_id?: number | null;
      dry_run?: boolean;
      cap?: number;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<BulkRunOut>(`/api/connections/${id}/bulk/send-message`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  accessMatrix: (id: string, models: string[]) =>
    request<AccessMatrixOut>(
      `/api/connections/${id}/access/matrix?models=${encodeURIComponent(models.join(","))}`,
    ),
  listCompanies: (id: string) =>
    request<CompanyRow[]>(`/api/connections/${id}/config/companies`),
  updateCompany: (
    id: string,
    companyId: number,
    body: Partial<{
      name: string;
      email: string;
      phone: string;
      website: string;
      street: string;
      street2: string;
      city: string;
      zip: string;
      vat: string;
      company_registry: string;
    }>,
  ) =>
    request<CompanyRow>(`/api/connections/${id}/config/companies/${companyId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  listSequences: (id: string, q?: string) =>
    request<SequenceRow[]>(
      `/api/connections/${id}/config/sequences${q ? `?q=${encodeURIComponent(q)}` : ""}`,
    ),
  updateSequence: (
    id: string,
    sequenceId: number,
    body: Partial<{
      name: string;
      prefix: string;
      suffix: string;
      padding: number;
      number_next: number;
      number_increment: number;
      active: boolean;
    }>,
  ) =>
    request<SequenceRow>(`/api/connections/${id}/config/sequences/${sequenceId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  exportFieldLabelsCsv: async (id: string, model: string) => {
    const res = await fetchApi(
      `/api/connections/${id}/config/field-labels.csv?model=${encodeURIComponent(model)}`,
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.text();
  },
  importFieldLabels: (
    id: string,
    body: {
      rows: Array<{ model: string; name: string; string: string }>;
      dry_run?: boolean;
    },
  ) =>
    request<{
      ok: boolean;
      updated: number;
      skipped: number;
      failed: number;
      message: string;
      errors: string[];
    }>(`/api/connections/${id}/config/field-labels`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listMenus: (id: string, rootsOnly = false) =>
    request<MenuRow[]>(
      `/api/connections/${id}/config/menus${rootsOnly ? "?roots_only=true" : ""}`,
    ),
  createAppMenu: (
    id: string,
    body: {
      root_name: string;
      model: string;
      child_label?: string | null;
      web_icon?: string;
    },
  ) =>
    request<{
      ok: boolean;
      root_menu_id: number;
      child_menu_id: number | null;
      action_id: number | null;
      message: string;
    }>(`/api/connections/${id}/config/menus/app`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createSequence: (
    id: string,
    body: {
      name: string;
      code?: string | null;
      prefix?: string | null;
      suffix?: string | null;
      padding?: number;
      number_next?: number;
      number_increment?: number;
    },
  ) =>
    request<SequenceRow>(`/api/connections/${id}/config/sequences`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listConfigMailTemplates: (id: string, model?: string) =>
    request<
      Array<{
        id: number;
        name: string;
        model: string | null;
        subject: string | null;
        body_html: string | null;
        email_to: string | null;
        description: string | null;
      }>
    >(
      `/api/connections/${id}/config/mail-templates${
        model ? `?model=${encodeURIComponent(model)}` : ""
      }`,
    ),
  createConfigMailTemplate: (
    id: string,
    body: {
      name: string;
      model: string;
      subject: string;
      body_html: string;
      email_to?: string;
      description?: string | null;
    },
  ) =>
    request<{
      id: number;
      name: string;
      model: string | null;
      subject: string | null;
      body_html: string | null;
      email_to: string | null;
      description: string | null;
    }>(`/api/connections/${id}/config/mail-templates`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateConfigMailTemplate: (
    id: string,
    templateId: number,
    body: Partial<{
      name: string;
      subject: string;
      body_html: string;
      email_to: string;
      description: string;
    }>,
  ) =>
    request<{ id: number; name: string }>(
      `/api/connections/${id}/config/mail-templates/${templateId}`,
      { method: "PATCH", body: JSON.stringify(body) },
    ),
  listConfigActivityTypes: (id: string) =>
    request<
      Array<{
        id: number;
        name: string;
        summary: string | null;
        icon: string | null;
        category: string | null;
        active: boolean;
      }>
    >(`/api/connections/${id}/config/activity-types`),
  createConfigActivityType: (
    id: string,
    body: { name: string; summary?: string; icon?: string; category?: string },
  ) =>
    request<{ id: number; name: string }>(
      `/api/connections/${id}/config/activity-types`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  listLanguages: (id: string) =>
    request<Array<{ id: number; code: string; name: string; active: boolean }>>(
      `/api/connections/${id}/config/languages`,
    ),
  exportTranslationsCsv: async (id: string, model: string, lang: string) => {
    const res = await fetchApi(
      `/api/connections/${id}/config/translations.csv?model=${encodeURIComponent(model)}&lang=${encodeURIComponent(lang)}`,
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.text();
  },
  importTranslations: (
    id: string,
    body: {
      rows: Array<{
        type: string;
        model: string;
        name: string;
        lang: string;
        value: string;
      }>;
      dry_run?: boolean;
    },
  ) =>
    request<{
      ok: boolean;
      updated: number;
      failed: number;
      skipped: number;
      message: string;
      errors: string[];
    }>(`/api/connections/${id}/config/translations`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  probeI18n: (id: string) =>
    request<{
      ok: boolean;
      major: number | null;
      method: string;
      context_lang_reads: boolean;
      ir_translation_model: boolean;
      message: string;
    }>(`/api/connections/${id}/config/i18n/probe`),
  exportSpecTranslationsCsv: async (
    id: string,
    spec: Record<string, unknown>,
    lang: string,
  ) => {
    const res = await fetchApi(`/api/connections/${id}/config/i18n/spec-export`, {
      method: "POST",
      body: JSON.stringify({ spec, lang }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.text();
  },
  importSpecTranslations: (
    id: string,
    body: { csv_text: string; dry_run?: boolean },
  ) =>
    request<{
      ok: boolean;
      dry_run: boolean;
      updated: number;
      skipped: number;
      preview: Array<{ model: string; name: string; lang: string; value: string }>;
    }>(`/api/connections/${id}/config/i18n/spec-import`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listConfigPaperformats: (id: string) =>
    request<
      Array<{
        id: number;
        name: string;
        format: string | null;
        orientation: string | null;
        margin_top: number | null;
        margin_bottom: number | null;
        margin_left: number | null;
        margin_right: number | null;
        header_line: boolean | null;
        dpi: number | null;
      }>
    >(`/api/connections/${id}/config/paperformats`),
  upsertConfigPaperformat: (
    id: string,
    body: {
      id?: number;
      name?: string;
      format?: string;
      orientation?: string;
      margin_top?: number;
      margin_bottom?: number;
      margin_left?: number;
      margin_right?: number;
      header_line?: boolean;
      dpi?: number;
    },
  ) =>
    request<{ id: number; name: string }>(`/api/connections/${id}/config/paperformats`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listIrDefaults: (id: string, model: string) =>
    request<
      Array<{
        id: number;
        field_id: number | null;
        field_name: string | null;
        model: string | null;
        json_value: string | null;
        user_id: number | null;
        company_id: number | null;
      }>
    >(`/api/connections/${id}/config/defaults?model=${encodeURIComponent(model)}`),
  upsertIrDefault: (
    id: string,
    body: {
      model?: string;
      model_id?: number;
      field_id?: number;
      field_name?: string;
      json_value?: string;
      value?: unknown;
      user_id?: number;
      company_id?: number;
    },
  ) =>
    request<{ id: number; json_value: string | null }>(
      `/api/connections/${id}/config/defaults`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  listIrProperties: (id: string, model?: string) => {
    const q = model ? `?model=${encodeURIComponent(model)}` : "";
    return request<
      Array<{
        id: number;
        name: string | null;
        fields_id: number | null;
        field_name: string | null;
        type: string | null;
        value_text: string | null;
      }>
    >(`/api/connections/${id}/config/properties${q}`);
  },
  listIrCrons: (id: string, opts?: { q?: string; active?: boolean }) => {
    const q = new URLSearchParams();
    if (opts?.q) q.set("q", opts.q);
    if (opts?.active != null) q.set("active", String(opts.active));
    const qs = q.toString();
    return request<
      Array<{
        id: number;
        name: string;
        model_id: number | null;
        model_name: string | null;
        interval_number: number | null;
        interval_type: string | null;
        active: boolean;
        nextcall: string | null;
      }>
    >(`/api/connections/${id}/config/crons${qs ? `?${qs}` : ""}`);
  },
  patchIrCronActive: (
    id: string,
    cronId: number,
    body: {
      active: boolean;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<{ id: number; name: string; active: boolean }>(
      `/api/connections/${id}/config/crons/${cronId}`,
      { method: "PATCH", body: JSON.stringify(body) },
    ),
  listWebsitePages: (id: string) =>
    request<{
      available: boolean;
      reason: string | null;
      pages: Array<{
        id: number;
        name: string | null;
        url: string | null;
        is_published: boolean | null;
      }> | null;
      menus: null;
    }>(`/api/connections/${id}/config/website/pages`),
  listWebsiteMenus: (id: string) =>
    request<{
      available: boolean;
      reason: string | null;
      pages: null;
      menus: Array<{
        id: number;
        name: string | null;
        url: string | null;
        sequence: number;
      }> | null;
    }>(`/api/connections/${id}/config/website/menus`),
  getWebsitePageBlocks: (id: string, pageId: number) =>
    request<{
      page_id: number;
      view_id: number;
      name: string;
      url: string | null;
      is_published: boolean;
      blocks: Array<Record<string, unknown>>;
    }>(`/api/connections/${id}/website/pages/${pageId}/blocks`),
  saveWebsitePageBlocks: (
    id: string,
    pageId: number,
    body: { page_id: number; view_id: number; blocks: Array<Record<string, unknown>> },
  ) =>
    request<{ ok: boolean; view_id: number; arch_len: number }>(
      `/api/connections/${id}/website/pages/${pageId}/blocks`,
      { method: "PUT", body: JSON.stringify(body) },
    ),
  publishWebsitePage: (id: string, pageId: number, publish: boolean) =>
    request<{ ok: boolean; page_id: number; is_published: boolean }>(
      `/api/connections/${id}/website/pages/${pageId}/publish`,
      { method: "POST", body: JSON.stringify({ page_id: pageId, publish }) },
    ),
  uploadWebsiteImage: (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return requestForm<{ attachment_id: number; src: string; name: string }>(
      `/api/connections/${id}/website/upload-image`,
      form,
    );
  },
  listMenuTree: (id: string, opts?: { rootsOnly?: boolean; parentId?: number }) => {
    const q = new URLSearchParams();
    if (opts?.rootsOnly) q.set("roots_only", "true");
    if (opts?.parentId != null) q.set("parent_id", String(opts.parentId));
    const qs = q.toString();
    return request<
      Array<{
        id: number;
        name: string;
        parent_id: number | null;
        parent_name: string | null;
        action: string | null;
        action_id: number | null;
        action_type: string | null;
        sequence: number;
        web_icon: string | null;
        child_count: number;
      }>
    >(`/api/connections/${id}/menus-builder/tree${qs ? `?${qs}` : ""}`);
  },
  createBuilderMenu: (
    id: string,
    body: {
      name: string;
      parent_id?: number | null;
      action_id?: number | null;
      sequence?: number;
      web_icon?: string | null;
    },
  ) =>
    request<{ id: number; name: string }>(`/api/connections/${id}/menus-builder/menus`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateBuilderMenu: (
    id: string,
    menuId: number,
    body: Record<string, unknown>,
  ) =>
    request<{ id: number; name: string }>(
      `/api/connections/${id}/menus-builder/menus/${menuId}`,
      { method: "PATCH", body: JSON.stringify(body) },
    ),
  deleteBuilderMenu: (
    id: string,
    menuId: number,
    body: { confirm_advanced?: boolean; confirm_phrase?: string | null },
  ) =>
    request<{ ok: boolean }>(`/api/connections/${id}/menus-builder/menus/${menuId}`, {
      method: "DELETE",
      body: JSON.stringify(body),
    }),
  listWindowActions: (
    id: string,
    opts?: { model?: string; q?: string; standaloneOnly?: boolean },
  ) => {
    const q = new URLSearchParams();
    if (opts?.model) q.set("model", opts.model);
    if (opts?.q) q.set("q", opts.q);
    if (opts?.standaloneOnly) q.set("standalone_only", "true");
    const qs = q.toString();
    return request<
      Array<{
        id: number;
        name: string;
        res_model: string | null;
        view_mode: string | null;
        domain: string | null;
        context: string | null;
        target: string | null;
        requires_active_id?: boolean;
      }>
    >(`/api/connections/${id}/menus-builder/actions${qs ? `?${qs}` : ""}`);
  },
  createWindowAction: (
    id: string,
    body: {
      name: string;
      model: string;
      view_mode?: string;
      domain?: string | null;
      context?: string | null;
      target?: string;
    },
  ) =>
    request<{ id: number; name: string; res_model: string | null }>(
      `/api/connections/${id}/menus-builder/actions`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  updateWindowAction: (id: string, actionId: number, body: Record<string, unknown>) =>
    request<{ id: number; name: string }>(
      `/api/connections/${id}/menus-builder/actions/${actionId}`,
      { method: "PATCH", body: JSON.stringify(body) },
    ),
  listReports: (id: string, model?: string) =>
    request<
      Array<{
        id: number;
        name: string;
        model: string | null;
        report_type: string | null;
        report_name: string | null;
        paperformat_id: number | null;
        paperformat_name: string | null;
        arch: string | null;
        view_id: number | null;
      }>
    >(
      `/api/connections/${id}/reports${model ? `?model=${encodeURIComponent(model)}` : ""}`,
    ),
  listPaperformats: (id: string) =>
    request<
      Array<{
        id: number;
        name: string;
        format: string | null;
        orientation: string | null;
      }>
    >(`/api/connections/${id}/reports/paperformats`),
  createReport: (
    id: string,
    body: {
      name: string;
      model: string;
      report_key: string;
      arch?: string | null;
      paperformat_id?: number | null;
    },
  ) =>
    request<{ id: number; name: string; report_name: string | null }>(
      `/api/connections/${id}/reports`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  updateReport: (id: string, reportId: number, body: Record<string, unknown>) =>
    request<{ id: number; name: string }>(`/api/connections/${id}/reports/${reportId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteReport: (
    id: string,
    reportId: number,
    body: { confirm_advanced?: boolean; confirm_phrase?: string | null },
  ) =>
    request<{ ok: boolean }>(`/api/connections/${id}/reports/${reportId}`, {
      method: "DELETE",
      body: JSON.stringify(body),
    }),
  reportRenderProbe: (id: string, reportId?: number, resId?: number) => {
    const params = new URLSearchParams();
    if (reportId != null) params.set("report_id", String(reportId));
    if (resId != null) params.set("res_id", String(resId));
    const q = params.toString();
    return request<ReportRenderProbeOut>(
      `/api/connections/${id}/reports/render-probe${q ? `?${q}` : ""}`,
    );
  },
  getReportDesignPalette: (id: string) =>
    request<Array<{ type: string; label: string; hint: string }>>(
      `/api/connections/${id}/reports/design/palette`,
    ),
  compileReportDesign: (id: string, body: { spec: Record<string, unknown> }) =>
    request<{ ok: boolean; arch: string; body_html: string }>(
      `/api/connections/${id}/reports/design/compile`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  previewReportDesign: (
    id: string,
    body: { spec: Record<string, unknown>; report_id: number; record_id: number },
  ) =>
    request<{
      ok: boolean;
      content_base64: string;
      render_path: string;
      message: string;
    }>(`/api/connections/${id}/reports/design/preview`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  reportDesignToModuleSpec: (id: string, body: { spec: Record<string, unknown> }) =>
    request<{ ok: boolean; fragment: Record<string, unknown> }>(
      `/api/connections/${id}/reports/design/to-module-spec`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  mergePrintReports: async (
    id: string,
    body: {
      items: Array<{ report_id: number; record_ids: number[] }>;
      order?: number[];
      filename?: string;
    },
  ) => {
    const res = await fetchApi(`/api/connections/${id}/reports/merge-print`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      let detail: unknown = res.statusText;
      try {
        const parsed = await res.json();
        detail = parsed.detail !== undefined ? parsed.detail : parsed;
      } catch {
        /* ignore */
      }
      throw new Error(formatDetailMessage(detail) || `Merge print failed (${res.status})`);
    }
    return {
      blob: await res.blob(),
      totalPages: res.headers.get("X-Total-Pages"),
      renderPath: res.headers.get("X-Render-Path"),
    };
  },
  listPipelines: () =>
    request<
      Array<{
        id: string;
        name: string;
        staging_connection_id: string;
        prod_connection_id: string;
        sandbox_connection_id: string | null;
        created_at: string | null;
      }>
    >("/api/pipelines"),
  createPipeline: (body: {
    name: string;
    staging_connection_id: string;
    prod_connection_id: string;
    sandbox_connection_id?: string | null;
  }) =>
    request<{ id: string; name: string }>("/api/pipelines", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listPipelineHops: (pipelineId: string) =>
    request<
      Array<{
        id: string;
        hop: string;
        module_name: string;
        zip_sha256: string;
        status: string;
        message: string;
        validation_id: string | null;
        created_at: string | null;
      }>
    >(`/api/pipelines/${pipelineId}/hops`),
  pipelinePromote: (
    pipelineId: string,
    body: {
      hop: "sandbox" | "staging" | "prod";
      zip_base64: string;
      validation_id?: string | null;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    },
  ) =>
    request<{
      ok: boolean;
      hop: string;
      module_name: string;
      zip_sha256: string;
      validation_id: string | null;
      message: string;
      hop_record_id: string | null;
      promote_method: string | null;
    }>(`/api/pipelines/${pipelineId}/promote`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listSeedPacks: (id: string) =>
    request<
      Array<{ id: string; name: string; description: string; models: string[] }>
    >(`/api/connections/${id}/data-import/seed-packs`),
  getSeedPack: (id: string, packId: string) =>
    request<{
      id: string;
      name: string;
      description: string;
      models: Array<{ model: string; filename: string; csv: string }>;
    }>(`/api/connections/${id}/data-import/seed-packs/${packId}`),
  listComponentGallery: () =>
    request<Array<{ id: string; name: string; description: string; host_slot: string }>>("/api/ai/component-gallery"),
  expertAsk: (body: {
    question: string;
    connection_id?: string;
    ui_context?: Record<string, unknown>;
    conversation?: Array<{ role: string; content: string }>;
  }) =>
    request<ExpertAskResponse>("/api/expert/ask", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};

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

export type CronListOut = {
  crons: CronRowOut[];
  probe: Record<string, unknown>;
};

async function requestForm<T>(path: string, form: FormData): Promise<T> {
  const res = await fetchApi(path, {
    method: "POST",
    body: form,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = (data as { detail?: unknown }).detail;
    if (isConfirmationDetail(detail)) {
      throw new ConfirmationRequiredError(
        detail as ConfirmationRequiredDetail,
        res.status,
      );
    }
    throw new Error(formatDetailMessage(detail) || `HTTP ${res.status}`);
  }
  return data as T;
}
