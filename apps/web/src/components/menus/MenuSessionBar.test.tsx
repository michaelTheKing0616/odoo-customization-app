/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { composerSessionState } from "@/lib/menuForm";
import { MenuSessionBar } from "./MenuSessionBar";

afterEach(() => cleanup());

describe("MenuSessionBar", () => {
  it("shows unsaved chrome and enables discard", () => {
    const onDiscard = vi.fn();
    render(
      <MenuSessionBar
        sessionState="unsaved"
        canDiscard
        submitLabel="Create menu"
        onDiscard={onDiscard}
      />,
    );
    expect(screen.getByTestId("menus-session-state")).toHaveTextContent("Unsaved");
    expect(screen.getByTestId("menus-session-hint")).toHaveTextContent(
      "stays local until you create it on Odoo",
    );
    fireEvent.click(screen.getByTestId("menus-discard"));
    expect(onDiscard).toHaveBeenCalledTimes(1);
  });

  it("disables discard on a clean draft", () => {
    render(
      <MenuSessionBar
        sessionState="draft"
        canDiscard={false}
        submitLabel="Create menu"
        onDiscard={vi.fn()}
      />,
    );
    expect(screen.getByTestId("menus-discard")).toBeDisabled();
    expect(composerSessionState({ dirty: false, savedOnce: false })).toBe("draft");
  });
});
