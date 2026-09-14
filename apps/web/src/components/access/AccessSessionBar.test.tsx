/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { composerSessionState } from "@/lib/accessForm";
import { AccessSessionBar } from "./AccessSessionBar";

afterEach(() => cleanup());

describe("AccessSessionBar", () => {
  it("shows unsaved chrome and enables discard", () => {
    const onDiscard = vi.fn();
    render(
      <AccessSessionBar
        sessionState="unsaved"
        canDiscard
        submitLabel="Create access"
        onDiscard={onDiscard}
      />,
    );
    expect(screen.getByTestId("access-session-state")).toHaveTextContent("Unsaved");
    expect(screen.getByTestId("access-session-hint")).toHaveTextContent(
      "stays local until you create it on Odoo",
    );
    fireEvent.click(screen.getByTestId("access-discard"));
    expect(onDiscard).toHaveBeenCalledTimes(1);
  });

  it("disables discard on a clean draft", () => {
    render(
      <AccessSessionBar
        sessionState="draft"
        canDiscard={false}
        submitLabel="Create access"
        onDiscard={vi.fn()}
      />,
    );
    expect(screen.getByTestId("access-discard")).toBeDisabled();
    expect(composerSessionState({ dirty: false, savedOnce: false })).toBe("draft");
  });
});
