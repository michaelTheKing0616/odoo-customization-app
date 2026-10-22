/** @vitest-environment jsdom */
import React from "react";
import { cleanup, createEvent, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { MenuNode } from "@/lib/api";
import { MenusTree } from "./MenusTree";

afterEach(() => cleanup());

const menus: MenuNode[] = [
  {
    id: 1,
    name: "Sales",
    parent_id: null,
    action: null,
    action_id: null,
    sequence: 10,
    web_icon: null,
    child_count: 1,
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
    name: "Quotations",
    parent_id: 2,
    action: null,
    action_id: null,
    sequence: 10,
    web_icon: null,
    child_count: 0,
  },
  {
    id: 4,
    name: "Contacts",
    parent_id: null,
    action: null,
    action_id: null,
    sequence: 20,
    web_icon: null,
    child_count: 0,
  },
];

function renderTree(props: Partial<React.ComponentProps<typeof MenusTree>> = {}) {
  const handlers = {
    onSelect: vi.fn(),
    onCreate: vi.fn(),
    onQueryChange: vi.fn(),
    onMove: vi.fn(),
  };
  render(
    <MenusTree menus={menus} selectedId={null} query="" {...handlers} {...props} />,
  );
  return handlers;
}

/** jsdom has no DataTransfer; a plain stub carries the fields React reads. */
function dataTransfer() {
  const store = new Map<string, string>();
  return {
    dropEffect: "none",
    effectAllowed: "all",
    setData: (k: string, v: string) => store.set(k, v),
    getData: (k: string) => store.get(k) ?? "",
    types: [] as string[],
  };
}

function drag(node: HTMLElement, type: "dragStart" | "dragEnter" | "dragOver" | "drop" | "dragEnd", dt: object) {
  const ev = createEvent[type](node);
  Object.defineProperty(ev, "dataTransfer", { value: dt });
  fireEvent(node, ev);
}

describe("MenusTree", () => {
  it("filters by name and calls onSelect", () => {
    const { onSelect } = renderTree({ query: "orders" });
    expect(screen.getByText("Sales")).toBeInTheDocument();
    expect(screen.queryByText("Contacts")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("menu-row-2"));
    expect(onSelect).toHaveBeenCalledWith(menus[1]);
  });

  it("shows empty state with create action", () => {
    const onCreate = vi.fn();
    render(
      <MenusTree
        menus={[]}
        selectedId={null}
        query=""
        onQueryChange={vi.fn()}
        onSelect={vi.fn()}
        onCreate={onCreate}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Create menu" }));
    expect(onCreate).toHaveBeenCalledTimes(1);
  });

  it("offers Clear filter when nothing matches", () => {
    const { onQueryChange } = renderTree({ query: "zzz" });
    expect(screen.getByText("No matching menus")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Clear filter" }));
    expect(onQueryChange).toHaveBeenCalledWith("");
  });

  it("exposes the APG tree roles and levels", () => {
    renderTree({ selectedId: 2 });
    const tree = screen.getByRole("tree", { name: /Menu tree/ });
    expect(tree).toBeInTheDocument();
    const sales = screen.getByRole("treeitem", { name: "Sales" });
    expect(sales).toHaveAttribute("aria-level", "1");
    expect(sales).toHaveAttribute("aria-expanded", "true");
    expect(sales).toHaveAttribute("aria-setsize", "2");
    expect(sales).toHaveAttribute("aria-posinset", "1");
    const orders = screen.getByRole("treeitem", { name: "Orders" });
    expect(orders).toHaveAttribute("aria-level", "2");
    expect(orders).toHaveAttribute("aria-selected", "true");
    // Leaves carry no aria-expanded.
    expect(screen.getByRole("treeitem", { name: "Contacts" })).not.toHaveAttribute("aria-expanded");
    // Roving tabindex: only the selected row is in the tab order.
    expect(orders).toHaveAttribute("tabindex", "0");
    expect(sales).toHaveAttribute("tabindex", "-1");
  });

  it("walks the tree with arrow keys, collapses and expands, and selects on Enter", () => {
    const { onSelect } = renderTree();
    const tree = screen.getByRole("tree");
    const sales = screen.getByRole("treeitem", { name: "Sales" });
    sales.focus();
    fireEvent.keyDown(tree, { key: "ArrowDown" });
    expect(screen.getByRole("treeitem", { name: "Orders" })).toHaveFocus();
    fireEvent.keyDown(tree, { key: "ArrowRight" });
    expect(screen.getByRole("treeitem", { name: "Quotations" })).toHaveFocus();
    fireEvent.keyDown(tree, { key: "ArrowLeft" });
    expect(screen.getByRole("treeitem", { name: "Orders" })).toHaveFocus();
    fireEvent.keyDown(tree, { key: "ArrowLeft" });
    expect(screen.getByRole("treeitem", { name: "Orders" })).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("treeitem", { name: "Quotations" })).not.toBeInTheDocument();
    fireEvent.keyDown(tree, { key: "ArrowRight" });
    expect(screen.getByRole("treeitem", { name: "Orders" })).toHaveAttribute("aria-expanded", "true");
    fireEvent.keyDown(tree, { key: "End" });
    expect(screen.getByRole("treeitem", { name: "Contacts" })).toHaveFocus();
    fireEvent.keyDown(tree, { key: "Home" });
    expect(sales).toHaveFocus();
    fireEvent.keyDown(tree, { key: "c" });
    expect(screen.getByRole("treeitem", { name: "Contacts" })).toHaveFocus();
    fireEvent.keyDown(tree, { key: "Enter" });
    expect(onSelect).toHaveBeenCalledWith(menus[3]);
  });

  it("toggles a branch from the chevron without selecting it", () => {
    const { onSelect } = renderTree();
    fireEvent.click(screen.getByTestId("menu-row-toggle-1"));
    expect(screen.getByRole("treeitem", { name: "Sales" })).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("treeitem", { name: "Orders" })).not.toBeInTheDocument();
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("refuses a drop inside the dragged menu's own branch, with a reason", () => {
    const { onMove } = renderTree();
    const dt = dataTransfer();
    const sales = screen.getByTestId("menu-row-1");
    const quotes = screen.getByTestId("menu-row-3");
    drag(sales, "dragStart", dt);
    drag(quotes, "dragOver", dt);
    expect(quotes).toHaveAttribute("data-drop", "refused");
    expect(dt.dropEffect).toBe("none");
    expect(screen.getByTestId("menus-drop-hint")).toHaveTextContent("Can't drop inside its own branch");
    // The browser fires no drop on a refused target; dragend reports the refusal.
    drag(sales, "dragEnd", dt);
    expect(onMove).not.toHaveBeenCalled();
    expect(screen.getByTestId("menus-drop-refusal-title")).toHaveTextContent(
      "Can't move “Sales” under “Quotations”",
    );
    expect(screen.getByTestId("menus-drop-refusal-why")).toHaveTextContent("Odoo refuses recursive menus");
    expect(screen.getByTestId("menus-tree-live")).toHaveTextContent("Can't move “Sales” under “Quotations”");
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByTestId("menus-drop-refusal")).not.toBeInTheDocument();
  });

  it("refuses a drop on itself", () => {
    const { onMove } = renderTree();
    const dt = dataTransfer();
    const orders = screen.getByTestId("menu-row-2");
    drag(orders, "dragStart", dt);
    drag(orders, "dragOver", dt);
    drag(orders, "drop", dt);
    expect(onMove).not.toHaveBeenCalled();
    expect(screen.getByTestId("menus-drop-refusal-why")).toHaveTextContent("A menu can't be its own parent.");
  });

  it("stages a valid move and announces it", () => {
    const { onMove } = renderTree();
    const dt = dataTransfer();
    const quotes = screen.getByTestId("menu-row-3");
    const contacts = screen.getByTestId("menu-row-4");
    drag(quotes, "dragStart", dt);
    expect(screen.getByTestId("menus-drop-root")).toBeInTheDocument();
    drag(contacts, "dragOver", dt);
    expect(contacts).toHaveAttribute("data-drop", "ok");
    drag(contacts, "drop", dt);
    drag(quotes, "dragEnd", dt);
    expect(onMove).toHaveBeenCalledWith(menus[2], 4);
    expect(screen.queryByTestId("menus-drop-refusal")).not.toBeInTheDocument();
    expect(screen.getByTestId("menus-tree-live")).toHaveTextContent("Not saved yet");
  });

  it("drops on Top level to make an app", () => {
    const { onMove } = renderTree();
    const dt = dataTransfer();
    const orders = screen.getByTestId("menu-row-2");
    drag(orders, "dragStart", dt);
    const root = screen.getByTestId("menus-drop-root");
    drag(root, "dragOver", dt);
    drag(root, "drop", dt);
    expect(onMove).toHaveBeenCalledWith(menus[1], null);
  });

  it("does not drag when moves are blocked, and says why", () => {
    renderTree({ canMove: false, moveBlockedReason: "This connection is read-only." });
    expect(screen.getByTestId("menu-row-1")).toHaveAttribute("draggable", "false");
    expect(screen.getByTestId("menus-move-blocked")).toHaveTextContent("This connection is read-only.");
  });

  it("marks a staged row as an unsaved move", () => {
    renderTree({ stagedMenuId: 3 });
    expect(screen.getByTestId("menus-row-staged")).toHaveTextContent("Unsaved move");
  });
});

describe("MenusTree load failure", () => {
  it("does not claim the database has no menus when the load failed", () => {
    render(
      <MenusTree
        menus={[]}
        selectedId={null}
        query=""
        onQueryChange={vi.fn()}
        onSelect={vi.fn()}
        onCreate={vi.fn()}
        unavailable
      />,
    );
    expect(screen.getByTestId("menus-tree-unavailable")).toBeInTheDocument();
    expect(screen.queryByText("No menus yet")).not.toBeInTheDocument();
  });
});
