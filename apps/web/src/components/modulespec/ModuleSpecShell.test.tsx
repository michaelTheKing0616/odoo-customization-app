/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ModuleSpecShell } from "./ModuleSpecShell";

afterEach(() => cleanup());

describe("ModuleSpecShell", () => {
  it("keeps ModuleSpec identity and sibling studio links", () => {
    render(
      <ModuleSpecShell connectionId="c1" connectionName="Lab 19" journey={{ id: "load" }}>
        <p>workbench</p>
      </ModuleSpecShell>,
    );
    expect(screen.getByTestId("modulespec-page")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "ModuleSpec" })).toBeTruthy();
    expect(screen.getByText(/Lab 19/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Draft Studio" })).toHaveAttribute(
      "href",
      "/connections/c1/wizard",
    );
    expect(screen.getByRole("link", { name: "View Designer" })).toHaveAttribute(
      "href",
      "/connections/c1/designer",
    );
    expect(screen.getByRole("link", { name: "Job Autopilot" })).toHaveAttribute(
      "href",
      "/connections/c1/job",
    );
    expect(screen.getByTestId("modulespec-steps")).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Projects" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Expert" })).toBeNull();
  });
});
