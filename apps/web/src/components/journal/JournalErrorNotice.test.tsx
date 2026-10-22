import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { JournalErrorNotice } from "@/components/journal/JournalErrorNotice";

vi.mock("@/lib/expert-diagnostics", () => ({
  diagnoseWithExpert: vi.fn(),
}));

describe("JournalErrorNotice", () => {
  it("shows classified why and next for rollback timeout", () => {
    render(
      <JournalErrorNotice message="Connection timed out during rollback" context="rollback" />,
    );
    expect(screen.getByTestId("journal-error-notice")).toBeInTheDocument();
    expect(screen.getByTestId("journal-error-why").textContent?.toLowerCase()).toMatch(
      /took too long|timed/,
    );
    expect(screen.getByTestId("journal-error-next")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Diagnose with Expert/i })).toBeInTheDocument();
  });
});
