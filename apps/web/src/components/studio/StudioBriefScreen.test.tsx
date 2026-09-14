/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { StudioBriefScreen } from "./StudioBriefScreen";

afterEach(() => cleanup());

describe("StudioBriefScreen", () => {
  it("uses verb-first See a preview and starter chips", () => {
    const onStart = vi.fn();
    render(
      <StudioBriefScreen prompt="On vendor bills, add a Vendor TIN field." busy={false} onPromptChange={vi.fn()} onStart={onStart} />,
    );
    expect(screen.getByTestId("studio-brief").textContent).toMatch(/nothing is installed until you say so/i);
    expect(screen.getByRole("button", { name: "See a preview" })).not.toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "See a preview" }));
    expect(onStart).toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Car rental" })).toBeTruthy();
  });
});
