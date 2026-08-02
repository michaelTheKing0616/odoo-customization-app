const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export { API_BASE };

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

export type Connection = {
  id: string;
  name: string;
  url: string;
  db_name: string;
  username: string;
  server_version: string | null;
  created_at: string | null;
  updated_at: string | null;
  capabilities?: CapabilityMatrix | null;
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
  created_at: string | null;
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const storedKey = getStoredApiKey();
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(storedKey ? { Authorization: `Bearer ${storedKey}` } : {}),
      ...(init?.headers ?? {}),
    },
  });
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
    throw new Error(formatDetailMessage(detail) || `Request failed (${res.status})`);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

export const api = {
  authStatus: () => request<AuthStatus>("/api/auth/status"),
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
  exportLibraryModule: (body: {
    technical_name?: string;
    display_name?: string;
    fines?: boolean;
    reminders?: boolean;
    multi_company?: boolean;
  }) =>
    request<ModuleExport>("/api/apps/templates/library/export", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  draftModuleFromPrompt: (
    prompt: string,
    opts?: {
      connection_id?: string;
      reuse_models?: string[];
      reuse_view_ids?: number[];
      reuse_action_ids?: number[];
      expand?: boolean;
    },
  ) =>
    request<{
      ok: boolean;
      draft: Record<string, unknown>;
      raw_response?: string | null;
      note?: string;
      warnings?: string[];
      domain_pack?: string | null;
    }>("/api/ai/draft-module", {
      method: "POST",
      body: JSON.stringify({
        prompt,
        connection_id: opts?.connection_id,
        reuse_models: opts?.reuse_models ?? [],
        reuse_view_ids: opts?.reuse_view_ids ?? [],
        reuse_action_ids: opts?.reuse_action_ids ?? [],
        expand: opts?.expand ?? true,
      }),
    }),
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
  listModels: (id: string, customOnly = false) =>
    request<ModelRow[]>(`/api/connections/${id}/models?custom_only=${customOnly}`),
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
        created_at?: string | null;
        updated_at?: string | null;
      }[]
    >(`/api/connections/${id}/projects`),
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
    const storedKey = getStoredApiKey();
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API_BASE}/api/module-spec/import`, {
      method: "POST",
      headers: storedKey ? { Authorization: `Bearer ${storedKey}` } : {},
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
    body: { confirm_advanced?: boolean; confirm_phrase?: string | null },
  ) =>
    request<{ ok: boolean; field_id: number; snapshot_id: string | null }>(
      `/api/connections/${id}/fields/${fieldId}`,
      { method: "DELETE", body: JSON.stringify(body) },
    ),
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
    },
  ) =>
    request<
      ModuleExport & {
        model_count: number;
        view_count: number;
        report_count?: number;
        target_major?: number | null;
        manifest_version?: string | null;
        warnings?: string[];
      }
    >(`/api/connections/${id}/export-module`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
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
  powerOpsRecipes: (id: string) =>
    request<{ recipes: PowerOpsRecipe[] }>(`/api/connections/${id}/power-ops/recipes`),
  powerOpsCapabilities: (id: string) =>
    request<PowerOpsCapabilities>(`/api/connections/${id}/power-ops/capabilities`),
  listEePlaybooks: (id: string) =>
    request<EePlaybook[]>(`/api/connections/${id}/ee-playbooks`),
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
    const storedKey = getStoredApiKey();
    const res = await fetch(
      `${API_BASE}/api/connections/${id}/config/field-labels.csv?model=${encodeURIComponent(model)}`,
      {
        headers: {
          ...(storedKey ? { Authorization: `Bearer ${storedKey}` } : {}),
        },
      },
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
    const storedKey = getStoredApiKey();
    const res = await fetch(
      `${API_BASE}/api/connections/${id}/config/translations.csv?model=${encodeURIComponent(model)}&lang=${encodeURIComponent(lang)}`,
      { headers: { ...(storedKey ? { Authorization: `Bearer ${storedKey}` } : {}) } },
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

async function requestForm<T>(path: string, form: FormData): Promise<T> {
  const storedKey = getStoredApiKey();
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body: form,
    headers: {
      ...(storedKey ? { Authorization: `Bearer ${storedKey}` } : {}),
    },
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
