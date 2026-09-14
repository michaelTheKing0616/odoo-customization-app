/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ModuleSpecSessionBar } from "./ModuleSpecSessionBar";
import { moduleSpecSessionState } from "@/lib/modulespec-journey";

afterEach(() => cleanup());

describe("ModuleSpecSessionBar", () => {
  it("shows unsaved chrome and enables discard", () => {
    const onDiscard = vi.fn();
    render(
      <ModuleSpecSessionBar
        sessionState="unsaved"
        canDiscard
        submitLabel="Save as project, or Generate UI when ready"
        onDiscard={onDiscard}
      />,
    );
    expect(screen.getByTestId("modulespec-session-state")).toHaveTextContent("Unsaved");
    expect(screen.getByTestId("modulespec-session-hint")).toHaveTextContent(
      "Edits stay in this browser",
    );
    fireEvent.click(screen.getByTestId("modulespec-discard"));
    expect(onDiscard).toHaveBeenCalledTimes(1);
  });

  it("disables discard on a clean draft", () => {
    render(
      <ModuleSpecSessionBar
        sessionState="draft"
        canDiscard={false}
        submitLabel="Load a draft, then edit"
        onDiscard={vi.fn()}
      />,
    );
    expect(screen.getByTestId("modulespec-discard")).toBeDisabled();
    expect(moduleSpecSessionState({ dirty: false, savedOnce: false })).toBe("draft");
  });
});
