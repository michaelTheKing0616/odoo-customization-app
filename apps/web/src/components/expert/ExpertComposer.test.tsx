/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ExpertComposer } from "./ExpertComposer";

afterEach(() => cleanup());

describe("ExpertComposer", () => {
  it("submits Ask Expert and keeps the diagnose paste control", () => {
    const onSubmit = vi.fn();
    render(
      <ExpertComposer
        value="What is xpath inherit?"
        onChange={() => undefined}
        errorPaste=""
        onErrorPasteChange={() => undefined}
        errorInMainInput={false}
        onSubmit={onSubmit}
      />,
    );
    expect(screen.getByTestId("expert-input")).toHaveValue("What is xpath inherit?");
    expect(screen.getByTestId("expert-error-paste")).toBeTruthy();
    expect(screen.getByText(/never auto-promotes/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Ask Expert" }));
    expect(onSubmit).toHaveBeenCalledOnce();
  });
});
