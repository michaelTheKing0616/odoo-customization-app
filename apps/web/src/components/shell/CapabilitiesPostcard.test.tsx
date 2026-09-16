import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { CapabilitiesPostcard } from "./CapabilitiesPostcard";
import type { Connection, CapabilityMatrix } from "@/lib/api";

const connection = {
  id: "c1",
  name: "Lab",
  url: "http://localhost:8069",
  server_version: "17.0",
  write_mode: "standard",
} as Connection;

const caps = {
  major: 17,
  edition: "community",
  server_version: "17.0",
  supported: ["a", "b"],
  unsupported: [{ id: "x", label: "Grid view", reason: "Enterprise module" }],
  ga: true,
  message: "Community 17 — Studio-class via public ORM.",
  hosting_hint: "on-prem",
} as CapabilityMatrix;

describe("CapabilitiesPostcard", () => {
  it("renders human postcard, not raw JSON", () => {
    render(
      <CapabilitiesPostcard connection={connection} capabilities={caps} />,
    );
    expect(screen.getByTestId("capabilities-postcard")).toBeInTheDocument();
    expect(screen.getByText(/Community · Odoo 17/)).toBeInTheDocument();
    const expertLinks = screen.getAllByRole("link", { name: /Ask Expert/i });
    expect(expertLinks[0]).toHaveAttribute("href", "/connections/c1/expert");
    expect(screen.getByTestId("locked-explainer")).toBeInTheDocument();
    expect(screen.getByText(/Grid view is locked/i)).toBeInTheDocument();
  });
});
