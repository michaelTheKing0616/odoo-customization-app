/** @vitest-environment happy-dom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ScriptRunnerStageRail } from "./ScriptRunnerStageRail";

afterEach(() => cleanup());

describe("ScriptRunnerStageRail", () => {
  it("marks Confirm current and Compose done", () => {
    render(<ScriptRunnerStageRail step={2} />);
    expect(screen.getByTestId("script-runner-step-compose")).toHaveAttribute("data-state", "done");
    expect(screen.getByTestId("script-runner-step-confirm")).toHaveAttribute("data-state", "current");
    expect(screen.getByTestId("script-runner-step-run")).toHaveAttribute("data-state", "todo");
    expect(screen.getByTestId("script-runner-stage-rail")).toHaveAttribute(
      "aria-label",
      "Script Runner stages",
    );
  });

  it("has no dry-run stage", () => {
    render(<ScriptRunnerStageRail step={1} />);
    expect(screen.queryByText(/dry-run/i)).toBeNull();
    expect(screen.getByText("Compose")).toBeInTheDocument();
    expect(screen.getByText("Confirm")).toBeInTheDocument();
    expect(screen.getByText("Run")).toBeInTheDocument();
  });
});
