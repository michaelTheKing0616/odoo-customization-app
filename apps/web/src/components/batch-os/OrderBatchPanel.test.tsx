import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { OrderBatchPanel } from "@/components/batch-os/OrderBatchPanel";

vi.mock("@/lib/api", () => ({
  api: {},
  ConfirmationRequiredError: class extends Error {},
}));

describe("OrderBatchPanel smoke", () => {
  it("shows preview ≠ confirmed honesty", () => {
    render(<OrderBatchPanel connectionId="conn-1" />);
    expect(screen.getByTestId("order-batch-panel")).toBeInTheDocument();
    expect(screen.getByText(/Preview ≠ confirmed/i)).toBeInTheDocument();
  });
});
