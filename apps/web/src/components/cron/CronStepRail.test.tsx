/** @vitest-environment jsdom */
import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { CronStepRail } from "./CronStepRail";

afterEach(() => cleanup());

describe("CronStepRail", () => {
  it("marks the current step", () => {
    render(
      <div className="cron-operate">
        <CronStepRail current="select" />
      </div>,
    );
    expect(screen.getByTestId("cron-stage-rail")).toBeInTheDocument();
    expect(screen.getByTestId("cron-step-list")).toHaveAttribute("data-state", "done");
    expect(screen.getByTestId("cron-step-select")).toHaveAttribute("data-state", "current");
    expect(screen.getByTestId("cron-step-select")).toHaveAttribute("aria-current", "step");
    expect(screen.getByTestId("cron-step-trigger")).toHaveAttribute("data-state", "todo");
  });
});
