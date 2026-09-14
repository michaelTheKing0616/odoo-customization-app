/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ModuleSpecHandoffBar } from "./ModuleSpecHandoffBar";

afterEach(() => cleanup());

describe("ModuleSpecHandoffBar", () => {
  it("links Draft Studio, View Designer, Job Autopilot, App Studio, and Projects", () => {
    render(
      <ModuleSpecHandoffBar
        connectionId="c1"
        designerHref="/connections/c1/designer?model=x_visitor_log"
        designerModel="x_visitor_log"
        projectId="p1"
      />,
    );
    expect(screen.getByRole("link", { name: "Draft Studio" })).toHaveAttribute(
      "href",
      "/connections/c1/wizard",
    );
    expect(screen.getByTestId("modulespec-open-designer")).toHaveAttribute(
      "href",
      "/connections/c1/designer?model=x_visitor_log",
    );
    expect(screen.getByTestId("modulespec-open-job")).toHaveAttribute("href", "/connections/c1/job");
    expect(screen.getByRole("link", { name: "App Studio" })).toHaveAttribute(
      "href",
      "/connections/c1/studio",
    );
    expect(screen.getByTestId("modulespec-open-projects")).toHaveAttribute(
      "href",
      "/connections/c1/projects?project=p1",
    );
    expect(screen.getByTestId("modulespec-handoff-bar").textContent).toMatch(/Promote stays human/);
    expect(screen.queryByRole("link", { name: "Expert" })).toBeNull();
  });
});
