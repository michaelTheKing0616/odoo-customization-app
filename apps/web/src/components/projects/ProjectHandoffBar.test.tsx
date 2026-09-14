/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ProjectHandoffBar } from "./ProjectHandoffBar";

afterEach(() => cleanup());

describe("ProjectHandoffBar", () => {
  it("links ModuleSpec, Designer, and snapshots — never Expert", () => {
    render(
      <ProjectHandoffBar
        connectionId="c1"
        projectId="p1"
        designerModel="x_visitor_log"
      />,
    );
    expect(screen.getByTestId("projects-handoff-modulespec")).toHaveAttribute(
      "href",
      "/connections/c1/modulespec?project=p1",
    );
    expect(screen.getByTestId("projects-handoff-designer")).toHaveAttribute(
      "href",
      "/connections/c1/designer?model=x_visitor_log",
    );
    expect(screen.getByTestId("projects-handoff-journal")).toHaveAttribute(
      "href",
      "/connections/c1/journal",
    );
    expect(screen.getByRole("link", { name: "Draft Studio" })).toHaveAttribute(
      "href",
      "/connections/c1/wizard",
    );
    expect(screen.getByTestId("projects-handoff-bar").textContent).toMatch(/Promote stays human/);
    expect(screen.queryByRole("link", { name: "Odoo Expert" })).toBeNull();
  });
});
