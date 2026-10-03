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

export type ExpertDraftReviewResponse = {
  score_before: number;
  score_after?: number | null;
  verdict: string;
  review_markdown: string;
  findings: Array<{
    priority: number;
    element: string;
    summary: string;
    detail: string;
    deterministic: boolean;
    repair_hint?: string | null;
    citation?: string | null;
    narrative_paragraph?: string | null;
    narrative_citations?: ExpertCitation[];
  }>;
  repairs: string[];
  suggestions: string[];
  draft?: Record<string, unknown> | null;
};

export type ExpertSuggestedPrompt = {
  id: string;
  label: string;
  question: string;
};

export type ExpertNLSearchHit = {
  id: string;
  kind: string;
  label: string;
  description: string;
  href?: string | null;
  expert_question?: string | null;
  score: number;
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
