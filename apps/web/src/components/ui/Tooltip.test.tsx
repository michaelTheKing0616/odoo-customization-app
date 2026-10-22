/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Tooltip, TooltipProvider } from "@/components/ui/Tooltip";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

function TooltipHarness({ label = "Helper text" }: { label?: string }) {
  return (
    <TooltipProvider>
      <Tooltip label={label}>
        <button type="button">Trigger button</button>
      </Tooltip>
    </TooltipProvider>
  );
}

describe("Tooltip characterization", () => {
  it("shows the label when the trigger receives keyboard focus", async () => {
    render(<TooltipHarness />);
    const trigger = screen.getByRole("button", { name: "Trigger button" });

    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();

    trigger.focus();
    fireEvent.focus(trigger);

    await waitFor(() => {
      expect(screen.getByRole("tooltip")).toHaveTextContent("Helper text");
    });
  });

  it("keeps the child click handler", () => {
    const onClick = vi.fn();
    render(
      <TooltipProvider>
        <Tooltip label="Helper text">
          <button type="button" onClick={onClick}>
            Trigger button
          </button>
        </Tooltip>
      </TooltipProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Trigger button" }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("hides the tooltip on Escape and removes it from the document", async () => {
    render(<TooltipHarness />);
    const trigger = screen.getByRole("button", { name: "Trigger button" });
    trigger.focus();
    fireEvent.focus(trigger);

    await waitFor(() => {
      expect(screen.getByRole("tooltip")).toBeInTheDocument();
    });

    fireEvent.keyDown(document, { key: "Escape", code: "Escape", bubbles: true });

    await waitFor(() => {
      expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    });
  });

  describe("open delay", () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    it("opens only after a delay between 125 ms and 200 ms", async () => {
      render(<TooltipHarness />);
      const trigger = screen.getByRole("button", { name: "Trigger button" });

      fireEvent.pointerEnter(trigger, { pointerType: "mouse" });
      fireEvent.mouseEnter(trigger);
      fireEvent.mouseMove(trigger);

      expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();

      await vi.advanceTimersByTimeAsync(124);
      expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();

      await vi.advanceTimersByTimeAsync(75);
      expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();

      await vi.advanceTimersByTimeAsync(1);
      expect(screen.getByRole("tooltip")).toHaveTextContent("Helper text");
    });
  });
});
