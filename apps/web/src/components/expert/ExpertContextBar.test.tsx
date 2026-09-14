/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ExpertContextBar } from "./ExpertContextBar";

afterEach(() => cleanup());

describe("ExpertContextBar", () => {
  it("toggles page context and offers a new thread", () => {
    const onToggle = vi.fn();
    const onClear = vi.fn();
    render(
      <ExpertContextBar
        contextLabel="res.partner · builder"
        contextEnabled
        onToggleContext={onToggle}
        canClear
        onClear={onClear}
      />,
    );
    expect(screen.getByText(/res.partner/)).toBeTruthy();
    fireEvent.click(screen.getByTestId("expert-context-toggle"));
    expect(onToggle).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByTestId("expert-clear-history"));
    expect(onClear).toHaveBeenCalledOnce();
    expect(screen.getByRole("button", { name: "New thread" })).toBeTruthy();
  });
});
