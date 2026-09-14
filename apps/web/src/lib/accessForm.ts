import type { AccessRightRow, RecordRuleRow } from "@/lib/api";

export const CONFIRM_PHRASE = "I understand the risks";

export const DEFAULT_ACCESS_MODEL = "res.partner";

export const ACCESS_DELETE_RISKS = [
  "Users may lose or gain unintended access",
  "Can lock operators out of custom models if no other ACL remains",
  "A snapshot is taken so the access line can be restored when Odoo allows it",
];

export const RULE_DELETE_RISKS = [
  "May expose records previously filtered by domain",
  "Or hide records if other rules still apply",
  "A snapshot is taken so the rule definition can be restored when Odoo allows it",
];

export type CrudPermits = {
  perm_read: boolean;
  perm_write: boolean;
  perm_create: boolean;
  perm_unlink: boolean;
};

export const CRUD_KEYS = [
  ["perm_read", "Read"],
  ["perm_write", "Write"],
  ["perm_create", "Create"],
  ["perm_unlink", "Delete"],
] as const;

export type AccessComposerForm = {
  name: string;
  group_id: string;
  perm_read: boolean;
  perm_write: boolean;
  perm_create: boolean;
  perm_unlink: boolean;
};

export type RuleComposerForm = {
  name: string;
  domain_force: string;
  group_ids: number[];
  perm_read: boolean;
  perm_write: boolean;
  perm_create: boolean;
  perm_unlink: boolean;
};

export type AccessSessionState = "draft" | "unsaved" | "saved";

export type AccessPane = "new-access" | "new-rule" | "access" | "rule";

export function defaultAccessForm(): AccessComposerForm {
  return {
    name: "",
    group_id: "",
    perm_read: true,
    perm_write: true,
    perm_create: true,
    perm_unlink: false,
  };
}

export function defaultRuleForm(): RuleComposerForm {
  return {
    name: "",
    domain_force: "[('create_uid', '=', user.id)]",
    group_ids: [],
    perm_read: true,
    perm_write: true,
    perm_create: true,
    perm_unlink: true,
  };
}

export function composerSessionState(opts: {
  dirty: boolean;
  savedOnce: boolean;
}): AccessSessionState {
  if (opts.dirty) return "unsaved";
  if (opts.savedOnce) return "saved";
  return "draft";
}

export function isComposerDirty<T>(form: T, baseline: T): boolean {
  return JSON.stringify(form) !== JSON.stringify(baseline);
}

export function filterByQuery<T>(
  rows: T[],
  query: string,
  haystack: (row: T) => string,
): T[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return rows;
  return rows.filter((row) => haystack(row).toLowerCase().includes(needle));
}

export function crudLetters(row: CrudPermits): string {
  return (
    [row.perm_read && "R", row.perm_write && "W", row.perm_create && "C", row.perm_unlink && "D"]
      .filter(Boolean)
      .join("") || "—"
  );
}

export function parseModelList(raw: string): string[] {
  return raw
    .split(",")
    .map((m) => m.trim())
    .filter(Boolean);
}

export function isGlobalAccess(groupId: string | number | null | undefined): boolean {
  if (groupId == null) return true;
  if (typeof groupId === "number") return false;
  return groupId.trim() === "";
}

export function isGlobalRule(groupIds: number[]): boolean {
  return groupIds.length === 0;
}

export function accessFormFromRow(row: AccessRightRow): AccessComposerForm {
  return {
    name: row.name,
    group_id: row.group_id != null ? String(row.group_id) : "",
    perm_read: row.perm_read,
    perm_write: row.perm_write,
    perm_create: row.perm_create,
    perm_unlink: row.perm_unlink,
  };
}

export function ruleFormFromRow(row: RecordRuleRow): RuleComposerForm {
  return {
    name: row.name,
    domain_force: row.domain_force || "[]",
    group_ids: row.group_ids ?? [],
    perm_read: row.perm_read,
    perm_write: row.perm_write,
    perm_create: row.perm_create,
    perm_unlink: row.perm_unlink,
  };
}

export function designerHref(connectionId: string, model: string): string {
  const base = `/connections/${connectionId}/designer`;
  const trimmed = model.trim();
  return trimmed ? `${base}?model=${encodeURIComponent(trimmed)}` : base;
}

export function builderHref(connectionId: string, model: string): string {
  const base = `/connections/${connectionId}/builder`;
  const trimmed = model.trim();
  return trimmed ? `${base}?model=${encodeURIComponent(trimmed)}` : base;
}

export function menusHref(connectionId: string, model?: string): string {
  const base = `/connections/${connectionId}/menus`;
  const trimmed = (model ?? "").trim();
  return trimmed ? `${base}?model=${encodeURIComponent(trimmed)}` : base;
}
