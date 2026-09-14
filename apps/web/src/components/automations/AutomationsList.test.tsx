/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AutomationsList } from "./AutomationsList";
import type { AutomationRow } from "@/lib/api";

afterEach(() => cleanup());

const rows: AutomationRow[] = [
  {
    id: 1,
    name: "Set partner note",
    model: "res.partner",
    model_id: 10,
    trigger: "on_create",
    active: true,
    filter_domain: null,
    action_server_ids: [3],
  },
  {
    id: 2,
    name: "Loan returned",
    model: "x_lib_loan",
    model_id: 11,
    trigger: "on_write",
    active: false,
    filter_domain: "[('x_returned', '=', True)]",
    action_server_ids: [4],
  },
];

describe("AutomationsList", () => {
  it("filters by name and calls onSelect", () => {
    const onSelect = vi.fn();
    const onQueryChange = vi.fn();
    render(
      <AutomationsList
        rows={rows}
        selectedId={null}
        modelFilter=""
        query="loan"
        onQueryChange={onQueryChange}
        onSelect={onSelect}
        onCreate={vi.fn()}
      />,
    );
    expect(screen.queryByText("Set partner note")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("automation-row-2"));
    expect(onSelect).toHaveBeenCalledWith(rows[1]);
  });

  it("shows empty state with create action", () => {
    const onCreate = vi.fn();
    render(
      <AutomationsList
        rows={[]}
        selectedId={null}
        modelFilter=""
        query=""
        onQueryChange={vi.fn()}
        onSelect={vi.fn()}
        onCreate={onCreate}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Create automation" }));
    expect(onCreate).toHaveBeenCalledTimes(1);
  });
});
