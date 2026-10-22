/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ExpertHeader } from "./ExpertHeader";

afterEach(() => cleanup());

describe("ExpertHeader", () => {
  it("states Expert is a copilot that never auto-promotes", () => {
    render(<ExpertHeader connectionName="Lab 19" />);
    expect(screen.getByTestId("expert-header")).toBeTruthy();
    expect(screen.getByTestId("expert-header-description").textContent).toMatch(/Lab 19/);
    expect(screen.getByTestId("expert-honesty-line").textContent).toMatch(
      /A complete draft is not the same as certified, and neither means Autopilot-ready/,
    );
    expect(screen.getByTestId("expert-honesty-line").textContent).toMatch(/never publishes on its own/);
  });
});
