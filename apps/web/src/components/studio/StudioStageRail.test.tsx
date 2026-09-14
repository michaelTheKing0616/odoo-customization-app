/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { StudioStageRail } from "./StudioStageRail";

afterEach(() => cleanup());

describe("StudioStageRail", () => {
  it("marks the current journey step and Completeness honesty on generate", () => {
    render(<StudioStageRail journey={{ id: "generate" }} />);
    const rail = screen.getByTestId("studio-stage-rail");
    expect(rail.querySelector('[data-stage="generate"]')?.className).toMatch(/is-current/);
    expect(rail.querySelector('[data-stage="brief"]')?.className).toMatch(/is-done/);
    expect(screen.getByTestId("studio-stage-hint").textContent).toMatch(/Completeness is not Cert/);
    expect(screen.getByTestId("studio-stage-hint").textContent).toMatch(/Promote stays human/);
  });

  it("advances to Apply after the draft is live", () => {
    render(<StudioStageRail journey={{ id: "apply", applied: true }} />);
    expect(screen.getByTestId("studio-stage-rail").querySelector('[data-stage="apply"]')).toHaveAttribute(
      "aria-current",
      "step",
    );
    expect(screen.getByTestId("studio-stage-hint").textContent).toMatch(/View Designer/);
  });
});
