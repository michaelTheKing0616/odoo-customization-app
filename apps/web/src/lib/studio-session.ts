/** App Studio session types and URL helpers. */

import { inheritHostModelFromDraft } from "./draft-models";

export type StudioClarificationOption = {
  id: string;
  label: string;
};

export type StudioCraftSmartButton = {
  id?: string;
  on_model: string;
  label: string;
  related_model: string;
  relation_field: string;
  rationale?: string;
  default_on?: boolean;
  chip_label?: string;
  source?: string;
};

/** Operator craft opt-ins — all default false until Diagnosis toggles them on. */
export type StudioApprovedCraft = {
  company_scoping?: boolean;
  money_slots?: boolean;
  purchase_link?: boolean;
  partner_links?: boolean;
  datetime_over_date?: boolean;
  depth_seeds?: boolean;
};

export type StudioDesignField = {
  name: string;
  ttype: string;
  string?: string;
  required?: boolean;
  relation?: string | null;
  inverse_name?: string | null;
  selection?: string[][];
};

export type StudioDesignModel = {
  name: string;
  label: string;
  description?: string;
  why?: string;
  fields: StudioDesignField[];
  views?: string[];
  is_config?: boolean;
  /** AI-proposed supporting model, not named in the brief. */
  suggested?: boolean;
};

export type StudioDesignIntegration = {
  app: string;
  module: string;
  models?: string[];
  required?: boolean;
  installed?: boolean | null;
  status?: "available" | "deferred" | "unchecked" | string;
  note?: string;
};

export type StudioDesignPythonPiece = {
  key?: string;
  label: string;
  models?: string[];
  reason?: string;
  online_blocked?: boolean | string;
  lane_note?: string;
  requirement_id?: string;
  evidence?: { quote?: string; start?: number; end?: number };
};

export type StudioAutomation = {
  requirement_id: string;
  label: string;
  target_model: string;
  trigger?: string;
  mechanism?: string;
  automation?: { when?: string; action?: string; date_field?: string; offset_days?: number; summary?: string };
  evidence?: { quote?: string; start?: number; end?: number };
};

export type StudioIntentRequirement = {
  id: string;
  kind: string;
  subject: string;
  decision: "metadata" | "stock_automation" | "option_a" | "clarify" | "declined" | string;
  origin?: "stated" | "inferred" | string;
  evidence?: { quote?: string; start?: number; end?: number };
  trigger?: string;
  target_model?: string;
  downgrade_reason?: string;
  why_metadata_cannot_do_it?: string;
  metadata_alternative?: string;
  question?: string;
  confidence?: string;
};

export type StudioCriticFinding = {
  id: string;
  kind: string;
  subject: string;
  evidence?: { quote?: string; start?: number; end?: number };
  detail?: string;
  question?: string;
  severity?: string;
};

export type StudioAppDesign = {
  /** Built-in Odoo apps the brief points to, offered with Install. */
  stock_suggestions?: { module: string; name: string; why: string; quote?: string; installed?: boolean; enterprise_only?: boolean; available?: boolean }[];
  /** Choices App Studio made for you; the person can change each one. */
  assumptions?: { text: string; requirement_id?: string; alternatives?: string[]; chosen?: string }[];
  /** Things the brief asks for that this app leaves out. */
  out_of_scope?: string[];
  /** Parts the brief said not to build (or not now). Put back re-adds them. */
  left_out?: { id: string; item: string; quote: string; status?: string; message?: string; put_back?: boolean }[];
  /** Parts App Studio was unsure about: built by default, untick to leave out. */
  checklist_choices?: { id: string; item: string; quote: string; restatement?: string; why?: string; ticked?: boolean }[];
  stock_checks?: { id?: string; item: string; label: string; choice: "stock" | "custom"; install?: string; custom_without_reason?: boolean }[];
  integration_routes?: { service: string; route: "stock" | "webhook" | "bridge" | "decline"; label: string; reason?: string; module?: string }[];
  app_name: string;
  purpose?: string;
  new_models: StudioDesignModel[];
  stock_extensions?: { model: string; fields: StudioDesignField[]; reason?: string }[];
  integrations?: StudioDesignIntegration[];
  security_groups?: { name: string; implied?: string[]; access?: Record<string, string> }[];
  python_needed?: StudioDesignPythonPiece[];
  relations?: { model: string; field: string; type: string; target: string; inverse?: string }[];
  menus?: string[];
  source?: "llm" | "llm_repaired" | "outline" | string;
  /** Plain reason the AI design did not come through (outline only). */
  fallback_reason?: string;
  notes?: string[];
  intent_contract?: StudioIntentRequirement[];
  critic_findings?: StudioCriticFinding[];
  automations?: StudioAutomation[];
  /** Diagnosis-screen edit: automation requirement ids the operator removed. */
  automations_off?: string[];  
  /** Diagnosis-screen edit: integration modules the operator turned off. */
  integrations_off?: string[];
  [key: string]: unknown;
};

