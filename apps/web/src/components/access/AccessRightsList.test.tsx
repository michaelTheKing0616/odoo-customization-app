/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AccessRightRow } from "@/lib/api";
import { AccessRightsList } from "./AccessRightsList";

afterEach(() => cleanup());

const rows: AccessRightRow[] = [
  {
    id: 1,
    name: "Partner user",
    model: "res.partner",
    model_id: 8,
    group_id: 4,
    group_name: "Internal User",
    perm_read: true,
    perm_write: true,
    perm_create: true,
    perm_unlink: false,
    active: true,
  },
  {
    id: 2,
    name: "Ticket admin",
    model: "x_ticket",
    model_id: 20,
    group_id: null,
    group_name: null,
    perm_read: true,
    perm_write: true,
    perm_create: true,
    perm_unlink: true,
    active: true,
  },
];

describe("AccessRightsList", () => {
  it("filters by name and calls onSelect", () => {
    const onSelect = vi.fn();
    render(
      <AccessRightsList
        rows={rows}
        selectedId={null}
        query="ticket"
        onQueryChange={vi.fn()}
        onSelect={onSelect}
        onCreate={vi.fn()}
      />,
    );
    expect(screen.queryByText("Partner user")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("access-right-row-2"));
    expect(onSelect).toHaveBeenCalledWith(rows[1]);
  });

  it("shows empty state with create action", () => {
    const onCreate = vi.fn();
    render(
      <AccessRightsList
        rows={[]}
        selectedId={null}
        query=""
        onQueryChange={vi.fn()}
        onSelect={vi.fn()}
        onCreate={onCreate}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Create access" }));
    expect(onCreate).toHaveBeenCalledTimes(1);
  });
});
