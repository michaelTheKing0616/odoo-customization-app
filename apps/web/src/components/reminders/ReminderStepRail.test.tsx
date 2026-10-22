/** @vitest-environment jsdom */
import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ReminderStepRail } from "./ReminderStepRail";

afterEach(() => cleanup());

describe("ReminderStepRail", () => {
  it("marks the current step", () => {
    render(
      <div className="reminders-operate">
        <ReminderStepRail current="schedule" />
      </div>,
    );
    expect(screen.getByTestId("reminders-step-rail")).toBeInTheDocument();
    expect(screen.getByTestId("reminders-step-compose")).toHaveAttribute("data-state", "done");
    expect(screen.getByTestId("reminders-step-schedule")).toHaveAttribute("data-state", "current");
    expect(screen.getByTestId("reminders-step-schedule")).toHaveAttribute("aria-current", "step");
    expect(screen.getByTestId("reminders-step-confirm")).toHaveAttribute("data-state", "todo");
  });

  it("marks created as current when finished", () => {
    render(
      <div className="reminders-operate">
        <ReminderStepRail current="created" />
      </div>,
    );
    expect(screen.getByTestId("reminders-step-created")).toHaveAttribute("data-state", "current");
    expect(screen.getByTestId("reminders-step-confirm")).toHaveAttribute("data-state", "done");
  });
});
