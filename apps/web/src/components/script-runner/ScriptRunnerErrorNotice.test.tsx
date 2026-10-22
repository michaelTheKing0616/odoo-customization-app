/** @vitest-environment happy-dom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ScriptRunnerErrorNotice } from "./ScriptRunnerErrorNotice";

vi.mock("@/lib/expert-diagnostics", () => ({
  diagnoseWithExpert: vi.fn(),
}));

afterEach(() => cleanup());

describe("ScriptRunnerErrorNotice", () => {
  it("shows what / why / next for a load failure", () => {
    render(
      <ScriptRunnerErrorNotice message="Failed to fetch templates" context="load" onRetry={() => {}} />,
    );
    expect(screen.getByTestId("script-runner-error-notice")).toBeInTheDocument();
    expect(screen.getByTestId("script-runner-error-message")).toHaveTextContent(
      "Failed to fetch templates",
    );
    expect(screen.getByTestId("script-runner-error-why").textContent?.length).toBeGreaterThan(8);
    expect(screen.getByTestId("script-runner-error-next").textContent?.toLowerCase()).toContain(
      "retry",
    );
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Diagnose with Expert" })).toBeInTheDocument();
  });
});
