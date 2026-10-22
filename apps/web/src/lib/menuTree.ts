/**
 * UI-S-13 Menus: pure tree logic for the menus screen.
 * Flattening for the APG tree pattern, keyboard moves, drop validation, and draft helpers.
 * No React here; components call these and stay presentational.
 */
import type { MenuNode, SnapshotRow } from "@/lib/api";

export type TreeRow = {
  menu: MenuNode;
  level: number;
  posinset: number;
  setsize: number;
  hasChildren: boolean;
  expanded: boolean;
  parentId: number | null;
};

const bySequence = (a: MenuNode, b: MenuNode) => a.sequence - b.sequence || a.id - b.id;

/** Roots are menus with no parent, or whose parent is not in the list (keeps orphans reachable). */
export function treeRoots(menus: MenuNode[]): MenuNode[] {
  const ids = new Set(menus.map((m) => m.id));
  return menus.filter((m) => m.parent_id == null || !ids.has(m.parent_id)).sort(bySequence);
}

function kidsOf(menus: MenuNode[], id: number): MenuNode[] {
  return menus.filter((m) => m.parent_id === id).sort(bySequence);
}

/**
 * Visible rows in display order. While a filter is active every matching branch is open,
 * so a match is never hidden behind a collapsed parent.
 */
export function flattenMenuTree(
  menus: MenuNode[],
  opts: { collapsed: ReadonlySet<number>; visible: ReadonlySet<number> | null },
): TreeRow[] {
  const { collapsed, visible } = opts;
  const keep = (m: MenuNode) => visible == null || visible.has(m.id);
  const rows: TreeRow[] = [];
  const seen = new Set<number>();
  const walk = (nodes: MenuNode[], level: number, parentId: number | null) => {
    const shown = nodes.filter((n) => keep(n) && !seen.has(n.id));
    shown.forEach((menu, i) => {
      seen.add(menu.id);
      const kids = kidsOf(menus, menu.id).filter((k) => keep(k) && !seen.has(k.id));
      const hasChildren = kids.length > 0;
      const expanded = hasChildren && (visible != null || !collapsed.has(menu.id));
      rows.push({ menu, level, posinset: i + 1, setsize: shown.length, hasChildren, expanded, parentId });
      if (expanded) walk(kids, level + 1, menu.id);
    });
  };
  walk(treeRoots(menus), 1, null);
  return rows;
}

export type TreeKeyAction =
  | { type: "focus"; id: number }
  | { type: "expand"; id: number }
  | { type: "collapse"; id: number }
  | { type: "select"; id: number };

/** WAI-ARIA tree view keyboard model (single select, selection does not follow focus). */
export function treeKeyAction(rows: TreeRow[], focusedId: number | null, key: string): TreeKeyAction | null {
  if (rows.length === 0) return null;
  const index = rows.findIndex((r) => r.menu.id === focusedId);
  const row = index >= 0 ? rows[index] : null;
  switch (key) {
    case "ArrowDown":
      if (!row) return { type: "focus", id: rows[0].menu.id };
      return index < rows.length - 1 ? { type: "focus", id: rows[index + 1].menu.id } : null;
    case "ArrowUp":
      if (!row) return { type: "focus", id: rows[rows.length - 1].menu.id };
      return index > 0 ? { type: "focus", id: rows[index - 1].menu.id } : null;
    case "Home":
      return { type: "focus", id: rows[0].menu.id };
    case "End":
      return { type: "focus", id: rows[rows.length - 1].menu.id };
    case "ArrowRight":
      if (!row || !row.hasChildren) return null;
      if (!row.expanded) return { type: "expand", id: row.menu.id };
      return index < rows.length - 1 ? { type: "focus", id: rows[index + 1].menu.id } : null;
    case "ArrowLeft":
      if (!row) return null;
      if (row.expanded) return { type: "collapse", id: row.menu.id };
      return row.parentId != null && rows.some((r) => r.menu.id === row.parentId)
        ? { type: "focus", id: row.parentId }
        : null;
    case "Enter":
    case " ":
      return row ? { type: "select", id: row.menu.id } : null;
    default:
      return null;
  }
}

