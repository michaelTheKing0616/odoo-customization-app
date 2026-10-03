/** @vitest-environment jsdom */
import React, { useState } from "react";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { DialogPanel } from "@/components/ui/Dialog";

afterEach(() => {
  cleanup();
});

function DialogHarness() {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button type="button" onClick={() => setOpen(true)}>
        Open dialog
      </button>
      <input aria-label="outside field" />
      <DialogPanel
        open={open}
        onOpenChange={setOpen}
        title="Archive project"
        description="This cannot be undone."
      >
        <button type="button">Keep editing</button>
        <button type="button">Archive</button>
      </DialogPanel>
    </div>
  );
}

async function openDialog() {
  const trigger = screen.getByRole("button", { name: "Open dialog" });
  trigger.focus();
  fireEvent.click(trigger);
  const dialog = await screen.findByRole("dialog", { name: "Archive project" });
  return { trigger, dialog };
}

function pressTab(shiftKey = false) {
  const active = (document.activeElement as HTMLElement | null) ?? document.body;
  fireEvent.keyDown(active, { key: "Tab", code: "Tab", shiftKey, bubbles: true });
}

describe("DialogPanel characterization", () => {
  it("opens with an accessible name", async () => {
    render(<DialogHarness />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    const { dialog } = await openDialog();
    expect(dialog).toBeVisible();
    expect(dialog).toHaveAccessibleName("Archive project");
  });

  it("closes on Escape", async () => {
    render(<DialogHarness />);
    const { dialog } = await openDialog();
    fireEvent.keyDown(dialog, { key: "Escape", code: "Escape", bubbles: true });
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("traps focus so Tab does not leave the open dialog", async () => {
    render(<DialogHarness />);
    const { dialog } = await openDialog();
    const outside = screen.getByLabelText("outside field");

    await waitFor(() => {
      expect(dialog.contains(document.activeElement)).toBe(true);
    });

    const tabbableCount = within(dialog).getAllByRole("button").length;
    for (let i = 0; i < tabbableCount + 2; i += 1) {
      pressTab();
      expect(dialog.contains(document.activeElement)).toBe(true);
      expect(document.activeElement).not.toBe(outside);
    }

    pressTab(true);
    expect(dialog.contains(document.activeElement)).toBe(true);
    expect(document.activeElement).not.toBe(outside);
  });

  it("returns focus to the trigger after Escape", async () => {
    render(<DialogHarness />);
    const { trigger, dialog } = await openDialog();
    fireEvent.keyDown(dialog, { key: "Escape", code: "Escape", bubbles: true });
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
    expect(trigger).toHaveFocus();
  });
});
