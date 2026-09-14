/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BuilderSessionBar } from "./BuilderSessionBar";
import { composerSessionState } from "@/lib/builderForm";

afterEach(() => cleanup());

describe("BuilderSessionBar", () => {
  it("shows unsaved chrome and enables discard", () => {
    const onDiscard = vi.fn();
    render(
      <BuilderSessionBar
        sessionState="unsaved"
        canDiscard
        submitLabel="Create model"
        onDiscard={onDiscard}
      />,
    );
    expect(screen.getByTestId("builder-session-state")).toHaveTextContent("Unsaved");
    expect(screen.getByTestId("builder-session-hint")).toHaveTextContent(
      "stays local until you create it on Odoo",
    );
    fireEvent.click(screen.getByTestId("builder-discard"));
    expect(onDiscard).toHaveBeenCalledTimes(1);
  });

  it("disables discard on a clean draft", () => {
    render(
      <BuilderSessionBar
        sessionState="draft"
        canDiscard={false}
        submitLabel="Create field"
        onDiscard={vi.fn()}
      />,
    );
    expect(screen.getByTestId("builder-discard")).toBeDisabled();
    expect(composerSessionState({ dirty: false, savedOnce: false })).toBe("draft");
  });
});
