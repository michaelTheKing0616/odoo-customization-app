/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ProjectDetail } from "./ProjectDetail";
import type { ProjectRow } from "@/lib/projects-journey";

afterEach(() => cleanup());

const project: ProjectRow = {
  id: "p-visitor",
  name: "Visitor log",
  template_id: "library",
  status: "draft",
  spec_json: {
    models: [{ model: "x_visitor_log", fields: [{ name: "x_name" }] }],
    views: [{ name: "form" }],
  },
};

describe("ProjectDetail", () => {
  it("cross-links ModuleSpec and View Designer from the selected draft", () => {
    render(
      <ProjectDetail
        connectionId="c1"
        project={project}
        onDelete={vi.fn()}
      />,
    );
    expect(screen.getByTestId("projects-detail")).toBeTruthy();
    expect(screen.getByTestId("projects-open-modulespec")).toHaveAttribute(
      "href",
      "/connections/c1/modulespec?project=p-visitor",
    );
    expect(screen.getByTestId("projects-open-designer")).toHaveAttribute(
      "href",
      "/connections/c1/designer?model=x_visitor_log",
    );
    expect(screen.getByText("Delete draft")).toBeTruthy();
  });
});
