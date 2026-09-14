/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ProjectHistory } from "./ProjectHistory";
import type { SnapshotRow } from "@/lib/api";
import type { ProjectRow } from "@/lib/projects-journey";

afterEach(() => cleanup());

const project: ProjectRow = {
  id: "p1",
  name: "Visitor log",
  template_id: "library",
  status: "draft",
  spec_json: { models: [{ model: "x_visitor_log" }] },
};

const snapshots: SnapshotRow[] = [
  {
    id: "snap-1",
    resource_type: "model",
    resource_key: "model:x_visitor_log",
    label: "Before apply x_visitor_log",
    reversible: "partial",
    created_at: "2026-09-14T12:00:00Z",
  },
];

describe("ProjectHistory", () => {
  it("scopes snapshots and offers rollback with partial honesty", () => {
    const onRollback = vi.fn();
    render(
      <ProjectHistory
        connectionId="c1"
        project={project}
        snapshots={snapshots}
        onRollback={onRollback}
      />,
    );
    expect(screen.getByTestId("projects-history").textContent).toMatch(/partially recoverable/);
    expect(screen.getByText("Before apply x_visitor_log")).toBeTruthy();
    fireEvent.click(screen.getByTestId("projects-rollback-snap-1"));
    expect(onRollback).toHaveBeenCalledWith("snap-1");
    expect(screen.getByRole("link", { name: "Change journal" })).toHaveAttribute(
      "href",
      "/connections/c1/journal",
    );
  });
});
