/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ExpertEmptyState } from "./ExpertEmptyState";

afterEach(() => cleanup());

describe("ExpertEmptyState", () => {
  it("keeps Expert distinct from Completeness, Cert, and Autopilot", () => {
    const onSelect = vi.fn();
    render(
      <ExpertEmptyState
        onSelectPrompt={onSelect}
        prompts={[{ id: "xpath", label: "XPath inherit", question: "How does xpath inherit work?" }]}
      />,
    );
    expect(screen.getByTestId("expert-empty").textContent).toMatch(/not Job Autopilot/);
    expect(screen.getByTestId("expert-honesty-legend").textContent).toMatch(
      /Expert is a copilot/,
    );
    fireEvent.click(screen.getByRole("button", { name: "XPath inherit" }));
    expect(onSelect).toHaveBeenCalledWith("How does xpath inherit work?");
  });
});
