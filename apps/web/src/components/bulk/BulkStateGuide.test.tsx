/** @vitest-environment jsdom */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BulkStateGuide } from "./BulkStateGuide";
import { emptyBulkGuide } from "@/lib/bulkSuiteScreen";

describe("BulkStateGuide", () => {
  it("renders what / why / next without em dashes", () => {
    render(<BulkStateGuide testId="bulk-empty-guide" tone="accent" guide={emptyBulkGuide()} />);
    expect(screen.getByTestId("bulk-empty-guide-title")).toBeInTheDocument();
    expect(screen.getByTestId("bulk-empty-guide-why").textContent?.length).toBeGreaterThan(5);
    expect(screen.getByTestId("bulk-empty-guide-next").textContent?.toLowerCase()).toContain("test run");
    expect(screen.getByTestId("bulk-empty-guide").textContent).not.toMatch(/\u2014|\u2013/);
  });
});
