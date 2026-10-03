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

export type LocatorIssue = {
  severity: "error" | "warning";
  code: string;
  message: string;
  expr?: string | null;
  suggestion?: string | null;
};

export type XPathPreviewOut = {
  arch: string;
  issues: string[];
  locator_issues?: LocatorIssue[];
  suggested_expr?: string | null;
  default_inject_expr?: string | null;
  match_count?: number | null;
  blocking?: boolean;
};
