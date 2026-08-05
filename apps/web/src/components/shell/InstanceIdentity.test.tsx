import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { InstanceIdentity } from "@/components/shell/InstanceIdentity";
import type { Connection } from "@/lib/api";

const connection = {
  id: "c1",
  name: "Demo",
  url: "http://127.0.0.1:8069",
  server_version: "19.0",
  write_mode: "standard",
  capabilities: {
    ga: true,
    edition: "community",
    hosting_hint: "self_hosted",
    major: 19,
    supported: [],
    unsupported: [],
    message: "",
  },
} as Connection;

describe("InstanceIdentity (UIF-1)", () => {
  it("renders a single identity cluster", () => {
    render(<InstanceIdentity connection={connection} />);
    expect(screen.getAllByTestId("instance-identity")).toHaveLength(1);
    expect(screen.getByText(/Odoo 19\.0/)).toBeInTheDocument();
    expect(screen.getByText(/community/i)).toBeInTheDocument();
    expect(screen.getByText(/self hosted/i)).toBeInTheDocument();
    expect(screen.getByText("GA")).toBeInTheDocument();
  });
});
