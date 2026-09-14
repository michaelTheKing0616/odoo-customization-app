/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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
    child_count: 0,
  },
];

describe("MenusTree", () => {
  it("filters by name and calls onSelect", () => {
    const onSelect = vi.fn();
    render(
      <MenusTree
        menus={menus}
        selectedId={null}
        query="orders"
        onQueryChange={vi.fn()}
        onSelect={onSelect}
        onCreate={vi.fn()}
      />,
    );
    expect(screen.getByText("Sales")).toBeInTheDocument();
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
});
