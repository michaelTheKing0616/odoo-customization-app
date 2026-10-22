/** @vitest-environment happy-dom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ getSafetyContract: vi.fn() }));

vi.mock("@/lib/api", () => ({ api: mocks }));

import TrustSafetyPage from "./page";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("trust and safety page states", () => {
  it("shows a contract-shaped skeleton while the contract loads", () => {
    mocks.getSafetyContract.mockReturnValue(new Promise(() => undefined));
    render(<TrustSafetyPage />);

    const loading = screen.getByTestId("trust-safety-loading");
    expect(loading).toHaveAttribute("role", "status");
    expect(screen.getByText("Loading the safety contract.")).toBeInTheDocument();
    expect(loading.querySelectorAll(".shimmer-15").length).toBeGreaterThan(3);
    expect(screen.queryByText(/Loading…|Loading\.\.\./)).toBeNull();
  });

  it("replaces the skeleton with the contract once it arrives", async () => {
    mocks.getSafetyContract.mockResolvedValue({ markdown: "# Permission model" });
    render(<TrustSafetyPage />);

    expect(await screen.findByRole("heading", { name: "Permission model" })).toBeInTheDocument();
    expect(screen.queryByTestId("trust-safety-loading")).toBeNull();
  });

  it("drops the skeleton when the contract fails to load", async () => {
    mocks.getSafetyContract.mockRejectedValue(new Error("Contract unavailable"));
    render(<TrustSafetyPage />);

    expect(await screen.findByText(/Contract unavailable/)).toBeInTheDocument();
    expect(screen.queryByTestId("trust-safety-loading")).toBeNull();
  });
});
