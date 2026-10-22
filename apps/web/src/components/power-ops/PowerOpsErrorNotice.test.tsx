/** @vitest-environment jsdom */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PowerOpsErrorNotice } from "./PowerOpsErrorNotice";

vi.mock("@/lib/expert-diagnostics", () => ({
  diagnoseWithExpert: vi.fn(),
}));

describe("PowerOpsErrorNotice", () => {
  it("shows what / why / next for a test run failure", () => {
    render(<PowerOpsErrorNotice message="Connection timed out" context="dry_run" />);
    expect(screen.getByTestId("power-ops-error-notice")).toBeInTheDocument();
    expect(screen.getByTestId("power-ops-error-message")).toHaveTextContent(/timed out/i);
    expect(screen.getByTestId("power-ops-error-why").textContent?.length).toBeGreaterThan(5);
    expect(screen.getByTestId("power-ops-error-next").textContent?.toLowerCase()).toContain(
      "test run",
    );
    expect(screen.getByTestId("power-ops-error-notice").textContent).not.toMatch(/—|–/);
  });
});
