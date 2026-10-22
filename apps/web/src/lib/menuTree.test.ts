import { describe, expect, it } from "vitest";
import type { MenuNode } from "@/lib/api";
import {
  applyDraftParent,
  changeSummary,
  dropVerdict,
  flattenMenuTree,
  formatSnapshotTime,
  menuDraftChanges,
  menuPath,
  snapshotRestoreLabel,
  treeKeyAction,
  treeRoots,
  typeaheadMatch,
} from "./menuTree";
import { visibleMenuIds } from "./menuForm";

const m = (id: number, name: string, parent_id: number | null, sequence = 10): MenuNode => ({
  id,
  name,
  parent_id,
  action: null,
  action_id: null,
  sequence,
  web_icon: null,
  child_count: 0,
  group_ids: [],
});

// Front desk(1) > Visitors(2) > Checked in(3), Expected(4); Front desk > Config(5) > Badges(6); Fleet(7)
const menus: MenuNode[] = [
  m(1, "Front desk", null, 10),
  m(2, "Visitors", 1, 10),
  m(3, "Checked in", 2, 10),
  m(4, "Expected today", 2, 20),
  m(5, "Configuration", 1, 90),
  m(6, "Badge types", 5, 10),
  m(7, "Fleet", null, 20),
];

const open = { collapsed: new Set<number>(), visible: null };

describe("flattenMenuTree", () => {
  it("orders rows depth-first with level, posinset and setsize", () => {
    const rows = flattenMenuTree(menus, open);
    expect(rows.map((r) => r.menu.id)).toEqual([1, 2, 3, 4, 5, 6, 7]);
    const visitors = rows[1];
    expect(visitors).toMatchObject({ level: 2, posinset: 1, setsize: 2, hasChildren: true, expanded: true, parentId: 1 });
    expect(rows[6]).toMatchObject({ level: 1, posinset: 2, setsize: 2, hasChildren: false, expanded: false });
  });

  it("hides children of a collapsed parent", () => {
    const rows = flattenMenuTree(menus, { collapsed: new Set([2]), visible: null });
    expect(rows.map((r) => r.menu.id)).toEqual([1, 2, 5, 6, 7]);
    expect(rows[1].expanded).toBe(false);
  });

  it("opens every matching branch while filtering, even if collapsed", () => {
    const visible = visibleMenuIds(menus, "badge");
    const rows = flattenMenuTree(menus, { collapsed: new Set([1, 5]), visible });
    expect(rows.map((r) => r.menu.id)).toEqual([1, 5, 6]);
  });

  it("keeps orphans reachable as roots and survives a parent loop", () => {
    const orphan = [m(10, "Lost", 99), m(11, "A", 12), m(12, "B", 11)];
    expect(treeRoots(orphan).map((r) => r.id)).toEqual([10]);
    expect(() => flattenMenuTree(orphan, open)).not.toThrow();
  });
});

describe("treeKeyAction", () => {
  const rows = flattenMenuTree(menus, open);
  it("moves focus with arrows, Home and End", () => {
    expect(treeKeyAction(rows, 1, "ArrowDown")).toEqual({ type: "focus", id: 2 });
    expect(treeKeyAction(rows, 2, "ArrowUp")).toEqual({ type: "focus", id: 1 });
    expect(treeKeyAction(rows, 4, "Home")).toEqual({ type: "focus", id: 1 });
    expect(treeKeyAction(rows, 1, "End")).toEqual({ type: "focus", id: 7 });
    expect(treeKeyAction(rows, 7, "ArrowDown")).toBeNull();
  });

  it("ArrowRight expands, then enters the first child; leaves do nothing", () => {
    const closed = flattenMenuTree(menus, { collapsed: new Set([2]), visible: null });
    expect(treeKeyAction(closed, 2, "ArrowRight")).toEqual({ type: "expand", id: 2 });
    expect(treeKeyAction(rows, 2, "ArrowRight")).toEqual({ type: "focus", id: 3 });
    expect(treeKeyAction(rows, 3, "ArrowRight")).toBeNull();
  });

  it("ArrowLeft collapses an open parent, otherwise goes to the parent", () => {
    expect(treeKeyAction(rows, 2, "ArrowLeft")).toEqual({ type: "collapse", id: 2 });
    expect(treeKeyAction(rows, 4, "ArrowLeft")).toEqual({ type: "focus", id: 2 });
    expect(treeKeyAction(rows, 7, "ArrowLeft")).toBeNull();
  });

  it("Enter and Space select", () => {
    expect(treeKeyAction(rows, 6, "Enter")).toEqual({ type: "select", id: 6 });
    expect(treeKeyAction(rows, 6, " ")).toEqual({ type: "select", id: 6 });
  });

  it("type-ahead finds the next label that starts with the text, wrapping", () => {
    expect(typeaheadMatch(rows, 1, "e")).toBe(4);
    expect(typeaheadMatch(rows, 7, "f")).toBe(1);
    expect(typeaheadMatch(rows, 1, "zz")).toBeNull();
  });
});

