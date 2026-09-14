/** App Studio session types and URL helpers. */

import { inheritHostModelFromDraft } from "./draft-models";

export type StudioClarificationOption = {
  id: string;
  label: string;
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
  source?: string;
  confidence?: string;
  operator_note?: string;
};

export type StudioClarification = {
  id?: string;
  kind?: string;
  merge_key: string;
  question: string;
  help?: string;
  options?: StudioClarificationOption[];
  default_id?: string;
  understanding?: StudioUnderstanding;
  host_choices?: StudioClarificationOption[];
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
