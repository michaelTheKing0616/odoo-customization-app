import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DocumentBatchPanel } from "@/components/batch-os/DocumentBatchPanel";

vi.mock("@/lib/api", () => ({
  api: {
    batchOsDocumentIntake: vi.fn(),
    batchOsDocumentMap: vi.fn(),
    batchOsDocumentDryRun: vi.fn(),
    batchOsDocumentApply: vi.fn(),
  },
  ConfirmationRequiredError: class ConfirmationRequiredError extends Error {},
}));

describe("DocumentBatchPanel smoke", () => {
  it("renders honesty banner and upload control", () => {
    render(<DocumentBatchPanel connectionId="conn-1" />);
    expect(screen.getByTestId("document-batch-panel")).toBeInTheDocument();
    expect(screen.getByText(/Preview ≠ posted/i)).toBeInTheDocument();
    expect(screen.getByTestId("document-batch-file")).toBeInTheDocument();
  });
});
