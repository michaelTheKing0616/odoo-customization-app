/** @vitest-environment jsdom */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PowerOpsResultCounts } from "./PowerOpsResultCounts";

describe("PowerOpsResultCounts", () => {
  it("renders processed / succeeded / failed tiles with test run honesty", () => {
    render(<PowerOpsResultCounts processed={12} succeeded={10} failed={2} dryRun />);
    expect(screen.getByTestId("power-ops-result-counts-processed")).toHaveTextContent("12");
    expect(screen.getByTestId("power-ops-result-counts-succeeded")).toHaveTextContent("10");
    expect(screen.getByTestId("power-ops-result-counts-failed")).toHaveTextContent("2");
    expect(screen.getByTestId("power-ops-result-counts")).toHaveAttribute("data-dry-run", "true");
    expect(screen.getByLabelText(/[Tt]est run counts/i)).toBeInTheDocument();
  });
});
