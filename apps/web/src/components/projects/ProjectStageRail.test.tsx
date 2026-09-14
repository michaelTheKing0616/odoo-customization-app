/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ProjectStageRail } from "./ProjectStageRail";

afterEach(() => cleanup());

describe("ProjectStageRail", () => {
  it("marks inspect current and keeps Completeness honesty", () => {
    render(<ProjectStageRail journey={{ id: "inspect" }} />);
    const rail = screen.getByTestId("projects-stage-rail");
    expect(rail.querySelector('[data-stage="inspect"]')?.className).toMatch(/is-current/);
    expect(rail.querySelector('[data-stage="browse"]')?.className).toMatch(/is-done/);
    expect(screen.getByTestId("projects-steps")).toBeTruthy();
    expect(screen.getByTestId("projects-stage-hint").textContent).toMatch(
      /Completeness ≠ Cert ≠ Autopilot/,
    );
  });

  it("advances to Apply after a successful write", () => {
    render(<ProjectStageRail journey={{ id: "apply", applied: true }} />);
    expect(
      screen.getByTestId("projects-stage-rail").querySelector('[data-stage="apply"]'),
    ).toHaveAttribute("aria-current", "step");
    expect(screen.getByTestId("projects-stage-hint").textContent).toMatch(/Promote stays human/);
  });
});
