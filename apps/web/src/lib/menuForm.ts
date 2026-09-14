import type { MenuNode, WindowActionRow } from "@/lib/api";

export const CONFIRM_PHRASE = "I understand the risks";

export const MENUS_REPORTS_CAVEAT =
  "Menus / QWeb reports are experimental on Odoo 16 — verify in Open-in-Odoo after create.";

export const DEFAULT_ROOT_ICON = "base,static/description/icon.png";

export const MENU_DELETE_RISKS = [
  "Child menus may cascade or become orphans depending on Odoo",
  "Actions bound only via this menu remain but are harder to find",
  "A snapshot is taken so the menu definition can be restored when Odoo allows it",
];

export type MenuComposerForm = {
  name: string;
  parent_id: string;
  sequence: number;
  web_icon: string;
  action_id: string;
  action_mode: "existing" | "create";
  action_name: string;
  action_model: string;
  action_view_mode: string;
  group_ids: number[];
};

export type MenuSessionState = "draft" | "unsaved" | "saved";

export function defaultMenuForm(viewMode = "list,form"): MenuComposerForm {
  return {
    name: "",
    parent_id: "",
    sequence: 10,
    web_icon: DEFAULT_ROOT_ICON,
    action_id: "",
    action_mode: "existing",
    action_name: "",
    action_model: "",
    action_view_mode: viewMode,
    group_ids: [],
  };
}

export function composerSessionState(opts: {
  dirty: boolean;
  savedOnce: boolean;
}): MenuSessionState {
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

export function childrenOf(menus: MenuNode[], parentId: number): MenuNode[] {
  return menus
    .filter((m) => m.parent_id === parentId)
    .sort((a, b) => a.sequence - b.sequence || a.id - b.id);
}

export function rootMenus(menus: MenuNode[]): MenuNode[] {
  return menus
    .filter((m) => !m.parent_id)
    .sort((a, b) => a.sequence - b.sequence || a.id - b.id);
}

export function menuById(menus: MenuNode[], id: number | null): MenuNode | null {
  if (id == null) return null;
  return menus.find((m) => m.id === id) ?? null;
}

/** Ancestors of matching nodes stay visible so a filtered tree still has context. */
export function visibleMenuIds(menus: MenuNode[], query: string): Set<number> | null {
  const needle = query.trim().toLowerCase();
  if (!needle) return null;
  const byId = new Map(menus.map((m) => [m.id, m]));
  const visible = new Set<number>();
  for (const menu of menus) {
    const hay = `${menu.name} #${menu.id} ${menu.action_id ?? ""}`.toLowerCase();
    if (!hay.includes(needle)) continue;
    visible.add(menu.id);
    let pid = menu.parent_id;
    while (pid != null && byId.has(pid)) {
      visible.add(pid);
      pid = byId.get(pid)?.parent_id ?? null;
    }
  }
  return visible;
}

export function descendantIds(menus: MenuNode[], id: number): Set<number> {
  const out = new Set<number>();
  const walk = (pid: number) => {
    for (const child of childrenOf(menus, pid)) {
      out.add(child.id);
      walk(child.id);
    }
  };
  walk(id);
  return out;
}

/** Parent cannot be the menu itself or one of its descendants. */
export function wouldCreateCycle(
  menus: MenuNode[],
  menuId: number,
  parentId: number | null,
): boolean {
  if (parentId == null) return false;
  if (parentId === menuId) return true;
  return descendantIds(menus, menuId).has(parentId);
}

export function parentSelectOptions(
  menus: MenuNode[],
  currentId?: number | null,
): Array<{ value: string; label: string }> {
  const blocked = currentId != null ? descendantIds(menus, currentId) : new Set<number>();
  if (currentId != null) blocked.add(currentId);
  return [
    { value: "", label: "Root app" },
    ...menus
      .filter((m) => !blocked.has(m.id))
      .map((m) => ({
        value: String(m.id),
        label: m.parent_name ? `${m.name} · under ${m.parent_name}` : `${m.name} (#${m.id})`,
      })),
  ];
}

export function boundAction(
  actions: WindowActionRow[],
  actionId: number | null | undefined,
): WindowActionRow | null {
  if (actionId == null) return null;
  return actions.find((a) => a.id === actionId) ?? null;
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

export function accessHref(connectionId: string, model: string): string {
  const base = `/connections/${connectionId}/access`;
  const trimmed = model.trim();
  return trimmed ? `${base}?model=${encodeURIComponent(trimmed)}` : base;
}

export function groupIdsOf(menu: MenuNode): number[] {
  return menu.group_ids ?? [];
}