/** Type-ahead: the next visible row (after the focused one, wrapping) whose label starts with the text. */
export function typeaheadMatch(rows: TreeRow[], fromId: number | null, text: string): number | null {
  const needle = text.trim().toLowerCase();
  if (!needle || rows.length === 0) return null;
  const start = Math.max(0, rows.findIndex((r) => r.menu.id === fromId));
  for (let step = 1; step <= rows.length; step += 1) {
    const row = rows[(start + step) % rows.length];
    if (row.menu.name.toLowerCase().startsWith(needle)) return row.menu.id;
  }
  return null;
}

export function descendantsOf(menus: MenuNode[], id: number): Set<number> {
  const out = new Set<number>();
  const stack = [id];
  while (stack.length) {
    const pid = stack.pop() as number;
    for (const m of menus) {
      if (m.parent_id === pid && !out.has(m.id) && m.id !== id) {
        out.add(m.id);
        stack.push(m.id);
      }
    }
  }
  return out;
}

export type DropRefusalKind = "self" | "descendant" | "same" | "missing";

export type DropVerdict =
  | { ok: true; parentId: number | null; title: string }
  | { ok: false; kind: DropRefusalKind; title: string; why: string; next: string };

/** Top level is `null`. Odoo refuses recursive menus, so a branch can't move into itself. */
export function dropVerdict(menus: MenuNode[], dragId: number, targetParentId: number | null): DropVerdict {
  const dragged = menus.find((m) => m.id === dragId);
  if (!dragged) {
    return {
      ok: false,
      kind: "missing",
      title: "That menu is no longer in the tree",
      why: "Odoo returned a newer tree while you were dragging.",
      next: "Drag it again from its current place.",
    };
  }
  const name = `“${dragged.name}”`;
  const target = targetParentId == null ? null : menus.find((m) => m.id === targetParentId) ?? null;
  if (targetParentId != null && !target) {
    return {
      ok: false,
      kind: "missing",
      title: "That parent is no longer in the tree",
      why: "Odoo returned a newer tree while you were dragging.",
      next: "Drop it on a menu you can see now.",
    };
  }
  const currentParent = dragged.parent_id ?? null;
  if (targetParentId === dragId) {
    return {
      ok: false,
      kind: "self",
      title: `Can't move ${name} into itself`,
      why: "A menu can't be its own parent.",
      next: "Drop it on another menu, or on Top level.",
    };
  }
  if (target && descendantsOf(menus, dragId).has(target.id)) {
    return {
      ok: false,
      kind: "descendant",
      title: `Can't move ${name} under “${target.name}”`,
      why: `“${target.name}” sits inside ${name}. The menu would loop back into itself, and Odoo refuses recursive menus.`,
      next: "Drop it on a menu outside its own branch, or on Top level.",
    };
  }
  if (currentParent === targetParentId) {
    return {
      ok: false,
      kind: "same",
      title: target ? `${name} is already under “${target.name}”` : `${name} is already a top-level app`,
      why: "Nothing would change.",
      next: "Change Sequence to reorder it among its siblings.",
    };
  }
  return {
    ok: true,
    parentId: targetParentId,
    title: target ? `Move ${name} under “${target.name}”` : `Make ${name} a top-level app`,
  };
}

/** The tree as it will look once the draft parent is saved. */
export function applyDraftParent(
  menus: MenuNode[],
  draft: { menuId: number; parentId: number | null } | null,
): MenuNode[] {
  if (!draft) return menus;
  const parent = draft.parentId == null ? null : menus.find((m) => m.id === draft.parentId) ?? null;
  return menus.map((m) =>
    m.id === draft.menuId ? { ...m, parent_id: draft.parentId, parent_name: parent?.name ?? null } : m,
  );
}

