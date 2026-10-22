/** @vitest-environment jsdom */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { OpsHubToolGroups } from "./OpsHubToolGroups";
import { OPS_HUB_TOOLS } from "@/lib/operationsHubScreen";

describe("OpsHubToolGroups", () => {
  it("renders grouped quiet tool links with one featured Bulk Suite card", () => {
    render(<OpsHubToolGroups base="/connections/demo" />);
    expect(screen.getByTestId("ops-hub-groups")).toBeInTheDocument();
    expect(screen.getByTestId("ops-hub-group-write")).toBeInTheDocument();
    expect(screen.getByTestId("ops-hub-tool-bulk-suite")).toHaveAttribute("data-featured", "true");
    expect(screen.getByTestId("ops-hub-tool-power-ops")).toHaveAttribute("data-featured", "false");
    for (const tool of OPS_HUB_TOOLS) {
      const link = screen.getByTestId(`ops-hub-tool-${tool.id}`);
      expect(link).toHaveAttribute("href", `/connections/demo/${tool.href}`);
      // Quiet nav: no filled primary button chrome inside cards
      expect(link.querySelector("button")).toBeNull();
    }
    expect(screen.getByTestId("ops-hub-groups").textContent).not.toMatch(/[—–]/);
  });
});
