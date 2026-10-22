/** @vitest-environment jsdom */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BulkResultCounts } from "./BulkResultCounts";

describe("BulkResultCounts", () => {
  it("renders total / succeeded / failed tiles", () => {
    render(<BulkResultCounts total={412} succeeded={400} failed={12} dryRun />);
    expect(screen.getByTestId("bulk-result-counts-total")).toHaveTextContent("412");
    expect(screen.getByTestId("bulk-result-counts-succeeded")).toHaveTextContent("400");
    expect(screen.getByTestId("bulk-result-counts-failed")).toHaveTextContent("12");
    expect(screen.getByTestId("bulk-result-counts")).toHaveAttribute("data-dry-run", "true");
  });
});
