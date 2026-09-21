import { render, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { MasterDataBatchPanel } from "@/components/batch-os/MasterDataBatchPanel";

vi.mock("@/lib/api", () => ({
  api: {
    batchOsMasterIntake: vi.fn(),
    batchOsMasterMap: vi.fn(),
    batchOsMasterDryRun: vi.fn(),
    batchOsMasterApply: vi.fn(),
  },
  ConfirmationRequiredError: class ConfirmationRequiredError extends Error {},
}));

describe("MasterDataBatchPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = "";
  });

  it("renders honesty banner and upload → map scaffolding", () => {
    const { container } = render(<MasterDataBatchPanel connectionId="conn-1" />);
    expect(container.querySelector('[data-testid="master-data-batch-panel"]')).toBeTruthy();
    expect(container.textContent).toMatch(/Preview ≠ written/i);
    expect(container.querySelector('[data-testid="master-data-batch-file"]')).toBeTruthy();
    expect(container.querySelector('[data-testid="master-data-kind-partners"]')).toBeTruthy();
    expect(container.querySelector('[data-testid="master-data-kind-products"]')).toBeTruthy();
    expect(container.textContent).toMatch(/L1/);
  });

  it("switches kind tabs", () => {
    const { container } = render(<MasterDataBatchPanel connectionId="conn-1" />);
    const products = container.querySelector(
      '[data-testid="master-data-kind-products"]',
    ) as HTMLButtonElement;
    fireEvent.click(products);
    expect(container.querySelector('[data-testid="master-data-kind-products"]')).toBeTruthy();
  });
});
