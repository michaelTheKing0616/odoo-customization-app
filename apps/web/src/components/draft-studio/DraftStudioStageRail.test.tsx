/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { DraftStudioStageRail } from "./DraftStudioStageRail";

afterEach(() => cleanup());

describe("DraftStudioStageRail", () => {
  it("marks enrich current and keeps Completeness honesty", () => {
    render(<DraftStudioStageRail journey={{ id: "enrich" }} />);
    const rail = screen.getByTestId("draft-studio-stage-rail");
    expect(rail.querySelector('[data-stage="enrich"]')?.className).toMatch(/is-current/);
    expect(rail.querySelector('[data-stage="prompt"]')?.className).toMatch(/is-done/);
    expect(screen.getByTestId("draft-studio-steps")).toBeTruthy();
    expect(screen.getByTestId("draft-studio-stage-hint").textContent).toMatch(
      /Completeness is not Cert/,
    );
    expect(screen.getByTestId("draft-studio-stage-hint").textContent).toMatch(
      /Promote stays human/,
    );
  });

  it("advances to Apply after the draft is live", () => {
    render(<DraftStudioStageRail journey={{ id: "apply", applied: true }} />);
    expect(
      screen.getByTestId("draft-studio-stage-rail").querySelector('[data-stage="apply"]'),
    ).toHaveAttribute("aria-current", "step");
    expect(screen.getByTestId("draft-studio-stage-hint").textContent).toMatch(/View Designer/);
  });
});
