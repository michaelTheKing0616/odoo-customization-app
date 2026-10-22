/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DraftStudioMobileTabs } from "./DraftStudioMobileTabs";

afterEach(() => cleanup());

describe("DraftStudioMobileTabs", () => {
  it("switches between preview and scorecard with pressed state", () => {
    const onChange = vi.fn();
    render(<DraftStudioMobileTabs value="preview" onChange={onChange} />);
    expect(screen.getByTestId("draft-studio-mobile-tab-preview").getAttribute("aria-pressed")).toBe(
      "true",
    );
    fireEvent.click(screen.getByTestId("draft-studio-mobile-tab-scorecard"));
    expect(onChange).toHaveBeenCalledWith("chrome");
  });
});
