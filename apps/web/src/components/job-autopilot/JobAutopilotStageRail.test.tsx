/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { JobAutopilotStageRail } from "./JobAutopilotStageRail";

afterEach(() => cleanup());

describe("JobAutopilotStageRail", () => {
  it("marks run current and keeps Completeness / Autopilot honesty", () => {
    render(<JobAutopilotStageRail journey={{ id: "run" }} />);
    const rail = screen.getByTestId("job-autopilot-stage-rail");
    expect(rail.querySelector('[data-stage="run"]')?.className).toMatch(/is-current/);
    expect(rail.querySelector('[data-stage="brief"]')?.className).toMatch(/is-done/);
    expect(screen.getByTestId("job-autopilot-steps")).toBeTruthy();
    expect(screen.getByTestId("job-autopilot-stage-hint").textContent).toMatch(
      /Completeness ≠ Cert ≠ Autopilot/,
    );
    expect(screen.getByTestId("job-autopilot-stage-hint").textContent).toMatch(
      /Promote stays human/,
    );
  });

  it("advances to Promote after smoke is ready for a human", () => {
    render(<JobAutopilotStageRail journey={{ id: "promote", promoteReady: true }} />);
    expect(
      screen.getByTestId("job-autopilot-stage-rail").querySelector('[data-stage="promote"]'),
    ).toHaveAttribute("aria-current", "step");
    expect(screen.getByTestId("job-autopilot-stage-hint").textContent).toMatch(
      /never writes production/,
    );
  });
});
