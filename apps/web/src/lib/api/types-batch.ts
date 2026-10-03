import type { CronRowOut } from "./types-bulk";

export type AtlasIntent = {
  id: string;
  title: string;
  models: string[];
  risk: string;
  recipe: string | null;
  status: string;
  blurb: string;
};

export type AtlasClass = {
  id: string;
  title: string;
  status: string;
  blurb: string;
  intents: AtlasIntent[];
};

export type AtlasHit = {
  class_id: string;
  class_title: string;
  intent_id: string;
  title: string;
  models: string[];
  risk: string;
  recipe: string | null;
  status: string;
  blurb: string;
};


export type IntentRouteCanHandle = "true" | "false" | "partial";

export type IntentRouteMatch = {
  feature_id: string;
  title: string;
  confidence: number;
  why: string;
  route: string;
  deep_link: string;
  can_handle: IntentRouteCanHandle;
  recipe?: string | null;
  source?: string;
  status?: string;
  atlas_class?: string | null;
  risk?: string | null;
  matched_keywords?: string[];
};

export type IntentRouteResult = {
  prompt: string;
  can_handle: IntentRouteCanHandle;
  message: string;
  matches: IntentRouteMatch[];
  alternatives: IntentRouteMatch[];
  ambiguous: boolean;
  honesty: string;
  source: string;
  llm_used: boolean;
};

export type BatchOsRecipeCard = {
  id: string;
  title: string;
  blurb: string;
  risk: string;
  status: string;
  atlas_class: string;
  models: string[];
  phases: string[];
};

export type BatchOsRowError = {
  row_index: number;
  field?: string | null;
  code: string;
  message: string;
};

export type BatchOsMove = {
  group_key: string;
  journal_id: number | null;
  journal_name: string | null;
  date: string;
  ref: string;
  line_count: number;
  total_debit: number;
  total_credit: number;
  balanced: boolean;
  line_indexes: number[];
  errors: string[];
  move_id?: number | null;
  posted?: boolean;
};

export type BatchOsJob = {
  job_id: string;
  connection_id: string;
  recipe_id: string;
  risk: string;
  phase: string;
  filename: string;
  headers: string[];
  raw_row_count: number;
  sample_rows: Record<string, string>[];
  column_map: Record<string, string>;
  mapped_lines: Record<string, unknown>[];
  moves: BatchOsMove[];
  errors: BatchOsRowError[];
  warnings: string[];
  message: string;
  honesty: string;
  dry_run: boolean;
  post_after_create: boolean;
  created_move_ids: number[];
  posted_move_ids: number[];
  ok?: boolean;
};

export type RecipeCard = {
  id: string;
  phase: string;
  title: string;
  blurb: string;
  clicks: string;
};

export type RecipeStep = {
  op: string;
  target: string;
  detail: string;
  would_write?: boolean;
};

export type RecipePlanOut = {
  ok: boolean;
  dry_run: boolean;
  steps: RecipeStep[];
  applied?: string[];
  warnings?: string[];
  message?: string;
};

export type NumberingCatalogItem = {
  key: string;
  name: string;
  code: string;
  prefix: string;
  padding: number;
};

export type AppsPackItem = {
  id: string;
  title: string;
  modules: string[];
  blurb: string;
};

export type MasterPackItem = {
  id: string;
  title: string;
  categories?: string[];
  positions?: string[];
};

export type SettingsBoardOut = {
  allowlist: string[];
  values: Record<string, unknown>;
  message?: string;
};



export type CronListOut = {
  crons: CronRowOut[];
  probe: Record<string, unknown>;
};
