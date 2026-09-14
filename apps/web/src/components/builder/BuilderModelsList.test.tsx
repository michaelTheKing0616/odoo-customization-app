/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BuilderModelsList } from "./BuilderModelsList";
import type { ModelRow } from "@/lib/api";

afterEach(() => cleanup());

const rows: ModelRow[] = [
  {
    id: 1,
    model: "x_ticket",
    name: "Ticket",
    state: "manual",
    transient: false,
  },
  {
    id: 2,
    model: "x_loan",
    name: "Loan",
    state: "manual",
    transient: false,
  },
];

describe("BuilderModelsList", () => {
  it("filters by name and calls onSelect", () => {
    const onSelect = vi.fn();
    render(
      <BuilderModelsList
        rows={rows}
        selectedModel={null}
        query="loan"
        onQueryChange={vi.fn()}
        onSelect={onSelect}
        onCreate={vi.fn()}
        onOpenExisting={vi.fn()}
      />,
    );
    expect(screen.queryByText("Ticket")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("builder-model-row-x_loan"));
    expect(onSelect).toHaveBeenCalledWith(rows[1]);
  });

  it("shows empty state with create action", () => {
    const onCreate = vi.fn();
    render(
      <BuilderModelsList
        rows={[]}
        selectedModel={null}
        query=""
        onQueryChange={vi.fn()}
        onSelect={vi.fn()}
        onCreate={onCreate}
        onOpenExisting={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Create model" }));
    expect(onCreate).toHaveBeenCalledTimes(1);
  });

  it("offers to open a typed stock technical name", () => {
    const onOpenExisting = vi.fn();
    render(
      <BuilderModelsList
        rows={rows}
        selectedModel={null}
        query="res.partner"
        onQueryChange={vi.fn()}
        onSelect={vi.fn()}
        onCreate={vi.fn()}
        onOpenExisting={onOpenExisting}
      />,
    );
    fireEvent.click(screen.getByTestId("builder-open-existing"));
    expect(onOpenExisting).toHaveBeenCalledWith("res.partner");
  });
});
