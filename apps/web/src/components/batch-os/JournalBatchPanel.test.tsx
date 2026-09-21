import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { JournalBatchPanel } from "@/components/batch-os/JournalBatchPanel";

vi.mock("@/lib/api", () => ({
  api: {
    batchOsJournalIntake: vi.fn(),
    batchOsJournalMap: vi.fn(),
    batchOsJournalDryRun: vi.fn(),
    batchOsJournalApply: vi.fn(),
  },
  ConfirmationRequiredError: class ConfirmationRequiredError extends Error {},
}));

describe("JournalBatchPanel smoke", () => {
  it("renders honesty banner", () => {
    render(<JournalBatchPanel connectionId="conn-1" />);
    expect(screen.getByTestId("journal-batch-panel")).toBeInTheDocument();
    expect(screen.getByText(/Preview ≠ posted/i)).toBeInTheDocument();
  });
});
