import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EePlaybooksPanel } from "@/components/EePlaybooksPanel";

vi.mock("@/lib/api", () => ({
  api: {
    listEePlaybooks: () => Promise.reject(new Error("Failed to fetch")),
  },
}));

describe("playbook error callout (UIF-1)", () => {
  it("shows error callout with retry on failed loader", async () => {
    render(<EePlaybooksPanel connectionId="c1" />);
    expect(await screen.findByTestId("error-notice")).toBeInTheDocument();
    expect(screen.getByText(/Couldn't reach your Odoo instance/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
