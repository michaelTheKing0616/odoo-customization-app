/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { composerSessionState } from "@/lib/automationForm";
import { AutomationSessionBar } from "./AutomationSessionBar";

afterEach(() => cleanup());

describe("AutomationSessionBar", () => {
  it("shows unsaved chrome and enables discard", () => {
    const onDiscard = vi.fn();
    render(
      <AutomationSessionBar
        sessionState="unsaved"
        canDiscard
        submitLabel="Create automation"
        onDiscard={onDiscard}
      />,
    );
    expect(screen.getByTestId("automations-session-state")).toHaveTextContent("Unsaved");
    expect(screen.getByTestId("automations-session-hint")).toHaveTextContent(
      "stays local until you create it on Odoo",
    );
    fireEvent.click(screen.getByTestId("automations-discard"));
    expect(onDiscard).toHaveBeenCalledTimes(1);
  });

  it("disables discard on a clean draft", () => {
    render(
      <AutomationSessionBar
        sessionState="draft"
        canDiscard={false}
        submitLabel="Create automation"
        onDiscard={vi.fn()}
      />,
    );
    expect(screen.getByTestId("automations-discard")).toBeDisabled();
    expect(composerSessionState({ dirty: false, savedOnce: false })).toBe("draft");
  });
});
