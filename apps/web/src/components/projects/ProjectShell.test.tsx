/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ProjectShell } from "./ProjectShell";

afterEach(() => cleanup());

describe("ProjectShell", () => {
  it("keeps Projects identity and sibling studio links", () => {
    render(
      <ProjectShell connectionId="c1" connectionName="Lab 19" journey={{ id: "browse" }}>
        <p>board</p>
      </ProjectShell>,
    );
    expect(screen.getByTestId("projects-page")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Projects" })).toBeTruthy();
    expect(screen.getByText(/Lab 19/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "ModuleSpec" })).toHaveAttribute(
      "href",
      "/connections/c1/modulespec",
    );
    expect(screen.getByRole("link", { name: "View Designer" })).toHaveAttribute(
      "href",
      "/connections/c1/designer",
    );
    expect(screen.getByRole("link", { name: "Snapshots" })).toHaveAttribute(
      "href",
      "/connections/c1/journal",
    );
    expect(screen.getByTestId("projects-steps")).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Odoo Expert" })).toBeNull();
  });
});
