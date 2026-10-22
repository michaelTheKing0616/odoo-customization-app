/** @vitest-environment jsdom */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FleetStageRail } from "./FleetStageRail";

describe("FleetStageRail", () => {
  it("marks the current stage", () => {
    render(<FleetStageRail step={2} />);
    expect(screen.getByTestId("fleet-step-inspect")).toHaveAttribute("data-state", "current");
    expect(screen.getByTestId("fleet-step-fleet")).toHaveAttribute("data-state", "done");
    expect(screen.getByTestId("fleet-step-open-client")).toHaveAttribute("data-state", "todo");
  });
});