export type StudioUnderstanding = {
  title?: string;
  summary?: string;
  host_model?: string | null;
  host_label?: string | null;
  inherit_existing?: boolean;
  needs_module?: boolean;
  capability?: string;
  gold_artifact_id?: string | null;
  constraints?: string[];
  out_of_scope?: string[];
  craft_proposals?: StudioCraftSmartButton[];
  craft_smart_buttons?: StudioCraftSmartButton[];
  approved_craft?: StudioApprovedCraft;
  source?: string;
  confidence?: string;
  operator_note?: string;
  app_design?: StudioAppDesign | null;
};

export type StudioStockAppProposal = {
  module: string;
  app_label: string;
  model: string;
  noun: string;
  installable: boolean;
  question: string;
  reason: string;
  install_label: string;
  decline_label: string;
};

export type StudioInstallStepApp = {
  module: string;
  label: string;
  why: string;
  models: string[];
  installable: boolean;
};

/** S11: apps the design is built on that must be installed before Build/Apply. */
export type StudioInstallStep = {
  title: string;
  message: string;
  apps: StudioInstallStepApp[];
  can_install: boolean;
  install_label: string;
  blocked_message: string;
  /** The connection is read-only: Install is disabled and the guidance is shown up front. */
  read_only?: boolean;
  read_only_message?: string;
  /** Apps are installed; the design still needs its refresh on the real fields. */
  refresh?: boolean;
};

export type StudioClarification = {
  id?: string;
  kind?: string;
  stock_app?: StudioStockAppProposal;
  install_step?: StudioInstallStep | null;
  merge_key: string;
  question: string;
  help?: string;
  /** Plain restatement of the brief, shown before a question. */
  understood?: string;
  options?: StudioClarificationOption[];
  default_id?: string;
  understanding?: StudioUnderstanding;
  host_choices?: StudioClarificationOption[];
  nice_to_have?: string[];
  craft_proposals?: StudioCraftSmartButton[];
  app_design?: StudioAppDesign | null;
};

export type StudioTurn = {
  role: string;
  kind: string;
  content: string;
  metadata?: Record<string, unknown>;
  at?: string;
};

export type StudioSession = {
  id: string;
  connection_id?: string | null;
  feature?: string;
  status: string;
  prompt_original: string;
  prompt_resolved: string;
  conversation?: StudioTurn[];
  artifact?: Record<string, unknown>;
  resolved_answers?: Record<string, string>;
  pending_clarification?: StudioClarification | null;
  job_id?: string | null;
  provider_used?: string | null;
  fallback_used?: boolean;
  artifact_hash?: string | null;
  artifact_consistent?: boolean;
  metrics?: Record<string, number>;
  clarification?: StudioClarification | null;
  understanding?: StudioUnderstanding | null;
  rejected?: boolean;
  root_menu_id?: number | null;
  open_action_id?: number | null;
  host_model?: string | null;
  /** Optional-integration plan from create/generate (see lib/integration-plan). */
  integration_plan?: unknown;
  assessment?: {
    clear?: boolean;
    triggers?: string[];
    ir_confidence?: string;
  };
};

export type StudioPhase = "prompt" | "generating" | "clarify" | "review" | "failed";

/** Merge a 409 clarify payload onto the current session instead of failing the page. */
export function sessionWithClarification(
  session: StudioSession,
  clarification: StudioClarification | null,
): StudioSession {
  return {
    ...session,
    status: "clarifying",
    pending_clarification: clarification,
    clarification,
  };
}

export function studioPhaseFromSession(session: StudioSession | null): StudioPhase {
  if (!session) return "prompt";
  if (session.status === "failed") return "failed";
  if (session.status === "clarifying" || session.pending_clarification) return "clarify";
  if (session.status === "generating" || session.status === "ready") return "generating";
  if (
    session.status === "review" ||
    session.status === "delivered" ||
    (session.artifact && Object.keys(session.artifact).length > 0)
  ) {
    return "review";
  }
  return "prompt";
}

