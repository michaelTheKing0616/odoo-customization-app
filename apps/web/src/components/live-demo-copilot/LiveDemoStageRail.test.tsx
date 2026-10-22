/** @vitest-environment happy-dom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { LiveDemoStageRail } from "./LiveDemoStageRail";

afterEach(() => cleanup());

describe("LiveDemoStageRail", () => {
  it("marks Launch as current on step 3", () => {
    render(<LiveDemoStageRail step={3} />);
    expect(screen.getByTestId("live-demo-step-meeting")).toHaveAttribute("data-state", "done");
    expect(screen.getByTestId("live-demo-step-consent")).toHaveAttribute("data-state", "done");
    expect(screen.getByTestId("live-demo-step-launch")).toHaveAttribute("data-state", "current");
    expect(screen.getByTestId("live-demo-step-launch")).toHaveAttribute("aria-current", "step");
    expect(screen.getByTestId("live-demo-step-live")).toHaveAttribute("data-state", "todo");
  });
});
