/** @vitest-environment jsdom */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ImportErrorNotice } from "@/components/import/ImportErrorNotice";

vi.mock("@/lib/expert-diagnostics", () => ({
  diagnoseWithExpert: vi.fn(),
}));

describe("ImportErrorNotice", () => {
  it("shows what / why / next for a parse failure", () => {
    render(<ImportErrorNotice message="Sheet is empty" context="preview" />);
    expect(screen.getByTestId("import-error-notice")).toBeInTheDocument();
    expect(screen.getByTestId("import-error-message")).toHaveTextContent(/sheet is empty/i);
    expect(screen.getByTestId("import-error-why").textContent?.length).toBeGreaterThan(5);
    expect(screen.getByTestId("import-error-next").textContent?.toLowerCase()).toContain("parse");
    expect(screen.getByTestId("import-error-notice").textContent).not.toMatch(/\u2014|\u2013/);
  });
});
