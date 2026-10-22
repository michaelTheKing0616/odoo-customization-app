/**
 * Pure helpers for View Designer stage 2a: rules, who can see it, preview,
 * versions, history and comments. The server checks every change; these only
 * shape what the person picks into the ops the server understands.
 */
import type {
  Condition,
  ConditionRule,
  EngineNode,
  EngineOp,
  Marker,
  RuleAttr,
  ViewComment,
  Visibility,
} from "@/lib/api/view-engine";
import type { TreeIndex } from "@/lib/viewEngineOps";

export const DEVICES = [
  { id: "desktop", label: "Desktop", width: 1280 },
  { id: "tablet", label: "Tablet", width: 820 },
  { id: "phone", label: "Phone", width: 390 },
] as const;

export const RULE_WORDS: Record<RuleAttr, { label: string; show: string; hide: string }> = {
  invisible: { label: "Show and hide", show: "Show only when", hide: "Hide when" },
  required: { label: "Must be filled in", show: "Required when", hide: "Optional when" },
  readonly: { label: "Read-only", show: "Read-only when", hide: "Editable when" },
  column_invisible: { label: "Show and hide the column", show: "Show the column only when", hide: "Hide the column when" },
};

/** Rule attributes this item can carry. */
export function ruleAttrsFor(node: EngineNode, rootTag: string): RuleAttr[] {
  if (node.kind === "root" || node.tag === "sheet") return [];
  const out: RuleAttr[] = ["invisible"];
  if (node.tag === "field") out.push("required", "readonly");
  if (node.tag === "field" && (rootTag === "list" || rootTag === "tree")) out.push("column_invisible");
  return out;
}

/** The value op needs no value. */
export const NO_VALUE_OPS = new Set(["is_true", "is_false", "set", "not_set"]);
export const LIST_OPS = new Set(["in", "not_in"]);

export function blankRule(field: string, firstOp: string): ConditionRule {
  return { field, op: firstOp, value: LIST_OPS.has(firstOp) ? [] : undefined };
}

/** A rule is complete when every part the operator needs is filled in. */
export function ruleComplete(rule: ConditionRule): boolean {
  if (!rule.field || !rule.op) return false;
  if (NO_VALUE_OPS.has(rule.op)) return true;
  if (LIST_OPS.has(rule.op)) return Array.isArray(rule.value) && rule.value.length > 0;
  return rule.value !== undefined && rule.value !== null && rule.value !== "";
}

export function conditionComplete(cond: Condition): boolean {
  return cond.rules.length > 0 && cond.rules.every(ruleComplete);
}

/** Coerce a typed value the way the field expects. */
export function coerceValue(fieldType: string | undefined, raw: string): string | number {
  if (fieldType === "integer" || fieldType === "many2one") {
    const n = Number.parseInt(raw, 10);
    return Number.isFinite(n) ? n : raw;
  }
  if (fieldType === "float" || fieldType === "monetary") {
    const n = Number.parseFloat(raw);
    return Number.isFinite(n) ? n : raw;
  }
  return raw;
}

// ---- Who can see it ----------------------------------------------------------

export type AccessLevel = "edit" | "see" | "hidden";

/** Current per-role level from the item's groups attribute (comma list = OR). */
export function levelsFromGroups(groups: string | undefined): Record<string, AccessLevel> {
  const out: Record<string, AccessLevel> = {};
  for (const g of (groups ?? "").split(",").map((x) => x.trim()).filter(Boolean)) {
    if (!g.startsWith("!")) out[g] = "edit";
  }
  return out;
}

export function splitLevels(levels: Record<string, AccessLevel>): { edit: string[]; see: string[] } {
  const edit = Object.entries(levels).filter(([, l]) => l === "edit").map(([g]) => g).sort();
  const see = Object.entries(levels).filter(([, l]) => l === "see").map(([g]) => g).sort();
  return { edit, see };
}

/** One set_access op per selected item (multi-select applies the same roles to all). */
export function accessOps(nodeIds: string[], levels: Record<string, AccessLevel>): EngineOp[] {
  const { edit, see } = splitLevels(levels);
  return nodeIds.map((node) => ({ op: "set_access", node, edit, see }));
}

