/** @vitest-environment jsdom */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PowerOpsStateGuide } from "./PowerOpsStateGuide";
import { emptyPowerOpsGuide } from "@/lib/powerOpsScreen";

describe("PowerOpsStateGuide", () => {
  it("renders what / why / next without em dashes", () => {
    render(
      <PowerOpsStateGuide testId="power-ops-empty-guide" tone="accent" guide={emptyPowerOpsGuide()} />,
    );
    expect(screen.getByTestId("power-ops-empty-guide-title")).toBeInTheDocument();
    expect(screen.getByTestId("power-ops-empty-guide-why").textContent?.length).toBeGreaterThan(5);
    expect(screen.getByTestId("power-ops-empty-guide-next").textContent?.toLowerCase()).toMatch(
      /re-probe|module/,
    );
    expect(screen.getByTestId("power-ops-empty-guide").textContent).not.toMatch(/—|–/);
  });
});
