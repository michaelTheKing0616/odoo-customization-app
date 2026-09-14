/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/Tooltip";
import {
  DesignerSessionBar,
  designerPublishState,
} from "./DesignerSessionBar";

afterEach(() => cleanup());

function renderBar(
  overrides: Partial<React.ComponentProps<typeof DesignerSessionBar>> = {},
) {
  const onUndo = vi.fn();
  const onRedo = vi.fn();
  const onRollbackPublish = vi.fn();
  const onEmptyUndo = vi.fn();
  render(
    <TooltipProvider>
      <DesignerSessionBar
        publishState="unpublished"
        canUndo
        canRedo={false}
        canRollbackPublish={false}
        onUndo={onUndo}
        onRedo={onRedo}
        onRollbackPublish={onRollbackPublish}
        onEmptyUndo={onEmptyUndo}
        {...overrides}
      />
    </TooltipProvider>,
  );
  return { onUndo, onRedo, onRollbackPublish, onEmptyUndo };
}

describe("DesignerSessionBar", () => {
  it("shows unpublished chrome and disables redo", () => {
    renderBar();
    expect(screen.getByTestId("designer-publish-state")).toHaveTextContent("Unpublished");
    expect(screen.getByTestId("designer-session-hint")).toHaveTextContent(
      "stay local until you Save to Odoo",
    );
    expect(screen.getByTestId("designer-redo")).toBeDisabled();
    expect(screen.getByTestId("designer-undo")).toBeEnabled();
  });

  it("shows published chrome and a disabled session undo", () => {
    renderBar({
      publishState: "published",
      canUndo: false,
      canRedo: false,
      canRollbackPublish: true,
    });
    expect(screen.getByTestId("designer-publish-state")).toHaveTextContent("Published");
    expect(screen.getByTestId("designer-undo")).toBeDisabled();
    expect(screen.getByTestId("designer-rollback-publish")).toBeEnabled();
  });

  it("maps dirty / published flags to pill state", () => {
    expect(designerPublishState({ dirty: true, hasPublishedView: true })).toBe(
      "unpublished",
    );
    expect(designerPublishState({ dirty: false, hasPublishedView: true })).toBe(
      "published",
    );
    expect(designerPublishState({ dirty: false, hasPublishedView: false })).toBe("draft");
  });

  it("invokes undo from the toolbar button", () => {
    const { onUndo } = renderBar();
    fireEvent.click(screen.getByTestId("designer-undo"));
    expect(onUndo).toHaveBeenCalledTimes(1);
  });
});
