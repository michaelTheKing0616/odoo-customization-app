import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { InstanceFingerprintCard } from "@/components/overview/InstanceFingerprintCard";

vi.mock("@/lib/api", () => ({
  api: {
    jobAutopilotFingerprint: vi.fn(),
  },
}));

afterEach(() => {
  cleanup();
});

describe("InstanceFingerprintCard", () => {
  it("renders overview copy by default", () => {
    render(<InstanceFingerprintCard connectionId="conn-1" />);
    const card = screen.getByTestId("instance-fingerprint");
    expect(card).toHaveAttribute("data-context", "overview");
    expect(screen.getByText("Instance fingerprint")).toBeInTheDocument();
    expect(card).toHaveTextContent(/read-only snapshot/i);
    expect(card).toHaveTextContent(/never writes to Odoo/i);
    expect(screen.getByRole("link", { name: /Job Autopilot/i })).toHaveAttribute(
      "href",
      "/connections/conn-1/job",
    );
  });

  it("renders config context copy", () => {
    render(<InstanceFingerprintCard connectionId="conn-1" context="config" />);
    const card = screen.getByTestId("instance-fingerprint");
    expect(card).toHaveAttribute("data-context", "config");
    expect(card).toHaveTextContent(/change or replay settings/i);
    expect(card).toHaveTextContent(/does not write to Odoo/i);
  });

  it("renders develop context copy", () => {
    render(<InstanceFingerprintCard connectionId="conn-1" context="develop" />);
    const card = screen.getByTestId("instance-fingerprint");
    expect(card).toHaveAttribute("data-context", "develop");
    expect(card).toHaveTextContent(/before you promote/i);
    expect(card).toHaveTextContent(/does not write to Odoo/i);
  });
});
