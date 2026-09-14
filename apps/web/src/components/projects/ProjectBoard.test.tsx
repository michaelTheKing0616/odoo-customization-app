/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ProjectBoard } from "./ProjectBoard";
import type { ProjectRow } from "@/lib/projects-journey";

afterEach(() => cleanup());

const rows: ProjectRow[] = [
  {
    id: "p-draft",
    name: "Visitor log",
    template_id: "library",
    status: "draft",
    lifecycle_status: "active",
    spec_json: { models: [{ model: "x_visitor_log", fields: [{ name: "x_name" }] }] },
    created_at: "2026-09-14T10:00:00Z",
  },
  {
    id: "p-applied",
    name: "Loans",
    template_id: null,
    status: "applied",
    lifecycle_status: "active",
    spec_json: { models: [] },
    created_at: "2026-09-13T10:00:00Z",
  },
];

describe("ProjectBoard", () => {
  it("renders a selectable release board instead of a dump of action buttons", () => {
    const onSelect = vi.fn();
    render(
      <ProjectBoard
        projects={rows}
        selectedId="p-draft"
        filter="all"
        query=""
        onQueryChange={vi.fn()}
        onFilterChange={vi.fn()}
        onSelect={onSelect}
        onCreate={vi.fn()}
      />,
    );
    expect(screen.getByTestId("projects-board")).toBeTruthy();
    expect(screen.getByText("Release board")).toBeTruthy();
    expect(screen.getByTestId("project-row-p-draft")).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByTestId("project-row-p-applied"));
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("button", { name: "Apply" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Delete" })).toBeNull();
  });
});
