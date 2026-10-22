/** @vitest-environment jsdom */
import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ReminderStudioBar } from "./ReminderStudioBar";
import { reminderHonestyGuide } from "@/lib/remindersScreen";

afterEach(() => cleanup());

describe("ReminderStudioBar", () => {
  it("folds schedule-on honesty into the studio bar", () => {
    render(
      <div className="reminders-operate">
        <div className="rm-studio">
          <ReminderStudioBar step="compose" honesty={reminderHonestyGuide(true)} />
        </div>
      </div>,
    );
    expect(screen.getByTestId("reminders-studio-bar")).toBeInTheDocument();
    expect(screen.getByTestId("reminders-session-state")).toHaveTextContent("Draft");
    expect(screen.getByTestId("reminders-honesty-title")).toHaveTextContent(
      /Schedule will be enabled/i,
    );
    expect(screen.getByTestId("reminders-honesty-why")).toBeInTheDocument();
    expect(screen.getByTestId("reminders-honesty-next")).toBeInTheDocument();
  });

  it("shows template-only honesty and Created badge", () => {
    const { rerender } = render(
      <div className="reminders-operate">
        <div className="rm-studio">
          <ReminderStudioBar step="schedule" honesty={reminderHonestyGuide(false)} />
        </div>
      </div>,
    );
    expect(screen.getByTestId("reminders-honesty-title")).toHaveTextContent(/Template only/i);
    rerender(
      <div className="reminders-operate">
        <div className="rm-studio">
          <ReminderStudioBar step="created" honesty={null} />
        </div>
      </div>,
    );
    expect(screen.getByTestId("reminders-session-state")).toHaveTextContent("Created");
    expect(screen.queryByTestId("reminders-honesty")).toBeNull();
  });
});
