import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ConnectStepRail } from "./ConnectStepRail";

describe("ConnectStepRail", () => {
  it("marks the current step and prior as done", () => {
    render(<ConnectStepRail current="probe" />);
    expect(screen.getByTestId("connect-step-credentials")).toHaveAttribute(
      "data-state",
      "done",
    );
    expect(screen.getByTestId("connect-step-probe")).toHaveAttribute(
      "data-state",
      "current",
    );
    expect(screen.getByTestId("connect-step-probe")).toHaveAttribute(
      "aria-current",
      "step",
    );
    expect(screen.getByTestId("connect-step-summary")).toHaveAttribute(
      "data-state",
      "todo",
    );
  });
});
