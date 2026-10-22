/** @vitest-environment jsdom */
import React, { useState } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";

afterEach(() => {
  cleanup();
});

const PHRASE = "I understand the risks";

function ConfirmHarness({
  onConfirm,
  onCancel,
  busy = false,
}: {
  onConfirm: (phrase: string) => void;
  onCancel: () => void;
  busy?: boolean;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button type="button" onClick={() => setOpen(true)}>
        Open confirm
      </button>
      <ConfirmDialogV2
        open={open}
        title="Delete model"
        warning="This cannot be undone."
        risks={["Drops columns"]}
        riskLevel="danger"
        phrase={PHRASE}
        busy={busy}
        onConfirm={(phrase) => {
          onConfirm(phrase);
          setOpen(false);
        }}
        onCancel={() => {
          onCancel();
          setOpen(false);
        }}
      />
    </div>
  );
}

describe("ConfirmDialogV2", () => {
  it("opens, confirms, and cancels", async () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(<ConfirmHarness onConfirm={onConfirm} onCancel={onCancel} />);

    expect(screen.queryByTestId("confirm-dialog-v2")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open confirm" }));

    const dialog = await screen.findByRole("dialog", { name: "Delete model" });
    expect(dialog).toHaveAttribute("data-risk-level", "danger");
    expect(screen.getByTestId("confirm-dialog-v2-confirm").className).toMatch(/bg-danger/);

    const confirm = screen.getByRole("button", { name: "Confirm" });
    expect(confirm).toBeDisabled();
    fireEvent.click(confirm);
    expect(onConfirm).not.toHaveBeenCalled();

    fireEvent.change(screen.getByTestId("confirm-dialog-v2-input"), {
      target: { value: PHRASE },
    });
    expect(confirm).toBeEnabled();
    fireEvent.click(confirm);
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onConfirm).toHaveBeenCalledWith(PHRASE);
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Open confirm" }));
    await screen.findByRole("dialog", { name: "Delete model" });
    expect(screen.getByRole("button", { name: "Confirm" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).toHaveBeenCalledTimes(1);
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("dismisses on Escape and the backdrop when dismiss is allowed", async () => {
    const onCancel = vi.fn();
    render(<ConfirmHarness onConfirm={vi.fn()} onCancel={onCancel} />);

    fireEvent.click(screen.getByRole("button", { name: "Open confirm" }));
    const dialog = await screen.findByRole("dialog", { name: "Delete model" });
    fireEvent.keyDown(dialog, { key: "Escape", code: "Escape", bubbles: true });
    expect(onCancel).toHaveBeenCalledTimes(1);
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Open confirm" }));
    await screen.findByRole("dialog", { name: "Delete model" });
    const backdrop = document.querySelector('[class*="bg-black/30"]');
    expect(backdrop).not.toBeNull();
    fireEvent.click(backdrop!);
    expect(onCancel).toHaveBeenCalledTimes(2);
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("keeps confirm and cancel disabled and ignores dismiss while busy", async () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(
      <ConfirmDialogV2
        open
        busy
        title="Delete model"
        warning="This cannot be undone."
        risks={[]}
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    );

    expect(screen.getByTestId("confirm-dialog-v2-cancel")).toBeDisabled();
    expect(screen.getByTestId("confirm-dialog-v2-confirm")).toBeDisabled();
    expect(screen.getByTestId("confirm-dialog-v2-input")).toBeDisabled();

    const dialog = screen.getByRole("dialog", { name: "Delete model" });
    fireEvent.keyDown(dialog, { key: "Escape", code: "Escape", bubbles: true });
    const backdrop = document.querySelector('[class*="bg-black/30"]');
    expect(backdrop).not.toBeNull();
    fireEvent.click(backdrop!);

    expect(onCancel).not.toHaveBeenCalled();
    expect(onConfirm).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog", { name: "Delete model" })).toBeInTheDocument();
  });
});
