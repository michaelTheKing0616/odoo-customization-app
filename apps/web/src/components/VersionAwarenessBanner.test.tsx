import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { VersionAwarenessBanner } from "./VersionAwarenessBanner";
import type { CapabilityMatrix } from "@/lib/api";

function matrix(
  partial: Partial<CapabilityMatrix> & Pick<CapabilityMatrix, "major" | "ga">,
): CapabilityMatrix {
  return {
    edition: "community",
    server_version: `${partial.major}.0`,
    message: `mock major ${partial.major}`,
    supported: [],
    unsupported: [],
    ...partial,
  };
}

afterEach(() => {
  cleanup();
});

describe("VersionAwarenessBanner", () => {
  it("shows Odoo 20 supported for GA major 20", () => {
    render(<VersionAwarenessBanner capabilities={matrix({ major: 20, ga: true })} />);
    expect(screen.getByText(/Odoo 20 is supported/i)).toBeInTheDocument();
  });

  it("does not show Odoo 20 supported for experimental major 16", () => {
    render(<VersionAwarenessBanner capabilities={matrix({ major: 16, ga: false })} />);
    expect(screen.queryByText(/Odoo 20 is supported/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Odoo 16 is experimental/i)).toBeInTheDocument();
  });
});
