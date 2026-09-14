import { describe, expect, it } from "vitest";
import type { MenuNode } from "@/lib/api";
import {
  accessHref,
  builderHref,
  childrenOf,
  composerSessionState,
  defaultMenuForm,
  descendantIds,
  designerHref,
  isComposerDirty,
  parentSelectOptions,
  rootMenus,
  visibleMenuIds,
  wouldCreateCycle,
} from "./menuForm";

const menus: MenuNode[] = [
  {
    id: 1,
    name: "Sales",
    parent_id: null,
    action: null,
    action_id: null,
    sequence: 10,
    web_icon: "base,static/description/icon.png",
    child_count: 2,
    group_ids: [4],
  },
  {
    id: 2,
    name: "Orders",
    parent_id: 1,
    action: "ir.actions.act_window,9",
    action_id: 9,
    sequence: 10,
    web_icon: null,
    child_count: 1,
  },
  {
    id: 3,
    name: "Quotes",
    parent_id: 2,
    action: null,
    action_id: null,
    sequence: 5,
    web_icon: null,
    child_count: 0,
  },
  {
    id: 4,
    name: "Contacts",
    parent_id: null,
    action: "ir.actions.act_window,11",
    action_id: 11,
    sequence: 20,
    web_icon: null,
    child_count: 0,
  },
];

describe("composerSessionState", () => {
  it("maps dirty / savedOnce to chrome states", () => {
    expect(composerSessionState({ dirty: true, savedOnce: false })).toBe("unsaved");
    expect(composerSessionState({ dirty: false, savedOnce: true })).toBe("saved");
    expect(composerSessionState({ dirty: false, savedOnce: false })).toBe("draft");
  });
});

describe("isComposerDirty", () => {
  it("detects form vs baseline", () => {
    const a = defaultMenuForm();
    const b = defaultMenuForm();
    expect(isComposerDirty(a, b)).toBe(false);
    b.name = "Visitor log";
    expect(isComposerDirty(a, b)).toBe(true);
  });
});

describe("tree helpers", () => {
  it("sorts roots and children by sequence", () => {
    expect(rootMenus(menus).map((m) => m.id)).toEqual([1, 4]);
    expect(childrenOf(menus, 1).map((m) => m.id)).toEqual([2]);
    expect(childrenOf(menus, 2).map((m) => m.id)).toEqual([3]);
  });

  it("keeps ancestors when filtering", () => {
    const visible = visibleMenuIds(menus, "quotes");
    expect(visible).toEqual(new Set([1, 2, 3]));
  });

  it("blocks a parent that would cycle", () => {
    expect(descendantIds(menus, 1)).toEqual(new Set([2, 3]));
    expect(wouldCreateCycle(menus, 1, 3)).toBe(true);
    expect(wouldCreateCycle(menus, 1, 1)).toBe(true);
    expect(wouldCreateCycle(menus, 1, 4)).toBe(false);
    expect(wouldCreateCycle(menus, 1, null)).toBe(false);
  });

  it("omits self and descendants from parent options", () => {
    const opts = parentSelectOptions(menus, 1);
    expect(opts[0]).toEqual({ value: "", label: "Root app" });
    expect(opts.map((o) => o.value)).toEqual(["", "4"]);
  });
});

describe("hrefs", () => {
  it("encodes model query for Designer, Builder, and Access", () => {
    expect(designerHref("c1", "res.partner")).toBe(
      "/connections/c1/designer?model=res.partner",
    );
    expect(builderHref("c1", "x_ticket")).toBe("/connections/c1/builder?model=x_ticket");
    expect(accessHref("c1", "res.partner")).toBe(
      "/connections/c1/access?model=res.partner",
    );
  });
});