/** Labels from the root down to the menu, for a breadcrumb. */
export function menuPath(menus: MenuNode[], id: number): string[] {
  const byId = new Map(menus.map((m) => [m.id, m]));
  const out: string[] = [];
  const seen = new Set<number>();
  let cur = byId.get(id);
  while (cur && !seen.has(cur.id)) {
    seen.add(cur.id);
    out.unshift(cur.name);
    cur = cur.parent_id != null ? byId.get(cur.parent_id) : undefined;
  }
  return out;
}

export type MenuDraft = {
  name: string;
  parentId: number | null;
  sequence: number;
  actionId: number | null;
  groupIds: number[];
};

/** Which fields differ from what Odoo has, in reading order. */
export function menuDraftChanges(menu: MenuNode, draft: MenuDraft): string[] {
  const out: string[] = [];
  if (draft.name.trim() !== menu.name) out.push("label");
  if ((draft.parentId ?? null) !== (menu.parent_id ?? null)) out.push("parent");
  if (draft.sequence !== menu.sequence) out.push("sequence");
  if ((draft.actionId ?? null) !== (menu.action_id ?? null)) out.push("action");
  const a = [...draft.groupIds].sort((x, y) => x - y).join(",");
  const b = [...(menu.group_ids ?? [])].sort((x, y) => x - y).join(",");
  if (a !== b) out.push("visibility");
  return out;
}

export function changeSummary(changes: string[]): string {
  if (changes.length === 0) return "No changes";
  const list =
    changes.length === 1
      ? changes[0]
      : `${changes.slice(0, -1).join(", ")} and ${changes[changes.length - 1]}`;
  return `${changes.length === 1 ? "1 change" : `${changes.length} changes`}: ${list}`;
}

const REVERSIBLE: Record<string, string> = {
  yes: "Restorable",
  partial: "Partly restorable",
  no: "Not restorable",
};

export function snapshotRestoreLabel(reversible: string): string {
  return REVERSIBLE[reversible] ?? reversible;
}

export function snapshotKindLabel(row: SnapshotRow): string {
  if (row.resource_type === "menu") return "Menu";
  if (row.resource_type === "action") return "Window action";
  return row.resource_type;
}

/** Readable local time; falls back to the raw value when it does not parse. */
export function formatSnapshotTime(iso: string | null, locale?: string, timeZone?: string): string {
  if (!iso) return "Time not recorded";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone,
  }).format(d);
}

/** Short line shown on the hovered row while dragging. */
export function dropHint(verdict: DropVerdict): string {
  if (verdict.ok) return verdict.parentId == null ? "Drop to make it a top-level app" : "Drop to move it here";
  switch (verdict.kind) {
    case "self":
      return "Can't drop a menu on itself";
    case "descendant":
      return "Can't drop inside its own branch";
    case "same":
      return "Already its parent";
    default:
      return "No longer in the tree";
  }
}

export type MenusErrorContext = "load" | "create" | "save" | "delete" | "restore" | "bind" | "probe";

const ERROR_COPY: Record<MenusErrorContext, { title: string; next: string }> = {
  load: { title: "Menus didn't load", next: "Check the connection on Overview, then try again." },
  create: { title: "Odoo didn't create the menu", next: "Fix what Odoo named above, then create it again. Your draft is still here." },
  save: { title: "Odoo didn't save the menu", next: "Fix what Odoo named above, then save again. Your edits are still here." },
  delete: { title: "Odoo didn't delete the menu", next: "Try again, or check whether another menu or module still uses it." },
  restore: { title: "The snapshot didn't restore", next: "Open the Change journal to see what Odoo kept." },
  bind: { title: "Odoo didn't create the action", next: "Check the model's technical name, then try again." },
  probe: { title: "The capability check didn't finish", next: "Run Re-probe again in a moment." },
};

/** What happened, why (Odoo's own words), and what to do next. */
export function menusErrorGuide(context: MenusErrorContext, message: string) {
  const copy = ERROR_COPY[context];
  return { title: copy.title, why: message.trim() || "Odoo did not say why.", next: copy.next };
}
