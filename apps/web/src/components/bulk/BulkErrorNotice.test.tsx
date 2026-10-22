/** @vitest-environment jsdom */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { BulkErrorNotice } from "./BulkErrorNotice";

vi.mock("@/lib/expert-diagnostics", () => ({
  diagnoseWithExpert: vi.fn(),
}));

describe("BulkErrorNotice", () => {
  it("shows what / why / next for a test run failure", () => {
    render(<BulkErrorNotice message="Connection timed out" context="dry_run" />);
    expect(screen.getByTestId("bulk-error-notice")).toBeInTheDocument();
    expect(screen.getByTestId("bulk-error-message")).toHaveTextContent(/timed out/i);
    expect(screen.getByTestId("bulk-error-why").textContent?.length).toBeGreaterThan(5);
    expect(screen.getByTestId("bulk-error-next").textContent?.toLowerCase()).toContain("test run");
    expect(screen.getByTestId("bulk-error-notice").textContent).not.toMatch(/\u2014|\u2013/);
  });
});