function asPositiveInt(value: unknown): number | null {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) && n > 0 ? n : null;
}

function hostModelFromUnknown(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

/** Live Odoo menu ids from Apply — artifact stamp, then apply-turn metadata. */
export function studioApplyMenuTarget(session: StudioSession | null): {
  rootMenuId: number | null;
  openActionId: number | null;
  hostModel: string | null;
  applied: boolean;
} {
  const empty = {
    rootMenuId: null as number | null,
    openActionId: null as number | null,
    hostModel: null as string | null,
    applied: false,
  };
  if (!session) return empty;
  const inheritHost = inheritHostModelFromDraft(session.artifact ?? null);
  const stamped = session.artifact?._studio_apply;
  const stamp =
    stamped && typeof stamped === "object" && !Array.isArray(stamped)
      ? (stamped as Record<string, unknown>)
      : null;
  let rootMenuId = asPositiveInt(stamp?.root_menu_id) ?? asPositiveInt(session.root_menu_id);
  let openActionId = asPositiveInt(stamp?.open_action_id) ?? asPositiveInt(session.open_action_id);
  let hostModel =
    hostModelFromUnknown(stamp?.host_model) ||
    hostModelFromUnknown(session.host_model) ||
    inheritHost;
  let applied = Boolean(stamp) || session.status === "delivered";
  const via = typeof stamp?.via === "string" ? stamp.via : "";
  // Option A Promote inherits a stock form — never prefer a leftover Apps menu_id
  // (often Discuss) over the host model deep-link.
  if (via === "option_a_promote") {
    return {
      rootMenuId: null,
      openActionId,
      hostModel,
      applied: true,
    };
  }
  if (rootMenuId) {
    return { rootMenuId, openActionId, hostModel, applied: true };
  }
  for (const turn of session.conversation || []) {
    if (turn.kind !== "apply") continue;
    applied = true;
    const meta = turn.metadata || {};
    rootMenuId = asPositiveInt(meta.root_menu_id);
    openActionId = asPositiveInt(meta.open_action_id) ?? openActionId;
    hostModel = hostModelFromUnknown(meta.host_model) || hostModel;
    if (rootMenuId) return { rootMenuId, openActionId, hostModel, applied };
  }
  return { rootMenuId, openActionId, hostModel, applied };
}

/** True after Apply — a new app menu, or a field pack stamped onto a stock form. */
export function studioAppIsLiveOnOdoo(session: StudioSession | null): boolean {
  const target = studioApplyMenuTarget(session);
  return target.rootMenuId != null || (target.applied && Boolean(target.hostModel || target.openActionId));
}

const UNDO_UTTERANCE =
  /^(oops|undo|whoops|my\s+bad|scratch\s+that|never\s*mind)\b/i;

const CLAUSE_SPLIT =
  /(\s+and\s+|\s+then\s+|,\s+)(?=(?:restore|bring\s+back|put\s+(?:it\s+)?back|remove|drop|yeet|ditch|delete|get\s+rid\s+of|without|hide|show|add|make)\b)/i;

function invertClause(clause: string): string | null {
  const c = clause.trim();
  if (!c || UNDO_UTTERANCE.test(c)) return null;

  if (/\bmake\b/i.test(c) && /\b(required|mandatory)\b/i.test(c) && !/\boptional\b/i.test(c)) {
    return c.replace(/\b(required|mandatory)\b/i, "optional");
  }
  if (/\bmake\b/i.test(c) && /\boptional\b/i.test(c)) {
    return c.replace(/\boptional\b/i, "required");
  }

  const pairs: Array<[RegExp, string]> = [
    [/\bbring\s+back\b/i, "remove"],
    [/\bput\s+(?:it\s+)?back\b/i, "remove"],
    [/\brestore\b/i, "remove"],
    [/\bget\s+rid\s+of\b/i, "restore"],
    [/\bdon['’]?t\s+need\b/i, "restore"],
    [/\bdo\s+not\s+need\b/i, "restore"],
    [/\btake\s+off\b/i, "restore"],
    [/\bwithout\b/i, "restore"],
    [/\b(?:remove|drop|yeet|ditch|delete)\b/i, "restore"],
    [/\bhide\b/i, "show"],
    [/\bunhide\b/i, "hide"],
    [/\bshow\b/i, "hide"],
    [/\badd\b/i, "remove"],
  ];
  for (const [re, replacement] of pairs) {
    if (re.test(c)) {
      const inverted = c.replace(re, replacement);
      if (/^(restore|remove|show|hide)\s+(it|that|this)\s*$/i.test(inverted.trim())) {
        return null;
      }
      return inverted;
    }
  }
  return null;
}

/** Invert a refine phrase to the textual restore/remove command Refine already understands. */
export function invertRefineText(text: string): string | null {
  const raw = text.trim();
  if (!raw) return null;
  const bits = raw.split(CLAUSE_SPLIT);
  if (bits.length === 1) return invertClause(raw);
  const out: string[] = [];
  for (const bit of bits) {
    if (/^(\s+and\s+|\s+then\s+|,\s+)$/i.test(bit)) {
      out.push(bit);
      continue;
    }
    const inverted = invertClause(bit);
    if (!inverted) return null;
    out.push(inverted);
  }
  return out.join("").replace(/\s+/g, " ").trim();
}

/**
 * Latest turn → `oops` (uses `_refine_undo`).
 * Older turns → inverted restore/remove text (same path as typing it).
 */
export function undoInstructionForRefine(content: string, isLatest: boolean): string | null {
  const text = content.trim();
  if (!text || UNDO_UTTERANCE.test(text)) return null;
  if (isLatest) return "oops";
  return invertRefineText(text);
}

export type RefineHistoryItem = {
  at?: string;
  content: string;
  isLatest: boolean;
  undoInstruction: string | null;
};

/** User refine phrases, newest first — compact trail, not a second chat. */
export function refineHistoryItems(
  conversation: StudioTurn[] | undefined,
): RefineHistoryItem[] {
  const items: Array<{ at?: string; content: string }> = [];
  for (const turn of conversation || []) {
    if (turn.kind !== "refine" || turn.role !== "user") continue;
    const content = String(turn.content || "").trim();
    if (!content) continue;
    items.push({ at: turn.at, content });
  }
  items.reverse();
  return items.map((item, idx) => ({
    ...item,
    isLatest: idx === 0,
    undoInstruction: undoInstructionForRefine(item.content, idx === 0),
  }));
}

export function studioStorageKey(connectionId: string): string {
  return `app-studio:${connectionId}`;
}

export function rememberStudioSession(connectionId: string, sessionId: string): void {
  try {
    sessionStorage.setItem(studioStorageKey(connectionId), sessionId);
  } catch {
    /* private mode */
  }
}

export function forgetStudioSession(connectionId: string): void {
  try {
    sessionStorage.removeItem(studioStorageKey(connectionId));
    sessionStorage.removeItem(`app-studio-prompt:${connectionId}`);
  } catch {
    /* private mode */
  }
}

export function loadRememberedStudioSession(connectionId: string): string | null {
  try {
    return sessionStorage.getItem(studioStorageKey(connectionId));
  } catch {
    return null;
  }
}

export function stashPromptForStudio(connectionId: string, prompt: string): void {
  try {
    sessionStorage.setItem(`app-studio-prompt:${connectionId}`, prompt);
  } catch {
    /* private mode */
  }
}

export function loadStashedStudioPrompt(connectionId: string): string | null {
  try {
    return sessionStorage.getItem(`app-studio-prompt:${connectionId}`);
  } catch {
    return null;
  }
}

export const STUDIO_STARTER_CHIPS = [
  "Car rental with deposits and return checklist",
  "Clinic booking with walk-in appointments",
  "Helpdesk tickets with requester and status workflow",
  "Retail inventory and stock moves",
];


/** True when residual canvas display_name matches locked Contract title. */
export function artifactMatchesLockedContract(
  artifact: Record<string, unknown> | null | undefined,
  understanding: StudioUnderstanding | null | undefined,
): boolean {
  if (!artifact || !understanding) return true;
  const inherit = Boolean(understanding.inherit_existing);
  if (inherit) return true;
  const locked = String(understanding.title || "").trim().toLowerCase();
  const shown = String(artifact.display_name || "").trim().toLowerCase();
  if (!locked || !shown) return true;
  if (locked === shown) return true;
  // Allow short contained titles (Visitor Log ⊂ Visitor Log App) but not cross-app.
  if (locked.length >= 4 && shown.includes(locked)) return true;
  if (shown.length >= 4 && locked.includes(shown)) return true;
  return false;
}
