/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ModuleSpecStageRail } from "./ModuleSpecStageRail";

afterEach(() => cleanup());

describe("ModuleSpecStageRail", () => {
  it("marks edit current and keeps Completeness honesty", () => {
    render(<ModuleSpecStageRail journey={{ id: "edit" }} />);
    const rail = screen.getByTestId("modulespec-stage-rail");
    expect(rail.querySelector('[data-stage="edit"]')?.className).toMatch(/is-current/);
    expect(rail.querySelector('[data-stage="load"]')?.className).toMatch(/is-done/);
    expect(screen.getByTestId("modulespec-steps")).toBeTruthy();
    expect(screen.getByTestId("modulespec-stage-hint").textContent).toMatch(
      /Completeness ≠ Cert ≠ Autopilot/,
    );
    expect(screen.getByTestId("modulespec-stage-hint").textContent).toMatch(/escape hatch/);
  });

  it("advances to Apply after Generate UI", () => {
    render(<ModuleSpecStageRail journey={{ id: "apply", applied: true }} />);
    expect(
      screen.getByTestId("modulespec-stage-rail").querySelector('[data-stage="apply"]'),
    ).toHaveAttribute("aria-current", "step");
    expect(screen.getByTestId("modulespec-stage-hint").textContent).toMatch(/Promote stays human/);
  });
});