/** "Copy rules from another field": the source's roles and its show/hide rules. */
export function copyRuleOps(source: EngineNode, targets: string[], pending: EngineOp[]): EngineOp[] {
  const out: EngineOp[] = [];
  const pendingAccess = [...pending].reverse().find((o) => o.op === "set_access" && o.node === source.id);
  const levels =
    pendingAccess && pendingAccess.op === "set_access"
      ? Object.fromEntries([
          ...pendingAccess.edit.map((g) => [g, "edit" as AccessLevel]),
          ...pendingAccess.see.map((g) => [g, "see" as AccessLevel]),
        ])
      : levelsFromGroups(source.attrs.groups);
  for (const t of targets) {
    if (t === source.id) continue;
    const { edit, see } = splitLevels(levels);
    out.push({ op: "set_access", node: t, edit, see });
    for (const attr of ["invisible", "required", "readonly", "column_invisible"] as RuleAttr[]) {
      const pendingRule = [...pending].reverse().find((o) => o.op === "set_condition" && o.node === source.id && o.attr === attr);
      if (pendingRule && pendingRule.op === "set_condition") {
        out.push({ ...pendingRule, node: t });
      } else if (source.attrs[attr] && !["0", "False"].includes(source.attrs[attr])) {
        out.push({ op: "set_condition", node: t, attr, sense: "show", condition: null, copy_from: source.id });
      }
    }
  }
  return out;
}

/** Shift/Cmd click adds or removes; a plain click selects one. */
export function nextSelection(current: string[], id: string, additive: boolean): string[] {
  if (!additive) return [id];
  return current.includes(id) ? current.filter((x) => x !== id) : [...current, id];
}

// ---- Preview and "why hidden" --------------------------------------------------

/** Plain reason an item is hidden right now: role preview first, then Odoo's rules. */
export function whyHidden(node: EngineNode, preview: Visibility | null): string | null {
  const p = preview?.[node.id];
  if (p && !p.visible && p.reason) return p.reason;
  const rule = node.rules?.invisible ?? node.rules?.column_invisible;
  if (rule) return rule;
  const v = node.attrs.invisible ?? node.attrs.column_invisible;
  if (v === "1" || v === "True") return "Always hidden on this screen.";
  if (node.attrs.groups) return "Only some roles can see it. Open Who can see it for details.";
  return null;
}

export const MARKER_WORDS: Record<Marker, string> = {
  added: "Added",
  removed: "Removed",
  moved: "Moved",
  hidden: "Hidden",
  shown: "Shown",
  changed: "Changed",
};

/** Count markers for a short "3 moved, 1 added" line. */
export function markerSummary(markers: Record<string, Marker>): string {
  const counts = new Map<Marker, number>();
  for (const m of Object.values(markers)) counts.set(m, (counts.get(m) ?? 0) + 1);
  if (!counts.size) return "No differences";
  return [...counts.entries()].map(([m, n]) => `${n} ${MARKER_WORDS[m].toLowerCase()}`).join(", ");
}

// ---- Comments -------------------------------------------------------------------

export type Thread = { root: ViewComment; replies: ViewComment[] };

export function threadsByNode(comments: ViewComment[]): Map<string, Thread[]> {
  const roots = comments.filter((c) => !c.parent_id);
  const out = new Map<string, Thread[]>();
  for (const r of roots) {
    const t: Thread = { root: r, replies: comments.filter((c) => c.parent_id === r.id) };
    out.set(r.node_id, [...(out.get(r.node_id) ?? []), t]);
  }
  return out;
}

/** Open (unresolved) thread count per item, for the pinned dots. */
export function openCounts(comments: ViewComment[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const c of comments) if (!c.parent_id && !c.resolved) out[c.node_id] = (out[c.node_id] ?? 0) + 1;
  return out;
}

/** Comments pinned to items no longer on the screen. */
export function orphanThreads(comments: ViewComment[], index: TreeIndex): ViewComment[] {
  return comments.filter((c) => !c.parent_id && !index.byId.has(c.node_id));
}

// ---- Command bar ----------------------------------------------------------------

export type JumpItem = { id: string; label: string; hint: string };

export function jumpItems(index: TreeIndex): JumpItem[] {
  const out: JumpItem[] = [];
  for (const n of index.byId.values()) {
    if (n.kind === "root" || n.helper) continue;
    if (!["field", "group", "page", "notebook", "button"].includes(n.tag)) continue;
    out.push({ id: n.id, label: n.label || n.name || n.tag, hint: n.tag === "field" ? n.name ?? "field" : n.tag });
  }
  return out.sort((a, b) => a.label.localeCompare(b.label));
}
