/** @vitest-environment jsdom */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PowerOpsStageRail } from "./PowerOpsStageRail";

describe("PowerOpsStageRail", () => {
  it("marks the current stage", () => {
    render(<PowerOpsStageRail step={3} />);
    expect(screen.getByTestId("power-ops-step-dry-run")).toHaveAttribute("data-state", "current");
    expect(screen.getByTestId("power-ops-step-recipe")).toHaveAttribute("data-state", "done");
    expect(screen.getByTestId("power-ops-step-configure")).toHaveAttribute("data-state", "done");
    expect(screen.getByTestId("power-ops-step-run")).toHaveAttribute("data-state", "todo");
  });
});
