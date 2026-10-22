import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { IdGeneratorResultCounts } from "./IdGeneratorResultCounts";

describe("IdGeneratorResultCounts", () => {
  it("shows total changed skipped", () => {
    render(<IdGeneratorResultCounts total={12} changed={4} skipped={8} dryRun />);
    expect(screen.getByTestId("id-generator-counts")).toHaveAttribute("data-dry-run", "true");
    expect(screen.getByText("12")).toBeTruthy();
    expect(screen.getByText("4")).toBeTruthy();
    expect(screen.getByText("8")).toBeTruthy();
  });
});