describe("dropVerdict", () => {
  it("refuses a drop on itself", () => {
    const v = dropVerdict(menus, 2, 2);
    expect(v.ok).toBe(false);
    if (!v.ok) {
      expect(v.kind).toBe("self");
      expect(v.why).toBe("A menu can't be its own parent.");
    }
  });

  it("refuses a drop inside its own branch and names both menus", () => {
    const v = dropVerdict(menus, 1, 6);
    expect(v.ok).toBe(false);
    if (!v.ok) {
      expect(v.kind).toBe("descendant");
      expect(v.title).toBe("Can't move “Front desk” under “Badge types”");
      expect(v.why).toContain("Odoo refuses recursive menus");
      expect(v.next).toContain("Top level");
    }
  });

  it("treats the current parent as a no-op, not a move", () => {
    const v = dropVerdict(menus, 3, 2);
    expect(v).toMatchObject({ ok: false, kind: "same" });
    expect(dropVerdict(menus, 7, null)).toMatchObject({ ok: false, kind: "same", title: "“Fleet” is already a top-level app" });
  });

  it("accepts a move to another branch or to top level", () => {
    expect(dropVerdict(menus, 6, 2)).toEqual({ ok: true, parentId: 2, title: "Move “Badge types” under “Visitors”" });
    expect(dropVerdict(menus, 6, null)).toEqual({ ok: true, parentId: null, title: "Make “Badge types” a top-level app" });
  });

  it("refuses stale ids", () => {
    expect(dropVerdict(menus, 99, 1)).toMatchObject({ ok: false, kind: "missing" });
    expect(dropVerdict(menus, 6, 99)).toMatchObject({ ok: false, kind: "missing" });
  });
});

describe("draft helpers", () => {
  it("previews a draft parent in the tree", () => {
    const next = applyDraftParent(menus, { menuId: 6, parentId: 2 });
    const rows = flattenMenuTree(next, open);
    expect(rows.find((r) => r.menu.id === 6)).toMatchObject({ level: 3, parentId: 2 });
    expect(next.find((x) => x.id === 6)?.parent_name).toBe("Visitors");
    expect(applyDraftParent(menus, null)).toBe(menus);
  });

  it("builds a breadcrumb path", () => {
    expect(menuPath(menus, 6)).toEqual(["Front desk", "Configuration", "Badge types"]);
  });

  it("lists changed fields in reading order and summarises them", () => {
    const base = { name: "Visitors", parentId: 1, sequence: 10, actionId: null, groupIds: [] as number[] };
    expect(menuDraftChanges(menus[1], base)).toEqual([]);
    const changes = menuDraftChanges(menus[1], { ...base, parentId: 7, sequence: 5, groupIds: [3] });
    expect(changes).toEqual(["parent", "sequence", "visibility"]);
    expect(changeSummary(changes)).toBe("3 changes: parent, sequence and visibility");
    expect(changeSummary(["label"])).toBe("1 change: label");
    expect(changeSummary([])).toBe("No changes");
  });

  it("labels snapshots in plain words", () => {
    expect(snapshotRestoreLabel("yes")).toBe("Restorable");
    expect(snapshotRestoreLabel("partial")).toBe("Partly restorable");
    expect(formatSnapshotTime(null)).toBe("Time not recorded");
    expect(formatSnapshotTime("not a date")).toBe("not a date");
    expect(formatSnapshotTime("2026-10-05T17:40:00Z", "en-GB", "Africa/Lagos")).toBe("5 Oct, 18:40");
  });
});

describe("dropHint", () => {
  it("gives a short reason per verdict", async () => {
    const { dropHint } = await import("./menuTree");
    expect(dropHint(dropVerdict(menus, 1, 6))).toBe("Can't drop inside its own branch");
    expect(dropHint(dropVerdict(menus, 2, 2))).toBe("Can't drop a menu on itself");
    expect(dropHint(dropVerdict(menus, 3, 2))).toBe("Already its parent");
    expect(dropHint(dropVerdict(menus, 6, 2))).toBe("Drop to move it here");
    expect(dropHint(dropVerdict(menus, 6, null))).toBe("Drop to make it a top-level app");
  });
});

describe("menusErrorGuide", () => {
  it("keeps Odoo's reason and adds a next step", async () => {
    const { menusErrorGuide } = await import("./menuTree");
    expect(menusErrorGuide("load", "Access Denied")).toEqual({
      title: "Menus didn't load",
      why: "Access Denied",
      next: "Check the connection on Overview, then try again.",
    });
    expect(menusErrorGuide("save", "  ").why).toBe("Odoo did not say why.");
  });
});
